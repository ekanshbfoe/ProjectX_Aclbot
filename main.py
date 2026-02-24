import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import ChatMemberUpdated, Message
from aiogram.filters import Command

# Import logic from services
from services.links.membership import send_membership_reminder, handle_join_request, is_user_in_chat
from services.securitys.filters import detect_and_delete_ad, send_security_warning, add_to_whitelist, is_admin

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MANDATORY_CHAT_ID = int(os.getenv("MANDATORY_CHAT_ID"))
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", 600))
SUDO_USERS = list(map(int, os.getenv("SUDO_USERS", "").split()))

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_new_message(message: Message):
    """Handles messages in group chats: DELETE Ads first, then warn smartly."""
    if not message.from_user or message.from_user.is_bot:
        return
    
    # 1. ALWAYS delete ad/links first if detected (Silent deletion)
    is_ad = await detect_and_delete_ad(bot, message)
    
    # 2. Check if user is in mandatory hub
    is_member = await is_user_in_chat(bot, MANDATORY_CHAT_ID, message.from_user.id)
    
    if not is_member:
        # Try to send membership reminder (respects its own cooldown)
        sent_membership = await send_membership_reminder(bot, MANDATORY_CHAT_ID, message, COOLDOWN_SECONDS)
        
        # Fallback: If membership reminder was skipped (cooldown) but it WAS an ad,
        # send the security warning instead (respects its own cooldown).
        if not sent_membership and is_ad:
            await send_security_warning(message, COOLDOWN_SECONDS)
    elif is_ad:
        # User IS a member but sent an ad -> normal security warning
        await send_security_warning(message, COOLDOWN_SECONDS)

@dp.message(Command("whitelist"))
async def cmd_whitelist(message: Message):
    """Command to whitelist a user. Usage: /whitelist (reply to user) or /whitelist [user_id]"""
    user_id = message.from_user.id
    
    # Check if sender is Sudo or Admin
    if user_id not in SUDO_USERS and not await is_admin(bot, message.chat.id, user_id):
        return

    target_id = None
    
    # Option 1: Reply to a message
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    # Option 2: Pass ID as argument
    else:
        args = message.text.split()
        if len(args) >= 2:
            try:
                target_id = int(args[1])
            except ValueError:
                pass

    if target_id:
        add_to_whitelist(target_id)
        await message.reply(f"✅ User <code>{target_id}</code> has been whitelisted.", parse_mode="HTML")
        logger.info(f"User {target_id} whitelisted by {user_id}")
    else:
        await message.reply("❌ Usage: Reply to a user with <code>/whitelist</code> or use <code>/whitelist [user_id]</code>", parse_mode="HTML")

@dp.chat_member()
async def handle_chat_member_update(event: ChatMemberUpdated):
    """Handles users joining any group."""
    if event.new_chat_member.status == "member" and event.old_chat_member.status in ["left", "kicked", "restricted"]:
        await handle_join_request(bot, MANDATORY_CHAT_ID, event)

async def main():
    logger.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
