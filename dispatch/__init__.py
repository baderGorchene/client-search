"""Outbox email dispatch module with Gmail API OAuth2 integration, rate limiting, and safety jitter."""

from dispatch.gmail_sender import (
    GmailDispatchError,
    check_daily_cap,
    create_mime_message,
    dispatch_approved_lead,
    get_daily_sent_count,
    get_gmail_credentials,
    get_gmail_service,
    get_random_jitter_seconds,
    is_business_hours,
    send_cold_email,
)

__all__ = [
    "GmailDispatchError",
    "check_daily_cap",
    "create_mime_message",
    "dispatch_approved_lead",
    "get_daily_sent_count",
    "get_gmail_credentials",
    "get_gmail_service",
    "get_random_jitter_seconds",
    "is_business_hours",
    "send_cold_email",
]
