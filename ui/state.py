"""Reflex reactive state and business logic event handlers."""

from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any

import reflex as rx
from loguru import logger
from pydantic import BaseModel, Field

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


class PipelineNode(BaseModel):
    """Structured Pydantic schema representing a single scouting stage node."""

    id: str
    step_num: int
    title: str
    subtitle: str
    status: str = "pending"  # "pending", "active", "completed", "error"
    completed_time: str = ""
    logs: list[str] = Field(default_factory=list)


def get_initial_pipeline_nodes() -> list[PipelineNode]:
    """Return clean list of 6 pipeline nodes in deactivated/pending state."""
    return [
        PipelineNode(
            id="1",
            step_num=1,
            title="Discovery & Geo Search",
            subtitle="DuckDuckGo & Overpass Geo API",
            status="pending",
            completed_time="",
            logs=[],
        ),
        PipelineNode(
            id="2",
            step_num=2,
            title="Deduplication & Cache",
            subtitle="Supabase URL & Domain Check",
            status="pending",
            completed_time="",
            logs=[],
        ),
        PipelineNode(
            id="3",
            step_num=3,
            title="Web Extraction & Markdown",
            subtitle="Crawl4AI & Playwright Chromium SPA",
            status="pending",
            completed_time="",
            logs=[],
        ),
        PipelineNode(
            id="4",
            step_num=4,
            title="Contact Verification Gate",
            subtitle="Async DNS MX & Raw SMTP Sockets",
            status="pending",
            completed_time="",
            logs=[],
        ),
        PipelineNode(
            id="5",
            step_num=5,
            title="LLM Reasoning & Fit Scoring",
            subtitle="Gemini 3.5 Flash ICP Bottleneck Analysis",
            status="pending",
            completed_time="",
            logs=[],
        ),
        PipelineNode(
            id="6",
            step_num=6,
            title="Mobile HITL Notification",
            subtitle="Telegram Gate 1 Inline Review Card",
            status="pending",
            completed_time="",
            logs=[],
        ),
    ]


def _process_node_log_update(nodes: list[PipelineNode], msg: str) -> list[PipelineNode]:
    """Assign incoming log line to active node and advance node lifecycle states."""
    import datetime

    current_time_str = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    updated = [n.model_copy(deep=True) for n in nodes]

    step_target: int | None = None
    if "[Step 1/6]" in msg or ("Searching" in msg and "prospects" in msg):
        step_target = 1
    elif "[Step 2/6]" in msg or "Checking deduplication" in msg:
        step_target = 2
    elif "[Step 3/6]" in msg or "Crawling" in msg:
        step_target = 3
    elif "[Step 4/6]" in msg or "Verifying deliverable" in msg:
        step_target = 4
    elif "[Step 5/6]" in msg or "Evaluating" in msg:
        step_target = 5
    elif "[Step 6/6]" in msg or "Pushing Gate 1" in msg:
        step_target = 6
    elif "[FINISH]" in msg or "Scouting cycle complete" in msg or "complete" in msg.lower():
        for n in updated:
            if n.status in ("active", "pending"):
                n.status = "completed"
                if not n.completed_time:
                    n.completed_time = current_time_str
        return updated

    if step_target is not None:
        for n in updated:
            if n.step_num < step_target:
                if n.status != "completed":
                    n.status = "completed"
                    if not n.completed_time:
                        n.completed_time = current_time_str
            elif n.step_num == step_target:
                n.status = "active"
                n.logs.append(msg)
            else:
                if n.status != "completed":
                    n.status = "pending"
    else:
        active_found = False
        for n in updated:
            if n.status == "active":
                n.logs.append(msg)
                active_found = True
                break
        if not active_found and updated:
            updated[0].status = "active"
            updated[0].logs.append(msg)

    return updated


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
    active_lead_action_id: str = ""
    current_step_description: str = ""
    execution_logs: list[str] = []  # noqa: RUF012
    pipeline_nodes: list[PipelineNode] = get_initial_pipeline_nodes()

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
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to fetch leads from Supabase")
            self.status_message = f"Error fetching data: {exc}"
        finally:
            self.is_loading = False

    async def approve_lead(self, lead_id: str) -> None:
        """Approve Gate 1: Generate AI cold pitch draft and transition to DRAFT_GENERATED."""
        self.is_loading = True
        self.active_lead_action_id = lead_id
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
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to approve lead")
            self.status_message = f"Approval failed: {exc}"
        finally:
            self.is_loading = False
            self.active_lead_action_id = ""

    async def discard_lead(self, lead_id: str) -> None:
        """Discard Gate 1 lead: transition to LEAD_REJECTED."""
        self.active_lead_action_id = lead_id
        try:
            await update_lead_status(lead_id, LeadStatus.LEAD_REJECTED)
            self.status_message = "Lead discarded."
            await self.fetch_leads()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to discard lead")
            self.status_message = f"Discard failed: {exc}"
        finally:
            self.active_lead_action_id = ""

    async def send_draft(self, lead_id: str) -> None:
        """Approve Gate 2: Dispatch email via Gmail API and mark EMAIL_SENT."""
        self.is_loading = True
        self.active_lead_action_id = lead_id
        try:
            res = await dispatch_approved_lead(lead_id=lead_id, apply_jitter=False)
            self.status_message = f"Dispatched email to {res.get('to_email')} ({res.get('company_name')})."
            await self.fetch_leads()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to dispatch draft")
            self.status_message = f"Dispatch failed: {exc}"
        finally:
            self.is_loading = False
            self.active_lead_action_id = ""

    async def cancel_draft(self, lead_id: str) -> None:
        """Cancel Gate 2 draft: transition to DRAFT_REJECTED."""
        self.active_lead_action_id = lead_id
        try:
            await update_lead_status(lead_id, LeadStatus.DRAFT_REJECTED)
            self.status_message = "Draft cancelled."
            await self.fetch_leads()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to cancel draft")
            self.status_message = f"Cancellation failed: {exc}"
        finally:
            self.active_lead_action_id = ""

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
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to save edited draft")
            self.status_message = f"Save failed: {exc}"

    async def trigger_scouting(self):  # type: ignore[no-untyped-def]
        """Execute a one-shot prospect scouting cycle with real-time log streaming."""
        self.is_scouting = True
        self.pipeline_nodes = get_initial_pipeline_nodes()
        self.execution_logs = ["🚀 [INIT] Starting background scouting cycle..."]
        self.current_step_description = "Starting scouting cycle..."
        self.status_message = f"Running discovery for {self.scout_vertical} in {self.scout_location}..."
        yield

        queue: asyncio.Queue[str] = asyncio.Queue()

        async def _on_progress(msg: str) -> None:
            await queue.put(msg)

        task = asyncio.create_task(
            run_scouting_pipeline(
                verticals=[self.scout_vertical],
                locations=[self.scout_location],
                max_prospects_per_vertical=self.scout_limit,
                min_fit_score=self.scout_min_score,
                push_to_telegram=True,
                progress_callback=_on_progress,
            )
        )

        while not task.done() or not queue.empty():
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=0.1)
                self.execution_logs.append(msg)
                self.current_step_description = msg
                self.pipeline_nodes = _process_node_log_update(self.pipeline_nodes, msg)
                yield
            except TimeoutError:
                yield

        try:
            stats = task.result()
            self.status_message = (
                f"Scouting complete: Found {stats.get('discovered', 0)}, "
                f"Qualified {stats.get('qualified', 0)} new prospects."
            )
            self.pipeline_nodes = _process_node_log_update(self.pipeline_nodes, "[FINISH] Complete")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Scouting execution failed")
            self.status_message = f"Scouting failed: {exc}"
            self.execution_logs.append(f"❌ Execution error: {exc}")
            err_nodes = [n.model_copy(deep=True) for n in self.pipeline_nodes]
            for n in err_nodes:
                if n.status == "active":
                    n.status = "error"
                    n.logs = list(n.logs) + [f"❌ Execution error: {exc}"]
            self.pipeline_nodes = err_nodes
        finally:
            self.is_scouting = False

        yield
        await self.fetch_leads()

    def reset_pipeline_nodes(self) -> None:
        """Reset all nodes back to initial deactivated pending state."""
        self.pipeline_nodes = get_initial_pipeline_nodes()
        self.execution_logs = []
        self.current_step_description = ""

    def clear_execution_logs(self) -> None:
        """Clear execution log history and reset nodes."""
        self.reset_pipeline_nodes()

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

