import time
import logging
from aiogram import Bot, types
from aiogram.types import Message, ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

# Cooldown cache: {user_id: last_notification_time}
cooldown_cache = {}

async def is_user_in_chat(bot: Bot, mandatory_chat_id: int, user_id: int) -> bool:
    """Checks if a user is a member of the mandatory chat."""
    try:
        member = await bot.get_chat_member(chat_id=mandatory_chat_id, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Error checking membership for {user_id}: {e}")
        return False

async def send_membership_reminder(bot: Bot, mandatory_chat_id: int, message: Message, cooldown_seconds: int) -> bool:
    """Sends a public reply reminder to the user if they are not in the mandatory chat.
    Returns: True if a reminder was sent, False otherwise.
    """
    user = message.from_user
    user_id = user.id
    current_time = time.time()

    # Check cooldown
    last_sent = cooldown_cache.get(user_id, 0)
    if current_time - last_sent < cooldown_seconds:
        return False

    # User not in chat, check status
    if not await is_user_in_chat(bot, mandatory_chat_id, user_id):
        try:
            chat_info = await bot.get_chat(mandatory_chat_id)
            invite_link = chat_info.invite_link or f"https://t.me/c/{str(mandatory_chat_id)[4:]}"
            
            # Style 1: Neon Modern
            text = (
                f"🚀 <b>Hey there, {user.mention_html()}!</b>\n\n"
                f"To unlock the chat and start vibing with the community, "
                f"you need to be a member of our main hub.\n\n"
                f"🔘 <i>Click the button below to join!</i>"
            )
            
            # Create inline button
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 Join Official Channel", url=invite_link)]
            ])
            
            try:
                # Try to reply to the message
                await message.reply(text, parse_mode="HTML", reply_markup=keyboard)
            except Exception:
                # Fallback: Send a new message if the original was deleted (e.g. by security filter)
                await bot.send_message(chat_id=message.chat.id, text=text, parse_mode="HTML", reply_markup=keyboard)
                
            cooldown_cache[user_id] = current_time
            logger.info(f"Sent reminder to {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send reminder to {user_id}: {e}")
    
    return False

async def handle_join_request(bot: Bot, mandatory_chat_id: int, event: ChatMemberUpdated):
    """Handles users joining a group and reminds them to join the mandatory chat."""
    user = event.from_user
    if user.is_bot:
        return

    if not await is_user_in_chat(bot, mandatory_chat_id, user.id):
        try:
            chat_info = await bot.get_chat(mandatory_chat_id)
            invite_link = chat_info.invite_link or f"https://t.me/c/{str(mandatory_chat_id)[4:]}"
            
            # Style 1: Neon Modern
            text = (
                f"✨ <b>Welcome {user.mention_html()}!</b>\n\n"
                f"Glad to have you here! Before you start chatting, "
                f"please make sure to join our mandatory channel below. 🚀"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔗 Join Channel Now", url=invite_link)]
            ])
            
            await bot.send_message(chat_id=event.chat.id, text=text, parse_mode="HTML", reply_markup=keyboard)
            cooldown_cache[user.id] = time.time()
            logger.info(f"Sent join reminder to {user.id}")
        except Exception as e:
            logger.error(f"Failed to send join reminder to {user.id}: {e}")