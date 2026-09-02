# Copyright (c) 2026 ACL community
# Licensed under the MIT License.
# This file is part of ProjectX_Aclbot

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta

from aiogram import Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# ── Supabase Client ───────────────────────────────────────────────
_supabase: Client | None = None

REQUEST_COOLDOWN_SECONDS = 900  # 15 minutes


def init_supabase() -> Client:
    """Initializes and returns the Supabase client. Call once at startup."""
    global _supabase
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    _supabase = create_client(url, key)
    logger.info("Supabase client initialized.")
    return _supabase


def _get_db() -> Client:
    """Returns the Supabase client, raising if not initialized."""
    if _supabase is None:
        raise RuntimeError("Supabase not initialized. Call init_supabase() first.")
    return _supabase


def _generate_request_id() -> str:
    """Generates a short 8-char unique ID that fits comfortably in callback data."""
    return uuid.uuid4().hex[:8]


# ── Status Labels ─────────────────────────────────────────────────
STATUS_LABELS = {
    "pending":   "⏳ Pending",
    "done":      "✅ Fulfilled",
    "rejected":  "❌ Rejected",
    "available": "📦 Already Available",
}


# ══════════════════════════════════════════════════════════════════
#  1.  #request  COMMAND HANDLER
# ══════════════════════════════════════════════════════════════════

async def handle_request_command(bot: Bot, message: Message, request_channel_id: int):
    """
    Handles the  #request <apk_name>  command from group chats.
    Validates input, enforces cooldown, saves to DB, notifies user & admins.
    """
    user = message.from_user
    if not user:
        return

    # ── Parse APK name ────────────────────────────────────────────
    raw_text = message.text or ""
    # Remove the '#request' trigger and strip whitespace
    apk_name = raw_text.split(maxsplit=1)[1].strip() if len(raw_text.split(maxsplit=1)) > 1 else ""

    if not apk_name:
        await message.reply(
            "❌ <b>Please provide an app name.</b>\n"
            "Example: <code>#request Alight Motion</code>",
            parse_mode="HTML",
        )
        return

    # ── Cooldown check (15 min per user via Supabase) ─────────────
    db = _get_db()
    cooldown_cutoff = (datetime.now(timezone.utc) - timedelta(seconds=REQUEST_COOLDOWN_SECONDS)).isoformat()

    try:
        recent = (
            db.table("app_requests")
            .select("created_at")
            .eq("user_id", user.id)
            .gte("created_at", cooldown_cutoff)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if recent.data:
            last_time = datetime.fromisoformat(recent.data[0]["created_at"])
            elapsed = (datetime.now(timezone.utc) - last_time).total_seconds()
            remaining = int(REQUEST_COOLDOWN_SECONDS - elapsed)
            mins = remaining // 60
            secs = remaining % 60
            await message.reply(
                f"⏳ <b>Cooldown active!</b>\n"
                f"Please wait <b>{mins}m {secs}s</b> before making another request.",
                parse_mode="HTML",
            )
            return
    except Exception as e:
        logger.error(f"Cooldown check failed: {e}")
        # Continue anyway – don't block the user over a DB hiccup

    # ── Insert request into DB ────────────────────────────────────
    request_id = _generate_request_id()

    try:
        db.table("app_requests").insert({
            "id": request_id,
            "user_id": user.id,
            "user_name": user.full_name,
            "user_mention": user.mention_html(),
            "apk_name": apk_name,
            "status": "pending",
            "chat_id": message.chat.id,
            "message_id": message.message_id,
        }).execute()
    except Exception as e:
        logger.error(f"Failed to insert request: {e}")
        await message.reply("⚠️ Something went wrong. Please try again later.", parse_mode="HTML")
        return

    # ── Reply to user in the group ────────────────────────────────
    channel_link = await _get_channel_invite_link(bot, request_channel_id)
    user_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 View Status", callback_data=f"req_status:{request_id}")],
        [InlineKeyboardButton(text="📢 Request Channel", url=channel_link)],
    ])

    try:
        await message.reply(
            f"✨ <b>Hey {user.full_name}</b>, your request for "
            f"<b>{apk_name}</b> has been submitted to the admins. "
            f"It may take some time.\n\n"
            f"📌 <i>Request ID:</i> <code>{request_id}</code>",
            parse_mode="HTML",
            reply_markup=user_keyboard,
        )
    except Exception as e:
        logger.error(f"Failed to reply to user: {e}")

    # ── Forward to Admin Request Channel ──────────────────────────
    # Build the deep-link URL to the original message
    original_msg_link = _build_message_link(message.chat.id, message.message_id)

    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Request Message", url=original_msg_link)],
        [
            InlineKeyboardButton(text="✅ Done", callback_data=f"req_done:{request_id}"),
            InlineKeyboardButton(text="❌ Rejected", callback_data=f"req_reject:{request_id}"),
        ],
        [InlineKeyboardButton(text="🔍 Already Available", callback_data=f"req_avail:{request_id}")],
        [InlineKeyboardButton(text="🗑️ Cancel Request", callback_data=f"req_cancel:{request_id}")],
    ])

    admin_text = (
        f"📋 <b>New App Request</b>\n\n"
        f"👤 <b>Request By:</b> {user.mention_html()} (<code>{user.id}</code>)\n"
        f"📱 <b>Requested App:</b> <b>{apk_name}</b>\n\n"
        f"🆔 <i>Request ID:</i> <code>{request_id}</code>"
    )

    try:
        admin_msg = await bot.send_message(
            chat_id=request_channel_id,
            text=admin_text,
            parse_mode="HTML",
            reply_markup=admin_keyboard,
        )
        # Store admin_message_id back in DB so we can edit it later
        db.table("app_requests").update({
            "admin_message_id": admin_msg.message_id,
        }).eq("id", request_id).execute()
    except Exception as e:
        logger.error(f"Failed to send request to admin channel: {e}")


# ══════════════════════════════════════════════════════════════════
#  2.  VIEW STATUS  CALLBACK
# ══════════════════════════════════════════════════════════════════

async def handle_status_callback(bot: Bot, callback_query: CallbackQuery):
    """
    Handles the 'View Status' inline button.
    Shows the current request status as a popup alert.
    """
    request_id = callback_query.data.split(":")[1]
    db = _get_db()

    try:
        result = (
            db.table("app_requests")
            .select("status, apk_name")
            .eq("id", request_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            await callback_query.answer("❌ Request not found.", show_alert=True)
            return

        row = result.data[0]
        status_label = STATUS_LABELS.get(row["status"], row["status"])
        await callback_query.answer(
            f"📱 {row['apk_name']}\n\nStatus: {status_label}",
            show_alert=True,
        )
    except Exception as e:
        logger.error(f"Status callback failed: {e}")
        await callback_query.answer("⚠️ Could not fetch status.", show_alert=True)


# ══════════════════════════════════════════════════════════════════
#  3.  ADMIN ACTION  CALLBACKS (Done / Rejected / Available / Cancel)
# ══════════════════════════════════════════════════════════════════

async def handle_admin_action(bot: Bot, callback_query: CallbackQuery, request_channel_id: int):
    """
    Handles admin inline button actions on the request log message.
    Updates DB, edits admin message, and notifies the user.
    """
    # ── Admin permission check ─────────────────────────────────────
    actor = callback_query.from_user
    try:
        member = await bot.get_chat_member(request_channel_id, actor.id)
        if member.status not in ("administrator", "creator"):
            await callback_query.answer("🚫 Only admins of this channel can manage requests.", show_alert=True)
            return
    except Exception as e:
        logger.error(f"Admin check failed: {e}")
        await callback_query.answer("⚠️ Could not verify admin status.", show_alert=True)
        return

    data = callback_query.data  # e.g. "req_done:abc12345"
    parts = data.split(":")
    action = parts[0]       # req_done / req_reject / req_avail / req_cancel
    request_id = parts[1]

    db = _get_db()

    # ── Fetch request from DB ─────────────────────────────────────
    try:
        result = (
            db.table("app_requests")
            .select("*")
            .eq("id", request_id)
            .limit(1)
            .execute()
        )
    except Exception as e:
        logger.error(f"Admin action DB fetch failed: {e}")
        await callback_query.answer("⚠️ Database error.", show_alert=True)
        return

    if not result.data:
        await callback_query.answer("❌ Request not found.", show_alert=True)
        return

    req = result.data[0]

    # Already handled?
    if req["status"] != "pending":
        await callback_query.answer(
            f"ℹ️ Already handled: {STATUS_LABELS.get(req['status'], req['status'])}",
            show_alert=True,
        )
        return

    # ── Determine new status & user notification ──────────────────
    admin_user = callback_query.from_user
    admin_name = admin_user.full_name if admin_user else "Admin"

    if action == "req_done":
        new_status = "done"
        status_emoji = "✅"
        notify_in_gc = True  # Notify in group chat
        user_notification = (
            f"✅ {req['user_mention']}, your requested app "
            f"<b>{req['apk_name']}</b> has been uploaded to the channel! 🚀"
        )
    elif action == "req_reject":
        new_status = "rejected"
        status_emoji = "❌"
        notify_in_gc = False  # Notify via DM
        user_notification = (
            f"📋 <b>Request Update</b>\n\n"
            f"Your request for <b>{req['apk_name']}</b> has been <b>rejected</b>.\n"
            f"This could be due to availability or policy reasons."
        )
    elif action == "req_avail":
        new_status = "available"
        status_emoji = "📦"
        notify_in_gc = True  # Notify in group chat
        user_notification = (
            f"📦 {req['user_mention']}, the app "
            f"<b>{req['apk_name']}</b> is already available in the channel! 🔍"
        )
    elif action == "req_cancel":
        new_status = "cancelled"
        status_emoji = "🗑️"
        notify_in_gc = False
        user_notification = None  # Don't notify user on cancel
    else:
        await callback_query.answer("❌ Unknown action.", show_alert=True)
        return

    # ── Update DB ─────────────────────────────────────────────────
    try:
        db.table("app_requests").update({
            "status": new_status,
        }).eq("id", request_id).execute()
    except Exception as e:
        logger.error(f"Failed to update request status: {e}")
        await callback_query.answer("⚠️ Database update failed.", show_alert=True)
        return

    # ── Edit admin channel message (remove buttons, show result) ──
    notification_note = ""
    try:
        updated_text = (
            f"📋 <b>App Request</b> — {status_emoji} <b>{new_status.upper()}</b>\n\n"
            f"👤 <b>Request By:</b> {req['user_mention']} (<code>{req['user_id']}</code>)\n"
            f"📱 <b>Requested App:</b> <b>{req['apk_name']}</b>\n\n"
            f"🆔 <i>Request ID:</i> <code>{request_id}</code>\n"
            f"👮 <i>Handled by:</i> {admin_name}"
        )

        # ── Notify user (group chat reply or DM based on action) ───
        if user_notification:
            try:
                if notify_in_gc and req.get("chat_id"):
                    # Done / Already Available → reply to original message in group
                    await bot.send_message(
                        chat_id=req["chat_id"],
                        text=user_notification,
                        parse_mode="HTML",
                        reply_to_message_id=req.get("message_id"),
                    )
                else:
                    # Rejected → notify via DM
                    await bot.send_message(
                        chat_id=req["user_id"],
                        text=user_notification,
                        parse_mode="HTML",
                    )
                notification_note = "\n\n✅ <i>User notified successfully.</i>"
            except Exception as e:
                logger.warning(f"Could not notify user {req['user_id']}: {e}")
                notification_note = "\n\n⚠️ <i>Could not notify user (bot may be blocked).</i>"

        # Append notification status to admin message
        updated_text += notification_note

        if req.get("admin_message_id"):
            await bot.edit_message_text(
                chat_id=request_channel_id,
                message_id=req["admin_message_id"],
                text=updated_text,
                parse_mode="HTML",
                reply_markup=None,  # Remove all buttons
            )
    except Exception as e:
        logger.error(f"Failed to edit admin message: {e}")

    await callback_query.answer(f"{status_emoji} Marked as {new_status}.", show_alert=True)


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════

def _build_channel_link(channel_id: int) -> str:
    """Builds an internal t.me link for a channel from its chat ID (fallback only)."""
    clean_id = str(channel_id).replace("-100", "", 1)
    return f"https://t.me/c/{clean_id}"


async def _get_channel_invite_link(bot: Bot, channel_id: int) -> str:
    """Fetches the real invite link for a channel so non-members can join.
    Falls back to an internal link if the API call fails.
    """
    try:
        chat_info = await bot.get_chat(channel_id)
        # Public channels have a username → t.me/username
        if chat_info.username:
            return f"https://t.me/{chat_info.username}"
        # Private channels → use the invite_link
        if chat_info.invite_link:
            return chat_info.invite_link
    except Exception as e:
        logger.warning(f"Could not fetch invite link for {channel_id}: {e}")
    # Fallback to internal link
    return _build_channel_link(channel_id)


def _build_message_link(chat_id: int, message_id: int) -> str:
    """Builds a deep link to a specific message in a chat."""
    clean_id = str(chat_id).replace("-100", "", 1)
    return f"https://t.me/c/{clean_id}/{message_id}"
