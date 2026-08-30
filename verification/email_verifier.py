"""Zero-cost email resolution, permutation generation, DNS MX validation, and direct SMTP verification gate."""

from __future__ import annotations

import asyncio
import re
import secrets
import string
from typing import Any
from urllib.parse import urlparse

import dns.asyncresolver
import dns.exception
import dns.resolver
import validate_email
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from validate_email.exceptions import (
    AddressNotDeliverableError,
    DomainBlacklistedError,
    SMTPCommunicationError,
    SMTPTemporaryError,
    TLSNegotiationError,
)

EMAIL_SYNTAX_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)

DISPOSABLE_DOMAINS: set[str] = {
    "10minutemail.com",
    "10minutemail.net",
    "tempmail.com",
    "temp-mail.org",
    "guerrillamail.com",
    "guerrillamail.net",
    "guerrillamail.org",
    "guerrillamailblock.com",
    "sharklasers.com",
    "grr.la",
    "mailinator.com",
    "trashmail.com",
    "trashmail.net",
    "yopmail.com",
    "yopmail.net",
    "dispostable.com",
    "getairmail.com",
    "throwawaymail.com",
    "maildrop.cc",
    "fakemailgenerator.com",
    "fakeinbox.com",
    "nada.ltd",
    "inboxkitten.com",
    "burnermail.io",
    "crazymailing.com",
    "tempinbox.com",
    "mytemp.email",
    "mohmal.com",
    "emailondeck.com",
}

ROLE_PREFIXES: set[str] = {
    "admin",
    "administrator",
    "billing",
    "careers",
    "contact",
    "contact-us",
    "contactus",
    "customer-service",
    "editor",
    "general",
    "hello",
    "help",
    "hr",
    "info",
    "inquiries",
    "inquiry",
    "jobs",
    "legal",
    "mail",
    "marketing",
    "media",
    "office",
    "press",
    "privacy",
    "sales",
    "security",
    "service",
    "support",
    "team",
    "tech",
    "webmaster",
}

TITLE_PREFIXES: set[str] = {
    "mr",
    "mrs",
    "ms",
    "miss",
    "dr",
    "prof",
    "ceo",
    "cto",
    "cfo",
    "coo",
    "cmo",
    "president",
    "founder",
    "director",
    "manager",
}

TITLE_SUFFIXES: set[str] = {
    "jr",
    "sr",
    "ii",
    "iii",
    "iv",
    "phd",
    "md",
    "esq",
    "mba",
}

_MX_CACHE: dict[str, list[str]] = {}
_CATCH_ALL_CACHE: dict[str, bool] = {}


def _safe_exception_str(exc: BaseException) -> str:
    """Safely format exception message without crashing on invalid internal structures."""
    try:
        msg = str(exc)
        if msg:
            return msg
    except Exception:  # noqa: BLE001, S110
        pass
    args_repr = str(getattr(exc, "args", ""))
    return f"{type(exc).__name__}: {args_repr}" if args_repr else type(exc).__name__


class EmailVerificationResult(BaseModel):
    """Structured result model for multi-stage email validation."""

    email: str = Field(..., description="Target email address validated")
    is_valid: bool = Field(default=False, description="Overall deliverability verdict")
    format_valid: bool = Field(default=False, description="Whether syntax conforms to RFC specs")
    mx_valid: bool = Field(default=False, description="Whether domain has valid routable MX records")
    smtp_valid: bool | None = Field(default=None, description="SMTP mailbox existence handshake status")
    is_catch_all: bool | None = Field(default=None, description="Whether domain is configured as catch-all")
    is_disposable: bool = Field(default=False, description="Whether domain is a known temporary/throwaway provider")
    is_role_account: bool = Field(default=False, description="Whether address is a generic role inbox (e.g. info@)")
    mx_records: list[str] = Field(default_factory=list, description="Resolved mail server hostnames sorted by priority")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Estimated deliverability confidence (0-1)")
    error_message: str | None = Field(default=None, description="Detailed failure or error description")
    details: dict[str, Any] = Field(default_factory=dict, description="Diagnostic metadata from verification checks")

    model_config = ConfigDict(extra="ignore")


def clear_cache() -> None:
    """Clear in-memory DNS MX and catch-all verification caches."""
    _MX_CACHE.clear()
    _CATCH_ALL_CACHE.clear()


def clean_email(email: str) -> str:
    """Strip whitespace, mailto: prefix, and lowercase email address."""
    if not email:
        return ""
    addr = email.strip()
    if addr.lower().startswith("mailto:"):
        addr = addr[7:]
    return addr.split("?")[0].strip().lower()


def extract_domain(url_or_domain: str) -> str:
    """Extract and normalize clean base domain from URL or domain string.

    Examples:
        'https://www.apexfreight.com/contact' -> 'apexfreight.com'
        'http://sub.domain.co.uk:8080/path' -> 'sub.domain.co.uk'
        'company.com' -> 'company.com'
    """
    if not url_or_domain:
        return ""
    target = url_or_domain.strip().lower()
    if not target.startswith(("http://", "https://")):
        target = "https://" + target
    parsed = urlparse(target)
    netloc = parsed.netloc or parsed.path.split("/")[0]
    # Remove port if present
    domain = netloc.split(":")[0]
    # Remove leading 'www.'
    domain = domain.removeprefix("www.")
    return domain.strip()


def is_role_based_email(email: str) -> bool:
    """Check if the local part of an email matches common generic role prefixes."""
    cleaned = clean_email(email)
    if "@" not in cleaned:
        return False
    local_part = cleaned.split("@")[0].lower()
    # Normalize separators (info-us -> info, sales.dept -> sales)
    normalized_local = re.split(r"[-._+]", local_part)[0]
    return local_part in ROLE_PREFIXES or normalized_local in ROLE_PREFIXES


def is_disposable_domain(domain: str) -> bool:
    """Check if the domain is a known temporary or disposable email service."""
    return domain.strip().lower() in DISPOSABLE_DOMAINS


def parse_name_components(full_name: str) -> tuple[str, str]:
    """Parse a full name into sanitized (first_name, last_name) components.

    Strips professional titles (Dr., CEO), punctuation, middle initials, and suffixes.
    """
    if not full_name:
        return ("", "")

    # Clean punctuation and extra spaces
    cleaned = re.sub(r"[,;()\"']", " ", full_name)
    tokens = [t.lower() for t in cleaned.split() if t.strip()]

    # Filter out known prefixes and suffixes
    filtered_tokens: list[str] = []
    for token in tokens:
        stripped = token.rstrip(".")
        if stripped in TITLE_PREFIXES or stripped in TITLE_SUFFIXES:
            continue
        # Filter single letter middle initials if there are at least 3 tokens
        if len(stripped) == 1 and len(tokens) > 2:
            continue
        filtered_tokens.append(stripped)

    if not filtered_tokens:
        return ("", "")
    if len(filtered_tokens) == 1:
        single = re.sub(r"[^a-z0-9]", "", filtered_tokens[0])
        return (single, single)

    first = re.sub(r"[^a-z0-9]", "", filtered_tokens[0])
    last = re.sub(r"[^a-z0-9]", "", filtered_tokens[-1])
    return (first, last)


def generate_email_permutations(first_name: str, last_name: str, domain: str) -> list[str]:
    """Generate ordered list of corporate email permutation patterns for a person and domain."""
    first = re.sub(r"[^a-z0-9]", "", first_name.strip().lower())
    last = re.sub(r"[^a-z0-9]", "", last_name.strip().lower())
    dom = extract_domain(domain)

    if not dom:
        return []

    if not first and not last:
        return generate_role_emails(dom)

    if first and not last:
        return [f"{first}@{dom}"]

    if last and not first:
        return [f"{last}@{dom}"]

    if first == last:
        return [f"{first}@{dom}"]

    f_initial = first[0]
    l_initial = last[0]

    permutations = [
        f"{first}.{last}@{dom}",      # john.doe@domain.com (most common corporate)
        f"{first}@{dom}",             # john@domain.com (common in SMBs/founders)
        f"{first}{last}@{dom}",       # johndoe@domain.com
        f"{f_initial}.{last}@{dom}",  # j.doe@domain.com
        f"{f_initial}{last}@{dom}",   # jdoe@domain.com
        f"{first}_{last}@{dom}",      # john_doe@domain.com
        f"{last}.{first}@{dom}",      # doe.john@domain.com
        f"{first}.{l_initial}@{dom}", # john.d@domain.com
        f"{f_initial}_{last}@{dom}",  # j_doe@domain.com
        f"{last}@{dom}",              # doe@domain.com
    ]

    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for p in permutations:
        if p not in seen:
            seen.add(p)
            deduped.append(p)

    return deduped


def generate_permutations_for_name(full_name: str, domain: str) -> list[str]:
    """Generate corporate permutations directly from a full name and domain."""
    first, last = parse_name_components(full_name)
    return generate_email_permutations(first, last, domain)


def generate_role_emails(domain: str) -> list[str]:
    """Generate high-priority generic role emails for a domain."""
    dom = extract_domain(domain)
    if not dom:
        return []
    priority_roles = ["contact", "info", "hello", "sales", "support", "office", "team"]
    return [f"{role}@{dom}" for role in priority_roles]


async def resolve_mx_records(domain: str, timeout: float = 5.0, use_cache: bool = True) -> list[str]:
    """Resolve DNS MX records for a domain asynchronously, sorted by preference priority.

    Filters out RFC 7505 Null MX records (e.g., target '.') and caches results.
    """
    clean_dom = extract_domain(domain)
    if not clean_dom:
        return []

    if use_cache and clean_dom in _MX_CACHE:
        return list(_MX_CACHE[clean_dom])

    resolver = dns.asyncresolver.Resolver()
    resolver.timeout = timeout
    resolver.lifetime = timeout

    try:
        answers = await resolver.resolve(clean_dom, "MX")
        # Sort answers by preference (lowest number = highest priority)
        sorted_answers = sorted(answers, key=lambda rdata: rdata.preference)
        records: list[str] = []
        for rdata in sorted_answers:
            exchange = str(rdata.exchange).rstrip(".").lower()
            # RFC 7505: exchange "." indicates domain does not accept email
            if exchange and exchange != ".":
                records.append(exchange)

        if use_cache:
            _MX_CACHE[clean_dom] = records
        return records

    except (
        dns.resolver.NXDOMAIN,
        dns.resolver.NoAnswer,
        dns.resolver.NoNameservers,
        dns.exception.Timeout,
        dns.resolver.LifetimeTimeout,
    ) as e:
        logger.debug(f"DNS MX resolution failed for domain {clean_dom}: {e}")
        if use_cache:
            _MX_CACHE[clean_dom] = []
        return []
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Unexpected error resolving MX records for {clean_dom}: {e}")
        if use_cache:
            _MX_CACHE[clean_dom] = []
        return []


def _calculate_confidence_score(
    format_valid: bool,
    mx_valid: bool,
    smtp_valid: bool | None,
    is_catch_all: bool | None,
    is_disposable: bool,
    is_role: bool,
) -> float:
    """Calculate deliverability confidence score between 0.0 and 1.0."""
    if not format_valid or is_disposable or not mx_valid or smtp_valid is False:
        return 0.0

    # Base score for valid format and valid MX
    score = 0.70

    if smtp_valid is True:
        score = 0.95
    elif smtp_valid is None:
        score = 0.65

    if is_catch_all is True:
        score = min(score, 0.65)

    if is_role:
        score = max(0.0, score - 0.10)

    return round(score, 2)


async def check_catch_all_domain(
    domain: str,
    mx_records: list[str] | None = None,
    timeout: float = 10.0,
    use_cache: bool = True,
) -> bool:
    """Check if the domain accepts emails for non-existent random addresses (Catch-All)."""
    clean_dom = extract_domain(domain)
    if not clean_dom:
        return False

    if use_cache and clean_dom in _CATCH_ALL_CACHE:
        return _CATCH_ALL_CACHE[clean_dom]

    if not mx_records:
        mx_records = await resolve_mx_records(clean_dom, timeout=timeout / 2, use_cache=use_cache)

    if not mx_records:
        if use_cache:
            _CATCH_ALL_CACHE[clean_dom] = False
        return False

    # Generate a random 16-character alphanumeric address guaranteed to not exist
    random_str = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(16))
    fake_address = f"probe_catchall_{random_str}@{clean_dom}"

    try:
        # Perform SMTP check in worker thread
        is_accepted = await asyncio.to_thread(
            validate_email.validate_email_or_fail,
            fake_address,
            check_format=True,
            check_blacklist=False,
            check_dns=False,
            check_smtp=True,
            smtp_timeout=timeout,
        )
        catch_all = bool(is_accepted)
    except AddressNotDeliverableError:
        # Mailbox was rejected -> domain is NOT catch-all
        catch_all = False
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Catch-all probe inconclusive for {clean_dom}: {_safe_exception_str(e)}")
        catch_all = False

    if use_cache:
        _CATCH_ALL_CACHE[clean_dom] = catch_all
    return catch_all


async def verify_email(
    email: str,
    check_smtp: bool = True,
    smtp_timeout: float = 10.0,
    dns_timeout: float = 5.0,
    smtp_helo_host: str | None = None,
    smtp_from_address: str | None = None,
    check_catch_all: bool = False,
) -> EmailVerificationResult:
    """Execute multi-stage zero-cost email verification pipeline.

    Stages:
    1. Syntax & RFC Format Check
    2. Disposable / Burner Domain Detection
    3. Role-Based Inbox Classification
    4. Async DNS MX Record Resolution
    5. Catch-All Domain Detection (Optional)
    6. Direct SMTP Socket Handshake
    """
    cleaned = clean_email(email)

    # Stage 1: Syntax Validation
    if not cleaned or not EMAIL_SYNTAX_REGEX.match(cleaned) or "@" not in cleaned:
        return EmailVerificationResult(
            email=cleaned or email,
            is_valid=False,
            format_valid=False,
            mx_valid=False,
            confidence_score=0.0,
            error_message="Invalid RFC email syntax format",
        )

    domain = cleaned.split("@")[1].lower()
    is_role = is_role_based_email(cleaned)

    # Stage 2: Disposable Domain Check
    if is_disposable_domain(domain):
        return EmailVerificationResult(
            email=cleaned,
            is_valid=False,
            format_valid=True,
            mx_valid=False,
            is_disposable=True,
            is_role_account=is_role,
            confidence_score=0.0,
            error_message=f"Domain {domain} is a known disposable email provider",
        )

    # Stage 4: DNS MX Lookup
    mx_records = await resolve_mx_records(domain, timeout=dns_timeout)
    if not mx_records:
        return EmailVerificationResult(
            email=cleaned,
            is_valid=False,
            format_valid=True,
            mx_valid=False,
            is_role_account=is_role,
            confidence_score=0.0,
            error_message=f"No valid DNS MX records found for domain {domain}",
        )

    # Stage 5: Optional Catch-All Check
    catch_all: bool | None = None
    if check_catch_all and check_smtp:
        catch_all = await check_catch_all_domain(domain, mx_records=mx_records, timeout=smtp_timeout)

    # Stage 6: SMTP Socket Handshake
    smtp_valid: bool | None = None
    error_message: str | None = None
    details: dict[str, Any] = {"mx_records": mx_records}

    if check_smtp:
        try:
            # Run socket handshake in worker thread to avoid blocking asyncio event loop
            handshake_result = await asyncio.to_thread(
                validate_email.validate_email_or_fail,
                cleaned,
                check_format=True,
                check_blacklist=False,
                check_dns=False,
                check_smtp=True,
                smtp_timeout=smtp_timeout,
                smtp_helo_host=smtp_helo_host,
                smtp_from_address=smtp_from_address,
            )
            smtp_valid = True if handshake_result is True else None
            details["smtp_response"] = "250 Mailbox accepted"
        except AddressNotDeliverableError as e:
            smtp_valid = False
            err_msg = _safe_exception_str(e)
            error_message = f"SMTP mailbox rejected (550 User unknown): {err_msg}"
            details["smtp_error"] = err_msg
        except DomainBlacklistedError as e:
            err_msg = _safe_exception_str(e)
            return EmailVerificationResult(
                email=cleaned,
                is_valid=False,
                format_valid=True,
                mx_valid=True,
                is_disposable=True,
                is_role_account=is_role,
                confidence_score=0.0,
                error_message=f"Domain blacklisted: {err_msg}",
            )
        except (
            SMTPTemporaryError,
            SMTPCommunicationError,
            TLSNegotiationError,
            TimeoutError,
            ConnectionError,
            OSError,
        ) as e:
            # Temporary error, greylisting, or blocked outbound port 25
            smtp_valid = None
            err_msg = _safe_exception_str(e)
            error_message = f"SMTP handshake inconclusive (temporary error / greylist): {err_msg}"
            details["smtp_error"] = err_msg
        except Exception as e:  # noqa: BLE001
            smtp_valid = None
            err_msg = _safe_exception_str(e)
            error_message = f"SMTP handshake error: {err_msg}"
            details["smtp_error"] = err_msg

    # Overall validity verdict
    is_valid = (smtp_valid is not False)

    confidence = _calculate_confidence_score(
        format_valid=True,
        mx_valid=True,
        smtp_valid=smtp_valid,
        is_catch_all=catch_all,
        is_disposable=False,
        is_role=is_role,
    )

    return EmailVerificationResult(
        email=cleaned,
        is_valid=is_valid,
        format_valid=True,
        mx_valid=True,
        smtp_valid=smtp_valid,
        is_catch_all=catch_all,
        is_disposable=False,
        is_role_account=is_role,
        mx_records=mx_records,
        confidence_score=confidence,
        error_message=error_message,
        details=details,
    )


async def batch_verify_emails(
    emails: list[str],
    check_smtp: bool = True,
    max_concurrent: int = 5,
    **kwargs: Any,
) -> list[EmailVerificationResult]:
    """Asynchronously verify a list of email addresses with bounded concurrency."""
    if not emails:
        return []

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _bounded_verify(email_addr: str) -> EmailVerificationResult:
        async with semaphore:
            return await verify_email(email_addr, check_smtp=check_smtp, **kwargs)

    tasks = [_bounded_verify(e) for e in emails]
    return await asyncio.gather(*tasks)


async def resolve_lead_email(
    domain_or_url: str,
    decision_maker_name: str | None = None,
    discovered_emails: list[str] | None = None,
    check_smtp: bool = True,
) -> tuple[str | None, EmailVerificationResult | None]:
    """Resolve and verify the highest-probability decision maker or business email for a prospect.

    Strategy:
    1. If discovered emails exist from website extraction:
       - Check if any matches the decision maker's name.
       - Verify matching candidates first.
    2. If a decision maker name is provided:
       - Generate corporate email permutations (e.g., first.last@domain, first@domain).
       - Verify permutation candidates. Return first deliverable (smtp_valid=True) or highest confidence match.
    3. If no decision maker email verified, test discovered contact emails.
    4. Fall back to role-based emails (e.g., contact@domain, info@domain).
    """
    domain = extract_domain(domain_or_url)
    if not domain:
        return (None, None)

    # 1. Check if any discovered emails directly match decision maker name
    if decision_maker_name and discovered_emails:
        first, last = parse_name_components(decision_maker_name)
        if first and last:
            matching_discovered = [
                e for e in discovered_emails
                if extract_domain(e) == domain and (first in e.lower() or last in e.lower())
            ]
            if matching_discovered:
                for candidate in matching_discovered:
                    res = await verify_email(candidate, check_smtp=check_smtp)
                    if res.is_valid and res.smtp_valid is not False:
                        return (res.email, res)

    # 2. Test generated decision-maker permutations
    if decision_maker_name:
        permutations = generate_permutations_for_name(decision_maker_name, domain)
        best_candidate: tuple[str, EmailVerificationResult] | None = None

        for candidate in permutations:
            res = await verify_email(candidate, check_smtp=check_smtp)
            # If SMTP confirmed deliverable, return immediately!
            if res.smtp_valid is True:
                return (res.email, res)
            if res.is_valid and (best_candidate is None or res.confidence_score > best_candidate[1].confidence_score):
                best_candidate = (res.email, res)

        if best_candidate and best_candidate[1].is_valid and best_candidate[1].smtp_valid is not False:
            return best_candidate

    # 3. Test remaining discovered emails from crawling
    if discovered_emails:
        valid_domain_emails = [e for e in discovered_emails if extract_domain(e) == domain]
        for candidate in valid_domain_emails:
            res = await verify_email(candidate, check_smtp=check_smtp)
            if res.is_valid and res.smtp_valid is not False:
                return (res.email, res)

    # 4. Fallback to generic role-based aliases
    role_candidates = generate_role_emails(domain)
    for candidate in role_candidates:
        res = await verify_email(candidate, check_smtp=check_smtp)
        if res.is_valid and res.smtp_valid is not False:
            return (res.email, res)

    return (None, None)
