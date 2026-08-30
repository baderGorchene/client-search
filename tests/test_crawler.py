"""Unit and integration tests for Crawl4AI web extraction pipeline."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from crawl4ai.models import CrawlResult, MarkdownGenerationResult

from discovery.crawler import (
    ExtractedLeadContent,
    clean_and_truncate_markdown,
    extract_emails,
    extract_lead_content,
    extract_phones,
    extract_social_links,
    identify_priority_subpages,
    is_valid_contact_email,
)


def test_is_valid_contact_email():
    """Verify email validation rules and dummy/asset rejection."""
    assert is_valid_contact_email("john.doe@apexfreight.com") is True
    assert is_valid_contact_email("sales@3pl-logistics.io") is True
    assert is_valid_contact_email("contact@company.co.uk") is True

    # Rejection of invalid/image/asset patterns
    assert is_valid_contact_email("image@2x.png") is False
    assert is_valid_contact_email("logo@preview.svg") is False
    assert is_valid_contact_email("style@site.css") is False

    # Rejection of dummy/tracker domains
    assert is_valid_contact_email("test@example.com") is False
    assert is_valid_contact_email("admin@domain.com") is False
    assert is_valid_contact_email("error@sentry.io") is False
    assert is_valid_contact_email("site@wixpress.com") is False
    assert is_valid_contact_email("support@getbootstrap.com") is False

    # Rejection of placeholders
    assert is_valid_contact_email("username@corp.com") is False
    assert is_valid_contact_email("") is False


def test_extract_emails():
    """Verify extraction of emails from text, HTML, and mailto links."""
    text_content = """
    Welcome to Apex Logistics! Contact us at info@apexfreight.com or call our dispatch.
    Ignore dummy email dev@sentry.io and image@preview.png.
    """
    html_content = """
    <footer>
        <a href="mailto:contact@apexfreight.com">Contact Us</a>
        <a href="mailto:info@apexfreight.com">Duplicate Info</a>
        <span>Careers: careers@apexfreight.com</span>
    </footer>
    """

    emails = extract_emails(text=text_content, html=html_content)
    assert "info@apexfreight.com" in emails
    assert "contact@apexfreight.com" in emails
    assert "careers@apexfreight.com" in emails
    assert "dev@sentry.io" not in emails
    assert "image@preview.png" not in emails
    assert len(emails) == 3


def test_extract_phones():
    """Verify extraction of phone numbers in various formats including tel links."""
    text_content = """
    Main Office: (312) 555-0199
    Toll Free: +1-800-555-1234
    Local Dispatch: 312.555.9876
    Direct Line: +1 312 555 4321
    Invalid Date: 2026-08-30
    Short code: 12345
    """
    html_content = '<a href="tel:1-800-555-0123">1-800-555-0123</a>'

    phones = extract_phones(text_content, html_content)
    assert "(312) 555-0199" in phones
    assert "1-800-555-0123" in phones
    assert "+1-800-555-1234" in phones
    assert "312.555.9876" in phones
    assert "+1 312 555 4321" in phones
    assert "2026-08-30" not in phones
    assert "12345" not in phones


def test_extract_social_links():
    """Verify identification and mapping of social media profile links."""
    links_dict = {
        "external": [
            {"href": "https://www.linkedin.com/company/apex-freight-logistics", "text": "LinkedIn"},
            {"href": "https://twitter.com/apexfreight", "text": "Twitter"},
            {"href": "https://facebook.com/apexfreight", "text": "Facebook"},
            {"href": "https://www.linkedin.com/shareArticle?mini=true", "text": "Share"},
            {"href": "https://github.com/apexfreight-oss", "text": "GitHub"},
        ],
        "internal": [],
    }

    socials = extract_social_links(links_dict)
    assert socials["linkedin"] == "https://www.linkedin.com/company/apex-freight-logistics"
    assert socials["twitter"] == "https://twitter.com/apexfreight"
    assert socials["facebook"] == "https://facebook.com/apexfreight"
    assert socials["github"] == "https://github.com/apexfreight-oss"
    assert "sharer" not in socials.get("linkedin", "")


def test_identify_priority_subpages():
    """Verify priority ranking and filtering of internal subpages."""
    base_url = "https://apexfreight.com"
    internal_links = [
        {"href": "/about-us", "text": "About Us"},
        {"href": "/contact", "text": "Contact Us"},
        {"href": "/team/leadership", "text": "Our Team"},
        {"href": "/services/warehousing", "text": "Warehousing"},
        {"href": "/privacy-policy", "text": "Privacy Policy"},
        {"href": "/terms-and-conditions", "text": "Terms of Service"},
        {"href": "/blog/logistics-trends", "text": "Blog"},
        {"href": "/", "text": "Home"},
    ]

    priority_subpages = identify_priority_subpages(internal_links, base_url, max_subpages=2)
    assert len(priority_subpages) == 2
    assert any("contact" in u or "team" in u or "about" in u for u in priority_subpages)
    assert not any("privacy" in u or "terms" in u or "blog" in u for u in priority_subpages)


def test_clean_and_truncate_markdown():
    """Verify markdown cleaning, cookie stripping, and token budget truncation."""
    raw_md = """
    # Apex Freight Solutions
    ![Company Banner](https://apexfreight.com/banner.jpg)
    data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...

    We use cookies to enhance your browsing experience. Accept all cookies.

    ## Our Services
    We provide nationwide LTL freight, warehousing, and customs clearance.

    Contact us: dispatch@apexfreight.com
    """

    cleaned = clean_and_truncate_markdown(raw_md, max_chars=500)
    assert "data:image" not in cleaned
    assert "![Company Banner]" not in cleaned
    assert "We use cookies" not in cleaned
    assert "# Apex Freight Solutions" in cleaned
    assert "We provide nationwide LTL freight" in cleaned

    # Test truncation on very long text
    long_md = "This is a long sentence explaining freight operations. " * 200
    truncated = clean_and_truncate_markdown(long_md, max_chars=300)
    assert len(truncated) <= 400
    assert "[Content truncated for LLM token optimization]" in truncated


@pytest.mark.asyncio
async def test_extract_lead_content_full_flow():
    """Verify complete extraction flow with primary page and subpage crawling."""
    primary_url = "https://apexfreight.com"

    mock_primary_md = MarkdownGenerationResult(
        raw_markdown="# Apex Freight\nFull service 3PL provider.\nPhone: (312) 555-0199",
        fit_markdown="# Apex Freight\nFull service 3PL provider.\nPhone: (312) 555-0199",
        markdown_with_citations="# Apex Freight\nFull service 3PL provider.\nPhone: (312) 555-0199",
        references_markdown="",
    )
    mock_primary_res = MagicMock(spec=CrawlResult)
    mock_primary_res.success = True
    mock_primary_res.url = primary_url
    mock_primary_res.markdown = mock_primary_md
    mock_primary_res.html = "<html><head><title>Apex Freight - 3PL</title></head><body>...</body></html>"
    mock_primary_res.metadata = {"title": "Apex Freight - 3PL"}
    mock_primary_res.links = {
        "internal": [
            {"href": "https://apexfreight.com/contact-us", "text": "Contact Us"},
        ],
        "external": [
            {"href": "https://www.linkedin.com/company/apexfreight", "text": "LinkedIn"},
        ],
    }

    mock_subpage_md = MarkdownGenerationResult(
        raw_markdown="# Contact Us\nEmail us at info@apexfreight.com or ceo@apexfreight.com",
        fit_markdown="# Contact Us\nEmail us at info@apexfreight.com or ceo@apexfreight.com",
        markdown_with_citations="# Contact Us\nEmail us at info@apexfreight.com or ceo@apexfreight.com",
        references_markdown="",
    )
    mock_subpage_res = MagicMock(spec=CrawlResult)
    mock_subpage_res.success = True
    mock_subpage_res.url = "https://apexfreight.com/contact-us"
    mock_subpage_res.markdown = mock_subpage_md
    mock_subpage_res.html = "<html><body>Contact info@apexfreight.com</body></html>"
    mock_subpage_res.metadata = {}
    mock_subpage_res.links = {}

    mock_crawler = AsyncMock()
    mock_crawler.arun.side_effect = [mock_primary_res, mock_subpage_res]

    lead_content = await extract_lead_content(
        url=primary_url,
        company_name="Apex Freight",
        crawl_subpages=True,
        max_subpages=1,
        crawler=mock_crawler,
    )

    assert isinstance(lead_content, ExtractedLeadContent)
    assert lead_content.success is True
    assert lead_content.company_name == "Apex Freight"
    assert lead_content.page_title == "Apex Freight - 3PL"
    assert "info@apexfreight.com" in lead_content.emails_found
    assert "ceo@apexfreight.com" in lead_content.emails_found
    assert "(312) 555-0199" in lead_content.phones_found
    assert lead_content.social_links.get("linkedin") == "https://www.linkedin.com/company/apexfreight"
    assert "https://apexfreight.com/contact-us" in lead_content.subpages_crawled
    assert "Full service 3PL provider" in lead_content.markdown
    assert "Contact Us" in lead_content.markdown


@pytest.mark.asyncio
async def test_extract_lead_content_primary_failure():
    """Verify extract_lead_content handles failed primary crawl gracefully."""
    mock_primary_res = MagicMock(spec=CrawlResult)
    mock_primary_res.success = False
    mock_primary_res.error_message = "Connection timed out"

    mock_crawler = AsyncMock()
    mock_crawler.arun.return_value = mock_primary_res

    lead_content = await extract_lead_content(
        url="https://failedsite.com",
        crawler=mock_crawler,
    )

    assert lead_content.success is False
    assert "Connection timed out" in (lead_content.error_message or "")


@pytest.mark.asyncio
async def test_extract_lead_content_exception():
    """Verify extract_lead_content catches unexpected runtime exceptions."""
    mock_crawler = AsyncMock()
    mock_crawler.arun.side_effect = Exception("Playwright crash")

    lead_content = await extract_lead_content(
        url="https://crashedsite.com",
        crawler=mock_crawler,
    )

    assert lead_content.success is False
    assert "Playwright crash" in (lead_content.error_message or "")


@pytest.mark.asyncio
async def test_extract_lead_content_empty_url():
    """Verify empty URL input returns unsuccessful ExtractedLeadContent."""
    lead_content = await extract_lead_content(url="")
    assert lead_content.success is False
    assert lead_content.error_message == "Empty URL provided"
