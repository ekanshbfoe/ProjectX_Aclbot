import asyncio
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, InputMediaPhoto, InputMediaVideo, URLInputFile
from aiogram.exceptions import TelegramAPIError

from services.downloader.cache import extract_and_normalize_url, get_media_cache, set_media_cache
from services.downloader.cobalt import fetch_media_from_cobalt

logger = logging.getLogger(__name__)

downloader_router = Router()

# Combined regex for TikTok, Instagram, and Pinterest to trigger the handler
MEDIA_REGEX = r"(?i)(?:https?://)?(?:www\.)?(?:vm\.tiktok\.com|vt\.tiktok\.com|tiktok\.com/@[\w\.-]+/(?:video|photo)|instagram\.com/(?:reels?|p|stories)|pin\.it|pinterest\.com/pin)/[^\s]+"

@downloader_router.message(F.text.regexp(MEDIA_REGEX))
async def handle_media_link(message: Message, bot: Bot):
    """
    Detects media links, validates them, and schedules the download task.
    Wraps execution in asyncio.create_task for non-blocking webhook response.
    """
    text = message.text or ""
    canonical_url, platform = extract_and_normalize_url(text)
    
    if not canonical_url or not platform:
        return
        
    # Schedule the actual processing in the background
    asyncio.create_task(process_download(bot, message, canonical_url, platform))


async def process_download(bot: Bot, message: Message, canonical_url: str, platform: str):
    """
    Core download and upload logic.
    Checks Supabase cache, if miss calls Cobalt API, uploads to Telegram, and caches the new file_ids.
    """
    chat_id = message.chat.id
    
    # Send temporary status message
    try:
        status_msg = await bot.send_message(
            chat_id,
            "⚡ Fetching media...",
            reply_to_message_id=message.message_id
        )
    except TelegramAPIError as e:
        logger.error(f"Failed to send status message: {e}")
        return

    try:
        # 1. Check Supabase Cache
        cached_data = await get_media_cache(canonical_url)
        if cached_data:
            logger.info(f"Cache hit for {canonical_url}")
            file_ids = cached_data.get("file_ids")
            
            if isinstance(file_ids, str):
                # Single video
                await bot.send_video(chat_id, video=file_ids, reply_to_message_id=message.message_id)
            elif isinstance(file_ids, list):
                # Media group (album)
                for i in range(0, len(file_ids), 10):
                    batch = file_ids[i:i+10]
                    # We assume photos for picker cached items, but could be mixed. 
                    # For simplicity, assuming InputMediaPhoto if it was cached as list, 
                    # as Cobalt picker usually means photos (TikTok carousel).
                    # A robust implementation would store type along with file_id in cache.
                    # We will store them as dicts: {"type": "photo", "id": "..."} to be safe.
                    media_group = []
                    for item in batch:
                        if isinstance(item, dict) and item.get("type") == "video":
                            media_group.append(InputMediaVideo(media=item["id"]))
                        elif isinstance(item, dict) and item.get("type") == "photo":
                            media_group.append(InputMediaPhoto(media=item["id"]))
                        else:
                            # Fallback for plain strings
                            media_group.append(InputMediaPhoto(media=item))
                    
                    if media_group:
                        await bot.send_media_group(chat_id, media=media_group, reply_to_message_id=message.message_id)
            
            await bot.delete_message(chat_id, status_msg.message_id)
            return

        # 2. Cache Miss: Fetch from Cobalt
        logger.info(f"Cache miss for {canonical_url}. Calling Cobalt API.")
        media_data = await fetch_media_from_cobalt(canonical_url)
        
        if not media_data:
            await bot.edit_message_text("❌ Failed to fetch media.", chat_id=chat_id, message_id=status_msg.message_id)
            return

        new_cache_data = None
        
        # 3. Upload to Telegram
        if media_data["type"] == "video":
            url = media_data["url"]
            sent_msg = await bot.send_video(
                chat_id,
                video=URLInputFile(url),
                reply_to_message_id=message.message_id
            )
            new_cache_data = sent_msg.video.file_id
            
        elif media_data["type"] == "picker":
            items = media_data["items"]
            all_sent_items = []
            
            # Telegram limits media groups to 10 items
            for i in range(0, len(items), 10):
                batch = items[i:i+10]
                media_group = []
                
                for item in batch:
                    item_url = item.get("url")
                    item_type = item.get("type", "photo") # defaults to photo
                    if item_type == "video":
                        media_group.append(InputMediaVideo(media=URLInputFile(item_url)))
                    else:
                        media_group.append(InputMediaPhoto(media=URLInputFile(item_url)))
                        
                if media_group:
                    try:
                        sent_msgs = await bot.send_media_group(
                            chat_id, 
                            media=media_group, 
                            reply_to_message_id=message.message_id
                        )
                        # Extract file_ids
                        for m in sent_msgs:
                            if m.photo:
                                all_sent_items.append({"type": "photo", "id": m.photo[-1].file_id})
                            elif m.video:
                                all_sent_items.append({"type": "video", "id": m.video.file_id})
                    except Exception as e:
                        logger.error(f"Error sending media group batch: {e}")
            
            if all_sent_items:
                new_cache_data = all_sent_items
        
        # 4. Save to Cache
        if new_cache_data:
            await set_media_cache(canonical_url, platform, new_cache_data)
            await bot.delete_message(chat_id, status_msg.message_id)
        else:
            await bot.edit_message_text("⚠️ Could not upload media to Telegram.", chat_id=chat_id, message_id=status_msg.message_id)

    except Exception as e:
        logger.error(f"Error processing download for {canonical_url}: {e}")
        try:
            await bot.edit_message_text("❌ An error occurred during download.", chat_id=chat_id, message_id=status_msg.message_id)
        except:
            pass
