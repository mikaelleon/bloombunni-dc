# Ticketing system

> **Updated reference:** See **[tickets-and-panels.md](tickets-and-panels.md)** for the current command set, gates (TOS, shop open, age verification), quote integration, and payment workflow. Configuration is done with **`/setup`** and **`/config`** (not `/serverconfig`).

---

This document describes how the bot’s **commission / support ticketing** feature works: configuration, user flow, what gets shown in Discord, persistence, and closing behavior.

Implementation lives mainly in `cogs/tickets.py` with data in SQLite (`database.py`).

---

## Overview

- Staff post a **ticket panel** in a channel: an embed plus up to **five** interactive buttons (one per “ticket type”).
- A member clicks a button, passes **TOS** and **shop open** checks, picks a **commission type** from a select menu, then fills a **modal** with the configured questions.
- The bot creates a **private text channel** under a category, records the ticket in the database, and posts a **welcome embed** plus a **Close Ticket** button.
- **Staff** or the **ticket owner** can close via the button or `/close`. The bot generates an **HTML transcript**, DMs it to the client (if possible), posts it to the **transcript channel**, then deletes the ticket channel after a **15-second** countdown.

---

## Prerequisites (`/setup` / `/config`)

Before ticketing works end-to-end, the server should configure at least:

| Setting | Purpose |
|--------|---------|
| **Ticket category** | Default category for new ticket channels (unless overridden per button). |
| **Staff role** | Used for `/ticketpanel` setup check, ticket channel overwrites, and who may close tickets. |
| **TOS agreed role** | Required on the user before opening a ticket; user must have this role (after agreeing via the TOS panel). |
| **TOS channel** | Optional; used in prompts when the user lacks the TOS role. |
| **Transcript channel** | Where closed-ticket transcripts are posted. |

The **shop open/closed** state (database) is also checked when a user clicks a panel button: if commissions are closed, the user gets a warning and no ticket is created.

---

## Data model (SQLite)

### `ticket_panel` (one row per guild)

Stores where the panel message lives and how it looks:

- `guild_id`, `channel_id`, `message_id`
- `embed_title`, `embed_description`, `embed_color`, `embed_footer`

### `ticket_buttons` (up to 5 per guild)

Each button type:

- `button_id` — stable ID (slug from label + uniqueness suffix)
- `guild_id`, `label`, optional `emoji`, `color` (blurple / green / red / grey)
- `category_id` — optional; if set, tickets for this button open under that category; else the server’s default ticket category is used
- `form_fields` — optional JSON array defining modal fields (see **Form fields** below)
- `select_options` — optional JSON array of strings for the **commission type** dropdown (defaults built into the cog if unset)

### `tickets` (open and closed rows)

- `channel_id` (primary key), `guild_id`, `client_id`
- `button_id`, `answers` (JSON of submitted fields)
- `opened_at`, `closed_at`
- `order_id`, `order_number` — used when staff register an order via `/queue` (linked workflow)
- `transcript_sent`

---

## Staff commands

### `/ticketpanel`

**Who:** Staff (`is_staff`).

**Does:** Validates ticket **category** and **staff role** exist. Resolves the target channel (mention or ID). Deletes the **previous** panel message for this guild (if any), posts a new **embed** (title, description, color, optional footer), and attaches the **dynamic button view** for all configured `ticket_buttons` rows. Saves panel metadata to `ticket_panel` and registers the view with the bot for persistence.

**If no buttons exist yet:** The embed description is appended with a hint to use `/ticketbutton add`.

### `/ticketbutton`

| Subcommand | Description |
|------------|-------------|
| `add` | Add a button (max **5** per server). Label must be unique. Optional emoji, color, per-button category. |
| `remove` | Remove by label; refreshes the panel message. |
| `list` | Ephemeral summary of buttons (emoji, color, category, default vs custom form). |

Adding/removing triggers **`_refresh_panel_message`**: rebuilds the same embed from DB, deletes the old panel message, posts a new one, updates `message_id`, re-`add_view`s.

### `/ticketform`

| Subcommand | Description |
|------------|-------------|
| `set` | Set **modal** fields as a **JSON array** (1–4 fields; commission type is separate). Each item: `label`, `placeholder`, `required`, `long` (paragraph vs short). |
| `reset` | Clear custom JSON → default fields (see **Default form**). |
| `preview` | Ephemeral list of fields for a button. |
| `setoptions` | Comma-separated list for **commission type** select (max 25 options, 100 chars each). |
| `resetoptions` | Restore default commission type list. |

### `/deploy` (under `TicketsCog`)

| Subcommand | Description |
|------------|-------------|
| `tos` | Resolves channel → saves `TOS_CHANNEL` → delegates to **ShopCog** to post the TOS agreement panel. |
| `payment` | Resolves channel → saves `PAYMENT_CHANNEL` → delegates to **PaymentCog** to post the payment panel. |

Use the global **`/setup`** wizard (separate cog) for guided channel/role mapping; **`/config view`** lists current values.

These are related onboarding panels, not the ticket channel itself.

### `/close`

Same closing pipeline as the **Close Ticket** button (see **Closing a ticket**).

---

## Default form and commission types

If `form_fields` is missing or invalid JSON, the cog uses **DEFAULT_MODAL_FIELDS**:

1. Number of Characters  
2. Mode of Payment  
3. Reference Links  
4. Additional Notes  

Commission type is **not** in the modal: it comes from a **select menu** first.

Default **select** options (if `select_options` unset): Chibi, Chibi Scene, Normal / Semi-Realistic, Bust, Fullbody, Other.

---

## User flow (opening a ticket)

High-level sequence:

1. User clicks a panel button (`custom_id` pattern `bbtp:{guild_id}:{button_id}`).
2. **Guild + member** check; button row must match DB and guild (stale buttons show a “refresh `/ticketpanel`” style message).
3. **TOS role** check — user must have the configured TOS agreed role.
4. **Shop open** check — `db.shop_is_open_db()` must be true.
5. **One open ticket per user per guild** — if a row exists in `tickets` with `closed_at IS NULL`, user gets an ephemeral link to the existing channel.
6. Ephemeral **info embed**: “Commission type” / “What type of commission are you ordering?” plus **`CommissionTypeSelectView`** (select + 60s timeout).
7. User chooses commission type → **`CommissionModal`** opens (title: “Please answer the question below.”) with up to four text inputs from `form_fields`.
8. On submit, interaction is **deferred ephemerally**; channel creation runs.

### Channel creation

- **Category:** Button’s `category_id` if valid; else `TICKET_CATEGORY` from server config.
- **Name:** `ticket-{sanitized_username}`.
- **Permissions:** `@everyone` cannot view; **client** and **bot** can view/send; **staff role** gets extended permissions (messages, history, manage messages/channels, attach, embed).

### Messages posted in the new channel

1. **`@mention`** of the member (best-effort; errors ignored).
2. **Welcome embed** (primary/accent color `PRIMARY`):
   - **Title:** `🎀 {button_label} ticket — {display_name}`
   - **Description:** Lines built from answers, ordered by `WELCOME_FIELD_ORDER` (`Commission Type` first, then modal fields in default order), then any extra keys; truncated ~3900 chars.
3. Same message includes **`CloseTicketView`**: one button, **Close Ticket** (danger style, `custom_id` `ticket_close`).

### Ephemeral confirmation to the user

- **Success embed:** “Ticket opened” with “Go to #channel”.

---

## Closing a ticket

**Who can close:** User with **staff role**, or the **ticket client** (`client_id` in DB).

**Entry points:**

- **Close Ticket** button (`CloseTicketView` → `handle_close_button` → `_run_close`)
- Slash **`/close`** (same `_run_close`)

**Steps:**

1. Must be a **text channel** in a guild; channel must have an **open** ticket row (`get_ticket_by_channel`).
2. **Defer** ephemerally.
3. **`generate_transcript`** (`utils/transcript`) → HTML file.
4. **DM** the client member: embed “Ticket closed” + transcript attachment (if `Forbidden`, flag `dm_ok = false`).
5. **Transcript channel:** post embed “Transcript” with channel name + file copy.
6. If DM failed but transcript channel exists, optional warning message there mentioning the user.
7. **Ephemeral follow-up** to closer: success if DM worked; hint-style message if transcript only went to the log channel.
8. **`close_ticket_record`** in DB (`closed_at`, `transcript_sent`).
9. **Countdown:** bot sends `Channel closing in **n** seconds...` for **15** down to **1**, one second apart (stops if send fails).
10. **`channel.delete`** with reason “Ticket closed”.

---

## Persistent views (after bot restart)

On startup, `register_ticket_persistent_views` (called from `main.py` `setup_hook`):

1. Registers **`CloseTicketView()`** globally (no `message_id`) so existing **Close Ticket** buttons keep working.
2. For each row in `ticket_panel`, loads that guild’s buttons and **`add_view(view, message_id=...)`** so panel buttons work without re-clicking.

Ephemeral **commission select** / **modal** are **not** registered persistently (they are short-lived UI).

---

## Integration with other features

- **Queue:** `/queue` (in `cogs/queue.py`) can bind orders to a ticket channel; ticket rows store `order_id` / `order_number` when updated.
- **Shop / TOS / Payment:** Ticketing enforces TOS role and shop state at open; `/deploy tos` and `/deploy payment` on this cog post those panels (after channels are mapped via **`/setup`** / **`/config`**).

---

## Limits and behavior notes

- **Max 5** ticket buttons per guild.
- **Max 4** custom modal fields (Discord modal limits + design: commission type uses select).
- **Max 25** select options for commission type.
- Panel button `custom_id` includes `guild_id` to scope interactions.
- Stale buttons (DB mismatch) require staff to re-run **`/ticketpanel`** to refresh the message and sync IDs.

---

## Quick reference — user-visible surfaces

| Location | What appears |
|----------|----------------|
| Panel channel | Staff-configured embed + up to 5 labeled buttons |
| Ephemeral (after button) | Commission type select; then modal with form fields |
| Ephemeral (after open) | Success + link to new ticket channel |
| Ticket channel | Ping, welcome embed with answers, **Close Ticket** button |
| User DM (on close) | “Ticket closed” + HTML transcript (if allowed) |
| Transcript channel | Transcript embed + file; optional warning if DM failed |
| Ephemeral (closer) | Closing confirmation or “transcript only in log channel” |

---

*Last updated to match `cogs/tickets.py` and ticket-related tables in `database.py`.*
