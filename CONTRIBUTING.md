# Contributing to Project X

Welcome to the inner circle. We appreciate your interest in advancing Project X. Our mission is to maintain a high-performance, strictly typed, and impeccably structured Telegram management system. 

Whether you are optimizing the membership checker, expanding the Supabase integration, or engineering new Shadow Ops, this document sets the gold standard for your code.

## 🛠️ The Forge (Local Setup)

To construct and test your contributions locally:

1. **Clone & Install**:
   ```bash
   git clone https://github.com/ekanshbfoe/ProjectX_Aclbot.git
   cd ProjectX_Aclbot
   pip install -r requirements.txt
   ```
2. **Environment Simulation**:
   Copy `example.env` to `.env` and insert your testing credentials.
3. **Bypass Membership Checks**:
   For local testing, you may not want to enforce the `MANDATORY_CHAT_ID` logic. You can temporarily insert your own User ID into the `whitelisted_users` set in `services/security/filters.py` or set your ID in `SUDO_USERS` to bypass all filters natively.
4. **Ignite**:
   ```bash
   python main.py
   ```

## 📐 The Blueprint (Git Standards)

Maintain a pristine history. Adhere to these conventions:

- **Branch Naming**: 
  Prefix branches logically: `feature/shadow-stealth`, `fix/cooldown-cache`, `docs/readme-refresh`, `refactor/supabase-client`.
- **Commit Messages**: 
  Use imperative mood and clear descriptions:
  * `feat: implement /purge shadow command`
  * `fix: handle TelegramBadRequest on anonymous creators`
  * `chore: update dependencies`

## ⚔️ The Trial (Pull Requests)

Before submitting a Pull Request to the main branch, ensure you pass the following checklist. High-tier repositories demand rigorous edge-case handling.

- [ ] **Edge Cases Handled**: Have you accounted for anonymous admins, channel forwards, and hidden creators?
- [ ] **API Limits Respected**: Are all `aiogram` API calls wrapped in `try...except TelegramBadRequest`? Never let the bot crash due to permission deficits or Telegram rate limits.
- [ ] **Router Hierarchy Maintained**: Did you register your new aiogram routers in `main.py` correctly? Specific command routers (like Shadow Ops) **must** be registered via `dp.include_router()` *before* broad message catchers (like the membership and security filters) to prevent update consumption.
- [ ] **Syntax & Pydantic**: Have you tested your code against aiogram 3.x's latest Pydantic structures (e.g., using keyword arguments for `message_id` during unpins)?
- [ ] **Documentation**: Have you updated the `README.md` Command Matrix if you added new capabilities?

Your code is your legacy. Submit your PR when ready, and a maintainer will review the architecture.
