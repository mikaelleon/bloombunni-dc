# Database reference (`database.py`)

**Engine:** SQLite via **aiosqlite**. **Path:** `config.DATABASE_PATH` (default **`bot/bot.db`** next to `config.py`).

`init_db()` creates tables and runs **migrations** for `tickets` / `ticket_buttons` / `tickets` extra columns.

## Tables (summary)

| Table | Purpose |
|-------|---------|
| **`tickets`** | Open/closed ticket per **channel_id** PK: guild, client, button, answers JSON, order link, quote fields, status, WIP stage, revisions, references, downpayment flag, etc. |
| **`orders`** | Queue orders: `order_id`, handler/client, item/amount/mop/price, ticket channel, status, `queue_message_id`, timestamps. |
| **`warns`** | Warn records with moderator and reason. |
| **`vouches`** | Vouch text + optional order id. |
| **`loyalty`** | Per-client completed order counts. |
| **`tos_agreements`** | User id → agreed timestamp (button flow). |
| **`shop_state`** | Single row: open flag, last toggle time, toggled_by. |
| **`queue_message`** | Legacy/global queue pointer (single-row style in schema). |
| **`drops`** | Logged delivery links. |
| **`message_templates`** | Overrides for `templates.json` keys. |
| **`persist_panels`** | Panel name → channel/message id (**tos**, **shop_status**, **payment**, etc.). |
| **`sticky_messages`** | Per-channel sticky config + last posted message id. |
| **`guild_settings`** | `(guild_id, setting_key) → integer` — channels, roles, warn threshold, payment channel id, etc. Keys in **`guild_keys.py`**. |
| **`guild_string_settings`** | `(guild_id, setting_key) → text` — order prefix, payment URLs, GCash body, etc. |
| **`ticket_panel`** | One row per guild: panel message location + embed title/description/color/footer. |
| **`ticket_buttons`** | Button definitions: label, emoji, color, category, form JSON, select options, age gate. |
| **`quote_guild_settings`** | Extras + brand name. |
| **`quote_base_price`** | Matrix of PHP prices. |
| **`quote_role_discount`** | Boostie/reseller discounts. |
| **`quote_currency`** | Enabled FX codes for quote footer. |
| **`wizard_sessions`** | In-progress `/setup` bookkeeping (not full UI restore). |
| **`guild_flags`** | e.g. **`setup_hint_sent`** for first-join prompt. |

## Key helpers (non-exhaustive)

- **`get_guild_setting` / `set_guild_setting`** — integer map.
- **`get_guild_string_setting` / `set_guild_string_setting`** — text map.
- **`guild_has_any_config`** — whether setup hint should be skipped.
- **`clear_quote_data_for_guild`** — pricing reset from `/config reset`.

For command-level behavior, see the feature docs linked from [README.md](README.md).
