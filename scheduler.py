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


from collections.abc import Callable, Coroutine


async def run_scouting_pipeline(
    verticals: list[ICPVertical | str] | None = None,
    locations: list[str] | None = None,
    max_prospects_per_vertical: int = 3,
    min_fit_score: int | None = None,
    push_to_telegram: bool = True,
    bot: Bot | None = None,
    chat_id: str | int | None = None,
    progress_callback: Callable[[str], None | Coroutine[None, None, None]] | None = None,
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

    async def _emit_log(msg: str) -> None:
        logger.info(msg)
        if progress_callback:
            try:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(msg)
                else:
                    progress_callback(msg)
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Progress callback notification failed: {exc}")

    await _emit_log(
        f"🚀 [INIT] Starting scouting cycle: {len(target_verticals)} verticals, "
        f"{len(target_locations)} locations (Threshold: {score_threshold}/10)"
    )

    for vertical in target_verticals:
        for location in target_locations:
            vert_str = str(getattr(vertical, "value", vertical)).lower()
            vert_enum = ICPVertical._value2member_map_.get(vert_str, ICPVertical.LOGISTICS)

            try:
                # 1. Discovery Search
                await _emit_log(f"🔍 [Step 1/6] Searching {vert_enum.value} prospects in '{location}' via DuckDuckGo & Overpass...")
                prospects = await discover_prospects(
                    vertical=vert_enum,
                    location=location,
                    max_results=max_prospects_per_vertical,
                )
                stats["discovered"] += len(prospects)
                await _emit_log(f"  • Discovered {len(prospects)} candidate(s) for {vert_enum.value} in {location}")

                for idx, prospect in enumerate(prospects, start=1):
                    target_url = prospect.website_url
                    if not target_url:
                        continue

                    # 2. Deduplication Check
                    await _emit_log(f"🧹 [Step 2/6] [{idx}/{len(prospects)}] Checking deduplication: {prospect.company_name} ({target_url})...")
                    existing = await get_lead_by_url(target_url)
                    if existing:
                        await _emit_log(f"  ⏭️ Skipping duplicate prospect already in database: {target_url}")
                        stats["skipped_duplicate"] += 1
                        continue

                    stats["processed"] += 1

                    # 3. Web Extraction
                    await _emit_log(f"🌐 [Step 3/6] Crawling & hydrating SPA markdown with Crawl4AI: {target_url}...")
                    crawl_result = await extract_lead_content(target_url)
                    if not crawl_result or not crawl_result.markdown:
                        await _emit_log(f"  ⚠️ Could not extract markdown content for {target_url}")
                        continue
                    await _emit_log(f"  • Scraped {len(crawl_result.markdown)} chars, found {len(crawl_result.emails_found)} raw email(s)")

                    # 4. Email Resolution & Verification
                    await _emit_log(f"✉️ [Step 4/6] Verifying deliverable decision-maker email via DNS MX & SMTP sockets for {prospect.company_name}...")
                    resolved_email, _ver_res = await resolve_lead_email(
                        domain_or_url=target_url,
                        discovered_emails=crawl_result.emails_found,
                    )
                    if resolved_email:
                        await _emit_log(f"  ✅ Deliverable contact resolved: {resolved_email}")
                    else:
                        await _emit_log("  ℹ️ No direct SMTP-verified email found, using domain fallback")

                    # 5. LLM Evaluation & ICP Scoring
                    await _emit_log("🤖 [Step 5/6] Evaluating operational bottlenecks & scoring fit with Gemini 3.5 Flash...")
                    evaluation = await evaluate_lead(
                        markdown_content=crawl_result.markdown,
                        company_name=crawl_result.company_name or prospect.company_name or crawl_result.page_title,
                        website_url=target_url,
                        decision_maker_email=resolved_email or "",
                        discovered_contacts={
                            "resolved_email": resolved_email or "",
                            "emails_found": crawl_result.emails_found,
                            "phones_found": crawl_result.phones_found,
                            "social_links": crawl_result.social_links,
                        },
                    )

                    await _emit_log(
                        f"  🎯 Evaluation Score: {evaluation.fit_score}/10 for '{evaluation.company_name}' "
                        f"| Pitch: '{evaluation.suggested_angle}'"
                    )

                    # 6. Qualification Filter & Gate 1 Push
                    if evaluation.fit_score < score_threshold:
                        await _emit_log(
                            f"  ❌ Disqualified: Score {evaluation.fit_score} is below threshold {score_threshold}."
                        )
                        continue

                    stats["qualified"] += 1

                    # Persist Lead to Database
                    await _emit_log("💾 Saving qualified lead to Supabase (Status: PENDING_LEAD_REVIEW)...")
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
                        await _emit_log(f"📱 [Step 6/6] Pushing Gate 1 interactive card to Telegram for {evaluation.company_name}...")
                        msg_id = await send_lead_review_card(
                            bot=telegram_bot,
                            chat_id=target_chat_id,
                            lead_data=lead_record,
                            lead_id=str(saved_id),
                        )
                        if msg_id:
                            stats["pushed"] += 1
                            await _emit_log(f"  ✅ Gate 1 review card pushed to Telegram (Msg ID: {msg_id})")

            except Exception as exc:  # noqa: BLE001
                await _emit_log(f"⚠️ Error during scouting for {vertical} in {location}: {exc}")

    await _emit_log(
        f"🏁 [COMPLETE] Scouting finished: Discovered {stats['discovered']}, "
        f"Processed {stats['processed']}, Qualified {stats['qualified']}, Pushed {stats['pushed']}."
    )

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
