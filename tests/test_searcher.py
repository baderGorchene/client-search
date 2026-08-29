"""Tests for DuckDuckGo and Overpass zero-cost discovery engine."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from discovery.searcher import (
    DiscoveredProspect,
    ICPVertical,
    clean_company_name_from_title,
    discover_prospects,
    extract_domain,
    is_disqualified_domain,
    normalize_url,
    search_duckduckgo,
    search_overpass,
)


def test_url_normalization():
    """Verify URL normalization strips tracking, www, and fixes schemes."""
    assert normalize_url("http://www.example.com/about/") == "http://example.com/about"
    assert normalize_url("acmelogistics.com") == "https://acmelogistics.com/"
    assert normalize_url("https://www.speedy.io/contact") == "https://speedy.io/contact"
    assert normalize_url("") == ""


def test_domain_extraction():
    """Verify domain extraction logic."""
    assert extract_domain("https://www.example.com/path") == "example.com"
    assert extract_domain("http://sub.domain.org/test") == "sub.domain.org"
    assert extract_domain("invalid-url") == "invalid-url"


def test_disqualified_domains():
    """Verify aggregator and social platforms are flagged as disqualified."""
    assert is_disqualified_domain("https://www.yelp.com/biz/acme") is True
    assert is_disqualified_domain("https://linkedin.com/company/speedy") is True
    assert is_disqualified_domain("https://yellowpages.com/chicago/freight") is True
    assert is_disqualified_domain("https://www.facebook.com/trucking") is True
    assert is_disqualified_domain("https://realfreightlogistics.com") is False
    assert is_disqualified_domain("https://premierpropertymgmt.io") is False


def test_clean_company_name_from_title():
    """Verify company name cleaning from raw search titles."""
    assert clean_company_name_from_title("Apex Logistics - Freight Forwarding & Supply Chain", "apexlogistics.com") == "Apex Logistics"
    assert clean_company_name_from_title("Home | Horizon Property Management", "horizonpm.com") == "Horizon Property Management"
    assert clean_company_name_from_title("", "fast-freight-express.com") == "Fast Freight Express"


@pytest.mark.asyncio
async def test_search_duckduckgo_filtering():
    """Verify that search_duckduckgo filters disqualified domains and deduplicates."""
    mock_ddg_results = [
        {"title": "Apex Freight - Freight Solutions", "href": "https://www.apexlogistics.com/about", "body": "Logistics and dispatch."},
        {"title": "Apex Freight - Contact Us", "href": "https://apexlogistics.com/contact", "body": "Duplicate domain link."},
        {"title": "Top 10 Freight on Yelp", "href": "https://www.yelp.com/biz/freight-123", "body": "Directory listing."},
        {"title": "Horizon Logistics | Official", "href": "https://horizonlogistics.net", "body": "Full service 3PL."},
    ]

    with patch("discovery.searcher._sync_ddgs_search", return_value=mock_ddg_results):
        prospects = await search_duckduckgo(query="chicago freight", vertical="logistics", location="Chicago")

        assert len(prospects) == 2
        assert prospects[0].company_name == "Apex Freight"
        assert prospects[0].website_url == "https://apexlogistics.com/about"
        assert prospects[0].source == "duckduckgo"
        assert prospects[1].company_name == "Horizon Logistics"
        assert prospects[1].website_url == "https://horizonlogistics.net/"


@pytest.mark.asyncio
async def test_search_duckduckgo_error_handling():
    """Verify graceful handling when DuckDuckGo raises an exception."""
    with patch("discovery.searcher._sync_ddgs_search", side_effect=Exception("DDGS RateLimit")):
        prospects = await search_duckduckgo(query="test query")
        assert prospects == []


@pytest.mark.asyncio
async def test_search_overpass_success():
    """Verify search_overpass parses OSM JSON elements properly."""
    mock_osm_response = {
        "elements": [
            {
                "tags": {
                    "name": "Midwest Freight Hub",
                    "office": "logistics",
                    "website": "https://www.midwestfreighthub.com",
                }
            },
            {
                "tags": {
                    "name": "No Website Logistics",
                    "office": "logistics",
                }
            },
            {
                "tags": {
                    "name": "Directory on Yellowpages",
                    "office": "logistics",
                    "website": "https://yellowpages.com/item",
                }
            },
            {
                "tags": {
                    "name": "Midwest Logistics duplicate",
                    "office": "logistics",
                    "contact:website": "https://midwestfreighthub.com/contact",
                }
            },
        ]
    }

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_osm_response

    mock_client.post = MagicMock(return_value=mock_resp)

    # Make post an async mock
    async def async_post(*args, **kwargs):
        return mock_resp

    mock_client.post = async_post

    prospects = await search_overpass(
        city_or_area="Chicago",
        vertical=ICPVertical.LOGISTICS,
        client=mock_client,
    )

    assert len(prospects) == 1
    assert prospects[0].company_name == "Midwest Freight Hub"
    assert prospects[0].website_url == "https://midwestfreighthub.com/"
    assert prospects[0].source == "overpass"
    assert prospects[0].location == "Chicago"


@pytest.mark.asyncio
async def test_search_overpass_failure():
    """Verify search_overpass handles HTTP errors gracefully."""
    mock_client = MagicMock()

    async def async_post_error(*args, **kwargs):
        raise httpx.ConnectTimeout("Connection timeout")

    mock_client.post = async_post_error

    prospects = await search_overpass(
        city_or_area="Chicago",
        client=mock_client,
    )
    assert prospects == []


@pytest.mark.asyncio
async def test_discover_prospects_aggregation():
    """Verify discover_prospects combines results across queries and respects limits."""
    mock_prospects_1 = [
        DiscoveredProspect(company_name="Alpha", website_url="https://alpha.com"),
        DiscoveredProspect(company_name="Beta", website_url="https://beta.com"),
    ]
    mock_prospects_2 = [
        DiscoveredProspect(company_name="Alpha Duplicate", website_url="https://alpha.com/contact"),
        DiscoveredProspect(company_name="Gamma", website_url="https://gamma.com"),
    ]

    with patch("discovery.searcher.search_duckduckgo", side_effect=[mock_prospects_1, mock_prospects_2]), \
         patch("discovery.searcher.search_overpass", return_value=[]):

        results = await discover_prospects(
            vertical=ICPVertical.LOGISTICS,
            location="Dallas",
            max_results=2,
            enable_overpass=True,
            custom_queries=["query1", "query2"],
        )

        assert len(results) == 2
        assert results[0].company_name == "Alpha"
        assert results[1].company_name == "Beta"
