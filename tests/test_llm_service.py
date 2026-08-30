"""Unit and integration tests for LiteLLM intelligence and copywriting router."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from evaluators.llm_service import (
    DEFAULT_FALLBACK_MODEL,
    DEFAULT_PRIMARY_MODEL,
    clean_json_response,
    evaluate_lead,
    generate_email_draft,
)
from evaluators.schemas import EmailDraft, LeadEvaluation


def create_mock_litellm_response(content: str) -> MagicMock:
    """Create a mock LiteLLM response object with message content."""
    mock_resp = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_resp.choices = [mock_choice]
    return mock_resp


# ==============================================================================
# JSON Sanitization Tests
# ==============================================================================

def test_clean_json_response_raw():
    raw = '{"company_name": "Apex Freight", "fit_score": 9}'
    assert clean_json_response(raw) == raw


def test_clean_json_response_markdown_fences():
    fenced = """```json
{
  "company_name": "Apex Freight",
  "fit_score": 9
}
```"""
    cleaned = clean_json_response(fenced)
    parsed = json.loads(cleaned)
    assert parsed["company_name"] == "Apex Freight"
    assert parsed["fit_score"] == 9


def test_clean_json_response_generic_fences():
    fenced = """```
{
  "subject": "quick question re waybills",
  "body": "Hi John..."
}
```"""
    cleaned = clean_json_response(fenced)
    parsed = json.loads(cleaned)
    assert parsed["subject"] == "quick question re waybills"


def test_clean_json_response_surrounding_text():
    dirty = 'Here is your evaluation result:\n{"company_name": "Test Co", "fit_score": 8}\nLet me know if you need changes.'
    cleaned = clean_json_response(dirty)
    parsed = json.loads(cleaned)
    assert parsed["company_name"] == "Test Co"


def test_clean_json_response_empty():
    assert clean_json_response("") == "{}"
    assert clean_json_response("   ") == "{}"


# ==============================================================================
# Lead Evaluation Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_evaluate_lead_primary_success(mocker):
    mock_eval_data = {
        "company_name": "Apex Freight Logistics",
        "website_url": "https://apexfreight.com",
        "decision_maker_name": "John Doe",
        "decision_maker_title": "Founder & Managing Director",
        "decision_maker_email": "john.doe@apexfreight.com",
        "fit_score": 9,
        "summary": "Regional freight forwarding SMB managing high daily waybill volumes.",
        "pros": [
            "Manual waybill and customs paperwork entry bottlenecks",
            "High daily shipment status email inquiries",
        ],
        "cons": [
            "May use legacy on-premise dispatching software",
        ],
        "suggested_angle": "Automate waybill ingestion directly into their dispatch ERP in real time.",
    }

    mock_acompletion = mocker.patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        return_value=create_mock_litellm_response(json.dumps(mock_eval_data)),
    )

    markdown = "# Apex Freight\nWe process 500+ waybills daily across the Midwest."
    result = await evaluate_lead(
        markdown_content=markdown,
        company_name="Apex Freight Logistics",
        website_url="https://apexfreight.com",
        discovered_contacts={"emails": ["john.doe@apexfreight.com"]},
    )

    assert isinstance(result, LeadEvaluation)
    assert result.company_name == "Apex Freight Logistics"
    assert result.fit_score == 9
    assert len(result.pros) == 2
    assert len(result.cons) == 1
    assert result.decision_maker_name == "John Doe"

    mock_acompletion.assert_called_once()
    call_kwargs = mock_acompletion.call_args[1]
    assert call_kwargs["model"] == DEFAULT_PRIMARY_MODEL


@pytest.mark.asyncio
async def test_evaluate_lead_fallback_success(mocker):
    mock_eval_data = {
        "company_name": "Swift Haulage",
        "website_url": "https://swifthaul.com",
        "decision_maker_name": "Sarah Connor",
        "decision_maker_title": "Operations Lead",
        "decision_maker_email": "sarah@swifthaul.com",
        "fit_score": 8,
        "summary": "Trucking company with manual booking friction.",
        "pros": ["Repetitive dispatch phone calls"],
        "cons": ["Small fleet size"],
        "suggested_angle": "Implement automated inbound load dispatch agent.",
    }

    # Primary fails with API error, Fallback succeeds
    mock_acompletion = mocker.patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        side_effect=[
            Exception("Gemini API 429 Rate limit exceeded"),
            create_mock_litellm_response(json.dumps(mock_eval_data)),
        ],
    )

    result = await evaluate_lead(
        markdown_content="Fast regional haulage across Texas.",
        company_name="Swift Haulage",
        website_url="https://swifthaul.com",
    )

    assert isinstance(result, LeadEvaluation)
    assert result.company_name == "Swift Haulage"
    assert result.fit_score == 8
    assert mock_acompletion.call_count == 2

    first_call_model = mock_acompletion.call_args_list[0][1]["model"]
    second_call_model = mock_acompletion.call_args_list[1][1]["model"]
    assert first_call_model == DEFAULT_PRIMARY_MODEL
    assert second_call_model == DEFAULT_FALLBACK_MODEL


@pytest.mark.asyncio
async def test_evaluate_lead_all_fail(mocker):
    mocker.patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        side_effect=[
            Exception("Gemini connection error"),
            Exception("Groq server error"),
        ],
    )

    with pytest.raises(RuntimeError, match="All LLM routing attempts failed"):
        await evaluate_lead(
            markdown_content="Some website text",
            company_name="Fail Co",
            website_url="https://fail.com",
        )


# ==============================================================================
# Cold Email Copywriting Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_generate_email_draft_primary_success(mocker):
    mock_draft_data = {
        "subject": "quick question re waybill bottlenecks",
        "body": "Noticed Apex Freight is processing hundreds of regional waybills daily. We built a zero-cost OCR pipeline that extracts waybill data into your ERP in 3 seconds. Open to seeing a 2-minute video on how this works for your team?",
    }

    mock_acompletion = mocker.patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        return_value=create_mock_litellm_response(json.dumps(mock_draft_data)),
    )

    lead = LeadEvaluation(
        company_name="Apex Freight",
        website_url="https://apexfreight.com",
        decision_maker_name="John Doe",
        decision_maker_title="Managing Director",
        decision_maker_email="john@apexfreight.com",
        fit_score=9,
        summary="Freight forwarding company with high paperwork load.",
        pros=["Waybill extraction bottlenecks", "Manual dispatch overhead"],
        cons=["Legacy software"],
        suggested_angle="Automate waybill ingestion directly into dispatch ERP.",
    )

    draft = await generate_email_draft(lead=lead, sender_name="Bader")

    assert isinstance(draft, EmailDraft)
    assert draft.subject == "quick question re waybill bottlenecks"
    assert "Apex Freight" in draft.body
    assert len(draft.subject) <= 50
    assert len(draft.body) <= 600

    mock_acompletion.assert_called_once()
    assert mock_acompletion.call_args[1]["model"] == DEFAULT_PRIMARY_MODEL


@pytest.mark.asyncio
async def test_generate_email_draft_dict_input_fallback(mocker):
    mock_draft_data = {
        "subject": "operations at urban properties",
        "body": "Saw Urban Properties handles 300+ tenant maintenance requests across Chicago. We set up automated triage agents that qualify and dispatch work orders without manual review. Worth a quick 5-minute chat this Thursday?",
    }

    mock_acompletion = mocker.patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        side_effect=[
            Exception("Gemini quota exhausted"),
            create_mock_litellm_response(json.dumps(mock_draft_data)),
        ],
    )

    lead_dict = {
        "company_name": "Urban Properties",
        "decision_maker_name": "Sarah Miller",
        "summary": "Property management company in Chicago.",
        "pros": ["Repetitive tenant maintenance tickets"],
        "suggested_angle": "Automated ticket triage and vendor dispatch.",
    }

    draft = await generate_email_draft(lead=lead_dict, sender_name="Bader")

    assert isinstance(draft, EmailDraft)
    assert draft.subject == "operations at urban properties"
    assert "Urban Properties" in draft.body
    assert mock_acompletion.call_count == 2
    assert mock_acompletion.call_args_list[1][1]["model"] == DEFAULT_FALLBACK_MODEL


@pytest.mark.asyncio
async def test_generate_email_draft_all_fail(mocker):
    mocker.patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        side_effect=[
            Exception("Gemini timeout"),
            Exception("Groq timeout"),
        ],
    )

    with pytest.raises(RuntimeError, match="All LLM routing attempts failed"):
        await generate_email_draft(
            lead={"company_name": "Crash Co"},
            sender_name="Bader",
        )
