# EventBot

EventBot is a Telegram bot for quickly collecting participants for events in group chats.

Bot: [@SuperNewEventBot](https://t.me/SuperNewEventBot)

## What It Does

EventBot helps a group agree who is joining an event without messy chat threads.

You create an event directly in a Telegram group, and the bot publishes a message with a participant list and a join button. People tap the button, and the list updates in the same message.

## How To Use

1. Add [@SuperNewEventBot](https://t.me/SuperNewEventBot) to a Telegram group.
2. In the group, send:

```text
/newevent Board games on Saturday at 19:00
```

3. EventBot will create an event message with a join button.
4. Group members tap `Участвую` to join.
5. The bot updates the participant list in the original message.

## Commands

```text
/newevent description
```

Create a new event in the current group.

```text
/help
```

Show available commands and basic usage.

## Data Lifetime

Events are temporary. EventBot automatically deletes old events after 28 days.

## Current Status

EventBot is a small personal project for friendly group events. It is intentionally simple and focused on the core flow: create an event, join it, and keep the participant list visible in the chat.
