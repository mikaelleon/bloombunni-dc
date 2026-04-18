# Config (`cogs/config_cmd.py`)

## Table of contents

- [`/config view`](#config-view)
- [`/config reset`](#config-reset)
- [`/config payment`](#config-payment-subcommands)

**Who can use it:** `can_manage_server_config` — **Administrator**, **Manage Server**, **or** mapped **staff role** (`utils/checks.py`).

Guild data lives in SQLite: **`guild_settings`** (integer channel/role IDs and numeric values), **`guild_string_settings`** (text/URLs), plus quote tables managed by **`/config reset` → pricing**.

## `/config view`

- Builds lines via **`status_lines_for_guild`** (`utils/guild_config_display.py`): every mapped **channel slot**, **category slot**, and **role slot** from `guild_keys.py`, showing mention/name or “not set” / “missing”.
- Appends a **Payment panel** section for each key in `gk.PAYMENT_ALL_KEYS` (truncated preview).
- **Order ID prefix** from `ORDER_ID_PREFIX` (default label if unset: **MIKA**).
- **Warn threshold** (`WARN_THRESHOLD_KEY`) or “default 3”.
- **Custom warn reason presets** — count of extra strings (`warn_reason_templates_json`), or “none”.
- If the guild has **quote base price rows**, appends a line with the **count** of rows.
- Long output is split into **paged embeds** (`PagedEmbedView`).

**Typical line shapes (non-exhaustive):**

```text
**Queue (order list)** — #queue-channel
**New tickets** — `CategoryName` (category)
**Staff** — @StaffRole
**Payment panel (text / URLs)**
**GCash instructions (body text)** — `first 120 chars…`
**Order ID prefix** — `MIKA`
**Warn threshold** — 3
```

## `/config reset`

| Choice value | Clears |
|--------------|--------|
| `tickets` | Ticket categories, transcript channel, start-here, verification channel, age-verified role (see `RESET_GROUP_KEYS` in `config_cmd.py`). |
| `queue` | `QUEUE_CHANNEL`, `ORDER_NOTIFS_CHANNEL`, and string key `ORDER_ID_PREFIX`. |
| `shop` | TOS channel, shop status channel, TOS agreed role, commissions open role. |
| `payment` | `PAYMENT_CHANNEL` and **all** `PAYMENT_*` string keys. |
| `channels_roles` | Staff, Boostie, Reseller, Please vouch, Feedback pending, Review reward roles; vouches channel, **feedback** channel (owner `/review` inbox), warn log; **custom warn reason presets** (`warn_reason_templates_json`). |
| `pricing` | **Entire quote DB for the guild** via `clear_quote_data_for_guild` (not just keys). |

Flow: ephemeral **Confirm reset** / **Cancel** view. Confirm deletes keys or clears pricing; success embed confirms.

## `/config payment` (subcommands)

All require manage-server-style permission.

| Command | Stores | Success message |
|---------|--------|-----------------|
| **`gcash_details`** | `payment_gcash_details` | “GCash embed body updated.” |
| **`paypal_link`** | `payment_paypal_link` | URL must be `http://` or `https://` |
| **`kofi_link`** | `payment_kofi_link` | Same URL rule |
| **`gcash_qr`** | `payment_gcash_qr_url` | Direct image URL for QR |
| **`paypal_qr`** | `payment_paypal_qr_url` | Direct image URL for QR |

**`/deploy payment`** requires **every** string in `PAYMENT_ALL_KEYS` to be non-empty (`is_payment_config_complete`): GCash body, PayPal link, Ko‑fi link, GCash QR URL, and PayPal QR URL. Individual buttons still validate their own subset when clicked (e.g. Ko‑fi only needs the Ko‑fi link at runtime).
