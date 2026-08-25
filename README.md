# EventBot

Telegram bot for collecting participants for group events.

## Local Run

Create a local `.env` file:

```text
TELEGRAM_BOT_TOKEN=your_bot_token
DATABASE_PATH=./data/eventbot.sqlite
```

Run the bot:

```powershell
python -m eventbot
```

## Tests

```powershell
python -m unittest discover -s tests
```
