"""End-to-end and integration tests for scouting pipeline, scheduler, and CLI lifecycle."""

from __future__ import annotations

import argparse
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from discovery.crawler import ExtractedLeadContent
from discovery.searcher import DiscoveredProspect, ICPVertical
from evaluators.schemas import LeadEvaluation
from main import build_parser, cmd_dispatch, cmd_scout, cmd_status
from scheduler import create_scheduler, run_scouting_pipeline
from verification import EmailVerificationResult

# ==============================================================================
# End-to-End Scouting Pipeline Integration Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_run_scouting_pipeline_full_e2e(mocker):
    # 1. Mock Searcher
    mock_prospect = DiscoveredProspect(
        company_name="Apex Freight Solutions",
        website_url="https://apexfreightsolutions.com",
        snippet="Freight forwarding logistics company in Chicago",
        source="duckduckgo",
    )
    mocker.patch(
        "scheduler.discover_prospects",
        new_callable=AsyncMock,
        return_value=[mock_prospect],
    )

    # 2. Mock Deduplication Check (No existing lead)
    mocker.patch("scheduler.get_lead_by_url", new_callable=AsyncMock, return_value=None)

    # 3. Mock Web Extraction
    mock_crawl = ExtractedLeadContent(
        url="https://apexfreightsolutions.com",
        markdown="# Apex Freight\nWe handle logistics, freight forwarding, and waybills.",
        company_name="Apex Freight Solutions",
        page_title="Apex Freight Solutions",
        emails_found=["ops@apexfreightsolutions.com"],
        phones_found=["+13125550199"],
    )
    mocker.patch("scheduler.extract_lead_content", new_callable=AsyncMock, return_value=mock_crawl)

    # 4. Mock Email Resolver
    mock_resolution = EmailVerificationResult(
        email="john.doe@apexfreightsolutions.com",
        is_valid=True,
        confidence_score=0.9,
    )
    mocker.patch(
        "scheduler.resolve_lead_email",
        new_callable=AsyncMock,
        return_value=("john.doe@apexfreightsolutions.com", mock_resolution),
    )

    # 5. Mock LLM Evaluation
    mock_eval = LeadEvaluation(
        company_name="Apex Freight Solutions",
        website_url="https://apexfreightsolutions.com",
        decision_maker_name="John Doe",
        decision_maker_title="Managing Director",
        decision_maker_email="john.doe@apexfreightsolutions.com",
        fit_score=9,
        summary="High-volume freight operations with paperwork bottlenecks.",
        pros=["Waybill extraction automation", "Manual dispatch overhead"],
        cons=["Legacy TMS software"],
        suggested_angle="Automate waybill ingestion into dispatch ERP in real time.",
    )
    mocker.patch("scheduler.evaluate_lead", new_callable=AsyncMock, return_value=mock_eval)

    # 6. Mock Database Upsert
    lead_id = str(uuid4())
    mocker.patch(
        "scheduler.upsert_lead",
        new_callable=AsyncMock,
        return_value={"id": lead_id, "status": "PENDING_LEAD_REVIEW"},
    )

    # 7. Mock Telegram Push
    mock_push = mocker.patch("scheduler.send_lead_review_card", new_callable=AsyncMock, return_value=777)

    # Execute pipeline
    stats = await run_scouting_pipeline(
        verticals=[ICPVertical.LOGISTICS],
        locations=["Chicago, IL"],
        max_prospects_per_vertical=1,
        min_fit_score=7,
        push_to_telegram=True,
        chat_id="123456789",
    )

    assert stats["discovered"] == 1
    assert stats["processed"] == 1
    assert stats["qualified"] == 1
    assert stats["pushed"] == 1
    assert stats["skipped_duplicate"] == 0
    mock_push.assert_called_once()


@pytest.mark.asyncio
async def test_run_scouting_pipeline_duplicate_skip(mocker):
    mock_prospect = DiscoveredProspect(
        company_name="Apex Freight Solutions",
        website_url="https://apexfreightsolutions.com",
        snippet="Snippet",
        source="duckduckgo",
    )
    mocker.patch("scheduler.discover_prospects", new_callable=AsyncMock, return_value=[mock_prospect])
    # Duplicate lead found in database
    mocker.patch("scheduler.get_lead_by_url", new_callable=AsyncMock, return_value={"id": "existing-uuid"})

    mock_crawl = mocker.patch("scheduler.extract_lead_content", new_callable=AsyncMock)

    stats = await run_scouting_pipeline(
        verticals=[ICPVertical.LOGISTICS],
        locations=["Chicago, IL"],
    )

    assert stats["discovered"] == 1
    assert stats["processed"] == 0
    assert stats["skipped_duplicate"] == 1
    mock_crawl.assert_not_called()


@pytest.mark.asyncio
async def test_run_scouting_pipeline_disqualified_score(mocker):
    mock_prospect = DiscoveredProspect(
        company_name="Generic Site",
        website_url="https://generic.com",
        snippet="Snippet",
        source="duckduckgo",
    )
    mocker.patch("scheduler.discover_prospects", new_callable=AsyncMock, return_value=[mock_prospect])
    mocker.patch("scheduler.get_lead_by_url", new_callable=AsyncMock, return_value=None)
    mocker.patch(
        "scheduler.extract_lead_content",
        new_callable=AsyncMock,
        return_value=ExtractedLeadContent(url="https://generic.com", markdown="Sample text", company_name="Generic"),
    )
    mocker.patch(
        "scheduler.resolve_lead_email",
        new_callable=AsyncMock,
        return_value=(None, None),
    )
    # Low fit score
    mocker.patch(
        "scheduler.evaluate_lead",
        new_callable=AsyncMock,
        return_value=LeadEvaluation(
            company_name="Generic",
            website_url="https://generic.com",
            fit_score=3,  # Below threshold
            summary="Low automation potential",
            pros=[],
            cons=[],
            suggested_angle="None",
        ),
    )

    mock_upsert = mocker.patch("scheduler.upsert_lead", new_callable=AsyncMock)
    mock_push = mocker.patch("scheduler.send_lead_review_card", new_callable=AsyncMock)

    stats = await run_scouting_pipeline(
        verticals=[ICPVertical.LOGISTICS],
        locations=["Chicago, IL"],
        min_fit_score=7,
    )

    assert stats["discovered"] == 1
    assert stats["processed"] == 1
    assert stats["qualified"] == 0
    assert stats["pushed"] == 0
    mock_upsert.assert_not_called()
    mock_push.assert_not_called()


# ==============================================================================
# Scheduler Tests
# ==============================================================================

def test_create_scheduler():
    scheduler = create_scheduler(interval_hours=6, run_on_start=False)
    assert scheduler is not None
    job = scheduler.get_job("scouting_pipeline_job")
    assert job is not None
    assert job.name == "Periodic ICP Client Discovery & Evaluation Pipeline"


# ==============================================================================
# CLI Commands Tests
# ==============================================================================

def test_build_parser():
    parser = build_parser()

    # Test run subcommand
    args_run = parser.parse_args(["run", "--interval", "2", "--scout-now"])
    assert args_run.command == "run"
    assert args_run.interval == 2
    assert args_run.scout_now is True

    # Test scout subcommand
    args_scout = parser.parse_args(["scout", "--vertical", "logistics", "--limit", "5", "--min-score", "8"])
    assert args_scout.command == "scout"
    assert args_scout.vertical == "logistics"
    assert args_scout.limit == 5
    assert args_scout.min_score == 8

    # Test dispatch subcommand
    args_dispatch = parser.parse_args(["dispatch", "--lead-id", "test-uuid-123", "--jitter"])
    assert args_dispatch.command == "dispatch"
    assert args_dispatch.lead_id == "test-uuid-123"
    assert args_dispatch.jitter is True


@pytest.mark.asyncio
async def test_cmd_scout(mocker, capsys):
    mocker.patch(
        "main.run_scouting_pipeline",
        new_callable=AsyncMock,
        return_value={"discovered": 5, "processed": 4, "qualified": 2, "pushed": 2, "skipped_duplicate": 1},
    )

    args = argparse.Namespace(
        vertical="logistics",
        location="Dallas, TX",
        limit=3,
        min_score=8,
        no_telegram=False,
    )

    await cmd_scout(args)
    captured = capsys.readouterr().out
    assert "Scouting Cycle Complete" in captured
    assert "Discovered candidates: 5" in captured
    assert "Qualified (Score >= 8): 2" in captured


@pytest.mark.asyncio
async def test_cmd_status(mocker, capsys):
    mock_sb = MagicMock()
    mock_exec = AsyncMock()
    mock_exec.return_value = MagicMock(data=[
        {"status": "PENDING_LEAD_REVIEW"},
        {"status": "DRAFT_GENERATED"},
        {"status": "EMAIL_SENT"},
    ])
    mock_table = MagicMock()
    mock_table.select.return_value.execute = mock_exec
    mock_sb.table.return_value = mock_table

    mocker.patch("main.get_supabase_client", new_callable=AsyncMock, return_value=mock_sb)

    args = argparse.Namespace()
    await cmd_status(args)

    captured = capsys.readouterr().out
    assert "Pipeline Status Overview" in captured
    assert "Total Discovered Records: 3" in captured
    assert "Pending Gate 1 Review: 1" in captured
    assert "Pending Gate 2 Review: 1" in captured
    assert "Emails Dispatched:     1" in captured


@pytest.mark.asyncio
async def test_cmd_dispatch(mocker, capsys):
    mock_leads = [{"id": "lead-1", "company_name": "Apex"}]
    mocker.patch("main.get_leads_by_status", new_callable=AsyncMock, return_value=mock_leads)
    mocker.patch(
        "main.dispatch_approved_lead",
        new_callable=AsyncMock,
        return_value={"to_email": "ops@apex.com", "company_name": "Apex"},
    )

    args = argparse.Namespace(lead_id=None, limit=5, jitter=False)
    await cmd_dispatch(args)

    captured = capsys.readouterr().out
    assert "Dispatching outreach for 1 approved lead(s)" in captured
    assert "Dispatched to ops@apex.com (Company: Apex)" in captured
