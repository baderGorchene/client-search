"""Tests for Pydantic validation schemas, database client, and lead queries."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from config.settings import settings
from database.client import get_supabase_client, reset_supabase_client
from database.queries import (
    create_lead,
    delete_lead,
    get_lead_by_id,
    get_lead_by_url,
    get_leads_by_status,
    update_lead_draft,
    update_lead_status,
    update_lead_telegram_msg,
    upsert_lead,
)
from evaluators.schemas import EmailDraft, LeadEvaluation, LeadRecord, LeadStatus

# ==========================================
# Schema Tests
# ==========================================


def test_lead_evaluation_valid():
    """Verify that a valid LeadEvaluation is correctly parsed and validated."""
    evaluation = LeadEvaluation(
        company_name="Acme Logistics",
        website_url="https://acmelogistics.com",
        decision_maker_name="John Doe",
        decision_maker_title="Head of Operations",
        decision_maker_email="j.doe@acmelogistics.com",
        fit_score=9,
        summary="High-volume freight forwarding company dealing with manual invoice paperwork.",
        pros=["Manual paperwork bottleneck", "Growing freight team"],
        cons=["Uses legacy on-premise ERP"],
        suggested_angle="Automate bill of lading and invoice extraction to save 20 hours/week.",
    )
    assert evaluation.company_name == "Acme Logistics"
    assert evaluation.fit_score == 9
    assert len(evaluation.pros) == 2
    assert len(evaluation.cons) == 1


def test_lead_evaluation_fit_score_boundaries():
    """Verify that fit_score must be between 1 and 10."""
    with pytest.raises(ValidationError):
        LeadEvaluation(
            company_name="Invalid Score",
            website_url="https://example.com",
            fit_score=0,  # Below minimum
            summary="Summary",
            pros=[],
            cons=[],
            suggested_angle="Angle",
        )

    with pytest.raises(ValidationError):
        LeadEvaluation(
            company_name="Invalid Score",
            website_url="https://example.com",
            fit_score=11,  # Above maximum
            summary="Summary",
            pros=[],
            cons=[],
            suggested_angle="Angle",
        )


def test_lead_evaluation_max_items_and_lengths():
    """Verify max length constraints on summary, pros, cons, suggested angle."""
    with pytest.raises(ValidationError):
        LeadEvaluation(
            company_name="Acme",
            website_url="https://example.com",
            fit_score=8,
            summary="x" * 251,  # Exceeds max 250
            pros=["pro1"],
            cons=["con1"],
            suggested_angle="angle",
        )

    with pytest.raises(ValidationError):
        LeadEvaluation(
            company_name="Acme",
            website_url="https://example.com",
            fit_score=8,
            summary="summary",
            pros=["1", "2", "3", "4"],  # Exceeds max 3
            cons=["1"],
            suggested_angle="angle",
        )


def test_email_draft_schema():
    """Verify EmailDraft validation and constraints."""
    draft = EmailDraft(
        subject="quick question about freight ops",
        body="Saw you're scaling routes across the midwest. Are manual waybills slowing down your dispatchers? We build OCR pipelines that extract invoice data directly into your TMS in seconds.",
    )
    assert draft.subject == "quick question about freight ops"
    assert len(draft.body) <= 600

    with pytest.raises(ValidationError):
        EmailDraft(
            subject="x" * 51,  # Exceeds max 50
            body="body",
        )

    with pytest.raises(ValidationError):
        EmailDraft(
            subject="subject",
            body="x" * 601,  # Exceeds max 600
        )


def test_lead_record_defaults():
    """Verify LeadRecord defaults and DB serialization."""
    record = LeadRecord(
        company_name="Freight Tech",
        website_url="https://freighttech.io",
    )
    assert record.status == LeadStatus.PENDING_LEAD_REVIEW
    assert record.fit_score is None

    db_dict = record.to_db_dict()
    assert db_dict["company_name"] == "Freight Tech"
    assert db_dict["status"] == "PENDING_LEAD_REVIEW"


# ==========================================
# Database Client Tests
# ==========================================


@pytest.mark.asyncio
async def test_get_supabase_client_success(monkeypatch):
    """Verify Supabase async client initialization and caching."""
    await reset_supabase_client()
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_KEY", "test-secret-key")

    client1 = await get_supabase_client()
    client2 = await get_supabase_client()

    assert client1 is client2  # Cached singleton
    await reset_supabase_client()


@pytest.mark.asyncio
async def test_get_supabase_client_missing_credentials(monkeypatch):
    """Verify ValueError when Supabase credentials are missing."""
    await reset_supabase_client()
    monkeypatch.setattr(settings, "SUPABASE_URL", "")
    monkeypatch.setattr(settings, "SUPABASE_KEY", "")

    with pytest.raises(ValueError, match="Supabase credentials not found"):
        await get_supabase_client()


# ==========================================
# Database Queries Tests (Mocked)
# ==========================================


class MockPostgrestBuilder:
    """Mock helper for fluent Supabase/Postgrest async calls."""

    def __init__(self, return_data=None):
        self.return_data = return_data if return_data is not None else []
        self._last_op = None
        self._last_payload = None

    def insert(self, payload):
        self._last_op = "insert"
        self._last_payload = payload
        return self

    def upsert(self, payload, on_conflict=None):
        self._last_op = "upsert"
        self._last_payload = payload
        return self

    def select(self, *args, **kwargs):
        self._last_op = "select"
        return self

    def update(self, payload):
        self._last_op = "update"
        self._last_payload = payload
        return self

    def delete(self):
        self._last_op = "delete"
        return self

    def eq(self, column, value):
        return self

    def order(self, column, desc=False):
        return self

    def limit(self, count):
        return self

    async def execute(self):
        res = MagicMock()
        res.data = self.return_data
        return res


def create_mock_supabase(return_data=None):
    """Create a mock AsyncClient with MockPostgrestBuilder."""
    client = MagicMock()
    builder = MockPostgrestBuilder(return_data=return_data)
    client.table.return_value = builder
    return client, builder


@pytest.mark.asyncio
async def test_create_lead_with_evaluation():
    """Verify lead creation with LeadEvaluation."""
    eval_model = LeadEvaluation(
        company_name="Speedy Freight",
        website_url="https://speedyfreight.com",
        fit_score=8,
        summary="Logistics dispatch company",
        pros=["High paper volume"],
        cons=["Small IT team"],
        suggested_angle="Automate route dispatch",
    )
    fake_id = str(uuid4())
    mock_client, builder = create_mock_supabase([
        {"id": fake_id, "company_name": "Speedy Freight", "status": "PENDING_LEAD_REVIEW"}
    ])

    result = await create_lead(eval_model, client=mock_client)

    assert result["id"] == fake_id
    assert result["company_name"] == "Speedy Freight"
    mock_client.table.assert_called_with("leads")
    assert builder._last_payload["company_name"] == "Speedy Freight"
    assert builder._last_payload["status"] == "PENDING_LEAD_REVIEW"


@pytest.mark.asyncio
async def test_upsert_lead():
    """Verify upserting lead with on_conflict."""
    mock_client, builder = create_mock_supabase([
        {"id": "123", "website_url": "https://speedyfreight.com"}
    ])
    payload = {"company_name": "Speedy", "website_url": "https://speedyfreight.com"}

    result = await upsert_lead(payload, on_conflict="website_url", client=mock_client)

    assert result["id"] == "123"
    assert builder._last_op == "upsert"


@pytest.mark.asyncio
async def test_get_lead_by_id_and_url():
    """Verify retrieval by ID and by URL."""
    fake_lead = {"id": "lead-123", "website_url": "https://test.com", "company_name": "Test"}
    mock_client, _ = create_mock_supabase([fake_lead])

    found_by_id = await get_lead_by_id("lead-123", client=mock_client)
    assert found_by_id == fake_lead

    found_by_url = await get_lead_by_url("https://test.com", client=mock_client)
    assert found_by_url == fake_lead


@pytest.mark.asyncio
async def test_get_lead_not_found():
    """Verify None return when lead is not found."""
    mock_client, _ = create_mock_supabase([])

    result = await get_lead_by_id("missing-id", client=mock_client)
    assert result is None


@pytest.mark.asyncio
async def test_get_leads_by_status():
    """Verify retrieval of leads filtered by LeadStatus."""
    leads = [
        {"id": "1", "status": "PENDING_LEAD_REVIEW"},
        {"id": "2", "status": "PENDING_LEAD_REVIEW"},
    ]
    mock_client, _ = create_mock_supabase(leads)

    results = await get_leads_by_status(LeadStatus.PENDING_LEAD_REVIEW, limit=10, client=mock_client)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_update_lead_status():
    """Verify updating status of an existing lead."""
    mock_client, builder = create_mock_supabase([
        {"id": "lead-1", "status": "LEAD_REJECTED"}
    ])

    res = await update_lead_status("lead-1", LeadStatus.LEAD_REJECTED, client=mock_client)
    assert res["status"] == "LEAD_REJECTED"
    assert builder._last_payload["status"] == "LEAD_REJECTED"
    assert "updated_at" in builder._last_payload


@pytest.mark.asyncio
async def test_update_lead_draft():
    """Verify attaching email draft to lead."""
    draft = EmailDraft(
        subject="automated paperwork inquiry",
        body="Hi team, loved your route expansion. We build automated invoice parsers for logistics teams.",
    )
    mock_client, builder = create_mock_supabase([
        {"id": "lead-1", "email_subject": draft.subject, "status": "DRAFT_GENERATED"}
    ])

    res = await update_lead_draft("lead-1", draft, client=mock_client)
    assert res["status"] == "DRAFT_GENERATED"
    assert builder._last_payload["email_subject"] == draft.subject
    assert builder._last_payload["email_body"] == draft.body
    assert builder._last_payload["status"] == "DRAFT_GENERATED"


@pytest.mark.asyncio
async def test_update_lead_telegram_msg():
    """Verify updating telegram_message_id on a lead."""
    mock_client, builder = create_mock_supabase([
        {"id": "lead-1", "telegram_message_id": 998877}
    ])

    res = await update_lead_telegram_msg("lead-1", 998877, client=mock_client)
    assert res["telegram_message_id"] == 998877
    assert builder._last_payload["telegram_message_id"] == 998877


@pytest.mark.asyncio
async def test_delete_lead():
    """Verify deleting a lead."""
    mock_client, builder = create_mock_supabase([{"id": "lead-1"}])

    success = await delete_lead("lead-1", client=mock_client)
    assert success is True
    assert builder._last_op == "delete"
