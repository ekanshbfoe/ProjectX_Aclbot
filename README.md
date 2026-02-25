<!--
# Copyright (c) 2026 ACL community
# Licensed under the MIT License.
# This file is part of ProjectX_Aclbot
-->

# Project X - Telegram Security & Membership Bot

A premium, high-performance Telegram bot built with `aiogram 3.x` to manage group security and mandatory channel memberships.

## 🚀 Features

### 🛡️ Security & Filtering
- **Channel Forward Protection**: Automatically deletes messages forwarded from Telegram channels.
- **Link Filtering**: Blocks `t.me/`, `telegram.me/`, and invite links (`t.me/+`) to prevent spam.
- **Safe Mentions**: Allows simple `@mentions` so members can still tag their friends.
- **Instant Deletion**: Malicious content is removed immediately, followed by a friendly security warning.

### 💎 Membership Checker (Main Hub)
- **Mandatory Join**: Restricts user interaction until they join your official "Main Hub" chat.
- **Premium UI**: Uses high-end "Neon Modern" and minimal styles for reminders.
- **Smart Cooldowns**: 10-minute cooldown per user for reminders to prevent bot spam.
- **Fallback Logic**: Notifies users even if their original message was deleted.

### 👤 Admin & Whitelist
- **Sudo Access**: Support for owner/sudo IDs to bypass all filters.
- **Whitelist Command**: `/whitelist` (via reply or ID) to exempt trusted users from filtering.
- **Admin Immunity**: Group administrators are automatically exempted from security rules.

## 🛠️ Setup & Installation

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd "Project X"
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Create a `.env` file in the root directory:
   ```env
   BOT_TOKEN=your_telegram_bot_token
   MANDATORY_CHAT_ID=-100xxxxxxxxxx
   COOLDOWN_SECONDS=600
   SUDO_USERS=user_id1 user_id2
   ```

4. **Run the Bot**:
   ```bash
   python main.py
   ```

## 📂 Project Structure

- `main.py`: Entry point, dispatcher setup, and core message routing.
- `services/`:
  - `links/membership.py`: Logic for checking hub membership and sending reminders.
  - `security/filters.py`: Regex-based filtering for links, forwards, and whitelist management.
- `.env`: Secret configuration (Token, Chat IDs, Sudo users).
- `requirements.txt`: Python package dependencies.

## 🤖 Bot Commands

- `/whitelist`: (Reply to a user) Whitelists the user from security filters.
- `/whitelist [user_id]`: Whitelists a specific ID.

## 🏗️ Built With
- [Aiogram 3.x](https://docs.aiogram.dev/) - Asynchronous Telegram Bot Framework.
- [Python-Dotenv](https://pypi.org/project/python-dotenv/) - Environment variable management.

---
*Developed with ❤️ for Project X*
