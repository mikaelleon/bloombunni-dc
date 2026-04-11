# Mika Shop — Discord Bot

Python Discord bot for a digital art commission shop: tickets, **`/queue`** order registration, template-based queue cards, shop open/close, TOS gate, vouches, moderation, payments panel, and HTML transcripts. Built with **discord.py 2.x**, **SQLite** (`aiosqlite`), and a small **Flask** keep-alive for hosting.

## Requirements

- **Python 3.11+**
- Dependencies listed in [`requirements.txt`](requirements.txt)

## Quick start

1. Open a terminal inside this `bot` folder.

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

   - Copy [`.env.example`](.env.example) to `.env` and set `BOT_TOKEN` and payment fields.
   - In Discord, run **`/serverconfig`** (channel, category, role, show) to pick channels and roles—no channel/role IDs in `.env`.
   - Never commit `.env` or push secrets to Git.

5. **If upgrading from an older schema**, delete `bot.db` so the new tables can be created (or migrate manually).

6. Run the bot:

   ```bash
   python main.py
   ```

## Discord application settings

In the [Discord Developer Portal](https://discord.com/developers/applications), enable **Message Content Intent** and **Server Members Intent**. Grant the bot permissions for managing channels/categories, roles, embeds, files, and history where needed.

If `GUILD_ID` is set in `.env`, slash commands are **guild-synced** for fast updates; omit it to sync globally (slower to propagate).

## Environment variables

See [`.env.example`](.env.example) and [`config.py`](config.py). Only **secrets and payment copy** load from the environment; channel and role targets are stored in SQLite after you use `/serverconfig`.

## Project layout

```
bot/
├── main.py
├── keep_alive.py
├── config.py
├── guild_keys.py
├── guild_config.py
├── database.py
├── requirements.txt
├── tos.txt
├── templates.json       # Default message templates (overridable via DB)
├── cogs/
│   └── serverconfig.py
└── utils/
```

## Notable slash commands

| Area | Commands |
|------|----------|
| Config | `/serverconfig channel`, `/serverconfig category`, `/serverconfig role`, `/serverconfig show` |
| Setup | `/setup tickets`, `/setup tos`, `/setup payment` |
| Shop | `/shop open`, `/shop close`, `/shopstatus` |
| Queue | `/queue` (staff), `/settemplate`, `/viewtemplate`, `/listtemplates`, `/resettemplates`, `/loyalty`, `/loyaltytop` |
| Tickets | Panel button, `/close` |
| Sticky | `/sticky`, `/stickyupdate`, `/unsticky`, `/stickies`, `/stickypreview` |
| Other | `/drop`, `/drophistory`, `/vouch`, `/vouches`, `/warn`, … |

## Hosting (e.g. Render)

Use a **Background Worker** with `python main.py`. Set env vars in the dashboard. Flask keep-alive uses **port 8080**.

## Documentation

See [`docs/README.md`](docs/README.md).
