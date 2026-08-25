# EventBot Architecture

## Purpose

EventBot is a Telegram bot for organizing small group events. A user adds the bot to a Telegram group, creates an event with `/newevent`, and group members join the event through an inline button in the bot message.

The project is intended for personal use and friends, not for high-load public production.

## MVP Scope

The first version includes:

- Creating an event in a Telegram group with `/newevent <description>`.
- Publishing a bot message with the event description, participant list, and inline join button.
- Letting group members join the event by pressing the button.
- Updating the original event message after participation changes.
- Persisting events and participants across bot restarts.
- Automatically deleting events older than 14 days.
- Deploying to an existing VPS through GitHub Actions and Docker.

Out of scope for the MVP:

- Public multi-tenant SaaS behavior.
- Complex permissions and roles.
- Payments.
- Event discovery outside Telegram groups.
- Advanced scheduling, reminders, or calendar integrations.

## Runtime Model

The bot runs as a single Python service inside a Docker container.

```text
Telegram
  |
  | updates / callback queries
  v
EventBot container
  |
  | reads/writes
  v
SQLite database on persistent volume
```

The VPS does not need a system-wide Python installation for the application. Python is provided by the Docker image. The VPS needs Docker, Docker Compose, SSH access for deployment, and a persistent directory or Docker volume for SQLite data.

## Technology Choices

### Language

Python is the default backend language for the bot.

Reasoning:

- Telegram bot development is straightforward in Python.
- The ecosystem has mature bot frameworks.
- The application is small and event-driven.
- Docker keeps the runtime reproducible on the VPS.

### Telegram Framework

The recommended framework is `aiogram 3`.

Reasoning:

- Modern async-first design.
- Good fit for Telegram commands, messages, and callback queries.
- Clean handler-based architecture.

### Database

The MVP uses SQLite through `aiosqlite`.

Reasoning:

- The project is for personal and small-group use.
- Expected load is low.
- Data model is simple.
- Events are short-lived and can be removed after 14 days.
- SQLite avoids the operational cost of PostgreSQL or another database server.
- A persistent Docker volume is enough to survive container restarts and deploys.

SQLite should be stored outside the container filesystem, for example:

```text
/app/data/eventbot.sqlite
```

mounted from a VPS directory or Docker volume.

Schema initialization currently lives in `eventbot/storage/database.py`. The app runs this initialization on startup before polling Telegram updates. For the MVP this is enough: the schema is created if missing, and `PRAGMA user_version = 1` marks the first database version. Future incompatible schema changes should add an explicit migration path instead of silently rewriting existing data.

Database access should go through repository classes in `eventbot/storage/repositories.py`. Telegram handlers should not execute SQL directly.

## Telegram Behavior

### Group Chats

The MVP is group-first.

`/newevent` is accepted only in Telegram group or supergroup chats. Each event is bound to the Telegram `chat_id` where it was created.

Expected command format:

```text
/newevent Event description
```

If the description is missing, the bot should answer with a short usage hint.

### Private Chats

Private chat support is limited to a help response.

If a user opens the bot in a private chat, the bot should explain that EventBot works in groups and should be added to a group chat.

This keeps the MVP simple because private events would require a separate interaction model: choosing a target group, inviting participants, and deciding where the event message should live.

## Event Lifecycle

1. A group member sends `/newevent <description>`.
2. The bot creates an event record in SQLite.
3. The bot sends an event message to the same group.
4. The message includes an inline button for joining the event.
5. A group member presses the button.
6. The bot stores the participant in SQLite.
7. The bot edits the original event message with the updated participant list.
8. A cleanup task periodically deletes events older than 14 days.

For the MVP, any group member may create an event. Advanced permissions can be added later.

## Data Model

Initial SQLite tables:

### events

- `id`: internal event id.
- `chat_id`: Telegram group or supergroup id.
- `message_id`: Telegram message id of the bot's event message.
- `created_by_user_id`: Telegram user id of the creator.
- `description`: event text from `/newevent`.
- `created_at`: creation timestamp.
- `expires_at`: timestamp for cleanup, normally `created_at + 14 days`.
- `is_closed`: reserved for later manual closing.

### participants

- `id`: internal participant row id.
- `event_id`: foreign key to `events.id`.
- `user_id`: Telegram user id.
- `display_name`: best available Telegram display name at join time.
- `joined_at`: join timestamp.

Recommended uniqueness constraint:

```text
unique(event_id, user_id)
```

This prevents duplicate participant entries when a user presses the join button multiple times.

## Message Rendering

The event message should contain:

- Event description.
- Participant count.
- Participant list.
- Inline join button.

Example:

```text
Event:
Football on Saturday at 19:00

Participants: 3
1. Max
2. Anna
3. Ivan
```

The MVP can treat repeated button presses as "already joined" and show a short callback notification. Toggle join/leave behavior can be added later if needed.

## Cleanup

The application should run a periodic cleanup task, for example once per day.

Cleanup removes:

- Events where `expires_at` is older than the current time.
- Participants connected to deleted events.

The MVP does not need long-term history.

## Deployment

Deployment target: existing VPS.

Deployment model:

- Code is stored in GitHub.
- GitHub Actions connects to the VPS over SSH.
- The VPS runs the bot through Docker Compose.
- The bot token is provided through environment variables.
- SQLite data is stored in a persistent mounted directory or Docker volume.

Required environment variables:

```text
TELEGRAM_BOT_TOKEN=<bot token from BotFather>
DATABASE_PATH=/app/data/eventbot.sqlite
```

The repository should not store real secrets.

## Security Notes

- Never commit the Telegram bot token.
- Keep secrets in GitHub Actions secrets and VPS `.env` files.
- Validate callback data and load the event from the database before changing participation.
- Bind events to `chat_id` and `message_id` to avoid accidental cross-chat updates.
- Do not trust Telegram display names as stable identifiers; use `user_id` for identity.
- Use a non-root user inside the Docker container where practical.
- Keep the SQLite file in a directory writable only by the deployment user and container.
- Add basic structured logging, but avoid logging secrets.

## Future Extensions

Possible later features:

- Leave event button.
- Close event button.
- Delete event command.
- Event creator/admin permissions.
- Event time parsing.
- Reminders before event start.
- Participant limits.
- Waitlist.
- Export participant list.
- Multiple buttons such as "Maybe" or "Cannot attend".
