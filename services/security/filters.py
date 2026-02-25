import logging
import re
import time
from aiogram import Bot, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

# Regex for Telegram links (matches t.me/, telegram.me/, etc.)
# Covers: t.me/username, t.me/+invite, t.me/joinchat/xxx, telegram.me/..., telegram.dog/...
TG_LINK_PATTERN = re.compile(r"(t\.me|telegram\.me|telegram\.dog)(/\+[a-zA-Z0-9_-]+|/joinchat/[a-zA-Z0-9_-]+|/[a-zA-Z0-9_]+)")

# In-memory whitelist: {user_id}
whitelisted_users = set()

async def is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Checks if a user is an admin in the chat."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

async def detect_and_delete_ad(bot: Bot, message: Message) -> bool:
    """Detects if a message is an ad/link and deletes it. Returns True if ad detected."""
    user = message.from_user
    if not user or user.is_bot:
        return False

    # 1. Skip if sender is an Admin or Whitelisted
    if await is_admin(bot, message.chat.id, user.id) or user.id in whitelisted_users:
        logger.debug(f"Skipping filter for admin/whitelisted user {user.id}")
        return False

    is_ad = False
    
    # 2. Check for Channel Forwards (legacy field)
    if message.forward_from_chat and message.forward_from_chat.type == "channel":
        is_ad = True
        logger.info(f"Detected channel forward from {user.id} (forward_from_chat)")

    # 3. Check for Channel Forwards (newer API: forward_origin)
    if not is_ad and hasattr(message, 'forward_origin') and message.forward_origin:
        origin = message.forward_origin
        # forward_origin can be of type MessageOriginChannel
        if hasattr(origin, 'type') and origin.type == "channel":
            is_ad = True
            logger.info(f"Detected channel forward from {user.id} (forward_origin)")

    # 4. Check for Links in text or caption
    text_to_check = (message.text or "") + (message.caption or "")
    if not is_ad and TG_LINK_PATTERN.search(text_to_check):
        is_ad = True
        logger.info(f"Detected TG link from {user.id}")

    # 5. Check for URL entities (text_link, url types)
    if not is_ad:
        entities = (message.entities or []) + (message.caption_entities or [])
        for entity in entities:
            if entity.type in ("url", "text_link"):
                url_text = ""
                if entity.type == "text_link" and entity.url:
                    url_text = entity.url
                elif entity.type == "url" and message.text:
                    url_text = message.text[entity.offset:entity.offset + entity.length]
                if TG_LINK_PATTERN.search(url_text):
                    is_ad = True
                    logger.info(f"Detected TG link in entity from {user.id}")
                    break

    if is_ad:
        try:
            await message.delete()
            logger.info(f"Deleted ad/link from {user.id}")
        except Exception as e:
            logger.warning(f"Could not delete message from {user.id}: {e}")
        return True

    return False

# Cooldown for security warnings to avoid double-spamming with join reminders
security_cooldown = {}

async def send_security_warning(message: Message, cooldown_seconds: int):
    """Sends a friendly security warning with its own cooldown."""
    user = message.from_user
    current_time = time.time()
    
    last_sent = security_cooldown.get(user.id, 0)
    if current_time - last_sent < cooldown_seconds:
        return

    # Check reason (re-detecting is fine for localized logic)
    reason = "forwarding channel messages" if message.forward_from_chat else "sending external links"
    
    try:
        # Style 2: Elegant & Minimalist
        warning_text = (
            f"✨ <b>Security Notice</b>\n\n"
            f"Hello {user.mention_html()}! For a cleaner chat experience, "
            f"we don’t allow {reason} here.\n\n"
            f"📍 <b>Note</b>: <i>External content removed.</i>\n\n"
            f"<b>Enjoy the conversation!</b> 🥂"
        )
        
        # Create Inline Button for Support
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👨‍💻 Contact Support", url="https://t.me/OceanHave")]
        ])
        
        await message.answer(warning_text, parse_mode="HTML", reply_markup=keyboard)
        security_cooldown[user.id] = current_time
    except Exception as e:
        logger.error(f"Failed to send security warning: {e}")

def add_to_whitelist(user_id: int):
    whitelisted_users.add(user_id)

def remove_from_whitelist(user_id: int):
    whitelisted_users.discard(user_id)

def get_whitelisted_users():
    return list(whitelisted_users)