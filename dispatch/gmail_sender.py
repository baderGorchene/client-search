"""Gmail API OAuth2 outbox sender with daily rate limiting and safety jitter delays."""

from __future__ import annotations

import asyncio
import base64
import random
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any
from uuid import UUID

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from loguru import logger
from supabase import AsyncClient

from config.settings import settings
from database.client import get_supabase_client
from database.queries import (
    TABLE_LEADS,
    get_lead_by_id,
    update_lead_status,
)
from evaluators.schemas import LeadStatus

SCOPES: list[str] = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
]


class GmailDispatchError(Exception):
    """Custom exception raised when email outbox dispatch fails or caps are exceeded."""


def create_mime_message(
    to_email: str,
    subject: str,
    body: str,
    from_email: str | None = None,
) -> dict[str, str]:
    """Create an RFC 2822 base64url-encoded MIME plain text email payload."""
    message = MIMEText(body, "plain", "utf-8")
    message["To"] = to_email
    message["Subject"] = subject
    if from_email:
        message["From"] = from_email

    raw_bytes = base64.urlsafe_b64encode(message.as_bytes())
    return {"raw": raw_bytes.decode("utf-8")}


def get_random_jitter_seconds(
    min_seconds: int | None = None,
    max_seconds: int | None = None,
) -> int:
    """Calculate a randomized jitter delay between email dispatches."""
    min_val, max_val = sorted((
        min_seconds if min_seconds is not None else settings.EMAIL_JITTER_MIN_SECONDS,
        max_seconds if max_seconds is not None else settings.EMAIL_JITTER_MAX_SECONDS,
    ))
    return random.randint(min_val, max_val)


def is_business_hours(
    timezone_offset_hours: int = 0,
    start_hour: int = 9,
    end_hour: int = 17,
) -> bool:
    """Check if current time in target timezone is within business hours (09:00 to 17:00)."""
    now_utc = datetime.now(timezone.utc)
    target_hour = (now_utc.hour + timezone_offset_hours) % 24
    is_weekday = now_utc.weekday() < 5
    return is_weekday and (start_hour <= target_hour < end_hour)


def get_gmail_credentials(
    credentials_file: Path | str | None = None,
    token_file: Path | str | None = None,
) -> Credentials:
    """Load and validate stored Gmail API OAuth2 user credentials."""
    creds_path = Path(credentials_file or settings.GMAIL_CREDENTIALS_FILE)
    token_path = Path(token_file or settings.GMAIL_TOKEN_FILE)

    creds: Credentials | None = None

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to load OAuth2 token from {token_path}: {exc}")

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json(), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to refresh OAuth2 token: {exc}")
            creds = None

    if not creds or not creds.valid:
        if not creds_path.exists():
            raise GmailDispatchError(
                f"Gmail OAuth2 credentials file not found at {creds_path}. "
                f"Please configure client credentials."
            )
        raise GmailDispatchError(
            f"Valid Gmail user token not found at {token_path}. "
            f"Please authenticate and generate token.json."
        )

    return creds


def get_gmail_service(
    credentials: Credentials | None = None,
    credentials_file: Path | str | None = None,
    token_file: Path | str | None = None,
) -> Resource:
    """Build and return an authorized Gmail API service Resource client."""
    creds = credentials or get_gmail_credentials(
        credentials_file=credentials_file,
        token_file=token_file,
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


async def get_daily_sent_count(client: AsyncClient | None = None) -> int:
    """Query Supabase for count of emails dispatched today (UTC)."""
    sb = client or await get_supabase_client()
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    try:
        response = (
            await sb.table(TABLE_LEADS)
            .select("id")
            .eq("status", LeadStatus.EMAIL_SENT.value)
            .gte("updated_at", today_start)
            .execute()
        )
        return len(response.data) if response.data else 0
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to query daily sent email count: {exc}")
        return 0


async def check_daily_cap(
    limit: int | None = None,
    client: AsyncClient | None = None,
) -> tuple[bool, int, int]:
    """Check whether current email dispatch volume is below the daily safety limit.

    Returns:
        tuple[bool, int, int]: (can_send, current_sent_today, max_daily_cap)
    """
    max_cap = limit or settings.DAILY_EMAIL_CAP
    current_count = await get_daily_sent_count(client=client)
    can_send = current_count < max_cap
    return can_send, current_count, max_cap


async def send_cold_email(
    to_email: str,
    subject: str,
    body: str,
    from_email: str | None = None,
    check_cap: bool = True,
    service: Any | None = None,
    client: AsyncClient | None = None,
) -> dict[str, Any]:
    """Asynchronously dispatch a cold outreach email via Gmail API with rate limit protection."""
    if not to_email or "@" not in to_email:
        raise ValueError(f"Invalid recipient email address: '{to_email}'")

    if check_cap:
        can_send, current_count, max_cap = await check_daily_cap(client=client)
        if not can_send:
            raise GmailDispatchError(
                f"Daily email dispatch cap reached: {current_count}/{max_cap} emails sent today."
            )

    gmail_service = service or get_gmail_service()
    raw_message = create_mime_message(
        to_email=to_email,
        subject=subject,
        body=body,
        from_email=from_email,
    )

    def _sync_send() -> dict[str, Any]:
        return gmail_service.users().messages().send(userId="me", body=raw_message).execute()

    try:
        response = await asyncio.to_thread(_sync_send)
        msg_id = response.get("id", "")
        thread_id = response.get("threadId", "")
        logger.info(f"Email successfully dispatched to {to_email} (ID: {msg_id})")
        return {
            "success": True,
            "message_id": msg_id,
            "thread_id": thread_id,
            "to": to_email,
            "subject": subject,
        }
    except HttpError as exc:
        error_msg = f"Gmail API HTTP error: {exc}"
        logger.error(error_msg)
        raise GmailDispatchError(error_msg) from exc
    except Exception as exc:
        logger.error(f"Unexpected error dispatching email to {to_email}: {exc}")
        raise GmailDispatchError(f"Email dispatch failed: {exc}") from exc


async def dispatch_approved_lead(
    lead_id: str | UUID,
    apply_jitter: bool = False,
    service: Any | None = None,
    client: AsyncClient | None = None,
) -> dict[str, Any]:
    """Execute complete outbox dispatch workflow for an approved lead."""
    lead = await get_lead_by_id(lead_id, client=client)
    if not lead:
        raise GmailDispatchError(f"Lead with ID {lead_id} not found in database.")

    to_email = lead.get("decision_maker_email")
    subject = lead.get("email_subject")
    body = lead.get("email_body")

    if not to_email:
        raise GmailDispatchError(f"Lead {lead_id} has no resolved recipient email address.")
    if not subject or not body:
        raise GmailDispatchError(f"Lead {lead_id} has incomplete email draft copy (missing subject or body).")

    if apply_jitter:
        jitter_sec = get_random_jitter_seconds()
        logger.info(
            f"Applying safety jitter delay: {jitter_sec}s ({jitter_sec/60:.1f} min) "
            f"before dispatching to {to_email}..."
        )
        await asyncio.sleep(jitter_sec)

    dispatch_result = await send_cold_email(
        to_email=to_email,
        subject=subject,
        body=body,
        check_cap=True,
        service=service,
        client=client,
    )

    # Transition lead status to EMAIL_SENT in database
    await update_lead_status(lead_id, LeadStatus.EMAIL_SENT, client=client)

    return {
        "lead_id": str(lead_id),
        "company_name": lead.get("company_name"),
        "to_email": to_email,
        "subject": subject,
        "message_id": dispatch_result.get("message_id"),
        "status": LeadStatus.EMAIL_SENT.value,
    }
