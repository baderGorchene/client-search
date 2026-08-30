"""Email resolution and zero-cost verification module."""

from verification.email_verifier import (
    EmailVerificationResult,
    batch_verify_emails,
    check_catch_all_domain,
    clean_email,
    extract_domain,
    generate_email_permutations,
    generate_permutations_for_name,
    generate_role_emails,
    is_disposable_domain,
    is_role_based_email,
    parse_name_components,
    resolve_lead_email,
    resolve_mx_records,
    verify_email,
)

__all__ = [
    "EmailVerificationResult",
    "batch_verify_emails",
    "check_catch_all_domain",
    "clean_email",
    "extract_domain",
    "generate_email_permutations",
    "generate_permutations_for_name",
    "generate_role_emails",
    "is_disposable_domain",
    "is_role_based_email",
    "parse_name_components",
    "resolve_lead_email",
    "resolve_mx_records",
    "verify_email",
]
