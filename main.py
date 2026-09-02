import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import ChatMemberUpdated, Message, CallbackQuery
from aiogram.filters import Command

# Import logic from services
from services.links.membership import send_membership_reminder, handle_join_request, is_user_in_chat
from services.security.filters import detect_and_delete_ad, send_security_warning, add_to_whitelist, is_admin
from services.requests.handler import handle_request_command, handle_status_callback, handle_admin_action, init_supabase
from keep_alive import keep_alive

# Start Keep Alive
keep_alive()

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MANDATORY_CHAT_ID = int(os.getenv("MANDATORY_CHAT_ID"))
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", 600))
SUDO_USERS = list(map(int, os.getenv("SUDO_USERS", "").split()))
REQUEST_CHANNEL_ID = int(os.getenv("REQUEST_CHANNEL_ID", 0))

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# ── #request handler (must be registered BEFORE the catch-all group handler) ──
@dp.message(F.chat.type.in_({"group", "supergroup"}) & F.text.startswith("#request"))
async def handle_request_message(message: Message):
    """Intercepts #request commands in group chats."""
    if not message.from_user or message.from_user.is_bot:
        return
    if not REQUEST_CHANNEL_ID:
        logger.warning("REQUEST_CHANNEL_ID not set. Ignoring #request.")
        return
    await handle_request_command(bot, message, REQUEST_CHANNEL_ID)

# ── Callback: View Status ──
@dp.callback_query(F.data.startswith("req_status:"))
async def on_status_callback(callback_query: CallbackQuery):
    await handle_status_callback(bot, callback_query)

# ── Callback: Admin Actions (done / reject / avail / cancel) ──
@dp.callback_query(F.data.startswith("req_done:") | F.data.startswith("req_reject:") | F.data.startswith("req_avail:") | F.data.startswith("req_cancel:"))
async def on_admin_action_callback(callback_query: CallbackQuery):
    await handle_admin_action(bot, callback_query, REQUEST_CHANNEL_ID)

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
    """Handles users joining any group (except the Request Channel)."""
    # Skip the Request Channel — no membership reminder there
    if REQUEST_CHANNEL_ID and event.chat.id == REQUEST_CHANNEL_ID:
        return
    if event.new_chat_member.status == "member" and event.old_chat_member.status in ["left", "kicked", "restricted"]:
        await handle_join_request(bot, MANDATORY_CHAT_ID, event)

async def main():
    logger.info("Bot is starting...")
    # Initialize Supabase for the request feature
    if REQUEST_CHANNEL_ID:
        try:
            init_supabase()
            logger.info("Request feature enabled.")
        except Exception as e:
            logger.error(f"Failed to init Supabase (request feature disabled): {e}")
    else:
        logger.warning("REQUEST_CHANNEL_ID not set. Request feature disabled.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")