import os
import aiohttp
import logging

logger = logging.getLogger(__name__)

async def fetch_media_from_cobalt(url: str) -> dict | None:
    """
    Calls the Cobalt API to extract direct media URLs.
    Returns a dictionary with parsed response or None on failure.
    """
    cobalt_url = os.getenv("COBALT_API_URL", "https://cobalt-api-0syi.onrender.com/")
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    payload = {
        "url": url
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(cobalt_url, headers=headers, json=payload, timeout=30) as response:
                try:
                    data = await response.json()
                except Exception:
                    data = {}
                
                if data.get("status") == "error":
                    return {"type": "error", "text": data.get("text", "")}
                
                if response.status != 200:
                    text = await response.text()
                    logger.error(f"Cobalt API returned {response.status}: {text}")
                    return None
                
                status = data.get("status", "")
                
                # Cobalt v10 response structure
                if "picker" in data or status == "picker":
                    return {
                        "type": "picker",
                        "items": data.get("picker", [])
                    }
                elif "url" in data or status in ("tunnel", "redirect", "stream", "success"):
                    return {
                        "type": "video",  # Assume video by default for direct links
                        "url": data.get("url")
                    }
                else:
                    logger.warning(f"Unknown Cobalt response format for {url}: {data}")
                    return None
                    
    except Exception as e:
        logger.error(f"Cobalt API request failed for {url}: {e}")
        return None
