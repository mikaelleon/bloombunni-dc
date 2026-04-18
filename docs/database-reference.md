# Database reference (`database.py`)

**Engine:** SQLite via **aiosqlite**. **Path:** `config.DATABASE_PATH` (default **`bot/bot.db`** next to `config.py`).

`init_db()` creates tables and runs **migrations** for `tickets` / `ticket_buttons` / `tickets` extra columns.

## Tables (summary)

| Table | Purpose |
|-------|---------|
| **`tickets`** | Open/closed ticket per **channel_id** PK: guild, client, button, answers JSON, order link, quote fields, status, WIP stage, revisions, references, downpayment flag, etc. |
| **`orders`** | Queue orders: `order_id`, handler/client, item/amount/mop/price, ticket channel, status, `queue_message_id`, timestamps. |
| **`warns`** | Warn records with moderator and reason. |
| **`vouches`** | Vouch text + optional order id (includes fallback ticket-name tags from client `/vouch`). |
| **`commission_reviews`** | Client **`/review`** submissions per guild + reviewer + order_id (unique); ratings, text, dropdown answers, optional discount code. |
| **`loyalty`** | Per-client completed order counts. |
| **`tos_agreements`** | User id → agreed timestamp (button flow). |
| **`shop_state`** | Single row: open flag, last toggle time, toggled_by. |
| **`queue_message`** | Queue message pointer row (single-row style in schema). |
| **`drops`** | Logged delivery links. |
| **`message_templates`** | Overrides for `templates.json` keys. |
| **`persist_panels`** | Panel name → channel/message id (**tos**, **shop_status**, **payment**, etc.). |
| **`sticky_messages`** | Per-channel sticky config + last posted message id. |
| **`guild_settings`** | `(guild_id, setting_key) → integer` — channels, roles, warn threshold, payment channel id, etc. Keys in **`guild_keys.py`**. |
| **`guild_string_settings`** | `(guild_id, setting_key) → text` — order prefix, payment URLs, GCash body, warn reason preset JSON, etc. |
| **`ticket_panel`** | One row per guild: panel message location + embed title/description/color/footer. |
| **`ticket_buttons`** | Button definitions: label, emoji, color, category, form JSON, select options, age gate. |
| **`quote_guild_settings`** | Extras + brand name. |
| **`quote_base_price`** | Matrix of PHP prices. |
| **`quote_role_discount`** | Boostie/reseller discounts. |
| **`quote_currency`** | Enabled FX codes for quote footer. |
| **`wizard_sessions`** | In-progress `/setup` bookkeeping (not full UI restore). |
| **`guild_flags`** | e.g. **`setup_hint_sent`** for first-join prompt. |
| **`embed_builder_meta`** | Per-guild counter for last assigned **`EMB-XXX`** id. |
| **`embed_builder_embeds`** | Saved embed drafts/rows (`/embed`). |
| **`embed_builder_staff_roles`** | Roles allowed to use **`/embed`** and **`/button`**. |
| **`embed_builder_audit`** | Optional audit lines for embed builder actions. |
| **`button_builder_meta`** | Per-guild counter for last assigned **`BTN-XXX`** id. |
| **`button_builder_buttons`** | Saved button configs (`/button`): label, style, action type, role id, responses JSON, etc. |
| **`button_builder_audit`** | Optional audit lines for button builder actions. |
| **`ar_builder_meta`** | Per-guild counter for last assigned **`AR-XXX`** id. |
| **`ar_builder_entries`** | Saved autoresponder configs (`/ar`): trigger type/match mode, trigger group text, response, status, priority, cooldown, role/channel conditions, counters. |
| **`ar_builder_user_cooldowns`** | Per-user last-fire timestamps for autoresponder cooldown checks. |
| **`ar_builder_audit`** | Optional audit lines for autoresponder actions and fires. |
| **`loyalty_card_meta`** | Per-guild loyalty card counter + recycled card-number pool. |
| **`loyalty_card_images`** | Stamp image states per guild (`stamp_index` => `image_url`). |
| **`loyalty_cards`** | Active/voided loyalty card rows (`LC-XXX`): user, stamps, card message/thread ids, void timers. |

## Key helpers (non-exhaustive)

- **`get_guild_setting` / `set_guild_setting`** — integer map.
- **`get_guild_string_setting` / `set_guild_string_setting`** — text map.
- **`guild_has_any_config`** — whether setup hint should be skipped.
- **`clear_quote_data_for_guild`** — pricing reset from `/config reset`.
- **`create_builder_embed` / `get_builder_embed` / `list_builder_embeds` / `patch_builder_embed` / `delete_builder_embed`** — `/embed` storage.
- **`create_builder_button` / `get_builder_button` / `list_builder_buttons` / `patch_builder_button` / `delete_builder_button` / `clone_builder_button`** — `/button` storage.
- **`create_autoresponder` / `get_autoresponder` / `list_autoresponders` / `list_active_autoresponders` / `patch_autoresponder` / `delete_autoresponder`** — `/ar` storage.
- **`get_autoresponder_last_fire` / `bump_autoresponder_fire_count`** — runtime cooldown + fire counters.
- **`allocate_loyalty_card_number` / `recycle_loyalty_card_number`** — loyalty card ID lifecycle.
- **`upsert_loyalty_card_image` / `list_loyalty_card_images`** — stamp state image config.
- **`insert_loyalty_card` / `patch_loyalty_card` / `get_active_loyalty_cards_for_user` / `delete_loyalty_card_row`** — loyalty card runtime storage/update.
- **`insert_commission_review` / `has_commission_review` / `list_reviewable_order_tags_for_client`** — **`/review`** storage and autocomplete union (orders + vouch fallback tags).

For command-level behavior, see the project [`README.md`](../README.md), [`situational-flows.md`](situational-flows.md), and the feature docs linked from [README.md](README.md).
