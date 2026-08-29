"""Database module for Supabase/PostgreSQL connection and queries."""

from database.client import get_supabase_client, reset_supabase_client
from database.queries import (
    create_lead,
    delete_lead,
    get_lead_by_id,
    get_lead_by_url,
    get_leads_by_status,
    update_lead,
    update_lead_draft,
    update_lead_status,
    update_lead_telegram_msg,
    upsert_lead,
)

__all__ = [
    "create_lead",
    "delete_lead",
    "get_lead_by_id",
    "get_lead_by_url",
    "get_leads_by_status",
    "get_supabase_client",
    "reset_supabase_client",
    "update_lead",
    "update_lead_draft",
    "update_lead_status",
    "update_lead_telegram_msg",
    "upsert_lead",
]
