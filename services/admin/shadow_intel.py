import logging
import html
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from services.security.filters import IsSudo

logger = logging.getLogger(__name__)
intel_router = Router(name="shadow_intel")

@intel_router.message(Command("admins"), IsSudo())
async def shadow_admins(message: Message, bot: Bot):
    try:
        admins = await bot.get_chat_administrators(message.chat.id)
        filtered_admins = []
        for admin in admins:
            user = admin.user
            if user.is_bot:
                continue
            if admin.status == "creator" and admin.is_anonymous:
                continue
            name = html.escape(user.full_name)
            filtered_admins.append(f"<a href='tg://user?id={user.id}'>{name}</a> (`{user.id}`)")
        
        if not filtered_admins:
            await message.reply("No visible admins found.")
            return
            
        roster = "👥 **Admin Roster:**\n" + "\n".join(f"{i+1}. {a}" for i, a in enumerate(filtered_admins))
        await message.reply(roster, parse_mode="HTML")
    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Error: {e.message}")

@intel_router.message(Command("bots"), IsSudo())
async def shadow_bots(message: Message, bot: Bot):
    try:
        admins = await bot.get_chat_administrators(message.chat.id)
        bots = []
        for admin in admins:
            user = admin.user
            if user.is_bot:
                username = f"@{user.username}" if user.username else user.full_name
                bots.append(f"🤖 {html.escape(username)} (`{user.id}`)")
                
        if not bots:
            await message.reply("No admin bots found.")
            return
            
        roster = "🤖 **Admin Bots:**\n" + "\n".join(bots)
        await message.reply(roster, parse_mode="HTML")
    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Error: {e.message}")

@intel_router.message(Command("info"), IsSudo())
async def shadow_info(message: Message, bot: Bot, command: Command):
    target_id = None
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    elif command.args and command.args.isdigit():
        target_id = int(command.args)
        
    if not target_id:
        await message.reply("❌ Reply to a user or pass their ID.")
        return
        
    try:
        member = await bot.get_chat_member(message.chat.id, target_id)
        user = member.user
        
        info = (
            f"👤 **User Info**\n"
            f"ID: `{user.id}`\n"
            f"First Name: {html.escape(user.first_name)}\n"
        )
        if user.last_name:
            info += f"Last Name: {html.escape(user.last_name)}\n"
        if user.username:
            info += f"Username: @{user.username}\n"
            
        info += f"Status: `{member.status}`"
        
        await message.reply(info, parse_mode="HTML")
    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Error: {e.message}")

@intel_router.message(Command("invitelink"), IsSudo())
async def shadow_invitelink(message: Message, bot: Bot):
    try:
        link = await bot.create_chat_invite_link(message.chat.id, member_limit=1)
        try:
            await bot.send_message(message.from_user.id, f"🔗 One-time invite link for {html.escape(message.chat.title or 'this chat')}:\n{link.invite_link}", parse_mode="HTML")
            await message.reply("✅ Invite link sent to your DMs.")
        except TelegramBadRequest:
            await message.reply("❌ Could not DM you. Have you started a conversation with the bot?")
    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Error creating link: {e.message}")
