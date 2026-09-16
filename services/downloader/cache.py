import re
import logging
from urllib.parse import urlparse, urlunparse

from services.requests.handler import _get_db

logger = logging.getLogger(__name__)

# Regex patterns
TIKTOK_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?(?:vm\.tiktok\.com/|vt\.tiktok\.com/|tiktok\.com/@[\w\.-]+/(?:video|photo)/)[^\s]+")
INSTAGRAM_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/(?:reels?|p|stories)/[^\s/]+")
PINTEREST_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?(?:pin\.it/|pinterest\.com/pin/)[^\s/]+")

def extract_and_normalize_url(text: str) -> tuple[str | None, str | None]:
    """
    Extracts the first supported media link from text and normalizes it.
    Returns (canonical_url, platform) or (None, None).
    """
    # 1. Detect URL and Platform
    url = None
    platform = None

    if match := TIKTOK_PATTERN.search(text):
        url = match.group(0)
        platform = "tiktok"
    elif match := INSTAGRAM_PATTERN.search(text):
        url = match.group(0)
        platform = "instagram"
    elif match := PINTEREST_PATTERN.search(text):
        url = match.group(0)
        platform = "pinterest"

    if not url:
        return None, None

    # 2. Normalize: Strip tracking query parameters
    try:
        parsed = urlparse(url)
        # Reconstruct URL without query and fragment, ensuring https
        scheme = parsed.scheme if parsed.scheme else "https"
        canonical_url = urlunparse((scheme, parsed.netloc, parsed.path, "", "", ""))
        # For Pinterest pin.it or tiktok vm.tiktok.com, the path is enough
        return canonical_url, platform
    except Exception as e:
        logger.error(f"Error normalizing URL {url}: {e}")
        return None, None

async def get_media_cache(canonical_url: str):
    """
    Queries the media_cache table in Supabase for the canonical_url.
    Returns a dict with 'file_ids' and 'platform' if found, else None.
    """
    try:
        db = _get_db()
        result = (
            db.table("media_cache")
            .select("file_ids, platform")
            .eq("canonical_url", canonical_url)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]
    except Exception as e:
        logger.error(f"Supabase cache get error for {canonical_url}: {e}")
    return None

async def set_media_cache(canonical_url: str, platform: str, file_ids: list | str):
    """
    Upserts the media file IDs into the Supabase cache.
    """
    try:
        db = _get_db()
        # file_ids is stored as JSONB, so it can be a list or a string.
        db.table("media_cache").upsert({
            "canonical_url": canonical_url,
            "platform": platform,
            "file_ids": file_ids
        }, on_conflict="canonical_url").execute()
    except Exception as e:
        logger.error(f"Supabase cache set error for {canonical_url}: {e}")
