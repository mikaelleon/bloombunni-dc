# Tickets and panels (`cogs/tickets.py`)

## Table of contents

- [Panel commands](#panel-commands)
- [Deploy group](#deploy-group-deploy)
- [User flow](#user-flow-panel-button--ticket)
- [Ticket workflow commands](#ticket-workflow-commands)
- [Closing](#closing)
- [Warn appeal channels](#warn-appeal-channels)

Configurable **ticket panel** (embed + up to **five** buttons), **modal** intake with per-button JSON forms, **quote** integration, **payment** workflow commands, and **close + transcript**.

**Permission:** most staff commands use **`@is_staff()`** (mapped **staff role** in guild settings).

## Panel commands

### `/ticketpanel`

Parameters: **`channel`** (mention/ID string), **`title`**, **`description`**, optional **`color`** (hex), **`footer`**.

- Requires **ticket category** + **staff role** configured; else **`user_hint("Configuration required", …)`**.
- Deletes the **previous** panel message if `ticket_panel` row exists (best effort).
- If no buttons exist, appends italic line: *No ticket types configured yet…*
- Stores row in **`ticket_panel`** and registers the dynamic **`View`** on the new message id.

**Staff follow-up:** **`success_embed("Ticket panel", "✅ Ticket panel posted in {channel}.")`**

### `/ticketbutton` (group)

| Subcommand | Behavior |
|------------|----------|
| **`add`** | Max **5** buttons per guild. **`label`** must be unique. Builds `button_id` slug; optional **`category`** override; **`color`** ∈ blurple/green/red/grey. Inserts `ticket_buttons` row; refreshes panel message. Success lists button labels. |
| **`remove`** | By label; refreshes panel. |
| **`list`** | Ephemeral **`info_embed`** — each line: label, emoji, color, category name, form default vs custom, **age gate** flag. |
| **`agegate`** | Sets `require_age_verified` for NSFW-gated types; user must have **`AGE_VERIFIED_ROLE`** (and optional **`VERIFICATION_CHANNEL`** hint). |

### `/ticketform` (group)

| Subcommand | Behavior |
|------------|----------|
| **`set`** | JSON array of **1–4** field objects: `label`, `placeholder`, `required`, `long` (paragraph vs short). |
| **`reset`** | Clears custom JSON → default modal fields (Mode of Payment, Reference Links, Additional Notes). |
| **`preview`** | Shows parsed fields for a button. |
| **`setoptions`** | Comma-separated **commission type** options for the select (max 25, 100 chars each). |
| **`resetoptions`** | Restores default option list (`Chibi`, `Chibi Scene`, …). |

Default modal fields are in `DEFAULT_MODAL_FIELDS` in code; welcome embed field order uses `WELCOME_FIELD_ORDER`.

## Deploy group: `/deploy`

| Command | Behavior |
|---------|----------|
| **`tos`** | Resolves channel → sets **`TOS_CHANNEL`** → delegates to **`ShopCog.run_setup_tos`** (embed from `config.TOS_FILE`, **`TOSAgreeView`** button). Persists `persist_panels` entry `"tos"`. |
| **`payment`** | Sets **`PAYMENT_CHANNEL`** → **`PaymentCog.run_setup_payment`** (requires all `/config payment` strings). Posts **`Mode of Payment`** embed + **`PaymentView`**. |

## User flow (panel button → ticket)

1. **`handle_panel_button`**: must have **TOS agreed role**; optional **age gate**; **`shop_is_open_db()`** must be true; at most **one open ticket** per user per guild.
2. Ephemeral **`CommissionTypeSelectView`** → modal **`handle_modal_submit`**.
3. Creates **text channel** under button/category **`TICKET_CATEGORY`** with overwrites (user + staff).
4. **`compute_quote_totals`** + **`build_quote_embed`** posted; **`insert_ticket_open`** with status **`awaiting_payment`**.
5. **Welcome embed:** title `🎀 {button_label} ticket — {display_name}`; TAT / installment / loyalty lines; modal answers; **`CloseTicketView`**.
6. **Payment embed:** `💳 Awaiting payment` — due lines derived from **total to send** (PHP thresholds ₱500, USD $25); lists GCash/PayPal/Ko‑fi hints from DB strings.
7. **Staff shortcuts** embed listing **`/quote recalculate`**, **`/payment confirm`**, **`/stage`**, **`/revision log`**, **`/references add`**.

## Ticket workflow commands

### `/payment confirm` (group `payment`)

- In ticket channel: loads ticket + quote snapshot; if **`order_id`** already set → marks **in progress** + downpayment flag only.
- Else calls **`register_order_in_ticket_channel`** (queue cog) to create order, queue card, rename channel to **noted_***, post templates + **OrderStatusView** dropdown.

### `/stage`

- Choices from **`WIP_STAGES`** (Sketch → Delivered…). Updates `wip_stage` in DB; posts **`📍 Stage update`** embed.

### `/revision log`

- **`db.log_ticket_revision`** — first revisions free, then **+₱200** each (logic in DB). Posts **Revision** embed with optional note; mentions client.

### `/references add` / `/references view`

- Append URL to `references_json` / list numbered links (ephemeral **`info_embed`**).

## Closing

- **`/close`** or **`CloseTicketView`** → **`_run_close`**: HTML **`generate_transcript`**, DM to client, post to **`TRANSCRIPT_CHANNEL`**, **`close_ticket_record`**, 15s countdown messages, **delete channel**.
- Staff **or ticket owner** may close.

## Raw message patterns (examples)

**Open ticket — payment block:**

```text
Title: 💳 Awaiting payment
Description: {due lines from thresholds}
**Total to send (incl. fees):** …
**Artist commission (no fee to you):** …
+ configured payment method hints
```

**Staff shortcuts embed (description):**

```text
**/quote recalculate** — update quote embed
**/payment confirm** — payment received → queue + in progress
**/stage** — WIP stage update
**/revision log** — log a revision
**/references add** — save reference links
```

## Persistence

- **`register_ticket_persistent_views`** on startup re-adds **`CloseTicketView`** and each guild’s panel **`View`** for known message IDs.

## Warn appeal channels

Tickets created from the **warn appeal** DM button use `button_id = warn_appeal` and do **not** count toward the “one open commission ticket” check. See [warnings.md](warnings.md).

## Related docs

- [queue-templates-loyalty.md](queue-templates-loyalty.md) — what happens after **`/payment confirm`**.
- [quotes-and-pricing.md](quotes-and-pricing.md) — quote math.
- [warnings.md](warnings.md) — warn appeal tickets and **`/clearwarn`** in-channel.
