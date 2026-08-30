"""Unit and integration tests for Reflex Web UI and reactive AppState."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from evaluators.schemas import EmailDraft, LeadStatus
from ui.components.execution_logs import execution_logs_console
from ui.components.kanban import kanban_board
from ui.components.modals import edit_draft_modal
from ui.components.navbar import navbar
from ui.components.stat_cards import stat_cards
from ui.pages.dashboard import dashboard_page
from ui.pages.leads import leads_page
from ui.pages.settings_page import settings_page
from ui.state import AppState
from ui.ui import index


@pytest.fixture(autouse=True)
def mock_supabase_and_sent_count(mocker):
    """Automatically mock database client and sent counts for all UI tests."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_order = MagicMock()
    mock_order.execute = AsyncMock(return_value=MagicMock(data=[]))
    mock_select.order.return_value = mock_order
    mock_table.select.return_value = mock_select
    mock_sb.table.return_value = mock_table

    mocker.patch("ui.state.get_supabase_client", new_callable=AsyncMock, return_value=mock_sb)
    mocker.patch("ui.state.get_daily_sent_count", new_callable=AsyncMock, return_value=0)
    return mock_sb


# ==============================================================================
# State Computed Properties & Filtering Tests
# ==============================================================================

def test_app_state_computed_properties():
    state = AppState()
    id1 = str(uuid4())
    id2 = str(uuid4())
    id3 = str(uuid4())
    id4 = str(uuid4())

    state.leads = [
        {"id": id1, "company_name": "Apex Freight", "status": LeadStatus.PENDING_LEAD_REVIEW.value, "website_url": "https://apex.com", "summary": "Logistics ops"},
        {"id": id2, "company_name": "Prime Logistics", "status": LeadStatus.DRAFT_GENERATED.value, "website_url": "https://prime.com", "summary": "Dispatch"},
        {"id": id3, "company_name": "Swift Haul", "status": LeadStatus.EMAIL_SENT.value, "website_url": "https://swift.com", "summary": "Trucking"},
        {"id": id4, "company_name": "Bad Lead", "status": LeadStatus.LEAD_REJECTED.value, "website_url": "https://bad.com", "summary": "Kiosk"},
    ]

    assert state.total_leads_count == 4
    assert len(state.pending_gate1_leads) == 1
    assert state.pending_gate1_leads[0]["id"] == id1

    assert len(state.pending_gate2_leads) == 1
    assert state.pending_gate2_leads[0]["id"] == id2

    assert len(state.dispatched_leads) == 1
    assert state.dispatched_leads[0]["id"] == id3

    assert len(state.discarded_leads) == 1
    assert state.discarded_leads[0]["id"] == id4

    counts = state.status_counts
    assert counts["pending_gate1"] == 1
    assert counts["pending_gate2"] == 1
    assert counts["sent"] == 1
    assert counts["rejected"] == 1


def test_app_state_filtered_leads():
    state = AppState()
    state.leads = [
        {"id": "1", "company_name": "Alpha Freight", "status": "PENDING_LEAD_REVIEW", "website_url": "https://alpha.com", "decision_maker_email": "ops@alpha.com", "summary": "Waybills"},
        {"id": "2", "company_name": "Beta Realty", "status": "DRAFT_GENERATED", "website_url": "https://beta.com", "decision_maker_email": "info@beta.com", "summary": "Tenants"},
        {"id": "3", "company_name": "Gamma Boutique", "status": "EMAIL_SENT", "website_url": "https://gamma.com", "decision_maker_email": "hello@gamma.com", "summary": "Shopify"},
    ]

    # No filter
    assert len(state.filtered_leads) == 3

    # Status filter
    state.selected_status_filter = "PENDING_LEAD_REVIEW"
    assert len(state.filtered_leads) == 1
    assert state.filtered_leads[0]["company_name"] == "Alpha Freight"

    # Search filter
    state.selected_status_filter = "ALL"
    state.search_query = "Realty"
    assert len(state.filtered_leads) == 1
    assert state.filtered_leads[0]["company_name"] == "Beta Realty"

    # Search by email
    state.search_query = "hello@"
    assert len(state.filtered_leads) == 1
    assert state.filtered_leads[0]["company_name"] == "Gamma Boutique"


# ==============================================================================
# Async State Event Handler Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_app_state_fetch_leads(mocker):
    state = AppState()
    mock_leads_data = [
        {"id": "100", "company_name": "Test Freight", "status": "PENDING_LEAD_REVIEW"},
    ]

    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_order = MagicMock()
    mock_order.execute = AsyncMock(return_value=MagicMock(data=mock_leads_data))
    mock_select.order.return_value = mock_order
    mock_table.select.return_value = mock_select
    mock_sb.table.return_value = mock_table

    mocker.patch("ui.state.get_supabase_client", new_callable=AsyncMock, return_value=mock_sb)
    mocker.patch("ui.state.get_daily_sent_count", new_callable=AsyncMock, return_value=3)

    await state.fetch_leads()

    assert state.leads == mock_leads_data
    assert state.daily_sent_count == 3
    assert state.is_loading is False


@pytest.mark.asyncio
async def test_app_state_approve_lead(mocker):
    state = AppState()
    lead_id = str(uuid4())

    mock_lead = {
        "id": lead_id,
        "company_name": "Apex Logistics",
        "website_url": "https://apexlogistics.com",
        "decision_maker_name": "John Doe",
        "decision_maker_title": "Operations Director",
        "decision_maker_email": "john@apexlogistics.com",
        "fit_score": 9,
        "summary": "Freight forwarding company",
        "pros": ["Manual waybill processing"],
        "cons": ["Legacy systems"],
        "suggested_angle": "Automate waybill entry",
        "email_subject": None,
        "email_body": None,
    }

    mocker.patch("ui.state.get_lead_by_id", new_callable=AsyncMock, return_value=mock_lead)
    mocker.patch(
        "ui.state.generate_email_draft",
        new_callable=AsyncMock,
        return_value=EmailDraft(subject="waybill workflow", body="Hi John, quick question."),
    )
    mock_update_draft = mocker.patch("ui.state.update_lead_draft", new_callable=AsyncMock)
    mock_update_status = mocker.patch("ui.state.update_lead_status", new_callable=AsyncMock)

    await state.approve_lead(lead_id)

    mock_update_draft.assert_called_once_with(
        lead_id=lead_id,
        email_subject="waybill workflow",
        email_body="Hi John, quick question.",
    )
    mock_update_status.assert_called_once_with(lead_id, LeadStatus.DRAFT_GENERATED)


@pytest.mark.asyncio
async def test_app_state_discard_lead(mocker):
    state = AppState()
    lead_id = str(uuid4())

    mock_update_status = mocker.patch("ui.state.update_lead_status", new_callable=AsyncMock)

    await state.discard_lead(lead_id)

    mock_update_status.assert_called_once_with(lead_id, LeadStatus.LEAD_REJECTED)


@pytest.mark.asyncio
async def test_app_state_send_draft(mocker):
    state = AppState()
    lead_id = str(uuid4())

    mock_dispatch = mocker.patch(
        "ui.state.dispatch_approved_lead",
        new_callable=AsyncMock,
        return_value={"to_email": "john@apex.com", "company_name": "Apex"},
    )

    await state.send_draft(lead_id)

    mock_dispatch.assert_called_once_with(lead_id=lead_id, apply_jitter=False)


@pytest.mark.asyncio
async def test_app_state_cancel_draft(mocker):
    state = AppState()
    lead_id = str(uuid4())

    mock_update_status = mocker.patch("ui.state.update_lead_status", new_callable=AsyncMock)

    await state.cancel_draft(lead_id)

    mock_update_status.assert_called_once_with(lead_id, LeadStatus.DRAFT_REJECTED)


def test_app_state_edit_modal_lifecycle():
    state = AppState()
    lead = {
        "id": "123",
        "company_name": "Acme Corp",
        "decision_maker_email": "ceo@acme.com",
        "email_subject": "Initial subject",
        "email_body": "Initial body",
    }

    state.open_edit_modal(lead)
    assert state.is_edit_modal_open is True
    assert state.selected_lead_id == "123"
    assert state.selected_company_name == "Acme Corp"
    assert state.selected_recipient_email == "ceo@acme.com"
    assert state.editing_subject == "Initial subject"
    assert state.editing_body == "Initial body"

    state.close_edit_modal()
    assert state.is_edit_modal_open is False


@pytest.mark.asyncio
async def test_app_state_save_edited_draft(mocker):
    state = AppState()
    state.selected_lead_id = "123"
    state.editing_subject = "Updated subject"
    state.editing_body = "Updated body text"
    state.is_edit_modal_open = True

    mock_update = mocker.patch("ui.state.update_lead", new_callable=AsyncMock)

    await state.save_edited_draft()

    mock_update.assert_called_once_with(
        "123",
        email_subject="Updated subject",
        email_body="Updated body text",
        status=LeadStatus.DRAFT_GENERATED.value,
    )
    assert state.is_edit_modal_open is False


@pytest.mark.asyncio
async def test_app_state_trigger_scouting(mocker):
    state = AppState()
    state.scout_vertical = "logistics"
    state.scout_location = "Dallas, TX"
    state.scout_limit = 3
    state.scout_min_score = 7

    mock_pipeline = mocker.patch(
        "ui.state.run_scouting_pipeline",
        new_callable=AsyncMock,
        return_value={"discovered": 5, "qualified": 2},
    )

    async for _ in state.trigger_scouting():
        pass

    mock_pipeline.assert_called_once_with(
        verticals=["logistics"],
        locations=["Dallas, TX"],
        max_prospects_per_vertical=3,
        min_fit_score=7,
        push_to_telegram=True,
        progress_callback=mocker.ANY,
    )
    assert state.is_scouting is False
    assert "Scouting complete" in state.status_message


# ==============================================================================
# UI Component Render Tests
# ==============================================================================

def test_app_state_execution_logs():
    state = AppState()
    assert state.execution_logs == []
    assert state.current_step_description == ""

    state.execution_logs.append("🔍 Step 1: Searching prospects...")
    state.current_step_description = "Step 1"
    assert len(state.execution_logs) == 1

    state.clear_execution_logs()
    assert state.execution_logs == []
    assert state.current_step_description == ""


def test_pipeline_nodes_progression():
    """Verify node lifecycle transitions (pending -> active -> completed) and log binding."""
    from ui.state import _process_node_log_update, get_initial_pipeline_nodes

    nodes = get_initial_pipeline_nodes()
    assert len(nodes) == 6
    # All initially pending (deactivated)
    for n in nodes:
        assert n.status == "pending"
        assert n.completed_time == ""
        assert n.logs == []

    # Step 1 active
    nodes = _process_node_log_update(nodes, "🔍 [Step 1/6] Searching logistics prospects in Chicago...")
    assert nodes[0].status == "active"
    assert len(nodes[0].logs) == 1
    assert nodes[1].status == "pending"

    # Step 2 active -> Step 1 marked completed with timestamp
    nodes = _process_node_log_update(nodes, "🧹 [Step 2/6] Checking deduplication: Apex Freight")
    assert nodes[0].status == "completed"
    assert nodes[0].completed_time != ""
    assert nodes[1].status == "active"
    assert len(nodes[1].logs) == 1

    # Finish cycle -> All active/pending marked completed
    nodes = _process_node_log_update(nodes, "🏁 [FINISH] Scouting cycle complete.")
    for n in nodes:
        assert n.status == "completed"
        assert n.completed_time != ""


def test_app_state_reset_pipeline_nodes():
    state = AppState()
    state.pipeline_nodes[0].status = "completed"
    state.pipeline_nodes[0].completed_time = "12:00:00"
    state.pipeline_nodes[0].logs = ["log 1"]

    state.reset_pipeline_nodes()
    assert len(state.pipeline_nodes) == 6
    for n in state.pipeline_nodes:
        assert n.status == "pending"
        assert n.completed_time == ""
        assert n.logs == []


def test_ui_components_render():
    """Verify all UI components and pages compile into valid Reflex component structures."""
    nav_comp = navbar()
    assert nav_comp is not None

    stats_comp = stat_cards()
    assert stats_comp is not None

    kanban_comp = kanban_board()
    assert kanban_comp is not None

    modal_comp = edit_draft_modal()
    assert modal_comp is not None

    console_comp = execution_logs_console()
    assert console_comp is not None

    dash_comp = dashboard_page()
    assert dash_comp is not None

    leads_comp = leads_page()
    assert leads_comp is not None

    settings_comp = settings_page()
    assert settings_comp is not None

    layout_comp = index()
    assert layout_comp is not None

