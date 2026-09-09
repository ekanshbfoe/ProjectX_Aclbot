import os
from aiogram import Router
from aiogram.types import ChatJoinRequest
from aiogram.exceptions import TelegramBadRequest

join_router = Router(name="join_events")

@join_router.chat_join_request()
async def auto_accept_sudo(event: ChatJoinRequest):
    """Auto-approves join requests for Sudo users."""
    sudo_users = list(map(int, os.getenv("SUDO_USERS", "").split()))
    if event.from_user.id in sudo_users:
        try:
            await event.approve()
        except TelegramBadRequest:
            pass  # Bot lacks can_invite_users — degrade silently
