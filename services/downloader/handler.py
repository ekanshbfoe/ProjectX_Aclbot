import asyncio
import logging
import aiohttp
import os

from aiogram import Router, F, Bot
from aiogram.types import Message, InputMediaPhoto, InputMediaVideo, BufferedInputFile
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest

from services.downloader.cache import extract_and_normalize_url, get_media_cache, set_media_cache
from services.downloader.cobalt import fetch_media_from_cobalt

logger = logging.getLogger(__name__)

downloader_router = Router()
download_semaphore = asyncio.Semaphore(3)

async def get_media_type(url: str) -> bool:
    """Returns True if the URL points to an image, False otherwise."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, timeout=10) as resp:
                content_type = resp.headers.get("Content-Type", "")
                return "image/" in content_type
    except Exception as e:
        logger.warning(f"HEAD request failed for {url}: {e}")
        return False

# Combined regex for TikTok, Instagram, and Pinterest to trigger the handler
MEDIA_REGEX = r"(?i)(?:https?://)?(?:(?:www\.)?(?:v\.tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com|tiktok\.com/@[\w\.-]+/(?:video|photo)|instagram\.com/(?:reels?|p|stories))|pin\.it|(?:[\w-]+\.)?pinterest\.com/pin)/[^\s]+"

@downloader_router.message(F.text.regexp(MEDIA_REGEX))
async def handle_media_link(message: Message, bot: Bot):
    """
    Detects media links, validates them, and schedules the download task.
    Wraps execution in asyncio.create_task for non-blocking webhook response.
    """
    text = message.text or ""
    
    if "/reels/audio/" in text or "/audio/" in text:
        await bot.send_message(
            chat_id=message.chat.id, 
            text="❌ That's an audio page link. Please send a direct link to a specific Reel.", 
            reply_to_message_id=message.message_id
        )
        return
        
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
        async with download_semaphore:
            media_data = await fetch_media_from_cobalt(canonical_url)
        
        if not media_data:
            await bot.edit_message_text("❌ Failed to fetch media.", chat_id=chat_id, message_id=status_msg.message_id)
            return

        new_cache_data = None
        
        # 3. Upload to Telegram
        if media_data.get("type") == "error":
            if media_data.get("text") == "error.api.fetch.empty":
                await bot.edit_message_text(
                    "❌ Failed to fetch media. The post might be private, deleted, or a restricted carousel.",
                    chat_id=chat_id,
                    message_id=status_msg.message_id
                )
            else:
                await bot.edit_message_text(
                    f"❌ Failed to fetch media: {media_data.get('text')}",
                    chat_id=chat_id,
                    message_id=status_msg.message_id
                )
            return

        elif media_data["type"] == "video":
            url = media_data["url"]
            is_photo = await get_media_type(url)
            
            try:
                try:
                    if is_photo:
                        sent_msg = await bot.send_photo(
                            chat_id,
                            photo=url,
                            reply_to_message_id=message.message_id
                        )
                    else:
                        sent_msg = await bot.send_video(
                            chat_id,
                            video=url,
                            reply_to_message_id=message.message_id
                        )
                except TelegramBadRequest:
                    logger.info(f"Direct URL upload failed for {url}. Falling back to physical download.")
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as resp:
                            if resp.status == 200:
                                content_length = int(resp.headers.get("Content-Length", 0))
                                if content_length > 52428800:
                                    await bot.send_message(chat_id, "❌ File is too large for Telegram (Max 50MB).", reply_to_message_id=message.message_id)
                                    raise Exception("File exceeds 50MB limit")
                                    
                                file_data = await resp.read()
                                file_name = "photo.jpg" if is_photo else "video.mp4"
                                
                                input_file = BufferedInputFile(file_data, filename=file_name)
                                if is_photo:
                                    sent_msg = await bot.send_photo(chat_id, photo=input_file, reply_to_message_id=message.message_id)
                                else:
                                    sent_msg = await bot.send_video(chat_id, video=input_file, reply_to_message_id=message.message_id)
                            else:
                                raise Exception(f"Fallback download failed with status {resp.status}")
                    
                if sent_msg.photo:
                    new_cache_data = sent_msg.photo[-1].file_id
                elif sent_msg.video:
                    new_cache_data = sent_msg.video.file_id
                else:
                    new_cache_data = None
            except Exception as e:
                logger.error(f"Error sending media: {e}")
                await bot.edit_message_text("❌ Failed to send media.", chat_id=chat_id, message_id=status_msg.message_id)
                return
            
        elif media_data["type"] == "picker":
            items = media_data["items"]
            all_sent_items = []
            
            # Telegram limits media groups to 10 items
            for i in range(0, len(items), 10):
                batch = items[i:i+10]
                media_group = []
                
                urls = [item.get("url") for item in batch]
                is_photo_list = await asyncio.gather(*(get_media_type(u) for u in urls))
                
                for item, is_photo in zip(batch, is_photo_list):
                    item_url = item.get("url")
                    if is_photo:
                        media_group.append(InputMediaPhoto(media=item_url))
                    else:
                        media_group.append(InputMediaVideo(media=item_url))
                        
                if media_group:
                    try:
                        try:
                            sent_msgs = await bot.send_media_group(
                                chat_id, 
                                media=media_group, 
                                reply_to_message_id=message.message_id
                            )
                        except TelegramBadRequest:
                            logger.info("Direct media group upload failed. Falling back to physical download.")
                            fallback_media_group = []
                            async with aiohttp.ClientSession() as session:
                                for j, (item, is_photo) in enumerate(zip(batch, is_photo_list)):
                                    item_url = item.get("url")
                                    async with session.get(item_url) as resp:
                                        if resp.status == 200:
                                            content_length = int(resp.headers.get("Content-Length", 0))
                                            if content_length > 52428800:
                                                await bot.send_message(chat_id, "❌ File is too large for Telegram (Max 50MB).", reply_to_message_id=message.message_id)
                                                raise Exception("File exceeds 50MB limit")
                                                
                                            file_data = await resp.read()
                                            file_name = f"photo_{j}.jpg" if is_photo else f"video_{j}.mp4"
                                            
                                            input_file = BufferedInputFile(file_data, filename=file_name)
                                            if is_photo:
                                                fallback_media_group.append(InputMediaPhoto(media=input_file))
                                            else:
                                                fallback_media_group.append(InputMediaVideo(media=input_file))
                                        else:
                                            logger.error(f"Fallback download failed for {item_url} with status {resp.status}")
                            if fallback_media_group:
                                sent_msgs = await bot.send_media_group(
                                    chat_id, 
                                    media=fallback_media_group, 
                                    reply_to_message_id=message.message_id
                                )
                            else:
                                raise Exception("All fallback downloads failed.")
                                
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
            try:
                await set_media_cache(canonical_url, platform, new_cache_data)
            except Exception as e:
                logger.error(f"Cache save exception ignored after delivery: {e}")
            
            try:
                await bot.delete_message(chat_id, status_msg.message_id)
            except:
                pass
        else:
            await bot.edit_message_text("⚠️ Could not upload media to Telegram.", chat_id=chat_id, message_id=status_msg.message_id)

    except Exception as e:
        logger.error(f"Error processing download for {canonical_url}: {e}")
        try:
            await bot.edit_message_text("❌ The extraction system is currently overloaded or the link is invalid. Please try again shortly.", chat_id=chat_id, message_id=status_msg.message_id)
        except:
            pass
            
        sudo_users_env = os.getenv("SUDO_USERS", "")
        if sudo_users_env:
            for sudo_id_str in sudo_users_env.split():
                try:
                    sudo_id = int(sudo_id_str)
                    await bot.send_message(sudo_id, f"⚠️ **Downloader Crash**\n**URL:** {canonical_url}\n**Error:** {str(e)}")
                except Exception as sudo_e:
                    logger.error(f"Failed to send crash report to sudo {sudo_id_str}: {sudo_e}")
