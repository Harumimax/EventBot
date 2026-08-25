---
name: feature-workflow
description: Use this when implementing or changing a feature in this repository. Trigger for Telegram bot handlers, callback logic, SQLite schema, repositories, services, Docker/deploy configuration, background cleanup jobs, and tests. Do not use for pure Git-only tasks.
---

You are working in a Python Telegram bot project.

The project stack is:

- Python
- aiogram 3
- SQLite
- aiosqlite
- Docker
- GitHub Actions deploy to VPS over SSH

Follow this workflow exactly:

1. First, restate the task in 2-4 short bullets.
2. Then make a short implementation plan.
3. Before editing, list the files you expect to create or modify.
4. Prefer small, reversible changes.
5. Use project conventions:
   - aiogram routers and handlers for Telegram commands and callbacks
   - service classes/functions for business logic
   - repository/database layer for SQLite access
   - aiosqlite for async SQLite operations
   - environment variables for secrets and runtime configuration
   - Docker/Docker Compose for runtime and deployment
6. Do not add new packages unless the user explicitly asks or there is no reasonable simple solution with the current stack.
7. Do not refactor unrelated code.
8. For every new or changed feature, automatically add or update tests.
9. After writing code, automatically run the relevant tests.
10. If tests fail, investigate and fix the bugs before finishing.
11. Check that Russian text in source files, bot messages, docs, and config examples is saved with correct UTF-8 encoding.
12. Avoid mojibake and broken Cyrillic characters. If corrupted Russian text is detected, fix it in the same task.
13. After changes:
   - summarize what changed
   - show verification commands that were run
   - mention any manual steps
14. When changing the SQLite schema, include the schema initialization/migration path and mention any data or deployment impact.
15. If architecture, database structure, service boundaries, deployment flow, security assumptions, or other important code-organization decisions change, update `docs/architecture.md` in the same task.
16. If the task is large, do only the first safe slice and stop.

Project architecture reminders:

- EventBot works primarily in Telegram groups and supergroups.
- Private chats should only provide a short help message for the MVP.
- Any group member can create an event with `/newevent <description>`.
- Events are bound to the Telegram `chat_id` where they were created.
- Participants join through an inline Telegram button.
- The original bot message should be edited after participant changes.
- Events and participants must survive bot restarts.
- SQLite database must live in a persistent Docker volume or mounted VPS directory.
- Events are short-lived and should be automatically deleted after 28 days.
- Telegram `user_id` is the stable participant identity.
- Telegram display names are only presentation data and must not be used as identifiers.
- Telegram bot token and other secrets must never be committed.
- Callback data must be validated before changing participation.
- Business logic should not be buried directly inside Telegram handlers.
