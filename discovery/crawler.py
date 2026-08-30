"""Web extraction pipeline using Crawl4AI for zero-cost prospect website scraping and markdown synthesis."""

import logging
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
    DefaultMarkdownGenerator,
    PruningContentFilter,
)
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
PHONE_REGEX = re.compile(r"(?:(?:\+?1\s*(?:[.-]\s*)?)?(?:\(\s*[2-9]\d{2}\s*\)|[2-9]\d{2})\s*(?:[.-]\s*)?)?[2-9]\d{2}\s*(?:[.-]\s*)?\d{4}")

INVALID_EMAIL_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js", ".woff", ".woff2", ".ttf", ".eot", ".html", ".php", ".map"}
IGNORED_EMAIL_DOMAINS = {"example.com", "domain.com", "email.com", "sentry.io", "wixpress.com", "wix.com", "wordpress.com", "cloudflare.com", "getbootstrap.com", "schema.org", "google.com", "github.com", "gravatar.com", "mysite.com", "yoursite.com"}
IGNORED_EMAIL_USERS = {"username", "yourname", "name", "user", "email", "placeholder"}

HIGH_PRIORITY_SUBPAGE_KEYWORDS = {
    "contact": 10, "contact-us": 10, "get-in-touch": 10, "reach-us": 10,
    "team": 9, "leadership": 9, "executives": 9, "our-team": 9, "management": 9,
    "about": 8, "about-us": 8, "who-we-are": 8, "our-story": 8,
    "company": 7, "services": 6, "solutions": 6,
}
EXCLUDED_SUBPAGE_KEYWORDS = {"privacy", "terms", "tos", "cookie", "login", "signup", "cart", "checkout", "account", "wp-admin", "blog", "news", "tag", "category", "careers", "jobs"}


class ExtractedLeadContent(BaseModel):
    """Cleaned and synthesized website extraction output ready for LLM fit evaluation."""

    url: str = Field(..., description="Canonical base URL crawled")
    company_name: str = Field(default="", description="Inferred or matched company name")
    markdown: str = Field(default="", description="Cleaned, LLM-ready markdown (<1,500 tokens)")
    raw_markdown: str = Field(default="", description="Raw markdown output from primary crawl")
    fit_markdown: str = Field(default="", description="Pruned/filtered markdown output")
    page_title: str = Field(default="", description="Extracted webpage title")
    emails_found: list[str] = Field(default_factory=list, description="Extracted contact emails")
    phones_found: list[str] = Field(default_factory=list, description="Extracted phone numbers")
    social_links: dict[str, str] = Field(default_factory=dict, description="Identified social media links")
    subpages_crawled: list[str] = Field(default_factory=list, description="Subpage URLs crawled and merged")
    word_count: int = Field(default=0, description="Word count of final markdown")
    success: bool = Field(default=True, description="Whether extraction succeeded")
    error_message: str | None = Field(default=None, description="Error detail if crawl failed")

    model_config = ConfigDict(extra="ignore")


def is_valid_contact_email(email: str) -> bool:
    """Validate that an extracted string is a legitimate B2B contact email."""
    if not email or "@" not in email:
        return False
    email_clean = email.strip().lower()
    if any(email_clean.endswith(ext) for ext in INVALID_EMAIL_EXTENSIONS):
        return False

    parts = email_clean.split("@")
    if len(parts) != 2:
        return False
    local, domain = parts
    if not local or not domain or local in IGNORED_EMAIL_USERS:
        return False

    return not (domain in IGNORED_EMAIL_DOMAINS or any(domain.endswith(f".{d}") for d in IGNORED_EMAIL_DOMAINS))


def extract_emails(text: str, html: str = "") -> list[str]:
    """Extract, filter, and deduplicate valid contact emails from text and HTML content."""
    combined = f"{text}\n{html}"
    found: set[str] = set()
    ordered: list[str] = []

    # Parse mailto links and plaintext email matches
    matches = re.findall(r"mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", combined, re.IGNORECASE) + EMAIL_REGEX.findall(combined)
    for m in matches:
        clean = m.strip().lower()
        if clean not in found and is_valid_contact_email(clean):
            found.add(clean)
            ordered.append(clean)

    return ordered


def extract_phones(text: str, html: str = "") -> list[str]:
    """Extract and normalize phone numbers from scraped text and HTML content."""
    combined = f"{text}\n{html}"
    found_digits: set[str] = set()
    ordered: list[str] = []

    tel_matches = re.findall(r"tel:([+0-9()\-.\s]{7,25})", combined, re.IGNORECASE)
    for tm in tel_matches:
        clean = re.sub(r"[\"\'<>].*$", "", tm).strip().rstrip(").,-;")
        digits = re.sub(r"\D", "", clean)
        if 7 <= len(digits) <= 15 and digits not in found_digits:
            found_digits.add(digits)
            ordered.append(clean)

    for match in PHONE_REGEX.finditer(combined):
        raw_match = match.group(0).strip().rstrip(").,-;")
        digits = re.sub(r"\D", "", raw_match)
        if len(digits) in (10, 11) and digits not in found_digits:
            found_digits.add(digits)
            ordered.append(raw_match)

    return ordered


def extract_social_links(links: list[dict[str, Any]] | dict[str, Any] | None) -> dict[str, str]:
    """Extract identified social media profile links (LinkedIn, Twitter/X, Facebook, etc.)."""
    if not links:
        return {}

    items = (links.get("external", []) + links.get("internal", [])) if isinstance(links, dict) else links
    socials: dict[str, str] = {}
    platforms = {
        "linkedin": ("linkedin.com/company", "linkedin.com/in"),
        "twitter": ("twitter.com", "x.com"),
        "facebook": ("facebook.com",),
        "instagram": ("instagram.com",),
        "youtube": ("youtube.com",),
        "github": ("github.com",),
    }

    for item in items:
        href = (item.get("href", "") if isinstance(item, dict) else str(item)).strip()
        if not href.startswith(("http://", "https://")) or "share" in href.lower():
            continue
        href_lower = href.lower()
        for p, patterns in platforms.items():
            if p not in socials and any(pat in href_lower for pat in patterns):
                socials[p] = href

    return socials


def identify_priority_subpages(
    internal_links: list[dict[str, Any]] | None,
    base_url: str,
    max_subpages: int = 2,
) -> list[str]:
    """Rank and select high-value internal subpages (e.g., /about, /contact, /team) for deeper extraction."""
    if not internal_links or max_subpages <= 0:
        return []

    try:
        base_parsed = urlparse(base_url if base_url.startswith(("http://", "https://")) else f"https://{base_url}")
        base_domain = base_parsed.netloc.lower().removeprefix("www.")
        base_path = base_parsed.path.rstrip("/")
    except (ValueError, AttributeError):
        return []

    scored_urls: list[tuple[int, str]] = []
    seen: set[str] = {base_url.rstrip("/")}

    for item in internal_links:
        href = (item.get("href", "") if isinstance(item, dict) else str(item)).strip()
        text = (item.get("text", "") if isinstance(item, dict) else "").strip().lower()
        if not href:
            continue

        full_url = urljoin(base_url, href)
        try:
            parsed = urlparse(full_url)
            domain = parsed.netloc.lower().removeprefix("www.")
        except (ValueError, AttributeError):
            continue

        if domain != base_domain:
            continue

        path = parsed.path.lower().rstrip("/")
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"

        if not path or path == base_path or normalized in seen:
            continue

        if any(excluded in path for excluded in EXCLUDED_SUBPAGE_KEYWORDS):
            continue

        score = sum(kw_score for kw, kw_score in HIGH_PRIORITY_SUBPAGE_KEYWORDS.items() if kw in path or kw in text)
        if score > 0:
            seen.add(normalized)
            scored_urls.append((score, normalized))

    scored_urls.sort(key=lambda x: x[0], reverse=True)
    return [url for _, url in scored_urls[:max_subpages]]


def clean_and_truncate_markdown(markdown_text: str, max_chars: int = 6000) -> str:
    """Clean boilerplate noise, strip image data, compress spacing, and truncate to token budget."""
    if not markdown_text:
        return ""

    text = markdown_text
    text = re.sub(r"data:image\/[a-zA-Z]+;base64,[^\s\)\"\']+", "", text)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"(?i)(this website uses cookies|we use cookies to enhance|by continuing to browse|cookie policy|manage cookies|accept all cookies|privacy preference center|all rights reserved).*?(\n\n|\Z)", "", text)
    text = re.sub(r"(?:\[[^\]]+\]\([^\)]+\)\s*\|?\s*){4,}", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if len(text) > max_chars:
        cutoff = text[:max_chars].rfind("\n\n")
        if cutoff == -1 or cutoff < max_chars // 2:
            cutoff = text[:max_chars].rfind(". ")
            if cutoff != -1:
                cutoff += 1
        if cutoff == -1 or cutoff < max_chars // 2:
            cutoff = max_chars
        text = text[:cutoff].strip() + "\n\n... [Content truncated for LLM token optimization]"

    return text


def create_crawler_run_config(timeout_ms: int = 30000) -> CrawlerRunConfig:
    """Create default CrawlerRunConfig with noise pruning."""
    return CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(content_filter=PruningContentFilter(threshold=0.45, min_word_threshold=5)),
        remove_overlay_elements=True,
        remove_consent_popups=True,
        delay_before_return_html=0.5,
        page_timeout=timeout_ms,
        verbose=False,
    )


async def extract_lead_content(
    url: str,
    company_name: str = "",
    crawl_subpages: bool = True,
    max_subpages: int = 2,
    crawler: AsyncWebCrawler | None = None,
    timeout_ms: int = 30000,
) -> ExtractedLeadContent:
    """Crawl a prospect's website, hydrate SPAs, strip noise, and extract contact details."""
    if not url:
        return ExtractedLeadContent(url="", company_name=company_name, success=False, error_message="Empty URL provided")

    target_url = url.strip()
    if not target_url.startswith(("http://", "https://")):
        target_url = f"https://{target_url}"

    run_config = create_crawler_run_config(timeout_ms=timeout_ms)

    async def _execute(active_crawler: AsyncWebCrawler) -> ExtractedLeadContent:
        try:
            res = await active_crawler.arun(url=target_url, config=run_config)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Primary crawl failed for '%s': %s", target_url, exc)
            return ExtractedLeadContent(url=target_url, company_name=company_name, success=False, error_message=f"Failed to crawl primary URL: {exc}")

        if not res.success:
            return ExtractedLeadContent(url=target_url, company_name=company_name, success=False, error_message=res.error_message or "Primary page crawl failed")

        raw_md = res.markdown.raw_markdown if res.markdown else ""
        fit_md = res.markdown.fit_markdown if res.markdown else ""
        html = res.html or ""

        # Title extraction
        title = (res.metadata.get("title", "") if isinstance(res.metadata, dict) else "")
        if not title and "<title>" in html.lower():
            m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            if m:
                title = m.group(1).strip()

        emails = extract_emails(f"{fit_md}\n{raw_md}", html)
        phones = extract_phones(f"{fit_md}\n{raw_md}", html)
        socials = extract_social_links(res.links)

        subpages_crawled: list[str] = []
        md_parts: list[str] = [fit_md or raw_md]

        if crawl_subpages and res.links:
            for subpage_url in identify_priority_subpages(res.links.get("internal", []), target_url, max_subpages):
                try:
                    sub_res = await active_crawler.arun(url=subpage_url, config=run_config)
                    if sub_res and sub_res.success:
                        subpages_crawled.append(subpage_url)
                        sub_fit = sub_res.markdown.fit_markdown if sub_res.markdown else ""
                        sub_raw = sub_res.markdown.raw_markdown if sub_res.markdown else ""
                        sub_html = sub_res.html or ""

                        for e in extract_emails(f"{sub_fit}\n{sub_raw}", sub_html):
                            if e not in emails:
                                emails.append(e)
                        for p in extract_phones(f"{sub_fit}\n{sub_raw}", sub_html):
                            if p not in phones:
                                phones.append(p)

                        sub_name = urlparse(subpage_url).path.strip("/").replace("-", " ").title() or "Contact"
                        if sub_fit or sub_raw:
                            md_parts.append(f"\n\n## Subpage: {sub_name} ({subpage_url})\n{sub_fit or sub_raw}")
                except Exception as sub_exc:  # noqa: BLE001
                    logger.debug("Subpage crawl failed for '%s': %s", subpage_url, sub_exc)

        merged_md = clean_and_truncate_markdown("\n\n".join(p for p in md_parts if p.strip()), max_chars=6000)
        return ExtractedLeadContent(
            url=target_url,
            company_name=company_name,
            markdown=merged_md,
            raw_markdown=raw_md,
            fit_markdown=fit_md,
            page_title=title,
            emails_found=emails,
            phones_found=phones,
            social_links=socials,
            subpages_crawled=subpages_crawled,
            word_count=len(merged_md.split()),
            success=True,
        )

    if crawler is not None:
        return await _execute(crawler)

    browser_config = BrowserConfig(headless=True, verbose=False, ignore_https_errors=True, extra_args=["--disable-gpu", "--no-sandbox"])
    async with AsyncWebCrawler(config=browser_config) as local_crawler:
        return await _execute(local_crawler)
