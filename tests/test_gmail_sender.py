"""Unit and integration tests for Gmail API OAuth2 outbox sender and pacing controller."""

from __future__ import annotations

import base64
from email import message_from_bytes
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from googleapiclient.errors import HttpError

from dispatch.gmail_sender import (
    GmailDispatchError,
    check_daily_cap,
    create_mime_message,
    dispatch_approved_lead,
    get_daily_sent_count,
    get_gmail_credentials,
    get_random_jitter_seconds,
    is_business_hours,
    send_cold_email,
)
from evaluators.schemas import LeadStatus

# ==============================================================================
# MIME Message & Utility Tests
# ==============================================================================

def test_create_mime_message():
    payload = create_mime_message(
        to_email="john.doe@apexfreight.com",
        subject="quick question re waybills",
        body="Hi John,\n\nWe built an automation pipeline for waybills.\n\nBest,\nBader",
        from_email="bader@automation.ai",
    )

    assert "raw" in payload
    raw_decoded = base64.urlsafe_b64decode(payload["raw"].encode("utf-8"))
    mime_msg = message_from_bytes(raw_decoded)

    assert mime_msg["To"] == "john.doe@apexfreight.com"
    assert mime_msg["Subject"] == "quick question re waybills"
    assert mime_msg["From"] == "bader@automation.ai"
    payload_text = mime_msg.get_payload(decode=True).decode("utf-8")
    assert "We built an automation pipeline" in payload_text


def test_get_random_jitter_seconds():
    # Normal range
    jitter = get_random_jitter_seconds(min_seconds=600, max_seconds=1500)
    assert 600 <= jitter <= 1500

    # Inverted range
    jitter_inv = get_random_jitter_seconds(min_seconds=100, max_seconds=50)
    assert 50 <= jitter_inv <= 100


def test_is_business_hours():
    # Check that boolean is returned
    result = is_business_hours()
    assert isinstance(result, bool)


# ==============================================================================
# Credentials & Service Tests
# ==============================================================================

def test_get_gmail_credentials_missing(tmp_path):
    creds_file = tmp_path / "credentials.json"
    token_file = tmp_path / "token.json"

    with pytest.raises(GmailDispatchError, match="credentials file not found"):
        get_gmail_credentials(credentials_file=creds_file, token_file=token_file)


def test_get_gmail_credentials_valid_token(mocker, tmp_path):
    token_file = tmp_path / "token.json"
    token_file.write_text('{"token": "mock_token"}', encoding="utf-8")

    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.expired = False

    mocker.patch(
        "google.oauth2.credentials.Credentials.from_authorized_user_file",
        return_value=mock_creds,
    )

    creds = get_gmail_credentials(token_file=token_file)
    assert creds == mock_creds


# ==============================================================================
# Rate Limiting & Daily Cap Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_get_daily_sent_count(mocker):
    mock_sb = MagicMock()
    mock_exec = AsyncMock()
    mock_exec.return_value = MagicMock(data=[{"id": "1"}, {"id": "2"}, {"id": "3"}])
    mock_table = MagicMock()
    mock_table.select.return_value.eq.return_value.gte.return_value.execute = mock_exec
    mock_sb.table.return_value = mock_table

    mocker.patch("dispatch.gmail_sender.get_supabase_client", new_callable=AsyncMock, return_value=mock_sb)

    count = await get_daily_sent_count()
    assert count == 3


@pytest.mark.asyncio
async def test_check_daily_cap(mocker):
    # Under cap
    mocker.patch("dispatch.gmail_sender.get_daily_sent_count", new_callable=AsyncMock, return_value=5)
    can_send, count, cap = await check_daily_cap(limit=15)
    assert can_send is True
    assert count == 5
    assert cap == 15

    # At cap
    mocker.patch("dispatch.gmail_sender.get_daily_sent_count", new_callable=AsyncMock, return_value=15)
    can_send_at, count_at, _cap_at = await check_daily_cap(limit=15)
    assert can_send_at is False
    assert count_at == 15


# ==============================================================================
# Send Email Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_send_cold_email_success(mocker):
    mocker.patch("dispatch.gmail_sender.check_daily_cap", new_callable=AsyncMock, return_value=(True, 2, 15))

    mock_service = MagicMock()
    mock_send = MagicMock()
    mock_send.execute.return_value = {"id": "msg-12345", "threadId": "thread-67890"}
    mock_service.users.return_value.messages.return_value.send.return_value = mock_send

    result = await send_cold_email(
        to_email="john@apexfreight.com",
        subject="quick question re waybills",
        body="Hi John, cold email pitch.",
        service=mock_service,
    )

    assert result["success"] is True
    assert result["message_id"] == "msg-12345"
    assert result["thread_id"] == "thread-67890"
    assert result["to"] == "john@apexfreight.com"


@pytest.mark.asyncio
async def test_send_cold_email_cap_exceeded(mocker):
    mocker.patch("dispatch.gmail_sender.check_daily_cap", new_callable=AsyncMock, return_value=(False, 15, 15))
    mock_service = MagicMock()

    with pytest.raises(GmailDispatchError, match="Daily email dispatch cap reached"):
        await send_cold_email(
            to_email="john@apexfreight.com",
            subject="quick question",
            body="body",
            service=mock_service,
        )


@pytest.mark.asyncio
async def test_send_cold_email_invalid_recipient():
    with pytest.raises(ValueError, match="Invalid recipient email address"):
        await send_cold_email(
            to_email="invalid-email-string",
            subject="subject",
            body="body",
        )


@pytest.mark.asyncio
async def test_send_cold_email_api_error(mocker):
    mocker.patch("dispatch.gmail_sender.check_daily_cap", new_callable=AsyncMock, return_value=(True, 0, 15))

    mock_service = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status = 403
    mock_send = MagicMock()
    mock_send.execute.side_effect = HttpError(resp=mock_resp, content=b"Daily quota exceeded")
    mock_service.users.return_value.messages.return_value.send.return_value = mock_send

    with pytest.raises(GmailDispatchError, match="Gmail API HTTP error"):
        await send_cold_email(
            to_email="john@apexfreight.com",
            subject="subject",
            body="body",
            service=mock_service,
        )


# ==============================================================================
# Approved Lead Dispatch Workflow Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_dispatch_approved_lead_success(mocker):
    lead_id = str(uuid4())
    mock_lead = {
        "id": lead_id,
        "company_name": "Apex Freight",
        "decision_maker_email": "john.doe@apexfreight.com",
        "email_subject": "quick question re waybills",
        "email_body": "Hi John, personalized 3-sentence body.",
    }

    mocker.patch("dispatch.gmail_sender.get_lead_by_id", new_callable=AsyncMock, return_value=mock_lead)
    mocker.patch("dispatch.gmail_sender.update_lead_status", new_callable=AsyncMock)
    mock_send_email = mocker.patch(
        "dispatch.gmail_sender.send_cold_email",
        new_callable=AsyncMock,
        return_value={"success": True, "message_id": "msg-999"},
    )

    result = await dispatch_approved_lead(lead_id=lead_id, apply_jitter=False)

    assert result["lead_id"] == lead_id
    assert result["company_name"] == "Apex Freight"
    assert result["to_email"] == "john.doe@apexfreight.com"
    assert result["message_id"] == "msg-999"
    assert result["status"] == LeadStatus.EMAIL_SENT.value

    mock_send_email.assert_called_once_with(
        to_email="john.doe@apexfreight.com",
        subject="quick question re waybills",
        body="Hi John, personalized 3-sentence body.",
        check_cap=True,
        service=None,
        client=None,
    )


@pytest.mark.asyncio
async def test_dispatch_approved_lead_missing_draft(mocker):
    lead_id = str(uuid4())
    mock_lead = {
        "id": lead_id,
        "company_name": "Apex Freight",
        "decision_maker_email": "john@apexfreight.com",
        "email_subject": None,  # Missing draft
        "email_body": None,
    }

    mocker.patch("dispatch.gmail_sender.get_lead_by_id", new_callable=AsyncMock, return_value=mock_lead)

    with pytest.raises(GmailDispatchError, match="incomplete email draft copy"):
        await dispatch_approved_lead(lead_id=lead_id)
