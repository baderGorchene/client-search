"""Periodic background scouting pipeline runner and scheduler integration."""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot

from bot.telegram_bot import send_lead_review_card
from config.settings import settings
from database.queries import (
    get_lead_by_url,
    upsert_lead,
)
from discovery.crawler import extract_lead_content
from discovery.searcher import (
    ICPVertical,
    discover_prospects,
)
from evaluators.llm_service import evaluate_lead
from evaluators.schemas import LeadRecord, LeadStatus
from verification.email_verifier import resolve_lead_email

logger = logging.getLogger(__name__)

# Default target ICP verticals and geographic hubs
DEFAULT_VERTICALS: list[ICPVertical] = [
    ICPVertical.LOGISTICS,
    ICPVertical.REAL_ESTATE,
    ICPVertical.BOUTIQUE_AGENCIES,
    ICPVertical.ECOMMERCE,
]

DEFAULT_LOCATIONS: list[str] = [
    "Chicago, IL",
    "Dallas, TX",
    "Atlanta, GA",
    "Austin, TX",
    "London, UK",
]


async def run_scouting_pipeline(
    verticals: list[ICPVertical | str] | None = None,
    locations: list[str] | None = None,
    max_prospects_per_vertical: int = 3,
    min_fit_score: int | None = None,
    push_to_telegram: bool = True,
    bot: Bot | None = None,
    chat_id: str | int | None = None,
) -> dict[str, int]:
    """Execute an end-to-end automated prospect discovery, extraction, scoring, and HITL push cycle.

    Workflow:
      1. Discovery: Search ICP verticals across locations using DuckDuckGo / Overpass.
      2. Deduplication: Check if prospective domain/URL is already in Supabase.
      3. Extraction: Crawl target website with Crawl4AI to markdown & extract emails.
      4. Verification: Resolve verified corporate decision maker email via DNS MX & SMTP handshake.
      5. Evaluation: Evaluate operations and score automation fit (1-10) using LiteLLM router.
      6. Gate 1 Push: Persist qualified leads (score >= min_fit_score) and push interactive card to Telegram.

    Returns:
        dict[str, int]: Execution metrics (discovered, processed, qualified, pushed).
    """
    target_verticals = verticals or DEFAULT_VERTICALS
    target_locations = locations or DEFAULT_LOCATIONS
    score_threshold = min_fit_score if min_fit_score is not None else settings.MIN_LEAD_FIT_SCORE
    target_chat_id = chat_id or settings.TELEGRAM_CHAT_ID

    stats = {
        "discovered": 0,
        "processed": 0,
        "qualified": 0,
        "pushed": 0,
        "skipped_duplicate": 0,
    }

    telegram_bot = bot
    if push_to_telegram and not telegram_bot and settings.TELEGRAM_BOT_TOKEN:
        telegram_bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

    logger.info(
        f"Starting scouting cycle: {len(target_verticals)} verticals, "
        f"{len(target_locations)} locations (Threshold: {score_threshold}/10)"
    )

    for vertical in target_verticals:
        for location in target_locations:
            vert_str = str(getattr(vertical, "value", vertical)).lower()
            vert_enum = ICPVertical._value2member_map_.get(vert_str, ICPVertical.LOGISTICS)

            try:
                # 1. Discovery Search
                prospects = await discover_prospects(
                    vertical=vert_enum,
                    location=location,
                    max_results=max_prospects_per_vertical,
                )
                stats["discovered"] += len(prospects)
                logger.info(f"Discovered {len(prospects)} candidates for {vert_enum.value} in {location}")

                for prospect in prospects:
                    target_url = prospect.website_url
                    if not target_url:
                        continue

                    # 2. Deduplication Check
                    existing = await get_lead_by_url(target_url)
                    if existing:
                        logger.debug(f"Skipping duplicate prospect: {target_url}")
                        stats["skipped_duplicate"] += 1
                        continue

                    stats["processed"] += 1
                    logger.info(f"Processing prospect: {prospect.company_name} ({target_url})")

                    # 3. Web Extraction
                    crawl_result = await extract_lead_content(target_url)
                    if not crawl_result or not crawl_result.markdown:
                        logger.warning(f"Could not extract markdown content for {target_url}")
                        continue

                    # 4. Email Resolution & Verification
                    resolved_email, _ver_res = await resolve_lead_email(
                        domain_or_url=target_url,
                        discovered_emails=crawl_result.emails_found,
                    )

                    # 5. LLM Evaluation & ICP Scoring
                    evaluation = await evaluate_lead(
                        markdown_content=crawl_result.markdown,
                        company_name=crawl_result.company_name or prospect.company_name or crawl_result.page_title,
                        website_url=target_url,
                        decision_maker_email=resolved_email or "",
                    )

                    # 6. Qualification Filter & Gate 1 Push
                    if evaluation.fit_score < score_threshold:
                        logger.info(
                            f"Lead disqualified: {evaluation.company_name} "
                            f"(Score: {evaluation.fit_score}/{score_threshold})"
                        )
                        continue

                    stats["qualified"] += 1

                    # Persist Lead to Database
                    lead_record = LeadRecord(
                        company_name=evaluation.company_name,
                        website_url=evaluation.website_url,
                        decision_maker_name=evaluation.decision_maker_name,
                        decision_maker_title=evaluation.decision_maker_title,
                        decision_maker_email=evaluation.decision_maker_email,
                        fit_score=evaluation.fit_score,
                        summary=evaluation.summary,
                        pros=evaluation.pros,
                        cons=evaluation.cons,
                        suggested_angle=evaluation.suggested_angle,
                        status=LeadStatus.PENDING_LEAD_REVIEW,
                    )

                    saved_lead = await upsert_lead(lead_record)
                    saved_id = saved_lead.get("id") if saved_lead else None

                    # Push Gate 1 Card to Telegram
                    if push_to_telegram and telegram_bot and target_chat_id and saved_id:
                        msg_id = await send_lead_review_card(
                            bot=telegram_bot,
                            chat_id=target_chat_id,
                            lead_data=lead_record,
                            lead_id=str(saved_id),
                        )
                        if msg_id:
                            stats["pushed"] += 1
                            logger.info(f"Pushed Gate 1 review card to Telegram (Msg ID: {msg_id})")

            except Exception as exc:  # noqa: BLE001
                logger.error(f"Error during scouting for {vertical} in {location}: {exc}")

    logger.info(f"Scouting cycle completed: {stats}")
    return stats


def create_scheduler(
    interval_hours: int = 4,
    run_on_start: bool = False,
) -> AsyncIOScheduler:
    """Instantiate and configure the APScheduler background runner."""
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        run_scouting_pipeline,
        trigger="interval",
        hours=interval_hours,
        id="scouting_pipeline_job",
        name="Periodic ICP Client Discovery & Evaluation Pipeline",
        replace_existing=True,
        next_run_time=None if not run_on_start else asyncio.get_event_loop().time(),
    )

    return scheduler
