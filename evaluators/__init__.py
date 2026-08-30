"""Evaluators module for schemas and LLM routing."""

from evaluators.llm_service import (
    DEFAULT_FALLBACK_MODEL,
    DEFAULT_PRIMARY_MODEL,
    call_llm_with_fallback,
    clean_json_response,
    evaluate_lead,
    generate_email_draft,
)
from evaluators.schemas import (
    EmailDraft,
    LeadEvaluation,
    LeadRecord,
    LeadStatus,
)

__all__ = [
    "DEFAULT_FALLBACK_MODEL",
    "DEFAULT_PRIMARY_MODEL",
    "EmailDraft",
    "LeadEvaluation",
    "LeadRecord",
    "LeadStatus",
    "call_llm_with_fallback",
    "clean_json_response",
    "evaluate_lead",
    "generate_email_draft",
]
