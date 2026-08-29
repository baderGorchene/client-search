"""Supabase asynchronous client initialization and lifecycle management."""

import logging

from supabase import AsyncClient, create_async_client

from config.settings import settings

logger = logging.getLogger(__name__)

_supabase_client: AsyncClient | None = None
_cached_url: str | None = None
_cached_key: str | None = None


async def get_supabase_client(
    url: str | None = None,
    key: str | None = None,
) -> AsyncClient:
    """Get or initialize the shared asynchronous Supabase client instance.

    Args:
        url: Optional Supabase project URL override. Defaults to settings.SUPABASE_URL.
        key: Optional Supabase API key override. Defaults to settings.SUPABASE_KEY.

    Returns:
        AsyncClient: Connected Supabase async client instance.

    Raises:
        ValueError: If SUPABASE_URL or SUPABASE_KEY are not configured.
    """
    global _supabase_client, _cached_url, _cached_key

    resolved_url = url or settings.SUPABASE_URL
    resolved_key = key or settings.SUPABASE_KEY

    if not resolved_url or not resolved_key:
        raise ValueError(
            "Supabase credentials not found. Please set SUPABASE_URL and SUPABASE_KEY "
            "in your .env file or pass them explicitly."
        )

    # Return cached client if config matches
    if (
        _supabase_client is not None
        and _cached_url == resolved_url
        and _cached_key == resolved_key
    ):
        return _supabase_client

    logger.debug("Initializing new Async Supabase client for %s", resolved_url)
    _supabase_client = await create_async_client(resolved_url, resolved_key)
    _cached_url = resolved_url
    _cached_key = resolved_key

    return _supabase_client


async def reset_supabase_client() -> None:
    """Reset the cached Supabase client instance, useful for tests or reconfiguration."""
    global _supabase_client, _cached_url, _cached_key
    _supabase_client = None
    _cached_url = None
    _cached_key = None
