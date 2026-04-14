# Overview and core runtime

## Purpose

**Mika Shop** is a Discord commission bot: configurable ticket panels, quotes, queue cards, payments, vouches, warnings, stickies, and staff utilities. It uses **discord.py** with **application commands** (slash). Prefix `!` exists at bot level, but feature cogs expose slash-first UX.

## Entry point (`main.py`)

### Bot class

- **`MikaBot`** subclasses `commands.Bot` with `command_prefix="!"` and **`help_command=None`**.
- **Intents** (`INTENTS`): `discord.Intents.default()` plus **`message_content`** and **`members`**.

### `setup_hook` (runs once at startup)

1. **`database.init_db()`** — creates/migrates SQLite schema (`config.DATABASE_PATH`, default `bot/bot.db`).
2. **`config.validate_config()`** — ensures token exists.
3. **Loads extensions** (in order):

   `cogs.owner_tools`, `cogs.config_cmd`, `cogs.setup_wizard`, `cogs.quotes`, `cogs.tickets`, `cogs.queue`, `cogs.shop`, `cogs.vouch`, `cogs.warn`, `cogs.sticky`, `cogs.drop`, `cogs.payment`

4. **`await self.tree.sync()`** — global slash sync.
5. **Optional guild sync**: if `SYNC_GUILD_ID` is set in `.env`, copies globals to that guild and syncs there immediately (avoids long global propagation and `CommandSignatureMismatch` while developing).
6. **Persistent views** registered with the bot:
   - `TOSAgreeView` (shop)
   - `PaymentView` (payment panel buttons)
7. **`register_ticket_persistent_views(self)`** — re-attaches ticket panel button views and `CloseTicketView` from DB.
8. **`register_order_status_views(self)`** — re-attaches queue **order status** dropdowns for open orders.

### `on_ready`

- Logs user, id, latency.
- **`ShopCog.refresh_status_message()`** — reloads cached shop status message from `persist_panels`.
- **`StickyCog.refresh_sticky_cache()`** — loads channel IDs that have stickies.
- **First-join hint**: for each guild with no config and no hint sent yet, posts a short message in system/rules/first writable channel suggesting **`/setup`** or **`/config view`**, then sets `setup_hint_sent` in `guild_flags`.

### Interactions and errors

- **`on_interaction`** — logs slash command usage at INFO (`cmd`, `guild_id`, `channel_id`, `user_id`).
- **`@bot.tree.error`** (`on_app_error`):
  - **`CheckFailure`** → `check_failure_response`.
  - **`CommandSignatureMismatch`** → ephemeral embed explaining **`SYNC_GUILD_ID`** / wait for global sync.
  - Other errors → logged; user gets ephemeral **`user_warn("That didn't work", …)`**.

There is **no** `on_message` in `main.py`; message listeners live in cogs (vouch, sticky).

## Configuration (`config.py`)

| Variable | Role |
|----------|------|
| **`BOT_TOKEN`** | Required; bot login token (`.env`). |
| **`SYNC_GUILD_ID`** | Optional integer; guild-scoped slash sync for faster updates. |
| **`DATABASE_PATH`** | SQLite file (default `bot/bot.db`). |
| **`TOS_FILE`** | Default TOS text for `/deploy tos` (`tos.txt`). |
| **`TEMPLATES_FILE`** | Default queue templates (`templates.json`). |

## Embed palette (`utils/embeds.py`)

User-facing feedback uses consistent colors:

- **`user_hint`** — blue (`HINT_BLUE`) — wrong input, missing config.
- **`user_warn`** — amber (`WARN_ORANGE`) — permissions, blocked actions.
- **`success_embed`** — green (`SUCCESS`).
- **`info_embed`** / **`queue_embed`** / most quotes — **`PRIMARY`** (`DEFAULT_EMBED_COLOR` `0x242429`).

## Related docs

- [config.md](config.md) — `/config` and payment strings.
- [database-reference.md](database-reference.md) — tables and keys.
