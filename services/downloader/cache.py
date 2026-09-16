import os
import re
import logging
import aiohttp
import datetime
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)

# Regex patterns
TIKTOK_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?(?:v\.tiktok\.com/|vm\.tiktok\.com/|vt\.tiktok\.com/|tiktok\.com/@[\w\.-]+/(?:video|photo)/)[^\s]+")
INSTAGRAM_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/(?:reels?|p|stories)/[^\s/]+")
PINTEREST_PATTERN = re.compile(r"(?:https?://)?(?:pin\.it/|(?:[\w-]+\.)?pinterest\.com/pin/)[^\s/]+")

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
        netloc = parsed.netloc
        if platform == "pinterest" and netloc.endswith("pinterest.com"):
            netloc = "pinterest.com"
        canonical_url = urlunparse((scheme, netloc, parsed.path, "", "", ""))
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
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        logger.warning("Supabase credentials missing, skipping cache read.")
        return None

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{supabase_url}/rest/v1/media_cache"
            params = {
                "select": "file_ids,platform,created_at",
                "canonical_url": f"eq.{canonical_url}",
                "limit": "1"
            }
            async with session.get(url, headers=headers, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data:
                        cache_entry = data[0]
                        if cache_entry.get("platform") == "instagram" and "/stories/" in canonical_url:
                            created_at = cache_entry.get("created_at")
                            if created_at:
                                try:
                                    dt = datetime.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                                    if datetime.datetime.now(datetime.timezone.utc) - dt > datetime.timedelta(hours=24):
                                        logger.info(f"Cache expired for story {canonical_url}")
                                        return None
                                except Exception as e:
                                    logger.error(f"Error parsing created_at: {e}")
                        return cache_entry
                else:
                    text = await response.text()
                    logger.error(f"Supabase cache get error {response.status}: {text}")
    except Exception as e:
        logger.error(f"Supabase cache get exception for {canonical_url}: {e}")
    return None

async def set_media_cache(canonical_url: str, platform: str, file_ids: list | str):
    """
    Upserts the media file IDs into the Supabase cache.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        logger.warning("Supabase credentials missing, skipping cache write.")
        return
        
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    
    payload = {
        "canonical_url": canonical_url,
        "platform": platform,
        "file_ids": file_ids
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{supabase_url}/rest/v1/media_cache?on_conflict=canonical_url"
            async with session.post(url, headers=headers, json=payload, timeout=10) as response:
                if response.status not in (200, 201, 204):
                    text = await response.text()
                    logger.error(f"Supabase cache set error {response.status}: {text}")
    except Exception as e:
        logger.error(f"Supabase cache set exception for {canonical_url}: {e}")
