"""Unit and integration tests for Mobile HITL Telegram Bot interface and callback handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Bot, Chat, Message, Update, User
from telegram.ext import ContextTypes

from bot.callbacks import (
    handle_callback_query,
    handle_draft_cancel,
    handle_draft_edit,
    handle_draft_send,
    handle_lead_approval,
    handle_lead_discard,
    handle_text_message,
)
from bot.telegram_bot import (
    build_draft_review_card,
    build_lead_review_card,
    create_telegram_app,
    help_command,
    pending_command,
    send_draft_review_card,
    send_lead_review_card,
    start_command,
    status_command,
)
from evaluators.schemas import EmailDraft, LeadEvaluation, LeadStatus


def create_mock_update(
    callback_data: str | None = None,
    message_text: str | None = None,
    chat_id: int = 123456789,
    message_id: int = 42,
) -> Update:
    """Create a mock Telegram Update object."""
    mock_update = MagicMock(spec=Update)
    mock_user = MagicMock(spec=User)
    mock_user.id = 987654321
    mock_user.first_name = "Operator"

    mock_chat = MagicMock(spec=Chat)
    mock_chat.id = chat_id

    mock_message = MagicMock(spec=Message)
    mock_message.message_id = message_id
    mock_message.chat = mock_chat
    mock_message.chat_id = chat_id
    mock_message.from_user = mock_user
    mock_message.text = message_text
    mock_message.reply_text = AsyncMock()

    mock_update.message = mock_message if message_text else None
    mock_update.effective_chat = mock_chat
    mock_update.effective_user = mock_user

    if callback_data:
        mock_query = MagicMock()
        mock_query.data = callback_data
        mock_query.message = mock_message
        mock_query.from_user = mock_user
        mock_query.answer = AsyncMock()
        mock_query.edit_message_text = AsyncMock()
        mock_update.callback_query = mock_query
    else:
        mock_update.callback_query = None

    return mock_update


def create_mock_context() -> ContextTypes.DEFAULT_TYPE:
    """Create a mock telegram ContextTypes object."""
    context = MagicMock()
    context.user_data = {}
    context.bot = MagicMock(spec=Bot)
    context.bot.send_message = AsyncMock()
    return context


# ==============================================================================
# Card Builder Tests
# ==============================================================================

def test_build_lead_review_card():
    lead = LeadEvaluation(
        company_name="Apex Freight",
        website_url="https://apexfreight.com",
        decision_maker_name="John Doe",
        decision_maker_title="Managing Director",
        decision_maker_email="john@apexfreight.com",
        fit_score=9,
        summary="Freight forwarding company with paperwork bottlenecks.",
        pros=["Waybill extraction delays", "Manual dispatch overhead"],
        cons=["Legacy TMS software"],
        suggested_angle="Automate waybills directly into dispatch ERP.",
    )

    text, markup = build_lead_review_card(lead, lead_id="11111111-2222-3333-4444-555555555555")

    assert "Apex Freight" in text
    assert "John Doe" in text
    assert "9/10" in text
    assert "Waybill extraction delays" in text
    assert "Automate waybills directly" in text

    # Verify buttons
    buttons = markup.inline_keyboard[0]
    assert len(buttons) == 2
    assert buttons[0].text == "✅ Approve & Draft"
    assert buttons[0].callback_data == "approve_lead:11111111-2222-3333-4444-555555555555"
    assert buttons[1].text == "❌ Discard"
    assert buttons[1].callback_data == "discard_lead:11111111-2222-3333-4444-555555555555"


def test_build_draft_review_card():
    draft = EmailDraft(
        subject="quick question re waybills",
        body="Hi John, noticed Apex Freight processes hundreds of waybills daily. We built an automated pipeline that extracts waybills into your ERP in 3 seconds. Open to a 2-minute video on how this works?",
    )
    lead_data = {
        "company_name": "Apex Freight",
        "decision_maker_name": "John Doe",
        "decision_maker_email": "john@apexfreight.com",
    }

    text, markup = build_draft_review_card(lead_data, draft, lead_id="test-lead-123")

    assert "Apex Freight" in text
    assert "quick question re waybills" in text
    assert "extracts waybills into your ERP" in text

    # Verify 2 rows of buttons
    assert len(markup.inline_keyboard) == 2
    row1 = markup.inline_keyboard[0]
    row2 = markup.inline_keyboard[1]
    assert row1[0].text == "🚀 Confirm & Send"
    assert row1[0].callback_data == "send_draft:test-lead-123"
    assert row1[1].text == "✏️ Edit Copy"
    assert row1[1].callback_data == "edit_draft:test-lead-123"
    assert row2[0].text == "❌ Cancel"
    assert row2[0].callback_data == "cancel_draft:test-lead-123"


# ==============================================================================
# Notification Push Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_send_lead_review_card(mocker):
    mock_bot = MagicMock(spec=Bot)
    mock_msg = MagicMock()
    mock_msg.message_id = 999
    mock_bot.send_message = AsyncMock(return_value=mock_msg)

    mock_update_msg = mocker.patch("bot.telegram_bot.update_lead_telegram_msg", new_callable=AsyncMock)

    lead_data = {
        "id": "lead-uuid-123",
        "company_name": "Apex Freight",
        "website_url": "https://apexfreight.com",
        "fit_score": 8,
    }

    msg_id = await send_lead_review_card(mock_bot, chat_id=12345, lead_data=lead_data)

    assert msg_id == 999
    mock_bot.send_message.assert_called_once()
    mock_update_msg.assert_called_once_with(lead_id="lead-uuid-123", telegram_message_id=999)


@pytest.mark.asyncio
async def test_send_draft_review_card():
    mock_bot = MagicMock(spec=Bot)
    mock_msg = MagicMock()
    mock_msg.message_id = 1001
    mock_bot.send_message = AsyncMock(return_value=mock_msg)

    lead_data = {"company_name": "Apex Freight", "decision_maker_name": "John"}
    draft = EmailDraft(subject="subject line", body="body copy")

    msg_id = await send_draft_review_card(mock_bot, chat_id=12345, lead_data=lead_data, draft=draft, lead_id="lead-123")

    assert msg_id == 1001
    mock_bot.send_message.assert_called_once()


# ==============================================================================
# Callback Query Handler Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_handle_lead_approval_success(mocker):
    update = create_mock_update(callback_data="approve_lead:lead-123")
    context = create_mock_context()

    mock_lead = {
        "id": "lead-123",
        "company_name": "Apex Freight",
        "website_url": "https://apexfreight.com",
        "decision_maker_name": "John Doe",
        "decision_maker_email": "john@apexfreight.com",
        "fit_score": 9,
        "summary": "Freight forwarding company",
        "pros": ["Waybills"],
        "cons": ["TMS"],
        "suggested_angle": "Waybill automation",
    }

    mocker.patch("bot.callbacks.get_lead_by_id", new_callable=AsyncMock, return_value=mock_lead)
    mock_generate = mocker.patch(
        "bot.callbacks.generate_email_draft",
        new_callable=AsyncMock,
        return_value=EmailDraft(subject="quick question re waybills", body="Hi John, automation pitch body."),
    )
    mock_update_draft = mocker.patch("bot.callbacks.update_lead_draft", new_callable=AsyncMock)

    await handle_lead_approval(update, context, lead_id="lead-123")

    update.callback_query.answer.assert_called_once()
    mock_generate.assert_called_once_with(lead=mock_lead, sender_name="Bader")
    mock_update_draft.assert_called_once()
    assert mock_update_draft.call_args[1]["status"] == LeadStatus.DRAFT_GENERATED
    context.bot.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_handle_lead_discard(mocker):
    update = create_mock_update(callback_data="discard_lead:lead-123")
    context = create_mock_context()

    mocker.patch("bot.callbacks.get_lead_by_id", new_callable=AsyncMock, return_value={"company_name": "Apex Freight"})
    mock_update_status = mocker.patch("bot.callbacks.update_lead_status", new_callable=AsyncMock)

    await handle_lead_discard(update, context, lead_id="lead-123")

    update.callback_query.answer.assert_called_once()
    mock_update_status.assert_called_once_with("lead-123", LeadStatus.LEAD_REJECTED)
    update.callback_query.edit_message_text.assert_called_once()
    assert "Discarded" in update.callback_query.edit_message_text.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_draft_send(mocker):
    update = create_mock_update(callback_data="send_draft:lead-123")
    context = create_mock_context()

    mocker.patch(
        "bot.callbacks.get_lead_by_id",
        new_callable=AsyncMock,
        return_value={"company_name": "Apex Freight", "email_subject": "quick question"},
    )
    mock_update_status = mocker.patch("bot.callbacks.update_lead_status", new_callable=AsyncMock)

    await handle_draft_send(update, context, lead_id="lead-123")

    update.callback_query.answer.assert_called_once()
    mock_update_status.assert_called_once_with("lead-123", LeadStatus.EMAIL_SENT)
    update.callback_query.edit_message_text.assert_called_once()
    assert "Approved & Queued" in update.callback_query.edit_message_text.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_draft_cancel(mocker):
    update = create_mock_update(callback_data="cancel_draft:lead-123")
    context = create_mock_context()

    mocker.patch("bot.callbacks.get_lead_by_id", new_callable=AsyncMock, return_value={"company_name": "Apex Freight"})
    mock_update_status = mocker.patch("bot.callbacks.update_lead_status", new_callable=AsyncMock)

    await handle_draft_cancel(update, context, lead_id="lead-123")

    update.callback_query.answer.assert_called_once()
    mock_update_status.assert_called_once_with("lead-123", LeadStatus.DRAFT_REJECTED)
    update.callback_query.edit_message_text.assert_called_once()
    assert "Cancelled" in update.callback_query.edit_message_text.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_draft_edit_and_reply_flow(mocker):
    # Step 1: Trigger Edit
    update_edit = create_mock_update(callback_data="edit_draft:lead-123")
    context = create_mock_context()

    mocker.patch(
        "bot.callbacks.get_lead_by_id",
        new_callable=AsyncMock,
        return_value={
            "id": "lead-123",
            "company_name": "Apex Freight",
            "email_subject": "old subject",
            "email_body": "old body",
        },
    )

    await handle_draft_edit(update_edit, context, lead_id="lead-123")
    assert context.user_data.get("editing_lead_id") == "lead-123"
    context.bot.send_message.assert_called_once()

    # Step 2: Operator replies with text
    update_msg = create_mock_update(message_text="Subject: New Custom Subject\n\nNew custom email body pitch.")
    mock_update_draft = mocker.patch("bot.callbacks.update_lead_draft", new_callable=AsyncMock)

    await handle_text_message(update_msg, context)

    mock_update_draft.assert_called_once()
    saved_draft = mock_update_draft.call_args[0][1]
    assert saved_draft.subject == "New Custom Subject"
    assert saved_draft.body == "New custom email body pitch."
    assert "editing_lead_id" not in context.user_data
    update_msg.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_handle_callback_query_routing(mocker):
    mock_approve = mocker.patch("bot.callbacks.handle_lead_approval", new_callable=AsyncMock)
    mock_discard = mocker.patch("bot.callbacks.handle_lead_discard", new_callable=AsyncMock)
    mock_send = mocker.patch("bot.callbacks.handle_draft_send", new_callable=AsyncMock)
    mock_cancel = mocker.patch("bot.callbacks.handle_draft_cancel", new_callable=AsyncMock)
    mock_edit = mocker.patch("bot.callbacks.handle_draft_edit", new_callable=AsyncMock)

    context = create_mock_context()

    # Approve
    u1 = create_mock_update(callback_data="approve_lead:1")
    await handle_callback_query(u1, context)
    mock_approve.assert_called_once_with(u1, context, "1")

    # Discard
    u2 = create_mock_update(callback_data="discard_lead:2")
    await handle_callback_query(u2, context)
    mock_discard.assert_called_once_with(u2, context, "2")

    # Send
    u3 = create_mock_update(callback_data="send_draft:3")
    await handle_callback_query(u3, context)
    mock_send.assert_called_once_with(u3, context, "3")

    # Cancel
    u4 = create_mock_update(callback_data="cancel_draft:4")
    await handle_callback_query(u4, context)
    mock_cancel.assert_called_once_with(u4, context, "4")

    # Edit
    u5 = create_mock_update(callback_data="edit_draft:5")
    await handle_callback_query(u5, context)
    mock_edit.assert_called_once_with(u5, context, "5")


# ==============================================================================
# Command Handler Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_start_command():
    update = create_mock_update(message_text="/start")
    context = create_mock_context()

    await start_command(update, context)
    update.message.reply_text.assert_called_once()
    assert "Client Scouting & Outreach Engine Active" in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_help_command():
    update = create_mock_update(message_text="/help")
    context = create_mock_context()

    await help_command(update, context)
    update.message.reply_text.assert_called_once()
    assert "Operator Manual" in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_status_command(mocker):
    update = create_mock_update(message_text="/status")
    context = create_mock_context()

    mock_sb = MagicMock()
    mock_exec = AsyncMock()
    mock_exec.return_value = MagicMock(data=[
        {"status": "PENDING_LEAD_REVIEW"},
        {"status": "PENDING_LEAD_REVIEW"},
        {"status": "EMAIL_SENT"},
    ])
    mock_table = MagicMock()
    mock_table.select.return_value.execute = mock_exec
    mock_sb.table.return_value = mock_table

    mocker.patch("bot.telegram_bot.get_supabase_client", new_callable=AsyncMock, return_value=mock_sb)

    await status_command(update, context)
    update.message.reply_text.assert_called_once()
    reply_text = update.message.reply_text.call_args[0][0]
    assert "Total Discovered Leads:</b> <code>3</code>" in reply_text
    assert "Pending Gate 1 (Lead Review):</b> <code>2</code>" in reply_text
    assert "Emails Dispatched:</b> <code>1</code>" in reply_text


@pytest.mark.asyncio
async def test_pending_command(mocker):
    update = create_mock_update(message_text="/pending")
    context = create_mock_context()

    mocker.patch(
        "bot.telegram_bot.get_leads_by_status",
        side_effect=[
            [{"id": "lead-1", "company_name": "Apex Freight", "fit_score": 9}],
            [{"id": "lead-2", "company_name": "Urban Properties", "email_subject": "quick question"}],
        ],
    )

    await pending_command(update, context)
    update.message.reply_text.assert_called_once()
    reply_text = update.message.reply_text.call_args[0][0]
    assert "Apex Freight" in reply_text
    assert "Urban Properties" in reply_text


def test_create_telegram_app():
    app = create_telegram_app(token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    assert app is not None
    # Verify handler groups
    assert len(app.handlers) > 0
