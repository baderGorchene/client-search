"""Mobile HITL Telegram Bot interface, command handlers, and notification push service."""

from __future__ import annotations

import html
import logging
from typing import Any

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.callbacks import (
    handle_callback_query,
    handle_text_message,
)
from config.settings import settings
from database.client import get_supabase_client
from database.queries import (
    TABLE_LEADS,
    get_leads_by_status,
    update_lead_telegram_msg,
)
from evaluators.schemas import EmailDraft, LeadEvaluation, LeadRecord, LeadStatus

logger = logging.getLogger(__name__)


def build_lead_review_card(
    lead_data: LeadEvaluation | LeadRecord | dict[str, Any],
    lead_id: str | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """Format Gate 1 Lead Review push notification message and inline buttons."""
    if isinstance(lead_data, (LeadEvaluation, LeadRecord)):
        data = lead_data.model_dump()
    else:
        data = dict(lead_data)

    resolved_id = str(lead_id or data.get("id", ""))
    company_name = html.escape(data.get("company_name", "Target Prospect"))
    website_url = html.escape(data.get("website_url", ""))
    decision_maker_name = html.escape(data.get("decision_maker_name") or "Unknown")
    decision_maker_title = html.escape(data.get("decision_maker_title") or "Executive / Owner")
    decision_maker_email = html.escape(data.get("decision_maker_email") or "Not resolved")
    fit_score = data.get("fit_score", 0)
    summary = html.escape(data.get("summary") or "No operations summary provided.")
    suggested_angle = html.escape(data.get("suggested_angle") or "Custom productized workflow automation.")

    pros = data.get("pros") or []
    cons = data.get("cons") or []

    pros_formatted = "\n".join(f"  • {html.escape(str(p))}" for p in pros) if pros else "  • High automation potential"
    cons_formatted = "\n".join(f"  • {html.escape(str(c))}" for c in cons) if cons else "  • None identified"

    score_emoji = "🔥" if fit_score >= 8 else "⭐"

    text = (
        f"🎯 <b>Gate 1: New Qualified Lead Discovered</b>\n\n"
        f"🏢 <b>Company:</b> <a href=\"{website_url}\">{company_name}</a>\n"
        f"👤 <b>Decision Maker:</b> {decision_maker_name} (<i>{decision_maker_title}</i>)\n"
        f"✉️ <b>Email:</b> <code>{decision_maker_email}</code>\n"
        f"{score_emoji} <b>Fit Score:</b> <b>{fit_score}/10</b>\n\n"
        f"📝 <b>Summary:</b>\n<i>{summary}</i>\n\n"
        f"🟢 <b>Automation Opportunities (Pros):</b>\n{pros_formatted}\n\n"
        f"🔴 <b>Risk Factors (Cons):</b>\n{cons_formatted}\n\n"
        f"💡 <b>Pitch Angle:</b>\n<code>{suggested_angle}</code>"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve & Draft", callback_data=f"approve_lead:{resolved_id}"),
            InlineKeyboardButton("❌ Discard", callback_data=f"discard_lead:{resolved_id}"),
        ]
    ]

    return text, InlineKeyboardMarkup(keyboard)


def build_draft_review_card(
    lead_data: LeadRecord | dict[str, Any] | LeadEvaluation,
    draft: EmailDraft | dict[str, str],
    lead_id: str | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """Format Gate 2 Cold Outreach Draft Review notification message and inline buttons."""
    if isinstance(lead_data, (LeadEvaluation, LeadRecord)):
        data = lead_data.model_dump()
    else:
        data = dict(lead_data)

    if isinstance(draft, EmailDraft):
        subject = draft.subject
        body = draft.body
    else:
        subject = draft.get("subject", "")
        body = draft.get("body", "")

    resolved_id = str(lead_id or data.get("id", ""))
    company_name = html.escape(data.get("company_name", "Target Company"))
    recipient_name = html.escape(data.get("decision_maker_name") or "Operations Lead")
    recipient_email = html.escape(data.get("decision_maker_email") or "Unresolved Email")
    escaped_subject = html.escape(subject)
    escaped_body = html.escape(body)

    text = (
        f"✉️ <b>Gate 2: Cold Outreach Draft Ready for Review</b>\n\n"
        f"🏢 <b>Target:</b> {company_name}\n"
        f"👤 <b>Recipient:</b> {recipient_name} &lt;<code>{recipient_email}</code>&gt;\n"
        f"📌 <b>Subject:</b> <code>{escaped_subject}</code>\n\n"
        f"📄 <b>Pitch Copy:</b>\n"
        f"<blockquote>{escaped_body}</blockquote>"
    )

    keyboard = [
        [
            InlineKeyboardButton("🚀 Confirm & Send", callback_data=f"send_draft:{resolved_id}"),
            InlineKeyboardButton("✏️ Edit Copy", callback_data=f"edit_draft:{resolved_id}"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_draft:{resolved_id}"),
        ],
    ]

    return text, InlineKeyboardMarkup(keyboard)


async def send_lead_review_card(
    bot: Bot,
    chat_id: str | int,
    lead_data: LeadEvaluation | LeadRecord | dict[str, Any],
    lead_id: str | None = None,
) -> int | None:
    """Push Gate 1 interactive lead card to operator Telegram chat.

    Updates telegram_message_id in database if lead_id is present.
    """
    text, reply_markup = build_lead_review_card(lead_data, lead_id=lead_id)

    try:
        message = await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )

        resolved_id = lead_id or (lead_data.id if hasattr(lead_data, "id") else lead_data.get("id"))
        if resolved_id and message.message_id:
            await update_lead_telegram_msg(lead_id=resolved_id, telegram_message_id=message.message_id)

        return message.message_id

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to push Gate 1 lead review card to Telegram chat {chat_id}: {exc}")
        return None


async def send_draft_review_card(
    bot: Bot,
    chat_id: str | int,
    lead_data: LeadRecord | dict[str, Any] | LeadEvaluation,
    draft: EmailDraft | dict[str, str],
    lead_id: str | None = None,
) -> int | None:
    """Push Gate 2 interactive draft card to operator Telegram chat."""
    text, reply_markup = build_draft_review_card(lead_data, draft, lead_id=lead_id)

    try:
        message = await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )
        return message.message_id

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to push Gate 2 draft review card to Telegram chat {chat_id}: {exc}")
        return None


# ==============================================================================
# Telegram Command Handlers
# ==============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command with welcome dashboard."""
    if not update.message:
        return

    welcome_text = (
        "🤖 <b>Client Scouting & Outreach Engine Active</b>\n\n"
        "Welcome to your mobile Human-In-The-Loop (HITL) control center.\n\n"
        "<b>Available Commands:</b>\n"
        "• /status - View database pipeline metrics and lead count totals\n"
        "• /pending - View leads waiting for Gate 1 or Gate 2 review\n"
        "• /help - Display command reference and operating guide\n\n"
        "<i>Leads will be pushed here automatically as background discovery cycles complete.</i>"
    )

    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command displaying live database pipeline metrics."""
    if not update.message:
        return

    try:
        sb = await get_supabase_client()
        # Fetch counts by status
        response = await sb.table(TABLE_LEADS).select("status").execute()
        rows = response.data or []

        counts: dict[str, int] = {}
        for r in rows:
            s = r.get("status", "UNKNOWN")
            counts[s] = counts.get(s, 0) + 1

        total = len(rows)
        pending_lead = counts.get(LeadStatus.PENDING_LEAD_REVIEW.value, 0)
        draft_gen = counts.get(LeadStatus.DRAFT_GENERATED.value, 0)
        sent = counts.get(LeadStatus.EMAIL_SENT.value, 0)
        rejected = counts.get(LeadStatus.LEAD_REJECTED.value, 0)
        draft_rej = counts.get(LeadStatus.DRAFT_REJECTED.value, 0)
        interested = counts.get(LeadStatus.REPLIED_INTERESTED.value, 0)

        status_text = (
            "📊 <b>Pipeline Statistics & Lead Statuses</b>\n\n"
            f"📦 <b>Total Discovered Leads:</b> <code>{total}</code>\n\n"
            f"⏳ <b>Pending Gate 1 (Lead Review):</b> <code>{pending_lead}</code>\n"
            f"📝 <b>Pending Gate 2 (Draft Review):</b> <code>{draft_gen}</code>\n"
            f"🚀 <b>Emails Dispatched:</b> <code>{sent}</code>\n"
            f"💬 <b>Interested Replies:</b> <code>{interested}</code>\n"
            f"❌ <b>Discarded Leads:</b> <code>{rejected}</code>\n"
            f"🗑️ <b>Cancelled Drafts:</b> <code>{draft_rej}</code>\n\n"
            f"<i>Daily Outbox Cap: {settings.DAILY_EMAIL_CAP} emails/day</i>"
        )

        await update.message.reply_text(status_text, parse_mode=ParseMode.HTML)

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to query pipeline status: {exc}")
        await update.message.reply_text(
            f"⚠️ <b>Status query failed:</b> <code>{html.escape(str(exc))}</code>",
            parse_mode=ParseMode.HTML,
        )


async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /pending command listing leads currently waiting for operator review."""
    if not update.message:
        return

    try:
        pending_gate1 = await get_leads_by_status(LeadStatus.PENDING_LEAD_REVIEW, limit=5)
        pending_gate2 = await get_leads_by_status(LeadStatus.DRAFT_GENERATED, limit=5)

        if not pending_gate1 and not pending_gate2:
            await update.message.reply_text("✅ <b>No pending reviews!</b> All leads have been processed.", parse_mode=ParseMode.HTML)
            return

        response_lines = ["📋 <b>Pending Lead Action Items:</b>\n"]

        if pending_gate1:
            response_lines.append("<b>Gate 1: Pending Qualification</b>")
            for lead in pending_gate1:
                name = html.escape(lead.get("company_name", "Unknown"))
                score = lead.get("fit_score", 0)
                lead_id = lead.get("id")
                response_lines.append(f"• {name} (Fit: {score}/10) - <code>{lead_id}</code>")
            response_lines.append("")

        if pending_gate2:
            response_lines.append("<b>Gate 2: Pending Draft Approval</b>")
            for lead in pending_gate2:
                name = html.escape(lead.get("company_name", "Unknown"))
                subject = html.escape(lead.get("email_subject") or "No subject")
                lead_id = lead.get("id")
                response_lines.append(f"• {name} - \"{subject}\" - <code>{lead_id}</code>")

        await update.message.reply_text("\n".join(response_lines), parse_mode=ParseMode.HTML)

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to retrieve pending leads: {exc}")
        await update.message.reply_text(f"⚠️ Query failed: <code>{html.escape(str(exc))}</code>", parse_mode=ParseMode.HTML)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command with operating documentation."""
    if not update.message:
        return

    help_text = (
        "📖 <b>Operator Manual & Bot Help</b>\n\n"
        "<b>Workflow Gates:</b>\n"
        "1️⃣ <b>Gate 1 (Lead Qualification):</b> Review company operations, pros/cons, and score. Tap <code>[✅ Approve & Draft]</code> to trigger AI copy synthesis or <code>[❌ Discard]</code>.\n"
        "2️⃣ <b>Gate 2 (Email Approval):</b> Review generated cold email copy. Tap <code>[🚀 Confirm & Send]</code> to queue dispatch, <code>[✏️ Edit Copy]</code> to refine, or <code>[❌ Cancel]</code>.\n\n"
        "<b>Commands:</b>\n"
        "• /status - Metrics overview across all stages\n"
        "• /pending - View top 5 pending Gate 1 & Gate 2 leads\n"
        "• /help - Show this manual"
    )

    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)


def create_telegram_app(token: str | None = None) -> Application:
    """Build and configure the python-telegram-bot Application instance."""
    resolved_token = token or settings.TELEGRAM_BOT_TOKEN
    if not resolved_token:
        logger.warning("TELEGRAM_BOT_TOKEN is not set. Bot application created with dummy token.")
        resolved_token = "123456:DUMMY_TOKEN_FOR_UNCONFIGURED_ENVIRONMENT"

    app = ApplicationBuilder().token(resolved_token).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("pending", pending_command))
    app.add_handler(CommandHandler("help", help_command))

    # Register interactive callback query dispatcher
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    # Register plain text handler for manual draft edits
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    return app
