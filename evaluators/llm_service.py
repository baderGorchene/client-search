"""LLM intelligence and copywriting router with Gemini primary and Groq fallback."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

import litellm
from pydantic import BaseModel

from config.settings import settings
from evaluators.schemas import EmailDraft, LeadEvaluation

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Default model identifiers for LiteLLM routing
DEFAULT_PRIMARY_MODEL = "gemini/gemini-3.5-flash"
DEFAULT_FALLBACK_MODEL = "groq/llama-3.3-70b-versatile"

# System prompts
LEAD_EVALUATION_SYSTEM_PROMPT = """You are a Principal AI Automation Consultant and B2B Prospect Evaluator.
Your goal is to evaluate candidate businesses against our Ideal Customer Profile (ICP) for productized AI and workflow automation services.

### Core Offer:
High-value productized workflow automation ($0 infrastructure cost architectures):
1. Unstructured Invoice, Waybill & Paperwork OCR Extraction Pipelines (eliminating manual ERP/spreadsheet entry).
2. Real-Time Inbound Booking & Customer Triage Agents (voice/chat booking agents handling high ticket volumes).
3. Custom Operations Dashboards & Cross-Platform Inventory Synchronization.

### Target Verticals:
- Logistics, Freight & Trucking SMBs: High daily volume of bills of lading, customs manifests, dispatching overhead.
- Real Estate & Property Management: Repetitive tenant maintenance tickets, scheduling friction, lead follow-up.
- Boutique Agencies & E-commerce ($500k–$3M ARR): High order volume, manual supplier reconciliation, customer support triage.

### Disqualified Targets:
- Solo micro-businesses or single freelancers.
- Local kiosks, restaurants, or businesses without meaningful digital operations or paperwork flow.
- Companies without clear operational bottlenecks.

### Evaluation Requirements:
Analyze the provided website content and return a strict JSON object matching the requested schema:
- company_name: Official business name.
- website_url: Official website URL.
- decision_maker_name: Full name of owner, founder, CEO, or operations executive if identified in the text (or empty string).
- decision_maker_title: Identified title/role (e.g., "Founder & CEO", "VP Operations", or empty string).
- decision_maker_email: Verified direct or corporate email if identified (or empty string).
- fit_score: Integer from 1 to 10 (1-6: Low fit/disqualified, 7-8: Solid candidate, 9-10: High-priority immediate bottleneck).
- summary: High-level summary of what the company does and their business model (maximum 250 characters).
- pros: 1 to 3 bullet points identifying specific operational workflows or bottlenecks that can be automated (max 3 items).
- cons: 1 to 3 friction points, risk factors, or reasons they may not buy (max 3 items).
- suggested_angle: A specific, personalized 1-sentence value proposition hook addressing their biggest bottleneck (maximum 150 characters).

Always output strictly valid JSON conforming to the schema with no additional commentary."""

EMAIL_DRAFTING_SYSTEM_PROMPT = """You are an elite B2B Cold Email Copywriter specializing in productized AI & workflow automation.
Your goal is to write a highly personalized, compelling, zero-fluff cold outreach email based on the prospect's evaluated bottlenecks.

### Strict Cold Email Rules:
1. Exactly 3 sentences in the body:
   - Sentence 1 (Observation): Acknowledge a specific operational bottleneck or workflow unique to their business (derived from the lead's pros and suggested angle).
   - Sentence 2 (Value Proposition): Explain how a custom automation pipeline (e.g. automated waybill/invoice OCR or instant triage) solves that exact bottleneck without changing their current software stack.
   - Sentence 3 (Low-Friction CTA): Propose a low-commitment next step (e.g., "Open to seeing a 2-minute video of how this works?", "Worth a quick 5-minute chat this Thursday?").
2. No generic filler (e.g., "I hope this email finds you well", "I came across your website", "In today's fast-paced world").
3. Subject line must be short, punchy, lowercase, and relevant (maximum 50 characters, e.g., "quick question re waybills", "operations at apex freight").
4. Output strictly valid JSON matching the EmailDraft schema:
   - subject: short lowercase subject line (max 50 chars)
   - body: 3-sentence personalized body (max 600 chars)

Always output strictly valid JSON conforming to the schema with no additional commentary."""


def clean_json_response(content: str) -> str:
    """Extract and sanitize raw JSON string from LLM output, stripping markdown code fences."""
    if not content or not content.strip():
        return "{}"
    text = content.strip()
    # Strip markdown code blocks (```json ... ``` or ``` ...)
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # If text is enclosed in extra quotes or has leading/trailing characters
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    return text or "{}"


async def call_llm_with_fallback(
    messages: list[dict[str, str]],
    response_schema: type[T],
    primary_model: str = DEFAULT_PRIMARY_MODEL,
    fallback_model: str = DEFAULT_FALLBACK_MODEL,
    temperature: float = 0.2,
    max_tokens: int = 1200,
) -> T:
    """Execute LLM completion with automatic primary model failure detection and Groq fallback.

    Args:
        messages: OpenAI-format chat messages list.
        response_schema: Target Pydantic model class for structured output validation.
        primary_model: Primary model identifier (default Gemini 3.7 Flash).
        fallback_model: Fallback model identifier (default Groq Llama 3.3 70B).
        temperature: Sampling temperature.
        max_tokens: Maximum tokens to generate.

    Returns:
        Validated Pydantic model instance of type T.

    Raises:
        RuntimeError: If both primary and fallback LLM completions fail.
    """
    # 1. Attempt Primary Model (Gemini)
    primary_error: Exception | None = None
    try:
        logger.info(f"Calling primary LLM model: {primary_model}")
        response = await litellm.acompletion(
            model=primary_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.GEMINI_API_KEY or None,
            response_format={"type": "json_object"},
        )
        raw_content = response.choices[0].message.content or ""
        cleaned = clean_json_response(raw_content)
        parsed_data = json.loads(cleaned)
        return response_schema.model_validate(parsed_data)

    except Exception as exc:  # noqa: BLE001
        primary_error = exc
        logger.warning(
            f"Primary LLM ({primary_model}) failed: {exc}. Attempting fallback to {fallback_model}..."
        )

    # 2. Attempt Fallback Model (Groq Llama 3.3)
    try:
        logger.info(f"Calling fallback LLM model: {fallback_model}")
        response = await litellm.acompletion(
            model=fallback_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.GROQ_API_KEY or None,
            response_format={"type": "json_object"},
        )
        raw_content = response.choices[0].message.content or ""
        cleaned = clean_json_response(raw_content)
        parsed_data = json.loads(cleaned)
        return response_schema.model_validate(parsed_data)

    except Exception as fallback_exc:
        error_details = (
            f"All LLM routing attempts failed.\n"
            f"Primary ({primary_model}) error: {primary_error}\n"
            f"Fallback ({fallback_model}) error: {fallback_exc}"
        )
        logger.error(error_details)
        raise RuntimeError(error_details) from fallback_exc


async def evaluate_lead(
    markdown_content: str,
    company_name: str = "",
    website_url: str = "",
    discovered_contacts: dict[str, Any] | None = None,
    decision_maker_name: str | None = None,
    decision_maker_title: str | None = None,
    decision_maker_email: str | None = None,
    primary_model: str = DEFAULT_PRIMARY_MODEL,
    fallback_model: str = DEFAULT_FALLBACK_MODEL,
) -> LeadEvaluation:
    """Analyze prospect website markdown and produce a structured LeadEvaluation.

    Args:
        markdown_content: Scraped, cleaned website markdown text.
        company_name: Inferred company name (optional).
        website_url: Prospect website URL (optional).
        discovered_contacts: Metadata of discovered emails, phones, and social links.
        decision_maker_name: Known decision maker name (optional).
        decision_maker_title: Known decision maker title (optional).
        decision_maker_email: Resolved email address (optional).
        primary_model: Model name for primary inference.
        fallback_model: Model name for fallback inference.

    Returns:
        LeadEvaluation instance with ICP fit scoring, pros, cons, and suggested pitch hook.
    """
    contacts_dict = dict(discovered_contacts or {})
    if decision_maker_name:
        contacts_dict["decision_maker_name"] = decision_maker_name
    if decision_maker_title:
        contacts_dict["decision_maker_title"] = decision_maker_title
    if decision_maker_email:
        contacts_dict["decision_maker_email"] = decision_maker_email

    contacts_context = ""
    if contacts_dict:
        contacts_context = f"\n### Discovered Contact Information:\n{json.dumps(contacts_dict, indent=2)}\n"

    user_prompt = f"""Evaluate this target prospect for AI workflow automation services:

Company Name: {company_name or "Unknown"}
Website URL: {website_url or "Unknown"}
{contacts_context}
### Website Content (Markdown):
{markdown_content[:6000]}

Provide the evaluation in valid JSON matching the schema."""

    messages = [
        {"role": "system", "content": LEAD_EVALUATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    evaluation = await call_llm_with_fallback(
        messages=messages,
        response_schema=LeadEvaluation,
        primary_model=primary_model,
        fallback_model=fallback_model,
        temperature=0.1,
    )

    # Sanitize and ensure company name, URL, and verified contact details are preserved
    if company_name and not evaluation.company_name:
        evaluation.company_name = company_name
    if website_url and not evaluation.website_url:
        evaluation.website_url = website_url
    if decision_maker_name and not evaluation.decision_maker_name:
        evaluation.decision_maker_name = decision_maker_name
    if decision_maker_title and not evaluation.decision_maker_title:
        evaluation.decision_maker_title = decision_maker_title
    if decision_maker_email and not evaluation.decision_maker_email:
        evaluation.decision_maker_email = decision_maker_email

    return evaluation


async def generate_email_draft(
    lead: LeadEvaluation | dict[str, Any],
    sender_name: str = "Bader",
    offer_description: str | None = None,
    primary_model: str = DEFAULT_PRIMARY_MODEL,
    fallback_model: str = DEFAULT_FALLBACK_MODEL,
) -> EmailDraft:
    """Generate a personalized, 3-sentence value-driven cold email draft for an approved lead.

    Args:
        lead: LeadEvaluation instance or dictionary containing lead analysis.
        sender_name: Name of the sender for the pitch signature.
        offer_description: Optional custom offer focus.
        primary_model: Model name for primary inference.
        fallback_model: Model name for fallback inference.

    Returns:
        EmailDraft instance with punchy subject line and 3-sentence body.
    """
    if isinstance(lead, LeadEvaluation):
        lead_dict = lead.model_dump()
    else:
        lead_dict = dict(lead)

    company_name = lead_dict.get("company_name", "your team")
    decision_maker = lead_dict.get("decision_maker_name", "")
    summary = lead_dict.get("summary", "")
    pros = lead_dict.get("pros", [])
    suggested_angle = lead_dict.get("suggested_angle", "")

    user_prompt = f"""Generate a 3-sentence cold outreach email for this qualified prospect:

Target Company: {company_name}
Decision Maker: {decision_maker or "Founder / Operations Lead"}
Company Operations: {summary}
Identified Automation Bottlenecks (Pros):
{json.dumps(pros, indent=2)}
Suggested Angle: {suggested_angle}
Sender Name: {sender_name}
Custom Offer Context: {offer_description or "Custom AI workflow & invoice/waybill automation"}

Provide the email in valid JSON matching the schema."""

    messages = [
        {"role": "system", "content": EMAIL_DRAFTING_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    return await call_llm_with_fallback(
        messages=messages,
        response_schema=EmailDraft,
        primary_model=primary_model,
        fallback_model=fallback_model,
        temperature=0.3,
    )
