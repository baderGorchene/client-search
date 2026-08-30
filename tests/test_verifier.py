"""Unit and integration tests for email resolution and verification engine."""

from __future__ import annotations

from unittest.mock import AsyncMock

import dns.exception
import dns.resolver
import pytest
from validate_email.exceptions import (
    AddressNotDeliverableError,
    SMTPMessage,
    SMTPTemporaryError,
)

from verification.email_verifier import (
    batch_verify_emails,
    check_catch_all_domain,
    clean_email,
    clear_cache,
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


@pytest.fixture(autouse=True)
def reset_verification_cache():
    """Clear DNS MX and catch-all cache before each test."""
    clear_cache()
    yield
    clear_cache()


def make_undeliverable_error(host="mail.apexfreight.com", code=550, text="User unknown"):
    msg = SMTPMessage(command="RCPT TO", code=code, text=text, exceptions=[])
    return AddressNotDeliverableError(error_messages={host: msg})


def make_temporary_error(host="mail.apexfreight.com", code=451, text="Greylisted"):
    msg = SMTPMessage(command="RCPT TO", code=code, text=text, exceptions=[])
    return SMTPTemporaryError(error_messages={host: msg})


class DummyMXRecord:
    """Mock DNS MX record object."""

    def __init__(self, preference: int, exchange: str):
        self.preference = preference
        self.exchange = exchange


# ==============================================================================
# Helper & Extraction Tests
# ==============================================================================

def test_clean_email():
    assert clean_email("  mailto:John.Doe@ApexFreight.COM?subject=hello  ") == "john.doe@apexfreight.com"
    assert clean_email("Sales@Company.com") == "sales@company.com"
    assert clean_email("") == ""
    assert clean_email("   ") == ""


def test_extract_domain():
    assert extract_domain("https://www.apexfreight.com/contact/us") == "apexfreight.com"
    assert extract_domain("http://sub.domain.co.uk:8080/path") == "sub.domain.co.uk"
    assert extract_domain("www.example.com") == "example.com"
    assert extract_domain("company.com") == "company.com"
    assert extract_domain("") == ""


def test_is_role_based_email():
    assert is_role_based_email("info@apexfreight.com") is True
    assert is_role_based_email("sales-team@apexfreight.com") is True
    assert is_role_based_email("support.us@apexfreight.com") is True
    assert is_role_based_email("admin@apexfreight.com") is True
    assert is_role_based_email("john.doe@apexfreight.com") is False
    assert is_role_based_email("invalid-email") is False


def test_is_disposable_domain():
    assert is_disposable_domain("mailinator.com") is True
    assert is_disposable_domain("temp-mail.org") is True
    assert is_disposable_domain("10minutemail.net") is True
    assert is_disposable_domain("apexfreight.com") is False
    assert is_disposable_domain("gmail.com") is False


def test_parse_name_components():
    assert parse_name_components("John Doe") == ("john", "doe")
    assert parse_name_components("Dr. Sarah Jane Smith, CEO") == ("sarah", "smith")
    assert parse_name_components("Mr. Alex M. Turner Jr.") == ("alex", "turner")
    assert parse_name_components("Madonna") == ("madonna", "madonna")
    assert parse_name_components("") == ("", "")


def test_generate_email_permutations():
    permutations = generate_email_permutations("John", "Doe", "apexfreight.com")
    assert "john.doe@apexfreight.com" in permutations
    assert "john@apexfreight.com" in permutations
    assert "johndoe@apexfreight.com" in permutations
    assert "j.doe@apexfreight.com" in permutations
    assert "jdoe@apexfreight.com" in permutations
    assert "john_doe@apexfreight.com" in permutations
    assert "doe.john@apexfreight.com" in permutations
    assert len(permutations) == len(set(permutations))  # No duplicates

    # Single name
    single = generate_email_permutations("Alex", "", "apexfreight.com")
    assert single == ["alex@apexfreight.com"]

    # Name wrapper
    wrap = generate_permutations_for_name("CEO John Doe", "apexfreight.com")
    assert "john.doe@apexfreight.com" in wrap


def test_generate_role_emails():
    roles = generate_role_emails("https://www.apexfreight.com/about")
    assert "contact@apexfreight.com" in roles
    assert "info@apexfreight.com" in roles
    assert "sales@apexfreight.com" in roles
    assert "support@apexfreight.com" in roles


# ==============================================================================
# DNS MX Resolution Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_resolve_mx_records_success(mocker):
    mock_resolve = mocker.patch("dns.asyncresolver.Resolver.resolve", new_callable=AsyncMock)
    mock_resolve.return_value = [
        DummyMXRecord(preference=20, exchange="alt.mx.google.com."),
        DummyMXRecord(preference=10, exchange="aspmx.l.google.com."),
    ]

    records = await resolve_mx_records("apexfreight.com")
    assert records == ["aspmx.l.google.com", "alt.mx.google.com"]
    # Check cache
    cached = await resolve_mx_records("apexfreight.com")
    assert cached == ["aspmx.l.google.com", "alt.mx.google.com"]
    assert mock_resolve.call_count == 1


@pytest.mark.asyncio
async def test_resolve_mx_records_null_mx(mocker):
    # RFC 7505 Null MX
    mock_resolve = mocker.patch("dns.asyncresolver.Resolver.resolve", new_callable=AsyncMock)
    mock_resolve.return_value = [DummyMXRecord(preference=0, exchange=".")]

    records = await resolve_mx_records("noemail.com")
    assert records == []


@pytest.mark.asyncio
async def test_resolve_mx_records_nxdomain(mocker):
    mock_resolve = mocker.patch("dns.asyncresolver.Resolver.resolve", new_callable=AsyncMock)
    mock_resolve.side_effect = dns.resolver.NXDOMAIN()

    records = await resolve_mx_records("nonexistentdomain12345.xyz")
    assert records == []


@pytest.mark.asyncio
async def test_resolve_mx_records_timeout(mocker):
    mock_resolve = mocker.patch("dns.asyncresolver.Resolver.resolve", new_callable=AsyncMock)
    mock_resolve.side_effect = dns.exception.Timeout()

    records = await resolve_mx_records("timeoutdomain.com")
    assert records == []


# ==============================================================================
# Catch-All Domain Detection Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_check_catch_all_domain_true(mocker):
    mocker.patch("verification.email_verifier.resolve_mx_records", new_callable=AsyncMock, return_value=["mail.apexfreight.com"])
    mocker.patch("asyncio.to_thread", new_callable=AsyncMock, return_value=True)

    is_catch_all = await check_catch_all_domain("apexfreight.com")
    assert is_catch_all is True


@pytest.mark.asyncio
async def test_check_catch_all_domain_false(mocker):
    mocker.patch("verification.email_verifier.resolve_mx_records", new_callable=AsyncMock, return_value=["mail.apexfreight.com"])
    mocker.patch("asyncio.to_thread", new_callable=AsyncMock, side_effect=make_undeliverable_error())

    is_catch_all = await check_catch_all_domain("apexfreight.com")
    assert is_catch_all is False


# ==============================================================================
# Single & Batch Email Verification Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_verify_email_invalid_syntax():
    result = await verify_email("invalid-email-address")
    assert result.is_valid is False
    assert result.format_valid is False
    assert result.confidence_score == 0.0


@pytest.mark.asyncio
async def test_verify_email_disposable():
    result = await verify_email("user@mailinator.com")
    assert result.is_valid is False
    assert result.format_valid is True
    assert result.is_disposable is True
    assert result.confidence_score == 0.0


@pytest.mark.asyncio
async def test_verify_email_no_mx(mocker):
    mocker.patch("verification.email_verifier.resolve_mx_records", new_callable=AsyncMock, return_value=[])

    result = await verify_email("john@nomxdomain.com")
    assert result.is_valid is False
    assert result.format_valid is True
    assert result.mx_valid is False
    assert result.confidence_score == 0.0


@pytest.mark.asyncio
async def test_verify_email_mx_only_without_smtp(mocker):
    mocker.patch("verification.email_verifier.resolve_mx_records", new_callable=AsyncMock, return_value=["mail.apexfreight.com"])

    result = await verify_email("john.doe@apexfreight.com", check_smtp=False)
    assert result.is_valid is True
    assert result.format_valid is True
    assert result.mx_valid is True
    assert result.smtp_valid is None
    assert result.is_role_account is False
    assert result.confidence_score == 0.65


@pytest.mark.asyncio
async def test_verify_email_smtp_deliverable(mocker):
    mocker.patch("verification.email_verifier.resolve_mx_records", new_callable=AsyncMock, return_value=["mail.apexfreight.com"])
    mocker.patch("asyncio.to_thread", new_callable=AsyncMock, return_value=True)

    result = await verify_email("john.doe@apexfreight.com", check_smtp=True)
    assert result.is_valid is True
    assert result.smtp_valid is True
    assert result.confidence_score == 0.95


@pytest.mark.asyncio
async def test_verify_email_smtp_role_account(mocker):
    mocker.patch("verification.email_verifier.resolve_mx_records", new_callable=AsyncMock, return_value=["mail.apexfreight.com"])
    mocker.patch("asyncio.to_thread", new_callable=AsyncMock, return_value=True)

    result = await verify_email("info@apexfreight.com", check_smtp=True)
    assert result.is_valid is True
    assert result.is_role_account is True
    assert result.smtp_valid is True
    assert result.confidence_score == 0.85  # Adjusted for role account


@pytest.mark.asyncio
async def test_verify_email_smtp_rejected(mocker):
    mocker.patch("verification.email_verifier.resolve_mx_records", new_callable=AsyncMock, return_value=["mail.apexfreight.com"])
    mocker.patch("asyncio.to_thread", new_callable=AsyncMock, side_effect=make_undeliverable_error())

    result = await verify_email("nonexistent.person@apexfreight.com", check_smtp=True)
    assert result.is_valid is False
    assert result.smtp_valid is False
    assert result.confidence_score == 0.0


@pytest.mark.asyncio
async def test_verify_email_smtp_temporary_error(mocker):
    mocker.patch("verification.email_verifier.resolve_mx_records", new_callable=AsyncMock, return_value=["mail.apexfreight.com"])
    mocker.patch("asyncio.to_thread", new_callable=AsyncMock, side_effect=make_temporary_error())

    result = await verify_email("john.doe@apexfreight.com", check_smtp=True)
    assert result.is_valid is True  # MX is valid, temporary delay
    assert result.smtp_valid is None
    assert result.confidence_score == 0.65


@pytest.mark.asyncio
async def test_batch_verify_emails(mocker):
    mocker.patch("verification.email_verifier.resolve_mx_records", new_callable=AsyncMock, return_value=["mail.apexfreight.com"])
    mocker.patch("asyncio.to_thread", new_callable=AsyncMock, return_value=True)

    emails = ["john@apexfreight.com", "sales@apexfreight.com", "invalid-syntax"]
    results = await batch_verify_emails(emails, check_smtp=True, max_concurrent=2)

    assert len(results) == 3
    assert results[0].is_valid is True
    assert results[1].is_valid is True
    assert results[2].is_valid is False

    # Empty batch
    empty_res = await batch_verify_emails([])
    assert empty_res == []


# ==============================================================================
# Decision Maker & Lead Resolution Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_resolve_lead_email_matching_discovered(mocker):
    mocker.patch("verification.email_verifier.resolve_mx_records", new_callable=AsyncMock, return_value=["mail.apexfreight.com"])
    mocker.patch("asyncio.to_thread", new_callable=AsyncMock, return_value=True)

    discovered = ["sales@apexfreight.com", "john.doe@apexfreight.com", "contact@other.com"]
    email, res = await resolve_lead_email(
        domain_or_url="https://apexfreight.com",
        decision_maker_name="John Doe",
        discovered_emails=discovered,
        check_smtp=True,
    )

    assert email == "john.doe@apexfreight.com"
    assert res is not None
    assert res.is_valid is True


@pytest.mark.asyncio
async def test_resolve_lead_email_permutation_generation(mocker):
    mocker.patch("verification.email_verifier.resolve_mx_records", new_callable=AsyncMock, return_value=["mail.apexfreight.com"])

    async def mock_to_thread(func, *args, **kwargs):
        # args[0] is the email being checked
        email_arg = args[0]
        if email_arg == "j.smith@apexfreight.com":
            return True
        raise make_undeliverable_error()

    mocker.patch("asyncio.to_thread", side_effect=mock_to_thread)

    email, res = await resolve_lead_email(
        domain_or_url="apexfreight.com",
        decision_maker_name="Jane Smith",
        discovered_emails=None,
        check_smtp=True,
    )

    assert email == "j.smith@apexfreight.com"
    assert res is not None
    assert res.smtp_valid is True


@pytest.mark.asyncio
async def test_resolve_lead_email_fallback_to_discovered(mocker):
    mocker.patch("verification.email_verifier.resolve_mx_records", new_callable=AsyncMock, return_value=["mail.apexfreight.com"])

    async def mock_to_thread(func, *args, **kwargs):
        email_arg = args[0]
        if email_arg == "support@apexfreight.com":
            return True
        raise make_undeliverable_error()

    mocker.patch("asyncio.to_thread", side_effect=mock_to_thread)

    email, res = await resolve_lead_email(
        domain_or_url="apexfreight.com",
        decision_maker_name="Unknown Boss",
        discovered_emails=["support@apexfreight.com"],
        check_smtp=True,
    )

    assert email == "support@apexfreight.com"
    assert res is not None
    assert res.is_valid is True


@pytest.mark.asyncio
async def test_resolve_lead_email_fallback_to_role(mocker):
    mocker.patch("verification.email_verifier.resolve_mx_records", new_callable=AsyncMock, return_value=["mail.apexfreight.com"])

    async def mock_to_thread(func, *args, **kwargs):
        email_arg = args[0]
        if email_arg == "contact@apexfreight.com":
            return True
        raise make_undeliverable_error()

    mocker.patch("asyncio.to_thread", side_effect=mock_to_thread)

    email, res = await resolve_lead_email(
        domain_or_url="apexfreight.com",
        decision_maker_name=None,
        discovered_emails=None,
        check_smtp=True,
    )

    assert email == "contact@apexfreight.com"
    assert res is not None
    assert res.is_valid is True


@pytest.mark.asyncio
async def test_resolve_lead_email_invalid_domain():
    email, res = await resolve_lead_email("")
    assert email is None
    assert res is None
