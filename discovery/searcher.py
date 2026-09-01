"""Zero-cost prospect discovery engine using DuckDuckGo Search and OpenStreetMap Overpass."""

import asyncio
import re
from enum import Enum
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger
from pydantic import BaseModel, Field

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS  # type: ignore[no-redef]

# Explicit list of directory, aggregator, social, encyclopedia, job board, and media platforms
DISQUALIFIED_DOMAINS = {
    "yelp.com",
    "yellowpages.com",
    "linkedin.com",
    "wikipedia.org",
    "indeed.com",
    "glassdoor.com",
    "clutch.co",
    "upwork.com",
    "fiverr.com",
    "zoominfo.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "youtube.com",
    "tiktok.com",
    "pinterest.com",
    "reddit.com",
    "quora.com",
    "google.com",
    "bing.com",
    "duckduckgo.com",
    "apple.com",
    "amazon.com",
    "bbb.org",
    "tripadvisor.com",
    "mapquest.com",
    "dnb.com",
    "crunchbase.com",
    "g2.com",
    "capterra.com",
    "trustpilot.com",
    "goodfirms.co",
    "alignable.com",
    "manta.com",
    "superpages.com",
    "chamberofcommerce.com",
    "thomasnet.com",
    "kompass.com",
    "citysearch.com",
    "github.com",
    "medium.com",
    "timeout.com",
    "choosechicago.com",
    "chicago.gov",
    "il.gov",
    "britannica.com",
    "wikivoyage.org",
    "ensun.io",
    "customsbrokerindex.com",
    "ship4wd.com",
    "clickpost.ai",
    "themanifest.com",
    "upcity.com",
    "designrush.com",
    "sortlist.com",
}

DISQUALIFIED_TLDS = {".gov", ".edu", ".mil"}

DISQUALIFIED_DOMAIN_KEYWORDS = {
    "directory",
    "yellowpages",
    "brokerindex",
    "companyindex",
    "companiesindex",
    "top10",
    "top100",
    "rankings",
    "agencyranking",
    "freightindex",
    "reviews",
    "listing",
    "listings",
    "finder",
    "jobboard",
    "jobsearch",
}

DISQUALIFIED_PATH_PREFIXES = (
    "/blog",
    "/article",
    "/articles",
    "/search",
    "/ranking",
    "/rankings",
    "/top-",
    "/best-",
    "/categories",
    "/category",
    "/city",
    "/cities",
    "/jobs",
    "/job",
    "/careers",
    "/tag",
    "/tags",
    "/brokers",
    "/broker",
    "/companies",
    "/directory",
    "/directories",
    "/near-me",
    "/locator",
    "/find",
)


class ICPVertical(str, Enum):
    """Target ICP business verticals."""

    LOGISTICS = "logistics"
    REAL_ESTATE = "real_estate"
    BOUTIQUE_AGENCIES = "boutique_agencies"
    ECOMMERCE = "ecommerce"


# Targeted search queries per vertical for finding commercial B2B operators
VERTICAL_QUERIES: dict[ICPVertical, list[str]] = {
    ICPVertical.LOGISTICS: [
        "{location} freight forwarding company",
        "{location} 3PL warehouse logistics",
        "{location} customs broker freight logistics",
        "{location} freight brokerage dispatch",
    ],
    ICPVertical.REAL_ESTATE: [
        "{location} property management company residential commercial",
        "{location} residential property managers leasing",
        "{location} real estate asset management services",
    ],
    ICPVertical.BOUTIQUE_AGENCIES: [
        "{location} boutique digital marketing agency",
        "{location} performance marketing creative agency",
        "{location} branding design studio agency",
    ],
    ICPVertical.ECOMMERCE: [
        "{location} direct to consumer brand headquarters",
        "{location} specialty retail order fulfillment",
    ],
}


class DiscoveredProspect(BaseModel):
    """Data transfer object for a newly discovered candidate lead."""

    company_name: str = Field(..., description="Inferred or extracted company name")
    website_url: str = Field(..., description="Canonical website URL")
    snippet: str = Field(default="", description="Search snippet or description")
    vertical: str = Field(default="", description="Identified ICP vertical")
    source: str = Field(default="duckduckgo", description="Discovery source (duckduckgo / overpass)")
    location: str = Field(default="", description="Target location or region queried")


def normalize_url(url: str) -> str:
    """Normalize and clean a URL to standard scheme and host/path without tracking params."""
    if not url:
        return ""
    clean = url.strip()
    if not clean.startswith(("http://", "https://")):
        clean = f"https://{clean}"

    parsed = urlparse(clean)
    netloc = parsed.netloc.lower()
    netloc = netloc.removeprefix("www.")

    # Reconstruct clean base
    path = parsed.path.rstrip("/")
    if not path:
        path = "/"

    return f"{parsed.scheme}://{netloc}{path}"


def extract_domain(url: str) -> str:
    """Extract root domain without www or subdomains."""
    try:
        parsed = urlparse(url if url.startswith(("http://", "https://")) else f"https://{url}")
        host = parsed.netloc.lower()
        host = host.removeprefix("www.")
        return host
    except (ValueError, AttributeError):
        return ""


def is_disqualified_domain(url: str, custom_disqualified: set[str] | list[str] | None = None) -> bool:
    """Check if the given URL belongs to a directory, social platform, aggregator, or blog/job list."""
    try:
        parsed = urlparse(url if url.startswith(("http://", "https://")) else f"https://{url}")
    except (ValueError, AttributeError):
        return True

    domain = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()

    if not domain:
        return True

    # Check non-commercial TLDs
    for tld in DISQUALIFIED_TLDS:
        if domain.endswith(tld):
            return True

    # Check dynamic user-provided disqualified domains
    if custom_disqualified:
        for cd in custom_disqualified:
            clean_cd = cd.strip().lower().removeprefix("www.")
            if clean_cd and (domain == clean_cd or domain.endswith(f".{clean_cd}")):
                return True

    # Check explicit domain blocklist
    for disqualified in DISQUALIFIED_DOMAINS:
        if domain == disqualified or domain.endswith(f".{disqualified}"):
            return True

    # Check directory keyword heuristics in domain name
    for kw in DISQUALIFIED_DOMAIN_KEYWORDS:
        if kw in domain:
            return True

    # Check disqualified blog/listing/search path prefixes
    for prefix in DISQUALIFIED_PATH_PREFIXES:
        if path.startswith(prefix):
            return True

    return False


def clean_company_name_from_title(title: str, domain: str) -> str:
    """Clean company title string by stripping common boilerplate separators."""
    if not title:
        # Fallback to domain name capitalized
        name_part = domain.split(".")[0]
        return name_part.replace("-", " ").replace("_", " ").title()

    # Split by standard title separators
    parts = re.split(r"\s*[-|–—:•·]\s*", title)
    # Pick the part that looks most like a company name
    for part in parts:
        cleaned = part.strip()
        # Skip generic terms
        lower = cleaned.lower()
        if lower in {"home", "contact us", "about us", "welcome", "official site", "homepage"}:
            continue
        if len(cleaned) >= 2:
            return cleaned

    return parts[0].strip() if parts else domain


def generate_search_queries(
    keyword: str,
    location: str = "",
    language: str = "en",
) -> list[str]:
    """Generate localized search queries based on keyword, location, and target language."""
    loc = location.strip()
    kw = keyword.strip()
    lang = language.lower()

    if lang == "fr":
        if loc:
            return [
                f"{kw} à {loc} contact site web",
                f"entreprise {kw} {loc} coordonnées",
                f"société {kw} {loc} email",
                f"meilleurs {kw} {loc}",
            ]
        return [
            f"entreprise {kw} contact site web",
            f"société {kw} coordonnées email",
        ]
    if lang == "ar":
        if loc:
            return [
                f"شركة {kw} في {loc} تواصل موقع",
                f"مكتب {kw} {loc} بريد الكتروني",
                f"أفضل شركات {kw} في {loc}",
                f"{kw} {loc} خدمات",
            ]
        return [
            f"شركة {kw} تواصل موقع",
            f"خدمات {kw} بريد الكتروني",
        ]
    # Default English
    if loc:
        return [
            f"{kw} in {loc} contact website",
            f"{kw} company {loc} email",
            f"best {kw} services {loc}",
            f"{loc} {kw} business contact",
        ]
    return [
        f"{kw} company contact website",
        f"{kw} business email contact",
    ]


def _sync_ddgs_search(query: str, max_results: int, region: str = "wt-wt") -> list[dict[str, Any]]:
    """Synchronous worker for DuckDuckGo search execution."""
    results: list[dict[str, Any]] = []
    try:
        with DDGS() as ddgs:
            raw_results = ddgs.text(query, region=region, max_results=max_results)
            if raw_results:
                results.extend(raw_results)
            elif hasattr(ddgs, "_text_html"):
                html_res = ddgs._text_html(query, region=region, max_results=max_results)
                if html_res:
                    results.extend(html_res)
    except Exception as exc:  # noqa: BLE001
        logger.debug("DuckDuckGo search debug for '%s': %s", query, exc)
    return results


async def search_duckduckgo(
    query: str,
    max_results: int = 15,
    vertical: str = "",
    location: str = "",
    language: str = "en",
    disqualified_domains: set[str] | list[str] | None = None,
) -> list[DiscoveredProspect]:
    """Asynchronously execute DuckDuckGo search with domain filtering and deduplication.

    Args:
        query: Search keywords or query string.
        max_results: Maximum raw results to fetch before filtering.
        vertical: Optional ICP vertical label.
        location: Optional location query context.
        language: Language code ('en', 'fr', 'ar').
        disqualified_domains: Optional custom set/list of excluded domains.

    Returns:
        list[DiscoveredProspect]: Filtered and structured prospects.
    """
    region_map = {"en": "us-en", "fr": "fr-fr", "ar": "xa-ar"}
    region = region_map.get(language.lower(), "wt-wt")

    try:
        raw_results = await asyncio.to_thread(_sync_ddgs_search, query, max_results, region)
    except Exception as exc:  # noqa: BLE001
        logger.warning("DuckDuckGo search failed for '%s': %s", query, exc)
        raw_results = []

    prospects: list[DiscoveredProspect] = []
    seen_domains: set[str] = set()

    for item in raw_results:
        href = item.get("href", "")
        title = item.get("title", "")
        body = item.get("body", "")

        if not href or is_disqualified_domain(href, custom_disqualified=disqualified_domains):
            continue

        domain = extract_domain(href)
        if not domain or domain in seen_domains:
            continue

        seen_domains.add(domain)
        canonical_url = normalize_url(href)
        company_name = clean_company_name_from_title(title, domain)

        prospects.append(
            DiscoveredProspect(
                company_name=company_name,
                website_url=canonical_url,
                snippet=body,
                vertical=vertical,
                source="duckduckgo",
                location=location,
            )
        )

    return prospects


async def search_overpass(
    city_or_area: str,
    vertical: ICPVertical | str = ICPVertical.LOGISTICS,
    timeout_seconds: int = 25,
    client: httpx.AsyncClient | None = None,
    disqualified_domains: set[str] | list[str] | None = None,
) -> list[DiscoveredProspect]:
    """Search OpenStreetMap via Overpass API for registered business offices in a target city."""
    tag_query = '["office"~"logistics|freight|transport|customs|shipping"]'
    if str(vertical) in (ICPVertical.REAL_ESTATE.value, "real_estate"):
        tag_query = '["office"~"estate_agent|property_management"]'
    elif str(vertical) in (ICPVertical.BOUTIQUE_AGENCIES.value, "boutique_agencies"):
        tag_query = '["office"~"advertising|marketing|consulting"]'
    elif str(vertical) in (ICPVertical.ECOMMERCE.value, "ecommerce"):
        tag_query = '["office"~"it|retail|logistics"]'

    overpass_ql = f"""[out:json][timeout:{timeout_seconds}];
area["name"="{city_or_area}"]->.searchArea;
(
  node{tag_query}(area.searchArea);
  way{tag_query}(area.searchArea);
);
out center tags 30;"""

    prospects: list[DiscoveredProspect] = []
    seen_domains: set[str] = set()

    http = client or httpx.AsyncClient(timeout=timeout_seconds)
    should_close = client is None

    try:
        response = await http.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": overpass_ql},
            headers={"User-Agent": "ClientSearchBot/1.0 (B2B Lead Discovery)"},
        )
        if response.status_code == 200:
            data = response.json()
            elements = data.get("elements", [])
            for el in elements:
                tags = el.get("tags", {})
                name = tags.get("name")
                website = tags.get("website") or tags.get("contact:website") or tags.get("url")

                if not name or not website:
                    continue

                if is_disqualified_domain(website, custom_disqualified=disqualified_domains):
                    continue

                domain = extract_domain(website)
                if not domain or domain in seen_domains:
                    continue

                seen_domains.add(domain)
                prospects.append(
                    DiscoveredProspect(
                        company_name=name,
                        website_url=normalize_url(website),
                        snippet=f"OSM {tags.get('office', 'business')} located in {city_or_area}",
                        vertical=str(vertical),
                        source="overpass",
                        location=city_or_area,
                    )
                )
        else:
            logger.debug("Overpass API returned status %d for %s", response.status_code, city_or_area)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Overpass search failed for %s: %s", city_or_area, exc)
    finally:
        if should_close:
            await http.aclose()

    return prospects


async def discover_prospects(
    vertical: ICPVertical | str = ICPVertical.LOGISTICS,
    location: str = "Chicago",
    max_results: int = 15,
    enable_overpass: bool = True,
    custom_queries: list[str] | None = None,
    delay_between_queries: float = 0.4,
    language: str = "en",
    keywords: list[str] | str | None = None,
    disqualified_domains: set[str] | list[str] | None = None,
) -> list[DiscoveredProspect]:
    """Coordinate multi-engine prospect discovery with intelligent query pacing and early-exit.

    Args:
        vertical: Target business vertical from ICPVertical or custom string.
        location: City, region, or metro area to target.
        max_results: Max target candidate prospects to return.
        enable_overpass: Whether to run concurrent Overpass geo lookup.
        custom_queries: Optional explicit search queries overriding default templates.
        delay_between_queries: Seconds to pause between sequential queries to prevent throttling.
        language: Target search language ('en', 'fr', 'ar').
        keywords: Optional custom search keyword(s) to query.
        disqualified_domains: Optional list/set of excluded domains.

    Returns:
        list[DiscoveredProspect]: Unified, deduplicated list of candidate prospects.
    """
    vert_val = getattr(vertical, "value", str(vertical))
    logger.info("Starting prospect discovery for vertical/keyword='%s', location='%s', language='%s'", keywords or vert_val, location, language)

    queries: list[str] = []
    if custom_queries:
        queries = custom_queries
    elif keywords:
        kw_list = [keywords] if isinstance(keywords, str) else keywords
        for kw in kw_list:
            queries.extend(generate_search_queries(keyword=kw, location=location, language=language))
    else:
        # Fallback to vertical templates or language generator
        if language != "en":
            queries = generate_search_queries(keyword=vert_val, location=location, language=language)
        else:
            templates = VERTICAL_QUERIES.get(vertical, ["{location} {vertical} business contact"])
            queries = [t.format(location=location, vertical=vert_val) for t in templates]

    combined_prospects: list[DiscoveredProspect] = []
    seen_domains: set[str] = set()

    # If Overpass is enabled and vertical is a standard ICPVertical, launch it in background
    overpass_task = None
    if enable_overpass and isinstance(vertical, ICPVertical):
        overpass_task = asyncio.create_task(
            search_overpass(city_or_area=location, vertical=vertical, disqualified_domains=disqualified_domains)
        )

    # Sequentially execute search queries with polite pacing and early exit
    for i, q in enumerate(queries):
        if len(combined_prospects) >= max_results:
            break

        if i > 0 and delay_between_queries > 0:
            await asyncio.sleep(delay_between_queries)

        prospects = await search_duckduckgo(
            query=q,
            max_results=max_results,
            vertical=vert_val,
            location=location,
            language=language,
            disqualified_domains=disqualified_domains,
        )

        for p in prospects:
            domain = extract_domain(p.website_url)
            if domain and domain not in seen_domains:
                seen_domains.add(domain)
                combined_prospects.append(p)
                if len(combined_prospects) >= max_results:
                    break

    # Merge Overpass results if available
    if overpass_task:
        try:
            overpass_results = await overpass_task
            for op in overpass_results:
                domain = extract_domain(op.website_url)
                if domain and domain not in seen_domains:
                    seen_domains.add(domain)
                    combined_prospects.append(op)
                    if len(combined_prospects) >= max_results:
                        break
        except Exception as exc:  # noqa: BLE001
            logger.debug("Overpass background task error: %s", exc)

    logger.info("Discovered %d candidate prospects", len(combined_prospects))
    return combined_prospects
