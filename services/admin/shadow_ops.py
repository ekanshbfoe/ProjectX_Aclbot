import logging
import re
from datetime import datetime, timedelta
from aiogram import Router, Bot, F
from aiogram.types import Message, ChatPermissions
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from services.security.filters import IsSudo

logger = logging.getLogger(__name__)
shadow_router = Router(name="shadow_ops")

def _parse_duration(text: str) -> int | None:
    """Parses 'm', 'h', 'd' into seconds."""
    match = re.match(r'^(\d+)([mhd])$', text)
    if not match:
        return None
    val = int(match.group(1))
    unit = match.group(2)
    if unit == 'm':
        return val * 60
    elif unit == 'h':
        return val * 3600
    elif unit == 'd':
        return val * 86400
    return None

def _get_until_date(seconds: int) -> datetime:
    """Returns a datetime within Telegram's 30s to 366d limit."""
    seconds = max(30, min(seconds, 366 * 86400))
    return datetime.now() + timedelta(seconds=seconds)

# --- Direct Actions ---

@shadow_router.message(Command("ban"), IsSudo())
async def shadow_ban(message: Message, bot: Bot):
    if not message.reply_to_message:
        await message.reply("❌ Reply to a message to ban the user.")
        return
    try:
        await bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        await message.reply(f"🔨 Shadow banned `{message.reply_to_message.from_user.id}`.", parse_mode="Markdown")
    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Error: {e.message}")

@shadow_router.message(Command("unban"), IsSudo())
async def shadow_unban(message: Message, bot: Bot):
    if not message.reply_to_message:
        await message.reply("❌ Reply to a message to unban the user.")
        return
    try:
        await bot.unban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        await message.reply(f"✅ Shadow unbanned `{message.reply_to_message.from_user.id}`.", parse_mode="Markdown")
    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Error: {e.message}")

@shadow_router.message(Command("mute"), IsSudo())
async def shadow_mute(message: Message, bot: Bot):
    if not message.reply_to_message:
        await message.reply("❌ Reply to a message to mute the user.")
        return
    try:
        perms = ChatPermissions(can_send_messages=False)
        await bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id, permissions=perms)
        await message.reply(f"🔇 Shadow muted `{message.reply_to_message.from_user.id}`.", parse_mode="Markdown")
    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Error: {e.message}")

@shadow_router.message(Command("unmute"), IsSudo())
async def shadow_unmute(message: Message, bot: Bot):
    if not message.reply_to_message:
        await message.reply("❌ Reply to a message to unmute the user.")
        return
    try:
        chat = await bot.get_chat(message.chat.id)
        await bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id, permissions=chat.permissions)
        await message.reply(f"🔊 Shadow unmuted `{message.reply_to_message.from_user.id}`.", parse_mode="Markdown")
    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Error: {e.message}")

@shadow_router.message(Command("kick"), IsSudo())
async def shadow_kick(message: Message, bot: Bot):
    if not message.reply_to_message:
        await message.reply("❌ Reply to a message to kick the user.")
        return
    target_id = message.reply_to_message.from_user.id
    try:
        await bot.ban_chat_member(message.chat.id, target_id)
        await bot.unban_chat_member(message.chat.id, target_id)
        await message.reply(f"👢 Shadow kicked `{target_id}`.", parse_mode="Markdown")
    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Error: {e.message}")

# --- Temporal Actions ---

@shadow_router.message(Command("tban"), IsSudo())
async def shadow_tban(message: Message, bot: Bot, command: Command):
    if not message.reply_to_message or not command.args:
        await message.reply("❌ Usage: `/tban <time>` (e.g., 10m, 2h, 1d) as a reply.")
        return
    seconds = _parse_duration(command.args.split()[0])
    if not seconds:
        await message.reply("❌ Invalid time format. Use m, h, or d.")
        return
    try:
        await bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id, until_date=_get_until_date(seconds))
        await message.reply(f"🔨 Shadow banned for {command.args.split()[0]}.", parse_mode="Markdown")
    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Error: {e.message}")

@shadow_router.message(Command("tmute"), IsSudo())
async def shadow_tmute(message: Message, bot: Bot, command: Command):
    if not message.reply_to_message or not command.args:
        await message.reply("❌ Usage: `/tmute <time>` (e.g., 10m, 2h, 1d) as a reply.")
        return
    seconds = _parse_duration(command.args.split()[0])
    if not seconds:
        await message.reply("❌ Invalid time format. Use m, h, or d.")
        return
    try:
        perms = ChatPermissions(can_send_messages=False)
        await bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id, permissions=perms, until_date=_get_until_date(seconds))
        await message.reply(f"🔇 Shadow muted for {command.args.split()[0]}.", parse_mode="Markdown")
    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Error: {e.message}")

# --- Stealth Actions ---

@shadow_router.message(Command("del"), IsSudo())
async def shadow_del(message: Message, bot: Bot):
    if not message.reply_to_message:
        return
    try:
        await message.reply_to_message.delete()
        await message.delete()
    except TelegramBadRequest as e:
        await message.answer(f"⚠️ Error: {e.message}")

@shadow_router.message(Command("sban"), IsSudo())
async def shadow_sban(message: Message, bot: Bot):
    if not message.reply_to_message:
        return
    try:
        await bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        await message.reply_to_message.delete()
        await message.delete()
    except TelegramBadRequest as e:
        await message.answer(f"⚠️ Error: {e.message}")

@shadow_router.message(Command("smute"), IsSudo())
async def shadow_smute(message: Message, bot: Bot):
    if not message.reply_to_message:
        return
    try:
        perms = ChatPermissions(can_send_messages=False)
        await bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id, permissions=perms)
        await message.reply_to_message.delete()
        await message.delete()
    except TelegramBadRequest as e:
        await message.answer(f"⚠️ Error: {e.message}")

@shadow_router.message(Command("purge"), IsSudo())
async def shadow_purge(message: Message, bot: Bot):
    if not message.reply_to_message:
        await message.reply("❌ Reply to the first message you want to delete.")
        return
    start_id = message.reply_to_message.message_id
    end_id = message.message_id
    deleted_count = 0
    try:
        for i in range(start_id, end_id + 1, 100):
            batch = list(range(i, min(i + 100, end_id + 1)))
            try:
                await bot.delete_messages(message.chat.id, batch)
                deleted_count += len(batch)
            except TelegramBadRequest:
                pass # Batch might contain 48h+ messages or already deleted ones
        await message.answer(f"🧹 Purged messages.")
    except Exception as e:
        await message.answer(f"⚠️ Error: {e}")

# --- Domain Actions ---

@shadow_router.message(Command("lock"), IsSudo())
async def shadow_lock(message: Message, bot: Bot, command: Command):
    if not command.args or command.args not in ["media", "all"]:
        await message.reply("❌ Usage: `/lock media` or `/lock all`")
        return
    try:
        if command.args == "all":
            perms = ChatPermissions(can_send_messages=False)
        else: # media
            perms = ChatPermissions(
                can_send_messages=True,
                can_send_audios=False,
                can_send_documents=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_video_notes=False,
                can_send_voice_notes=False,
            )
        await bot.set_chat_permissions(message.chat.id, perms)
        await message.reply(f"🔒 Locked `{command.args}`.", parse_mode="Markdown")
    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Error: {e.message}")

@shadow_router.message(Command("unlock"), IsSudo())
async def shadow_unlock(message: Message, bot: Bot, command: Command):
    if not command.args or command.args not in ["media", "all"]:
        await message.reply("❌ Usage: `/unlock media` or `/unlock all`")
        return
    try:
        if command.args == "all":
            chat = await bot.get_chat(message.chat.id)
            perms = chat.permissions # Restore to default
        else:
            perms = ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=True,
                can_invite_users=True,
                can_pin_messages=True,
                can_manage_topics=True,
            )
        await bot.set_chat_permissions(message.chat.id, perms)
        await message.reply(f"🔓 Unlocked `{command.args}`.", parse_mode="Markdown")
    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Error: {e.message}")

@shadow_router.message(Command("slowmode"), IsSudo())
async def shadow_slowmode(message: Message, bot: Bot, command: Command):
    if not command.args or not command.args.isdigit():
        await message.reply("❌ Usage: `/slowmode <seconds>` (0 to disable).")
        return
    try:
        await bot.set_chat_slow_mode_delay(message.chat.id, int(command.args))
        await message.reply(f"⏱ Slowmode set to `{command.args}` seconds.", parse_mode="Markdown")
    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Error: {e.message}")

@shadow_router.message(Command("pin"), IsSudo())
async def shadow_pin(message: Message, bot: Bot):
    if not message.reply_to_message:
        await message.reply("❌ Reply to a message to pin it.")
        return
    try:
        await bot.pin_chat_message(message.chat.id, message_id=message.reply_to_message.message_id)
        await message.reply("📌 Message pinned.")
    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Error: {e.message}")

@shadow_router.message(Command("unpin"), IsSudo())
async def shadow_unpin(message: Message, bot: Bot):
    if not message.reply_to_message:
        await message.reply("❌ Reply to a message to unpin it.")
        return
    try:
        await bot.unpin_chat_message(message.chat.id, message_id=message.reply_to_message.message_id)
        await message.reply("📌 Message unpinned.")
    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Error: {e.message}")

@shadow_router.message(Command("unpinall"), IsSudo())
async def shadow_unpinall(message: Message, bot: Bot):
    try:
        await bot.unpin_all_chat_messages(message.chat.id)
        await message.reply("📌 All messages unpinned.")
    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Error: {e.message}")

# --- Promote Logic ---

@shadow_router.message(Command("promote"), IsSudo())
async def shadow_promote(message: Message, bot: Bot, command: Command):
    if not message.reply_to_message:
        await message.reply("❌ Reply to the user you want to promote.")
        return
        
    target_id = message.reply_to_message.from_user.id
    
    try:
        # 1. Abort if creator
        target_member = await bot.get_chat_member(message.chat.id, target_id)
        if target_member.status == "creator":
            await message.reply("ℹ️ User is the creator of this chat.")
            return

        # 2. Get bot's own permissions
        bot_member = await bot.get_chat_member(message.chat.id, bot.id)
        if bot_member.status != "administrator":
            await message.reply("⚠️ Bot is not an administrator here.")
            return

        # Mirror bot permissions
        kwargs = {}
        for perm in [
            'can_manage_chat', 'can_delete_messages', 'can_manage_video_chats',
            'can_restrict_members', 'can_promote_members', 'can_change_info',
            'can_invite_users', 'can_post_messages', 'can_edit_messages',
            'can_pin_messages', 'can_post_stories', 'can_edit_stories',
            'can_delete_stories', 'can_manage_topics'
        ]:
            if hasattr(bot_member, perm) and getattr(bot_member, perm) is True:
                kwargs[perm] = True

        # 3. Bypass proxy rule: If already admin, demote first
        if target_member.status == "administrator":
            demote_kwargs = {k: False for k in kwargs}
            await bot.promote_chat_member(message.chat.id, target_id, **demote_kwargs)

        # Promote user
        await bot.promote_chat_member(message.chat.id, target_id, **kwargs)

        # 4. Set custom title
        custom_title = command.args.strip() if command.args else "owner asf"
        custom_title = custom_title[:16]
        
        try:
            await bot.set_chat_administrator_custom_title(message.chat.id, target_id, custom_title)
            title_msg = f" with title `{custom_title}`"
        except TelegramBadRequest as e:
            title_msg = f" (failed to set title: {e.message})"
            
        await message.reply(f"🌟 Shadow promoted `{target_id}` successfully{title_msg}.", parse_mode="Markdown")

    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Error: {e.message}")
