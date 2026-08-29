"""Discovery package for search and web extraction."""

from discovery.searcher import (
    DiscoveredProspect,
    ICPVertical,
    discover_prospects,
    search_duckduckgo,
    search_overpass,
)

__all__ = [
    "DiscoveredProspect",
    "ICPVertical",
    "discover_prospects",
    "search_duckduckgo",
    "search_overpass",
]
