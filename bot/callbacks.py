"""Interactive callback handlers for Gate 1 (Lead Review) and Gate 2 (Draft Review)."""

from __future__ import annotations

import html

from loguru import logger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from database.queries import (
    get_lead_by_id,
    update_lead_draft,
    update_lead_status,
)
from evaluators.llm_service import generate_email_draft
from evaluators.schemas import EmailDraft, LeadStatus


def _build_draft_inline_keyboard(lead_id: str) -> InlineKeyboardMarkup:
    """Build Gate 2 interactive inline action buttons."""
    keyboard = [
        [
            InlineKeyboardButton(
                "🚀 Confirm & Send", callback_data=f"send_draft:{lead_id}"
            ),
            InlineKeyboardButton("✏️ Edit Copy", callback_data=f"edit_draft:{lead_id}"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_draft:{lead_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def handle_lead_approval(
    update: Update, context: ContextTypes.DEFAULT_TYPE, lead_id: str
) -> None:
    """Handle Gate 1 approval: qualify lead, invoke LLM copywriting, and push Gate 2 draft card."""
    query = update.callback_query
    if not query:
        return

    await query.answer("✅ Lead approved! Generating cold email copy...")
    logger.info(f"Gate 1 Approved for lead_id: {lead_id}")

    # Fetch full lead record from database
    lead = await get_lead_by_id(lead_id)
    if not lead:
        await query.edit_message_text(
            f"⚠️ <b>Lead not found</b> in database (ID: <code>{lead_id}</code>).",
            parse_mode=ParseMode.HTML,
        )
        return

    company_name = html.escape(lead.get("company_name", "Target Company"))

    # Update original message to show progress
    await query.edit_message_text(
        f"✅ <b>Lead Approved:</b> {company_name}\n"
        f"⏳ <i>Synthesizing 3-sentence personalized cold email via AI Copywriter...</i>",
        parse_mode=ParseMode.HTML,
    )

    try:
        # Generate personalized 3-sentence cold pitch using LLM router
        draft = await generate_email_draft(lead=lead, sender_name="Bader")

        # Persist generated draft to database with DRAFT_GENERATED status
        await update_lead_draft(
            lead_id=lead_id,
            draft=draft,
            status=LeadStatus.DRAFT_GENERATED,
        )

        # Build Gate 2 Card
        recipient_name = html.escape(
            lead.get("decision_maker_name") or "Operations Lead"
        )
        recipient_email = html.escape(lead.get("decision_maker_email") or "Unresolved")
        escaped_subject = html.escape(draft.subject)
        escaped_body = html.escape(draft.body)

        draft_card_text = (
            f"✉️ <b>Gate 2: Cold Outreach Draft Ready for Review</b>\n\n"
            f"🏢 <b>Target:</b> {company_name}\n"
            f"👤 <b>Recipient:</b> {recipient_name} &lt;<code>{recipient_email}</code>&gt;\n"
            f"📌 <b>Subject:</b> <code>{escaped_subject}</code>\n\n"
            f"📄 <b>Pitch Copy:</b>\n"
            f"<blockquote>{escaped_body}</blockquote>"
        )

        reply_markup = _build_draft_inline_keyboard(lead_id)

        # Send Gate 2 review card as a new message to the operator chat
        chat_id = query.message.chat_id if query.message else None
        if chat_id:
            await context.bot.send_message(
                chat_id=chat_id,
                text=draft_card_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to generate draft for lead {lead_id}: {exc}")
        await query.edit_message_text(
            f"⚠️ <b>Draft Generation Failed</b> for {company_name}:\n<code>{html.escape(str(exc))}</code>",
            parse_mode=ParseMode.HTML,
        )


async def handle_lead_discard(
    update: Update, context: ContextTypes.DEFAULT_TYPE, lead_id: str
) -> None:
    """Handle Gate 1 discard: mark lead as LEAD_REJECTED in database."""
    query = update.callback_query
    if not query:
        return

    await query.answer("❌ Lead discarded")
    logger.info(f"Gate 1 Discarded for lead_id: {lead_id}")

    lead = await get_lead_by_id(lead_id)
    company_name = html.escape(lead.get("company_name", "Lead")) if lead else "Lead"

    await update_lead_status(lead_id, LeadStatus.LEAD_REJECTED)

    await query.edit_message_text(
        f"❌ <b>Lead Discarded:</b> {company_name}\n"
        f"<i>Status updated to LEAD_REJECTED.</i>",
        parse_mode=ParseMode.HTML,
    )


async def handle_draft_send(
    update: Update, context: ContextTypes.DEFAULT_TYPE, lead_id: str
) -> None:
    """Handle Gate 2 send approval: approve draft and queue for dispatch."""
    query = update.callback_query
    if not query:
        return

    await query.answer("🚀 Email approved for dispatch!")
    logger.info(f"Gate 2 Approved & Sent for lead_id: {lead_id}")

    lead = await get_lead_by_id(lead_id)
    company_name = html.escape(lead.get("company_name", "Lead")) if lead else "Lead"
    subject = html.escape(lead.get("email_subject", "No subject")) if lead else ""

    # Transition status to EMAIL_SENT
    await update_lead_status(lead_id, LeadStatus.EMAIL_SENT)

    await query.edit_message_text(
        f"🚀 <b>Email Approved & Queued for Sending!</b>\n\n"
        f"🏢 <b>Target:</b> {company_name}\n"
        f"📌 <b>Subject:</b> <code>{subject}</code>\n"
        f"<i>Status transitioned to EMAIL_SENT. Dispatcher will pace sending with safety jitter.</i>",
        parse_mode=ParseMode.HTML,
    )


async def handle_draft_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE, lead_id: str
) -> None:
    """Handle Gate 2 cancellation: mark draft as DRAFT_REJECTED in database."""
    query = update.callback_query
    if not query:
        return

    await query.answer("❌ Draft cancelled")
    logger.info(f"Gate 2 Cancelled for lead_id: {lead_id}")

    lead = await get_lead_by_id(lead_id)
    company_name = html.escape(lead.get("company_name", "Lead")) if lead else "Lead"

    await update_lead_status(lead_id, LeadStatus.DRAFT_REJECTED)

    await query.edit_message_text(
        f"❌ <b>Draft Cancelled:</b> {company_name}\n"
        f"<i>Status updated to DRAFT_REJECTED.</i>",
        parse_mode=ParseMode.HTML,
    )


async def handle_draft_edit(
    update: Update, context: ContextTypes.DEFAULT_TYPE, lead_id: str
) -> None:
    """Handle Gate 2 edit request: prompt operator for updated subject and copy."""
    query = update.callback_query
    if not query:
        return

    await query.answer("✏️ Ready for edits")
    logger.info(f"Gate 2 Edit requested for lead_id: {lead_id}")

    context.user_data["editing_lead_id"] = lead_id

    lead = await get_lead_by_id(lead_id)
    current_subject = lead.get("email_subject", "") if lead else ""
    current_body = lead.get("email_body", "") if lead else ""

    prompt_text = (
        f"✏️ <b>Edit Email Draft</b>\n\n"
        f"Reply to this message with your updated subject and body in this format:\n\n"
        f"<code>Subject: {html.escape(current_subject or 'new subject line')}\n\n"
        f"{html.escape(current_body or 'new 3-sentence body copy')}</code>"
    )

    if query.message:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=prompt_text,
            parse_mode=ParseMode.HTML,
        )


async def handle_text_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle plain text replies from operator for draft manual edits."""
    if not update.message or not update.message.text:
        return

    editing_lead_id = context.user_data.get("editing_lead_id")
    if not editing_lead_id:
        # Not in edit mode, ignore or reply
        return

    raw_text = update.message.text.strip()
    subject = ""
    body = raw_text

    # Parse optional "Subject: ..." header line
    lines = raw_text.splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        body = "\n".join(lines[1:]).strip()

    lead = await get_lead_by_id(editing_lead_id)
    if not lead:
        await update.message.reply_text("⚠️ Lead not found.")
        context.user_data.pop("editing_lead_id", None)
        return

    final_subject = subject or lead.get("email_subject", "quick question re automation")
    final_draft = EmailDraft(subject=final_subject[:50], body=body[:600])

    await update_lead_draft(
        editing_lead_id, final_draft, status=LeadStatus.DRAFT_GENERATED
    )
    context.user_data.pop("editing_lead_id", None)

    company_name = html.escape(lead.get("company_name", "Target Company"))
    recipient_name = html.escape(lead.get("decision_maker_name") or "Operations Lead")
    recipient_email = html.escape(lead.get("decision_maker_email") or "Unresolved")

    draft_card_text = (
        f"✏️ <b>Gate 2: Updated Email Draft Ready for Review</b>\n\n"
        f"🏢 <b>Target:</b> {company_name}\n"
        f"👤 <b>Recipient:</b> {recipient_name} &lt;<code>{recipient_email}</code>&gt;\n"
        f"📌 <b>Subject:</b> <code>{html.escape(final_draft.subject)}</code>\n\n"
        f"📄 <b>Pitch Copy:</b>\n"
        f"<blockquote>{html.escape(final_draft.body)}</blockquote>"
    )

    reply_markup = _build_draft_inline_keyboard(editing_lead_id)

    await update.message.reply_text(
        text=draft_card_text,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup,
    )


async def handle_callback_query(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Central callback query router matching callback_data prefixes."""
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data

    if data.startswith("approve_lead:"):
        lead_id = data.split(":", 1)[1]
        await handle_lead_approval(update, context, lead_id)
    elif data.startswith("discard_lead:"):
        lead_id = data.split(":", 1)[1]
        await handle_lead_discard(update, context, lead_id)
    elif data.startswith("send_draft:"):
        lead_id = data.split(":", 1)[1]
        await handle_draft_send(update, context, lead_id)
    elif data.startswith("cancel_draft:"):
        lead_id = data.split(":", 1)[1]
        await handle_draft_cancel(update, context, lead_id)
    elif data.startswith("edit_draft:"):
        lead_id = data.split(":", 1)[1]
        await handle_draft_edit(update, context, lead_id)
    else:
        logger.warning(f"Unrecognized callback query data: {data}")
        await query.answer("Unknown action")
