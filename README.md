<!--
# Copyright (c) 2026 ACL community
# Licensed under the MIT License.
# This file is part of ProjectX_Aclbot
-->

# Project X - Telegram Security & Membership Bot

A premium, high-performance Telegram bot built with `aiogram 3.x` to manage group security, mandatory channel memberships, and user app requests.

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

### 📱 App Request System (`#request`)
- **User Requests**: Users send `#request <app_name>` in the group to request modded APKs.
- **Spam Prevention**: 15-minute cooldown per user to prevent request flooding.
- **Status Tracking**: Users can check their request status (Pending / Done / Rejected / Available) via inline button.
- **Admin Channel**: Requests are forwarded to a dedicated admin channel with action buttons.
- **Admin Actions**: Admins can mark requests as ✅ Done, ❌ Rejected, 🔍 Already Available, or 🗑️ Cancel.
- **Smart Notifications**: Done/Available replies to the original message in-group; Rejected notifies via DM.
- **Admin-Only Controls**: Only admins of the request channel can manage requests.
- **Supabase Database**: All requests are stored in Supabase with status tracking.

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

   # Request Feature (Supabase)
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your_service_role_key
   REQUEST_CHANNEL_ID=-100xxxxxxxxxx
   ```

4. **Set up Supabase** (for the request feature):
   Run this SQL in Supabase SQL Editor:
   ```sql
   CREATE TABLE IF NOT EXISTS app_requests (
       id TEXT PRIMARY KEY,
       user_id BIGINT NOT NULL,
       user_name TEXT,
       user_mention TEXT,
       apk_name TEXT NOT NULL,
       status TEXT NOT NULL DEFAULT 'pending',
       chat_id BIGINT,
       message_id BIGINT,
       admin_message_id BIGINT,
       created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
   );
   CREATE INDEX idx_app_requests_user_id ON app_requests (user_id);
   CREATE INDEX idx_app_requests_status ON app_requests (status);
   ```

5. **Run the Bot**:
   ```bash
   python main.py
   ```

## 📂 Project Structure

- `main.py`: Entry point, dispatcher setup, and core message routing.
- `services/`:
  - `links/membership.py`: Logic for checking hub membership and sending reminders.
  - `security/filters.py`: Regex-based filtering for links, forwards, and whitelist management.
  - `requests/handler.py`: App request command, admin actions, status callbacks, and Supabase integration.
- `.env`: Secret configuration (Token, Chat IDs, Sudo users, Supabase keys).
- `requirements.txt`: Python package dependencies.

## 🤖 Bot Commands

- `#request <app_name>`: Request a modded APK. Bot confirms and forwards to admin channel.
- `/whitelist`: (Reply to a user) Whitelists the user from security filters.
- `/whitelist [user_id]`: Whitelists a specific ID.

## 🏗️ Built With
- [Aiogram 3.x](https://docs.aiogram.dev/) - Asynchronous Telegram Bot Framework.
- [Supabase](https://supabase.com/) - Database for app request tracking.
- [Python-Dotenv](https://pypi.org/project/python-dotenv/) - Environment variable management.

---
*Developed with ❤️ for Project X*
"# ProjectX_Aclbot" 
