"""Reflex reactive state and business logic event handlers."""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

import reflex as rx

from config.settings import settings
from database.client import get_supabase_client
from database.queries import (
    TABLE_LEADS,
    get_lead_by_id,
    update_lead,
    update_lead_draft,
    update_lead_status,
)
from dispatch.gmail_sender import dispatch_approved_lead, get_daily_sent_count
from evaluators.llm_service import generate_email_draft
from evaluators.schemas import LeadEvaluation, LeadStatus
from scheduler import run_scouting_pipeline

logger = logging.getLogger("ui.state")


class AppState(rx.State):
    """Primary reactive state manager for the client scouting dashboard."""

    # Data Collections
    leads: list[dict[str, Any]] = []  # noqa: RUF012
    daily_sent_count: int = 0
    daily_cap: int = settings.DAILY_EMAIL_CAP

    # UI Loading & Status Flags
    is_loading: bool = False
    is_scouting: bool = False
    status_message: str = ""
    active_tab: str = "kanban"

    # Search & Filtering
    search_query: str = ""
    selected_status_filter: str = "ALL"

    # Scouting Trigger Form
    scout_vertical: str = "logistics"
    scout_location: str = "Chicago, IL"
    scout_limit: int = 5
    scout_min_score: int = settings.MIN_LEAD_FIT_SCORE

    # Modal Draft Editing State
    is_edit_modal_open: bool = False
    selected_lead_id: str = ""
    selected_company_name: str = ""
    selected_recipient_email: str = ""
    editing_subject: str = ""
    editing_body: str = ""

    # --------------------------------------------------------------------------
    # Computed Properties (Vars)
    # --------------------------------------------------------------------------

    @rx.var
    def total_leads_count(self) -> int:
        return len(self.leads)

    @rx.var
    def pending_gate1_leads(self) -> list[dict[str, Any]]:
        return [l for l in self.leads if l.get("status") == LeadStatus.PENDING_LEAD_REVIEW.value]

    @rx.var
    def pending_gate2_leads(self) -> list[dict[str, Any]]:
        return [l for l in self.leads if l.get("status") == LeadStatus.DRAFT_GENERATED.value]

    @rx.var
    def dispatched_leads(self) -> list[dict[str, Any]]:
        return [
            l for l in self.leads
            if l.get("status") in (
                LeadStatus.EMAIL_SENT.value,
                LeadStatus.REPLIED_INTERESTED.value,
                LeadStatus.REPLIED_NOT_INTERESTED.value,
            )
        ]

    @rx.var
    def discarded_leads(self) -> list[dict[str, Any]]:
        return [
            l for l in self.leads
            if l.get("status") in (LeadStatus.LEAD_REJECTED.value, LeadStatus.DRAFT_REJECTED.value)
        ]

    @rx.var
    def status_counts(self) -> dict[str, int]:
        counts = Counter(l.get("status", "UNKNOWN") for l in self.leads)
        return {
            "pending_gate1": counts.get(LeadStatus.PENDING_LEAD_REVIEW.value, 0),
            "pending_gate2": counts.get(LeadStatus.DRAFT_GENERATED.value, 0),
            "sent": counts.get(LeadStatus.EMAIL_SENT.value, 0),
            "interested": counts.get(LeadStatus.REPLIED_INTERESTED.value, 0),
            "rejected": counts.get(LeadStatus.LEAD_REJECTED.value, 0) + counts.get(LeadStatus.DRAFT_REJECTED.value, 0),
        }

    @rx.var
    def filtered_leads(self) -> list[dict[str, Any]]:
        results = self.leads
        if self.selected_status_filter != "ALL":
            results = [l for l in results if l.get("status") == self.selected_status_filter]

        if self.search_query.strip():
            q = self.search_query.lower()
            results = [
                l for l in results
                if q in str(l.get("company_name", "")).lower()
                or q in str(l.get("website_url", "")).lower()
                or q in str(l.get("decision_maker_email", "")).lower()
                or q in str(l.get("summary", "")).lower()
            ]
        return results

    # --------------------------------------------------------------------------
    # Event Handlers
    # --------------------------------------------------------------------------

    async def fetch_leads(self) -> None:
        """Fetch all leads from Supabase and calculate active metrics."""
        self.is_loading = True
        try:
            sb = await get_supabase_client()
            response = await sb.table(TABLE_LEADS).select("*").order("created_at", desc=True).execute()
            self.leads = response.data or []
            self.daily_sent_count = await get_daily_sent_count()
        except Exception as exc:
            logger.exception("Failed to fetch leads from Supabase")
            self.status_message = f"Error fetching data: {exc}"
        finally:
            self.is_loading = False

    async def approve_lead(self, lead_id: str) -> None:
        """Approve Gate 1: Generate AI cold pitch draft and transition to DRAFT_GENERATED."""
        self.is_loading = True
        try:
            lead = await get_lead_by_id(lead_id)
            if not lead:
                self.status_message = "Lead not found"
                return

            # Generate cold pitch copy if not already generated
            subject = lead.get("email_subject")
            body = lead.get("email_body")
            if not subject or not body:
                eval_obj = LeadEvaluation(
                    company_name=lead["company_name"],
                    website_url=lead["website_url"],
                    decision_maker_name=lead.get("decision_maker_name") or "Operations Lead",
                    decision_maker_title=lead.get("decision_maker_title") or "Leadership",
                    decision_maker_email=lead.get("decision_maker_email") or "",
                    fit_score=lead.get("fit_score", 8),
                    summary=lead.get("summary", ""),
                    pros=lead.get("pros") or [],
                    cons=lead.get("cons") or [],
                    suggested_angle=lead.get("suggested_angle", "Workflow automation"),
                )
                draft = await generate_email_draft(eval_obj)
                subject = draft.subject
                body = draft.body

            await update_lead_draft(lead_id=lead_id, email_subject=subject, email_body=body)
            await update_lead_status(lead_id, LeadStatus.DRAFT_GENERATED)
            self.status_message = f"Approved lead '{lead.get('company_name')}'. Draft generated for Gate 2."
            await self.fetch_leads()
        except Exception as exc:
            logger.exception("Failed to approve lead")
            self.status_message = f"Approval failed: {exc}"
        finally:
            self.is_loading = False

    async def discard_lead(self, lead_id: str) -> None:
        """Discard Gate 1 lead: transition to LEAD_REJECTED."""
        try:
            await update_lead_status(lead_id, LeadStatus.LEAD_REJECTED)
            self.status_message = "Lead discarded."
            await self.fetch_leads()
        except Exception as exc:
            logger.exception("Failed to discard lead")
            self.status_message = f"Discard failed: {exc}"

    async def send_draft(self, lead_id: str) -> None:
        """Approve Gate 2: Dispatch email via Gmail API and mark EMAIL_SENT."""
        self.is_loading = True
        try:
            res = await dispatch_approved_lead(lead_id=lead_id, apply_jitter=False)
            self.status_message = f"Dispatched email to {res.get('to_email')} ({res.get('company_name')})."
            await self.fetch_leads()
        except Exception as exc:
            logger.exception("Failed to dispatch draft")
            self.status_message = f"Dispatch failed: {exc}"
        finally:
            self.is_loading = False

    async def cancel_draft(self, lead_id: str) -> None:
        """Cancel Gate 2 draft: transition to DRAFT_REJECTED."""
        try:
            await update_lead_status(lead_id, LeadStatus.DRAFT_REJECTED)
            self.status_message = "Draft cancelled."
            await self.fetch_leads()
        except Exception as exc:
            logger.exception("Failed to cancel draft")
            self.status_message = f"Cancellation failed: {exc}"

    def open_edit_modal(self, lead: dict[str, Any]) -> None:
        """Open the draft copy editor modal."""
        self.selected_lead_id = str(lead.get("id", ""))
        self.selected_company_name = str(lead.get("company_name", ""))
        self.selected_recipient_email = str(lead.get("decision_maker_email", ""))
        self.editing_subject = str(lead.get("email_subject", ""))
        self.editing_body = str(lead.get("email_body", ""))
        self.is_edit_modal_open = True

    def close_edit_modal(self) -> None:
        """Close the draft copy editor modal."""
        self.is_edit_modal_open = False

    async def save_edited_draft(self) -> None:
        """Save edited email subject and body to database."""
        if not self.selected_lead_id:
            return
        try:
            await update_lead(
                self.selected_lead_id,
                email_subject=self.editing_subject,
                email_body=self.editing_body,
                status=LeadStatus.DRAFT_GENERATED.value,
            )
            self.is_edit_modal_open = False
            self.status_message = "Draft updated successfully."
            await self.fetch_leads()
        except Exception as exc:
            logger.exception("Failed to save edited draft")
            self.status_message = f"Save failed: {exc}"

    async def trigger_scouting(self) -> None:
        """Execute a one-shot prospect scouting cycle from the web dashboard."""
        self.is_scouting = True
        self.status_message = f"Running discovery for {self.scout_vertical} in {self.scout_location}..."
        try:
            stats = await run_scouting_pipeline(
                verticals=[self.scout_vertical],
                locations=[self.scout_location],
                max_prospects_per_vertical=self.scout_limit,
                min_fit_score=self.scout_min_score,
                push_to_telegram=True,
            )
            self.status_message = (
                f"Scouting complete: Found {stats.get('discovered', 0)}, "
                f"Qualified {stats.get('qualified', 0)} new prospects."
            )
            await self.fetch_leads()
        except Exception as exc:
            logger.exception("Scouting execution failed")
            self.status_message = f"Scouting failed: {exc}"
        finally:
            self.is_scouting = False

    def set_active_tab(self, tab_name: str) -> None:
        self.active_tab = tab_name

    def clear_status_message(self) -> None:
        self.status_message = ""

    def set_search_query(self, value: str) -> None:
        self.search_query = value

    def set_selected_status_filter(self, value: str) -> None:
        self.selected_status_filter = value

    def set_scout_vertical(self, value: str) -> None:
        self.scout_vertical = value

    def set_scout_location(self, value: str) -> None:
        self.scout_location = value

    def set_scout_limit(self, value: int) -> None:
        self.scout_limit = value

    def set_editing_subject(self, value: str) -> None:
        self.editing_subject = value

    def set_editing_body(self, value: str) -> None:
        self.editing_body = value

