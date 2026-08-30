"""CLI entrypoint and unified service lifecycle manager."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

from bot.telegram_bot import create_telegram_app
from config.settings import settings
from database.client import get_supabase_client
from database.queries import TABLE_LEADS, get_leads_by_status
from dispatch.gmail_sender import dispatch_approved_lead
from evaluators.schemas import LeadStatus
from scheduler import create_scheduler, run_scouting_pipeline

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("client-search")


async def cmd_scout(args: argparse.Namespace) -> None:
    """Execute a one-shot prospect scouting pipeline cycle."""
    verticals = [args.vertical] if args.vertical else None
    locations = [args.location] if args.location else None

    logger.info("Triggering one-shot discovery & evaluation pipeline...")
    stats = await run_scouting_pipeline(
        verticals=verticals,
        locations=locations,
        max_prospects_per_vertical=args.limit,
        min_fit_score=args.min_score,
        push_to_telegram=not args.no_telegram,
    )
    print("\n" + "=" * 50)
    print("🎯 Scouting Cycle Complete:")
    print(f"  • Discovered candidates: {stats.get('discovered', 0)}")
    print(f"  • Processed websites:   {stats.get('processed', 0)}")
    print(f"  • Qualified (Score >= {args.min_score or settings.MIN_LEAD_FIT_SCORE}): {stats.get('qualified', 0)}")
    print(f"  • Pushed to Telegram:   {stats.get('pushed', 0)}")
    print(f"  • Skipped duplicates:   {stats.get('skipped_duplicate', 0)}")
    print("=" * 50)


async def cmd_status(args: argparse.Namespace) -> None:
    """Query and print live pipeline metrics from Supabase."""
    sb = await get_supabase_client()
    response = await sb.table(TABLE_LEADS).select("status").execute()
    rows = response.data or []

    counts: dict[str, int] = {}
    for r in rows:
        st = r.get("status", "UNKNOWN")
        counts[st] = counts.get(st, 0) + 1

    print("\n" + "=" * 50)
    print("📊 Lead Scouting Pipeline Status Overview")
    print("=" * 50)
    print(f"Total Discovered Records: {len(rows)}")
    print("-" * 50)
    print(f"  ⏳ Pending Gate 1 Review: {counts.get(LeadStatus.PENDING_LEAD_REVIEW.value, 0)}")
    print(f"  📝 Pending Gate 2 Review: {counts.get(LeadStatus.DRAFT_GENERATED.value, 0)}")
    print(f"  🚀 Emails Dispatched:     {counts.get(LeadStatus.EMAIL_SENT.value, 0)}")
    print(f"  💬 Interested Replies:    {counts.get(LeadStatus.REPLIED_INTERESTED.value, 0)}")
    print(f"  ❌ Discarded Leads:       {counts.get(LeadStatus.LEAD_REJECTED.value, 0)}")
    print(f"  🗑️ Cancelled Drafts:      {counts.get(LeadStatus.DRAFT_REJECTED.value, 0)}")
    print("=" * 50)


async def cmd_dispatch(args: argparse.Namespace) -> None:
    """Dispatch cold outreach emails for approved leads."""
    if args.lead_id:
        lead_ids = [args.lead_id]
    else:
        leads = await get_leads_by_status(LeadStatus.DRAFT_GENERATED, limit=args.limit)
        lead_ids = [str(l["id"]) for l in leads]

    if not lead_ids:
        print("No approved drafts pending dispatch.")
        return

    print(f"Dispatching outreach for {len(lead_ids)} approved lead(s)...")
    for lid in lead_ids:
        try:
            res = await dispatch_approved_lead(lead_id=lid, apply_jitter=args.jitter)
            print(f"✅ Dispatched to {res.get('to_email')} (Company: {res.get('company_name')})")
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Failed to dispatch lead {lid}: {exc}")


async def cmd_bot(args: argparse.Namespace) -> None:
    """Run only the Telegram HITL Bot polling engine."""
    logger.info("Initializing Telegram HITL Bot...")
    app = create_telegram_app()

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("Telegram Bot polling started. Press Ctrl+C to terminate.")

    stop_event = asyncio.Event()

    def _on_signal() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_signal)
        except NotImplementedError:
            pass

    await stop_event.wait()
    logger.info("Shutting down Telegram Bot...")
    await app.updater.stop()
    await app.stop()
    await app.shutdown()
    logger.info("Bot cleanly stopped.")


async def cmd_run(args: argparse.Namespace) -> None:
    """Run the complete service: APScheduler background scouting + Telegram Bot HITL interface."""
    logger.info("Starting Autonomous Client Search & Outreach System...")

    # 1. Start Telegram Bot
    app = create_telegram_app()
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("Telegram HITL Bot polling active.")

    # 2. Start Background Scheduler
    scheduler = create_scheduler(interval_hours=args.interval, run_on_start=args.scout_now)
    scheduler.start()
    logger.info(f"Background APScheduler started (interval: {args.interval}h).")

    # 3. Graceful Shutdown Signals
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Termination signal received. Initiating graceful shutdown...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass

    # Wait until interrupted
    await stop_event.wait()

    # 4. Clean Shutdown
    logger.info("Stopping scheduler...")
    scheduler.shutdown(wait=False)

    logger.info("Stopping Telegram Bot...")
    await app.updater.stop()
    await app.stop()
    await app.shutdown()
    logger.info("System gracefully stopped.")


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="client-search",
        description="Autonomous Zero-Cost B2B Client Scouting & Outreach Engine",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available system commands")

    # run command (scheduler + bot)
    parser_run = subparsers.add_parser("run", help="Start background scheduler & Telegram bot")
    parser_run.add_argument("--interval", type=int, default=4, help="Scouting interval in hours (default: 4)")
    parser_run.add_argument("--scout-now", action="store_true", help="Trigger initial scouting run immediately on start")

    # scout command (one-shot)
    parser_scout = subparsers.add_parser("scout", help="Run a one-shot prospect scouting pipeline cycle")
    parser_scout.add_argument("--vertical", type=str, help="Target ICP vertical (logistics, real_estate, ecommerce_agencies)")
    parser_scout.add_argument("--location", type=str, help="Geographic location (e.g. 'Chicago, IL')")
    parser_scout.add_argument("--limit", type=int, default=3, help="Max candidates per vertical search")
    parser_scout.add_argument("--min-score", type=int, help="Minimum fit score (1-10) to qualify")
    parser_scout.add_argument("--no-telegram", action="store_true", help="Do not push notifications to Telegram")

    # bot command
    subparsers.add_parser("bot", help="Run only the Telegram HITL bot interface")

    # status command
    subparsers.add_parser("status", help="Display live Supabase lead pipeline metrics")

    # dispatch command
    parser_dispatch = subparsers.add_parser("dispatch", help="Send outreach emails for approved leads")
    parser_dispatch.add_argument("--lead-id", type=str, help="Specific lead UUID to dispatch")
    parser_dispatch.add_argument("--limit", type=int, default=5, help="Max approved drafts to dispatch")
    parser_dispatch.add_argument("--jitter", action="store_true", help="Apply 10-25 min safety jitter delay")

    return parser


def main() -> None:
    """CLI execution entrypoint."""
    parser = build_parser()
    args = parser.parse_args()

    command = args.command or "run"

    handlers = {
        "run": cmd_run,
        "scout": cmd_scout,
        "bot": cmd_bot,
        "status": cmd_status,
        "dispatch": cmd_dispatch,
    }

    handler = handlers.get(command)
    if not handler:
        parser.print_help()
        sys.exit(1)

    try:
        asyncio.run(handler(args))
    except (KeyboardInterrupt, SystemExit):
        logger.info("Exited.")


if __name__ == "__main__":
    main()
