# Mika Shop — Discord Bot

A Discord bot for running a **small art commission shop** in your server: agree to rules, open private tickets, track orders on a queue, take payments, and handle vouches and warnings. This guide is written so **you do not need to be a programmer** to understand or set it up.

---

## Table of contents

1. [Overview](#overview)
2. [Current progress](#current-progress)
3. [What the bot can do](#what-the-bot-can-do)
4. [What the bot does not do (yet)](#what-the-bot-does-not-do-yet)
5. [How the pieces fit together](#how-the-pieces-fit-together)
6. [Setup (step by step)](#setup-step-by-step)
7. [Discord settings your server needs](#discord-settings-your-server-needs)
8. [Core features and sub-features](#core-features-and-sub-features)
9. [Commands by who can use them](#commands-by-who-can-use-them)
10. [Hosting the bot online](#hosting-the-bot-online)
11. [Files and folders (optional)](#files-and-folders-optional)
12. [More documentation](#more-documentation)

---

## Overview

**Mika Shop** helps you run commissions in Discord: customers use **buttons** and **slash commands** (`/` commands) to open tickets, staff register orders with **`/queue`** or **`/payment confirm`**, and the bot keeps **HTML transcripts** (with optional ticket metadata) when a ticket closes. **Only the bot token** is read from your **`.env`** file. **Channels, roles, and payment text (GCash, PayPal, Ko-fi, QR image links)** are set **per server** with **`/config`** (and the **`/setup`** wizard) and stored in the database—no payment info in `.env`.

---

## Current progress

Overall core bot progress: **84%**
Planned expansion systems (`plans/`) progress: **0%**

- [x] Core ticketing flow (panel, open, close, transcript) - **100%**
- [x] Queue and order management pipeline - **100%**
- [x] Payment info panels and payment-confirm flow - **100%**
- [x] Quote calculator and ticket quote integration - **100%**
- [x] Staff moderation and utility commands (warn, sticky, drop, vouch) - **100%**
- [x] Embed builder (`/embed`) and button builder (`/button`) for staff — **implemented** (panels that combine embeds + buttons as saved objects are not implemented yet)
- [x] Autoresponder builder foundation (`/ar`) — **implemented (core)**: builder, message triggers, conditions, cooldown, pause/resume, ID autocomplete
- [x] ID autocomplete rollout for edit/post/delete-style commands across builders (`/embed`, `/button`, `/ar`)
- [x] Conditions editor UX upgrade (role/channel dropdown selectors; no developer mode IDs needed)
- [x] Ephemeral confirmation auto-dismiss (10s) for `/ar` micro-updates and status actions
- [ ] Autoresponder full-spec parity (`autoresponder builder/autoresponder-full-spec.md`) — **in progress**
- [ ] Remaining polish and optional enhancements from backlog - **20%**
- [ ] Plan 01: MYO system (`plans/01_MYO_SYSTEM.md`) - **0%**
- [ ] Plan 02: Batch and slot system (`plans/02_BATCH_SLOT_SYSTEM.md`) - **0%**
- [ ] Plan 03: Currency system (`plans/03_CURRENCY_SYSTEM.md`) - **0%**
- [ ] Plan 04: Gacha system (`plans/04_GACHA_SYSTEM.md`) - **0%**
- [ ] Plan 05: Casino minigames (`plans/05_CASINO_MINIGAMES.md`) - **0%**
- [ ] Plan 06: Collectible system (`plans/06_COLLECTIBLE_SYSTEM.md`) - **0%**
- [ ] Plan 07: MYO content/config tools (`plans/07_MYO_CONTENT_CONFIG.md`) - **0%**

---

## Builder implementation checklist

### Embed builder checklist (`/embed`)

- [x] Create/edit/list/show/showlist
- [x] Modal editing and live preview
- [x] Staff role allow-list (`/embed config staffrole`)
- [x] ID autocomplete in edit/show commands
- [ ] Full panel-builder parity from spec (`button builder/embed-button-improvements.md`)

### Button builder checklist (`/button`)

- [x] Create/edit/clone/list/post
- [x] Action modes: assign/remove/toggle role
- [x] Posted live button callback wiring
- [x] ID autocomplete in edit/clone/post commands
- [ ] Full action parity from spec (multi-role, exclusive groups, analytics, history)

### Autoresponder builder checklist (`/ar`)

- [x] Create/edit/delete/list/pause/resume
- [x] Trigger groups + match modes (`exact`, `startswith`, `endswith`, `includes`, `word_boundary`)
- [x] Conditions editor with role/channel dropdowns + cooldown modal
- [x] Conditions update toasts auto-dismiss in 10s
- [x] Per-user cooldown and runtime fire handling
- [x] ID autocomplete in edit/delete/pause/resume
- [x] Auto-dismiss short confirmation toasts (10s) in conditions and status updates
- [ ] Full function parity from spec (`{requirearg}`, inventory/currency modifiers, full redirect suite)
- [ ] Event triggers (join/leave/role/reaction)
- [ ] Analytics/version history/templates/import-export
- [ ] Chain flows and panel/template integrations

---

## What the bot can do

- **Onboarding:** Terms of Service (TOS) panel with an “I agree” button that gives a role.
- **Shop hours:** Open or close commissions; optional visibility rules on your “Start Here” area.
- **Tickets:** Private ticket channels under categories you pick; **quote wizard** (tier, characters, background, rush) posts a **PHP + FX** quote from your **price matrix**; welcome text includes **payment terms**, **turnaround estimates**, and optional **installment** hints; channel names can look like **`sr-bu-username`** for easier queue scanning. Optional **NSFW / age gate** per ticket button (requires **age verified** role + verification channel). Open/close with transcripts (optionally including revision and quote totals).
- **Orders:** Register orders from a ticket with **`/queue`**, or confirm payment with **`/payment confirm`** (same queue pipeline when no order exists yet). Show them on a **queue channel**, move ticket channels through **Noted → Processing → Done** stages, and use **templates** for wording.
- **Payments:** A panel with buttons for GCash, PayPal, and Ko-fi (each server sets copy and URLs with **`/config payment`** …). Tickets can also show an **awaiting payment** embed with amounts due.
- **Commission quotes:** Staff maintain **base prices** and add-ons in the database; anyone can run **`/quote calculator`**; staff can **`/quote recalculate`** inside a ticket to re-post an updated quote.
- **Loyalty:** Track completed orders per client and show milestones.
- **Vouches:** Dedicated vouch channel behavior and manual vouch logging.
- **Delivery:** Staff can send a “delivery” DM with a link; history can be listed.
- **Moderation:** Warn members, DM a notice, optional auto-ban after a set number of warns, warn log channel.
- **Sticky messages:** Keep a chosen embed reposted at the bottom of a channel.
- **Server wiring:** Map channels and roles by **picking them in slash commands** (`/setup` wizard or **`/config view`** to audit).
- **Embeds (staff):** Create and edit server-scoped embeds with IDs like **`EMB-001`** using **`/embed`** — interactive builder, variable placeholders (for example `{user_name}`, `{server_name}`), list/browse, and post to a channel.
- **Role buttons (staff):** Create interactive role buttons with IDs like **`BTN-001`** using **`/button`** — assign, remove, or toggle a role; optional emoji, color, staff-only notes, and custom ephemeral messages; post to a channel. Access is limited to **server owner**, **Administrators**, and roles allowed via **`/embed config staffrole`** (shared allow-list with the embed builder).
- **Autoresponders (staff/admin):** Build message-triggered autoresponders with IDs like **`AR-001`** using **`/ar`** — trigger groups, matchmode (`exact`, `startswith`, `endswith`, `includes`, `word_boundary`), response text, cooldown, role/channel conditions, live builder preview, pause/resume.

---

## What the bot does not do (yet)

- **No built-in economy or fake currency** (no coins, shop balances, or games).
- **No saved “panel” objects** that bundle one embed plus a full button layout (that roadmap lives in `button builder/embed-button-improvements.md`; the bot does **not** yet match every Mimu-style feature described there).
- **No automatic payments or invoicing**—it only **shows** payment info you configure; it does not charge cards or verify PayPal.
- **No built-in AI or image generation.**
- **No full moderation suite** (no automod, timeout commands, or ban suite beyond warn-driven auto-ban if you enable that flow).
- **Prefix commands** (`!command`) are **not** used for shop features; the bot is built around **slash commands** and **buttons**.

*If you add custom code later, some of these can change.*

---

## How the pieces fit together

1. **You** turn the bot on and put **only `BOT_TOKEN`** in `.env` (or your host’s environment).
2. **You or a manager** runs **`/setup`** (wizard) or maps slots manually and checks **`/config view`** so the bot knows **channels, roles, and payment text** for that server.
3. **Staff** runs **`/ticketpanel`** / **`/ticketbutton`** and **`/deploy tos`** / **`/deploy payment`** to post panels into the right channels.
4. **Members** agree to TOS, then **open a ticket** when the shop is open (commission type → quote steps → short form).
5. **Staff** uses **`/payment confirm`** after payment (registers the order like **`/queue`** if needed) or **`/queue`** directly; then updates status from menus in the ticket.
6. **Staff** can post **WIP stage** updates (**`/stage`**), log **revisions** (**`/revision log`**), and save **reference links** (**`/references`**).
7. When done, the client can be nudged toward **vouches** and **drops**.

---

## Setup (step by step)

### A. Get the bot running (computer)

1. Install **Python 3.11 or newer** if you do not have it.
2. Open a terminal in the **`bot`** folder (the folder that contains `main.py`).
3. (Recommended) Create a virtual environment and activate it. On Windows:

   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Copy **`.env.example`** to **`.env`** and open `.env` in a text editor.
6. Set **`BOT_TOKEN`** — from the [Discord Developer Portal](https://discord.com/developers/applications) (your bot’s token). **Nothing else is required in `.env`** for this bot.
7. Start the bot:

   ```bash
   python main.py
   ```

8. **First run** creates a local database file **`bot.db`**. Do not share it if it contains private data.
9. **Slash command sync (optional):** See **`.env.example`** for **`SYNC_GUILD_ID`** (guild-only registration for one server) and **`GUILD_SLASH_PURGE_ID`** (one-time cleanup if duplicates remain after changing sync mode).


### Slash command duplicate fix checklist

If Discord still shows duplicate `/` commands:

1. **Use one sync mode at a time:**
   - For single-server testing: set `SYNC_GUILD_ID=<your server id>`
   - For normal multi-server use: remove `SYNC_GUILD_ID`
2. **After switching from guild-only to global:** set `GUILD_SLASH_PURGE_ID=<same server id>`, restart once, then remove it and restart again.
3. Give Discord up to a few minutes to refresh command menus after sync.

This prevents old guild-scoped commands from stacking with global commands in the same server.

### B. Wire the server (inside Discord)

Do this **after** the bot is online and invited with enough permissions (see [Discord settings](#discord-settings-your-server-needs)).

1. Run **`/config view`** to see what is missing (managers only—see [commands](#commands-by-who-can-use-them)).
2. Use **`/setup`** (interactive wizard) to map **channels, categories, and roles**, or set them through your workflow until every slot you need is filled (queue channel, ticket categories, staff role, TOS role, **optional** age-verified role and verification channel for NSFW ticket types, etc.).
3. Set **payment** text and URLs with **`/config payment`** subcommands (`gcash_details`, `paypal_link`, `kofi_link`, `gcash_qr`, `paypal_qr`) so the payment buttons and ticket payment embeds work.
4. Put your TOS text in **`tos.txt`** (in the `bot` folder) if you use the TOS panel.
5. Staff configures **quote prices** (`/setprice`, `/quoteextras`, discounts, currencies—see [Quotes](#quotes-and-pricing)) if you want automatic ticket quotes.
6. Staff runs **`/ticketpanel`** (and **`/ticketbutton add`** for each ticket type), plus **`/deploy tos`** and **`/deploy payment`**, to post the panels into the channels you configured.

**Order matters:** configure **`/config`** / **`/setup`** before expecting tickets or queue to work.

---

## Discord settings your server needs

In the **Developer Portal** → your application → **Bot**:

- Turn on **Message Content Intent** and **Server Members Intent** (the bot reads messages in the vouch channel and needs member info for roles).

Invite the bot with permissions that match what you expect it to do, for example:

- Manage channels (create/delete ticket channels, rename stages)
- Manage roles (assign TOS / vouch-related roles if you use those flows)
- Send messages, embed links, attach files, read history
- Use slash commands in your server

If something fails with “missing permissions,” give the bot’s role a higher position in **Server Settings → Roles** (above roles it must assign), and check channel/category overrides.

---

## Core features and sub-features

### Server configuration (`/config`)

- **`/config view`:** Lists channels, categories, roles, payment text/URLs, and a count of quote price rows (managers / staff per bot rules).
- **`/config reset`:** Clears a chosen group (tickets, queue, shop, payment, channels/roles, or quote pricing) with confirmation.
- **Channels:** Queue, shop status, transcripts, vouches, optional order notifications, Start Here, TOS, **verification** (optional, for age gate), payment, warn log.
- **Categories:** New tickets, noted, processing, done (order pipeline).
- **Roles:** Staff, TOS agreed, **age verified** (optional, for NSFW ticket buttons), commissions open, please vouch, Boostie/Reseller (quote discounts).
- **Payment:** GCash text, PayPal/Ko-fi links, GCash/PayPal QR image URLs (`/config payment …`).

### Shop

- **`/shop open` / `/shop close`:** Staff toggles whether commissions are open (and can adjust Start Here visibility when configured).
- **`/shopstatus`:** Anyone can check if the shop is open.

### Quotes and pricing

- **`/quote calculator`:** Interactive quote (commission type → tier → characters → background → rush); shows **PHP** and enabled **foreign currency** lines from your matrix.
- **`/quote recalculate`:** Staff only, inside an open ticket — re-posts the quote from the saved snapshot (optional overrides).
- **`/pricelist`:** Shows base **PHP** grid from the database.
- **Staff:** **`/setprice`**, **`/quoteextras`**, **`/setdiscount`**, **`/setcurrency`** maintain the matrix and quote display options.

### Tickets and transcripts

- **Open a ticket:** Button on the panel from **`/ticketpanel`** / **`/ticketbutton`** (requires TOS role + shop open; **optional** age-verified role + verification channel when **`/ticketbutton agegate`** is enabled for that button).
- **Flow:** Commission type → **rendering tier** → **character count** → **background** → **rush** → short modal (e.g. mode of payment, references, notes). The bot posts a **quote embed**, a **welcome** embed (payment terms, TAT, loyalty count), an **awaiting payment** embed, and a **staff shortcuts** line.
- **Close:** Button in the ticket or **`/close`**; builds an **HTML transcript** (with optional lines for **revisions** and **quoted total** when stored), tries to DM the client, and posts a copy to your transcript channel when possible.

### Queue and orders

- **`/queue`:** Staff registers an order from a ticket (handler, buyer, item, price, etc.).
- **`/payment confirm`:** Staff confirms payment in-ticket; if there is no order yet, registers the same way as **`/queue`**, then marks the ticket **in progress**.
- **Status menu:** In the ticket, staff can move the order to **Processing** or **Done** (with template messages).
- **`/stage`:** Staff posts a **WIP stage** embed (sketch → delivered, etc.).
- **`/revision log`:** Staff logs a revision; after two free revisions, extra revisions add a running **₱200** fee line in the database.
- **`/references add`** / **`/references view`:** Staff stores and lists **reference URLs** on the ticket row.
- **Templates:** Staff can override message text (`/settemplate`, `/viewtemplate`, `/listtemplates`, `/resettemplates`).
- **Loyalty:** **`/loyalty`** and **`/loyaltytop`** show progress and a simple leaderboard.

### Payments

- Managers set **GCash body text**, **PayPal / Ko-fi links**, and **QR image URLs** with **`/config payment`** (see **`/config view`**).
- Panel with **GCash / PayPal / Ko-fi** buttons; each shows an ephemeral embed using that server’s saved values.

### Vouches

- Posting in the **vouches channel** can remove a “please vouch” role (when configured).
- **`/vouch`:** Staff manually logs a vouch.
- **`/vouches`:** List vouches for a member.

### Drops

- **`/drop`:** Staff DMs a delivery link; optional ping in the ticket.
- **`/drophistory`:** Staff views past drops for a member.

### Warnings

- **`/warn`:** Staff warns a user (public line + DM notice + log); auto-ban after **3** warns in this bot’s database (if the bot can ban).
- **`/warns`**, **`/clearwarn`**, **`/clearallwarns`:** Staff tools to inspect or clear warns.

### Sticky messages

- Staff sets an embed that the bot **reposts** so it stays at the bottom of a channel (`/sticky`, `/stickyupdate`, `/unsticky`, `/stickies`, `/stickypreview`).

### Embed builder (`/embed`)

- **Who can use it:** Server owner, **Administrator**, or members with a role added through **`/embed config staffrole`** (same list controls **`/button`**).
- **`/embed create`:** Creates a new draft **`EMB-XXX`** ID and opens an **interactive builder** (edit title, description, color, author, footer, images, timestamp; preview and discard).
- **`/embed edit`:** Reopens the builder for an existing ID; optional `field` shortcut for a single field.
- **`/embed list`** / **`/embed showlist`:** List IDs or browse with previews.
- **`/embed show`:** Post a resolved embed (variables filled using the user who runs the command) to a chosen text channel.
- **`/embed config staffrole`:** Add or remove roles that may use **`/embed`** and **`/button`** (owner/admin only).

### Button builder (`/button`)

- **Who can use it:** Same as **`/embed`** (owner, **Administrator**, embed staff roles).
- **`/button create`:** New **`BTN-XXX`** ID and builder — label, emoji, style, **action + role** (assign, remove, or toggle), staff-only label/note, optional response text for outcomes, live preview row.
- **`/button edit`**, **`/button clone`**, **`/button list`:** Edit or duplicate a button, or list all buttons on the server.
- **`/button post`:** Post a short info embed and the live button to a text channel. Posted buttons stay wired to the database (clicks use current config after restarts). Users only see **ephemeral** feedback when they click.

### Autoresponder builder (`/ar`)

- **Who can use it:** Server owner, **Administrator**, or configured **Staff** role.
- **`/ar create`:** New **`AR-XXX`** draft in interactive builder (trigger + matchmode, response, conditions, notes, variables reference, preview).
- **`/ar edit`** / **`/ar delete`** / **`/ar list`:** Manage existing ARs by ID (ID autocomplete picker available).
- **`/ar pause`** / **`/ar resume`:** Toggle without deleting.
- **Runtime behavior:** Active ARs evaluate on each member message and fire first highest-priority match; cooldown is per-user.
- **Quality-of-life:** Conditions editor updates via dropdowns; short confirmation toasts auto-dismiss after 10 seconds.

### Planned core systems (unimplemented)

The following systems are documented in `plans/` and are **not implemented yet**:

- [ ] **MYO system** (`plans/01_MYO_SYSTEM.md`) - **0%**
- [ ] **Batch and slot system** (`plans/02_BATCH_SLOT_SYSTEM.md`) - **0%**
- [ ] **Currency system (EC/PC)** (`plans/03_CURRENCY_SYSTEM.md`) - **0%**
- [ ] **Gacha system** (`plans/04_GACHA_SYSTEM.md`) - **0%**
- [ ] **Casino minigames** (`plans/05_CASINO_MINIGAMES.md`) - **0%**
- [ ] **Collectible system** (`plans/06_COLLECTIBLE_SYSTEM.md`) - **0%**
- [ ] **MYO content/config tooling** (`plans/07_MYO_CONTENT_CONFIG.md`) - **0%**

---

## Commands by who can use them

Slash commands are typed with **`/`** in Discord. Only commands that exist for your bot will show up after it has synced.

### Everyone (any member)

| Command | What it does |
|--------|----------------|
| **`/shopstatus`** | Shows if commissions are open or closed. |
| **`/quote calculator`** | Interactive commission quote from the server’s price matrix (ephemeral). |
| **`/pricelist`** | Shows base commission prices (**PHP**) from the database. |
| **`/loyalty`** *member* | Shows loyalty progress for a member. |
| **`/loyaltytop`** | Top 10 clients by completed orders. |
| **`/vouches`** *member* | Lists saved vouches for a member. |
| **`/close`** | Closes the **current ticket** if you are the ticket owner **or** staff (same rules as the Close button). |

*Also:* anyone can use **payment panel buttons** (GCash / PayPal / Ko-fi) and the **TOS agree** button when those messages exist.

---

### Staff (your configured **Staff** role)

Staff commands use the role mapped in **`/config view`** as **Staff**. If that role is missing, staff commands will error until you configure it.

| Command | What it does |
|--------|----------------|
| **`/ticketpanel`**, **`/ticketbutton`**, **`/ticketform`** | Configure and post the configurable ticket panel. |
| **`/ticketbutton agegate`** | Toggle **age verification required** for a ticket button (NSFW). |
| **`/deploy tos`** | Posts the TOS panel in your **TOS** channel. |
| **`/deploy payment`** | Posts the payment panel in your **payment** channel. |
| **`/shop open`**, **`/shop close`** | Opens or closes the shop. |
| **`/queue`** | Registers an order from a ticket channel. |
| **`/payment confirm`** | Confirms payment in-ticket and registers on the queue when needed. |
| **`/quote recalculate`** | Re-posts an updated quote embed in the **current ticket** (uses saved snapshot + optional overrides). |
| **`/stage`** | Posts a **WIP stage** update in the ticket. |
| **`/revision log`** | Logs a revision (extra fees after free revisions). |
| **`/references add`**, **`/references view`** | Save or list reference URLs on the ticket. |
| **`/setprice`**, **`/quoteextras`**, **`/setdiscount`**, **`/setcurrency`** | Maintain quote matrix and quote display options. |
| **`/settemplate`**, **`/viewtemplate`**, **`/listtemplates`**, **`/resettemplates`** | Manage custom message templates. |
| **`/warn`**, **`/warns`**, **`/clearwarn`**, **`/clearallwarns`** | Warning system. |
| **`/vouch`** | Manually log a vouch. |
| **`/drop`**, **`/drophistory`** | Send delivery links / view history. |
| **`/sticky`**, **`/stickyupdate`**, **`/unsticky`**, **`/stickies`**, **`/stickypreview`** | Sticky embed tools. |

*Also:* **Order status** dropdowns in tickets are meant for staff (the bot checks your staff role).

---

### Server managers (`/config` and `/setup`)

Use **`/setup`** for the interactive wizard, or audit settings with **`/config view`**. **`/config`** commands (view, reset, payment text) require **Administrator**, **Manage Server**, or your configured **Staff** role.

| Command | What it does |
|--------|----------------|
| **`/setup`** | Interactive wizard to map channels, categories, and roles. |
| **`/config view`** | Lists channels, roles, payment fields, and quote row count. |
| **`/config reset`** | Clears a configuration group (with confirmation). |
| **`/config payment gcash_details`** (and **`paypal_link`**, **`kofi_link`**, **`gcash_qr`**, **`paypal_qr`**) | Set payment copy and URLs for **this server**. |

---

### Embed and button builders (owner / Administrator / embed staff role)

These commands are **not** the same as the general **Staff** role used for tickets. They use the **embed staff** allow-list from **`/embed config staffrole`**, plus owners and administrators.

| Command | What it does |
|--------|----------------|
| **`/embed create`**, **`/embed edit`**, **`/embed list`**, **`/embed showlist`**, **`/embed show`** | Create and manage **`EMB-XXX`** embeds; post to a channel. |
| **`/embed config staffrole`** | **Owner/admin only** — grant **`/embed`** / **`/button`** access to a role. |
| **`/button create`**, **`/button edit`**, **`/button clone`**, **`/button list`**, **`/button post`** | Create and manage **`BTN-XXX`** role buttons; post a button to a channel. |
| **`/ar create`**, **`/ar edit`**, **`/ar delete`**, **`/ar list`**, **`/ar pause`**, **`/ar resume`** | Create and manage **`AR-XXX`** autoresponders with interactive builder and live triggers. |

---

## Hosting the bot online

For **Render**, Railway, or similar: run **`python main.py`** as the start command from the **`bot`** folder. Set **`BOT_TOKEN`** (and **`PORT`** is provided automatically on Render). The keep-alive server listens on **`PORT`** (defaults to **8080** locally). Do **not** point the app at a different port than **`PORT`** or public URLs may return **502**. Check your provider’s docs for “background worker” vs “web service.”

---

## Files and folders (optional)

| Item | Role |
|------|------|
| **`main.py`** | Starts the bot. |
| **`cogs/embed_builder.py`** | `/embed` commands and interactive embed builder. |
| **`cogs/button_builder.py`** | `/button` commands and interactive role-button builder. |
| **`cogs/autoresponder_builder.py`** | `/ar` commands and runtime message-trigger engine. |
| **`.env`** | **Bot token only** in the default setup (never commit this). |
| **`bot.db`** | Local database (orders, tickets, warns, guild settings, embed/button/autoresponder builder rows, etc.). |
| **`tos.txt`** | Text for the TOS panel. |
| **`templates.json`** | Default wording for queue/ticket messages (staff can override in the database). |

---

## More documentation

- [`docs/README.md`](docs/README.md) — index of extra docs.
- [`docs/database-reference.md`](docs/database-reference.md) — SQLite tables overview (includes embed/button builder tables).
- [`autoresponder builder/autoresponder-full-spec.md`](autoresponder%20builder/autoresponder-full-spec.md) — full AR target scope (parity + planned extensions).
- [`docs/TICKETING.md`](docs/TICKETING.md) — ticket system behavior (may lag behind code; prefer this README + `/config view` for current commands).
- [`button builder/embed-button-improvements.md`](button%20builder/embed-button-improvements.md) — design notes and future ideas for panels, conditions, analytics (implementation varies; see sections above for what the bot does today).
