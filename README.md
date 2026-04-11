# Mika Shop — Discord Bot

Python Discord bot for a Roblox digital commission shop: tickets, orders, queue, shop open/close, vouches, moderation, Roblox helpers, payments panel, and 24/7 voice presence. Built with **discord.py 2.x** (slash commands, UI components), **SQLite** (`aiosqlite`), **aiohttp**, and a small **Flask** keep-alive for hosting.

## Requirements

- **Python 3.11+**
- Dependencies listed in [`requirements.txt`](requirements.txt)

## Quick start

1. Clone or copy this `bot` folder and open a terminal inside it.

2. Create a virtual environment (recommended):

   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:

   - Copy [`.env.example`](.env.example) to `.env`.
   - Fill in all values (bot token, guild ID, role/channel IDs, payment details, Roblox cookie for staff tools, etc.).
   - Never commit `.env` or push secrets to Git.

5. Run the bot:

   ```bash
   python main.py
   ```

On first run, the bot creates `bot.db` in this directory and initializes tables.

## Discord application settings

In the [Discord Developer Portal](https://discord.com/developers/applications), enable:

- **Privileged Gateway Intents**: *Message Content Intent*, *Server Members Intent* (required for sticky/vouch logic and member-based features).
- **Bot permissions** appropriate for your server (manage channels/roles where the features need them, voice connect, send messages, embeds, attach files, etc.).

Slash commands are **guild-synced** to the guild ID in `.env` for fast updates during development.

## Environment variables

All configuration is loaded from `.env` via [`config.py`](config.py). See [`.env.example`](.env.example) for the full list:

| Area | Examples |
|------|----------|
| Core | `BOT_TOKEN`, `GUILD_ID` |
| Roles | `STAFF_ROLE_ID`, `TOS_AGREED_ROLE_ID`, `PLEASE_VOUCH_ROLE_ID`, … |
| Channels / categories | `TICKET_CATEGORY_ID`, `QUEUE_CHANNEL_ID`, `VOUCHES_CHANNEL_ID`, … |
| Roblox | `ROBLOX_COOKIE`, `ROBLOX_GROUP_ID` |
| Payments | `GCASH_DETAILS`, `PAYPAL_LINK`, `KOFI_LINK`, `GCASH_QR_URL`, `PAYPAL_QR_URL` |

Startup fails fast with a clear error if a required variable is missing.

## Project layout

```
bot/
├── main.py              # Entry: DB init, cog load, guild sync, persistent views, keep-alive
├── keep_alive.py        # Flask GET / on port 8080 (background thread)
├── config.py            # Env loading and validation
├── database.py          # SQLite schema and async queries
├── requirements.txt
├── tos.txt              # TOS embed text (editable without code changes)
├── stocks.json          # Manual stock data for /stocks commands
├── cogs/                # Feature modules (one cog per area)
├── utils/               # embeds, checks, transcript helper
└── docs/                # Extra documentation (see docs/README.md)
```

## Notable slash commands (overview)

| Area | Examples |
|------|----------|
| Staff setup | `/setup tickets`, `/setup tos`, `/setup queue`, `/setup payment` |
| Shop | `/shop open`, `/shop close`, `/shopstatus` |
| Tickets | Open via panel button; `/close` in ticket channel |
| Queue | `/status`, `/queuepanel`, `/loyalty`, `/loyaltytop` |
| Other | `/warn`, `/vouches`, `/sticky`, `/calc`, `/tax`, `/stocks`, `/drop`, `/vcjoin`, … |

Exact behaviour lives in each cog under `cogs/`.

## Hosting (e.g. Render)

- Run as a **Background Worker** with start command: `python main.py`.
- Set all environment variables in the host dashboard (do not rely on a committed `.env`).
- The Flask keep-alive listens on **port 8080**; you can point an external monitor (e.g. UptimeRobot) at the provided URL if your platform exposes one.

## Documentation folder

Additional notes and runbooks can live under [`docs/`](docs/README.md).

## License

Use and modify according to your project’s license (add a `LICENSE` file if you need one).
