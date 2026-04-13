# Setup wizard (`cogs/setup_wizard.py`)

**Permission:** `can_manage_server_config` (same as `/config` — **Administrator**, **Manage Server**, or **staff role**).

## `/setup`

Sends an **ephemeral** message with **`WizardMainView`**: six buttons that each start a sub-flow. Completing a flow writes to **`guild_settings`** via `db.set_guild_setting` and returns to the main menu. Sessions are also recorded in **`wizard_sessions`** (saved on open; **`/setup_resume`** does not restore UI state).

### Main menu buttons

| Button | Flow |
|--------|------|
| **Tickets & Panels** | Six steps (`TICKET_FLOW`): **New tickets** category → **Noted** → **Processing** → **Done** → **Transcript** text channel → **Start here / panel** text channel. (Age verification channel/role are separate guild settings if you use **`/ticketbutton agegate`**.) On finish: saves IDs; success embed tells staff to use **`/ticketpanel`**. |
| **Queue & Orders** | Step 1: **queue** channel. Step 2: **order notifications** channel. Saves `QUEUE_CHANNEL` and `ORDER_NOTIFS_CHANNEL`. |
| **Shop & TOS** | Four steps: TOS **text** channel → **TOS agreed** role → **shop status** embed channel → **commissions open** role. Success: run **`/deploy tos`**, use **`/shop`** for open/close. |
| **Payment** | Single channel select for **payment panel** channel (`PAYMENT_CHANNEL`). Then staff must set all **`/config payment`** strings and run **`/deploy payment`**. |
| **Channels & Roles** | Roles: Staff → Boostie → Reseller → Please vouch. Channels: Vouches → Warn log. |
| **Pricing** | Informational only: points to **`/setprice`**, **`/quoteextras`**, **`/setdiscount`**, **`/setcurrency`**, **`/pricelist`**. |

Timeouts on views are **600s** (payment sub-view **300s**).

## `/setup_resume`

Ephemeral hint that **ephemeral wizard state cannot be restored**; run **`/setup`** again.

## Relationship to other commands

- **`/ticketpanel`** — actually posts the embed + buttons in the chosen start-here channel.
- **`/deploy tos`** / **`/deploy payment`** — post TOS and payment panels after channels and strings exist.
