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

## Telegram Commands

```text
/start - show a short introduction
/help - show available commands
/newevent description - create a group event
```

## Tests

```powershell
python -m unittest discover -s tests
```

## Docker

The container expects a server-side `.env` file and stores SQLite data in `./data`.

```powershell
docker compose up -d --build
```

## Deployment

Pushes to `main` run tests in GitHub Actions and deploy to `/srv/eventbot` on the VPS over SSH.

Required GitHub repository secrets:

```text
VPS_HOST
VPS_USER
VPS_SSH_KEY
VPS_PORT
```

`VPS_USER` is expected to be `deploy`. `VPS_PORT` can be set to `22` unless the server uses a custom SSH port.

The VPS `.env` file in `/srv/eventbot/.env` should contain:

```text
TELEGRAM_BOT_TOKEN=your_bot_token
DATABASE_PATH=/app/data/eventbot.sqlite
APP_UID=deploy_user_id
APP_GID=deploy_group_id
```

Get `APP_UID` and `APP_GID` on the VPS with:

```bash
id -u deploy
id -g deploy
```
