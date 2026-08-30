"""Lead CRUD operations and status lifecycle management for Supabase/PostgreSQL."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from loguru import logger
from supabase import AsyncClient

from database.client import get_supabase_client
from evaluators.schemas import EmailDraft, LeadEvaluation, LeadRecord, LeadStatus

TABLE_LEADS = "leads"


def _prepare_lead_payload(lead_data: LeadEvaluation | LeadRecord | dict[str, Any]) -> dict[str, Any]:
    """Normalize input lead data to a JSON-compatible dictionary for database insertion."""
    if isinstance(lead_data, LeadRecord):
        payload = lead_data.to_db_dict()
    elif isinstance(lead_data, LeadEvaluation):
        payload = {
            "company_name": lead_data.company_name,
            "website_url": lead_data.website_url,
            "decision_maker_name": lead_data.decision_maker_name or None,
            "decision_maker_title": lead_data.decision_maker_title or None,
            "decision_maker_email": lead_data.decision_maker_email or None,
            "fit_score": lead_data.fit_score,
            "summary": lead_data.summary,
            "pros": lead_data.pros,
            "cons": lead_data.cons,
            "suggested_angle": lead_data.suggested_angle,
            "status": LeadStatus.PENDING_LEAD_REVIEW.value,
        }
    elif isinstance(lead_data, dict):
        payload = dict(lead_data)
        if isinstance(payload.get("status"), LeadStatus):
            payload["status"] = payload["status"].value
        if isinstance(payload.get("id"), UUID):
            payload["id"] = str(payload["id"])
    else:
        raise TypeError(f"Unsupported lead data type: {type(lead_data)}")

    return payload


async def create_lead(
    lead_data: LeadEvaluation | LeadRecord | dict[str, Any],
    client: AsyncClient | None = None,
) -> dict[str, Any]:
    """Insert a new lead record into the database with PENDING_LEAD_REVIEW status.

    Args:
        lead_data: Lead details as LeadEvaluation, LeadRecord, or dictionary.
        client: Optional AsyncClient instance. Uses shared client if omitted.

    Returns:
        dict: The created lead record from the database.
    """
    sb = client or await get_supabase_client()
    payload = _prepare_lead_payload(lead_data)

    logger.info("Inserting lead for '%s' (%s)", payload.get("company_name"), payload.get("website_url"))
    response = await sb.table(TABLE_LEADS).insert(payload).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return payload


async def upsert_lead(
    lead_data: LeadEvaluation | LeadRecord | dict[str, Any],
    on_conflict: str = "website_url",
    client: AsyncClient | None = None,
) -> dict[str, Any]:
    """Upsert a lead record keyed by website_url or conflict column.

    Args:
        lead_data: Lead data payload or model.
        on_conflict: Conflict target column name (default 'website_url').
        client: Optional AsyncClient instance.

    Returns:
        dict: The upserted lead record.
    """
    sb = client or await get_supabase_client()
    payload = _prepare_lead_payload(lead_data)

    logger.info("Upserting lead for '%s' on conflict '%s'", payload.get("website_url"), on_conflict)
    response = await sb.table(TABLE_LEADS).upsert(payload, on_conflict=on_conflict).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return payload


async def get_lead_by_id(
    lead_id: str | UUID,
    client: AsyncClient | None = None,
) -> dict[str, Any] | None:
    """Retrieve a lead by its unique primary key ID.

    Args:
        lead_id: Lead UUID as string or UUID object.
        client: Optional AsyncClient instance.

    Returns:
        dict or None: Found record or None if not found.
    """
    sb = client or await get_supabase_client()
    response = await sb.table(TABLE_LEADS).select("*").eq("id", str(lead_id)).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None


async def get_lead_by_url(
    website_url: str,
    client: AsyncClient | None = None,
) -> dict[str, Any] | None:
    """Retrieve a lead by its canonical website URL to check for duplicates.

    Args:
        website_url: Target website URL.
        client: Optional AsyncClient instance.

    Returns:
        dict or None: Existing record or None.
    """
    sb = client or await get_supabase_client()
    response = await sb.table(TABLE_LEADS).select("*").eq("website_url", website_url).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None


async def get_leads_by_status(
    status: LeadStatus | str,
    limit: int = 50,
    client: AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Retrieve leads matching a specific lifecycle status, ordered chronologically.

    Args:
        status: LeadStatus enum value or string.
        limit: Maximum number of rows to retrieve.
        client: Optional AsyncClient instance.

    Returns:
        list[dict]: List of matching lead records.
    """
    sb = client or await get_supabase_client()
    status_val = status.value if isinstance(status, LeadStatus) else str(status)

    response = (
        await sb.table(TABLE_LEADS)
        .select("*")
        .eq("status", status_val)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    return response.data or []


async def update_lead_status(
    lead_id: str | UUID,
    status: LeadStatus | str,
    client: AsyncClient | None = None,
) -> dict[str, Any] | None:
    """Update the status and timestamp of a lead.

    Args:
        lead_id: Lead UUID.
        status: Target new LeadStatus.
        client: Optional AsyncClient instance.

    Returns:
        dict or None: The updated record or None.
    """
    status_val = status.value if isinstance(status, LeadStatus) else str(status)
    return await update_lead(
        lead_id=lead_id,
        update_data={"status": status_val},
        client=client,
    )


async def update_lead_draft(
    lead_id: str | UUID,
    draft: EmailDraft | dict[str, str],
    status: LeadStatus | str = LeadStatus.DRAFT_GENERATED,
    client: AsyncClient | None = None,
) -> dict[str, Any] | None:
    """Attach generated email copy and update status to DRAFT_GENERATED (or custom).

    Args:
        lead_id: Lead UUID.
        draft: Generated subject and body (EmailDraft or dict).
        status: Target status after draft generation.
        client: Optional AsyncClient instance.

    Returns:
        dict or None: Updated lead record.
    """
    status_val = status.value if isinstance(status, LeadStatus) else str(status)
    if isinstance(draft, EmailDraft):
        subject = draft.subject
        body = draft.body
    else:
        subject = draft.get("subject", "")
        body = draft.get("body", "")

    return await update_lead(
        lead_id=lead_id,
        update_data={
            "email_subject": subject,
            "email_body": body,
            "status": status_val,
        },
        client=client,
    )


async def update_lead_telegram_msg(
    lead_id: str | UUID,
    telegram_message_id: int,
    client: AsyncClient | None = None,
) -> dict[str, Any] | None:
    """Save Telegram message ID linked to this lead for interactive button callbacks.

    Args:
        lead_id: Lead UUID.
        telegram_message_id: Telegram message ID.
        client: Optional AsyncClient instance.

    Returns:
        dict or None: Updated record.
    """
    return await update_lead(
        lead_id=lead_id,
        update_data={"telegram_message_id": telegram_message_id},
        client=client,
    )


async def update_lead(
    lead_id: str | UUID,
    update_data: dict[str, Any],
    client: AsyncClient | None = None,
) -> dict[str, Any] | None:
    """Apply arbitrary field updates to a lead record, updating the updated_at timestamp.

    Args:
        lead_id: Lead UUID.
        update_data: Dictionary of columns to update.
        client: Optional AsyncClient instance.

    Returns:
        dict or None: Updated lead record or None if not found.
    """
    sb = client or await get_supabase_client()
    payload = dict(update_data)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()

    if isinstance(payload.get("status"), LeadStatus):
        payload["status"] = payload["status"].value

    response = await sb.table(TABLE_LEADS).update(payload).eq("id", str(lead_id)).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None


async def delete_lead(
    lead_id: str | UUID,
    client: AsyncClient | None = None,
) -> bool:
    """Delete a lead record from the database.

    Args:
        lead_id: Lead UUID.
        client: Optional AsyncClient instance.

    Returns:
        bool: True if operation completed.
    """
    sb = client or await get_supabase_client()
    response = await sb.table(TABLE_LEADS).delete().eq("id", str(lead_id)).execute()
    return bool(response.data is not None)
