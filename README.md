# Mika Shop — Discord Bot

A Discord bot for running a **small art commission shop** in your server: agree to rules, open private tickets, track orders on a queue, take payments, and handle vouches and warnings. This guide is written so **you do not need to be a programmer** to understand or set it up.

---

## Table of contents

1. [Overview](#overview)
2. [What the bot can do](#what-the-bot-can-do)
3. [What the bot does not do (yet)](#what-the-bot-does-not-do-yet)
4. [How the pieces fit together](#how-the-pieces-fit-together)
5. [Setup (step by step)](#setup-step-by-step)
6. [Discord settings your server needs](#discord-settings-your-server-needs)
7. [Core features and sub-features](#core-features-and-sub-features)
8. [Commands by who can use them](#commands-by-who-can-use-them)
9. [Hosting the bot online](#hosting-the-bot-online)
10. [Files and folders (optional)](#files-and-folders-optional)
11. [More documentation](#more-documentation)

---

## Overview

**Mika Shop** helps you run commissions in Discord: customers use **buttons** and **slash commands** (`/` commands) to open tickets, staff register orders with **`/queue`**, and the bot keeps **HTML transcripts** when a ticket closes. Money details (GCash, PayPal, Ko-fi) come from your **environment file**; **which channels and roles** the bot uses are chosen **inside Discord** with **`/serverconfig`**—you do not paste long ID numbers into a file for that.

---

## What the bot can do

- **Onboarding:** Terms of Service (TOS) panel with an “I agree” button that gives a role.
- **Shop hours:** Open or close commissions; optional visibility rules on your “Start Here” area.
- **Tickets:** Private ticket channels under categories you pick; open/close with transcripts.
- **Orders:** Register orders from a ticket, show them on a **queue channel**, move ticket channels through **Noted → Processing → Done** stages, and use **templates** for wording.
- **Payments:** A panel with buttons for GCash, PayPal, and Ko-fi (details from your config).
- **Loyalty:** Track completed orders per client and show milestones.
- **Vouches:** Dedicated vouch channel behavior and manual vouch logging.
- **Delivery:** Staff can send a “delivery” DM with a link; history can be listed.
- **Moderation:** Warn members, DM a notice, optional auto-ban after a set number of warns, warn log channel.
- **Sticky messages:** Keep a chosen embed reposted at the bottom of a channel.
- **Server wiring:** Map channels and roles by **picking them in slash commands** (`/serverconfig`).

---

## What the bot does not do (yet)

- **No built-in economy or fake currency** (no coins, shop balances, or games).
- **No generic “embed builder” wizard** like some third-party bots (you use panels, stickies, and templates instead).
- **No automatic payments or invoicing**—it only **shows** payment info you configure; it does not charge cards or verify PayPal.
- **No built-in AI or image generation.**
- **No full moderation suite** (no automod, timeout commands, or ban suite beyond warn-driven auto-ban if you enable that flow).
- **Prefix commands** (`!command`) are **not** used for shop features; the bot is built around **slash commands** and **buttons**.

*If you add custom code later, some of these can change.*

---

## How the pieces fit together

1. **You** turn the bot on and fill in **secrets and payment text** (`.env`).
2. **You or a manager** runs **`/serverconfig`** so the bot knows **which channel is the queue, which role is staff**, and so on.
3. **Staff** runs **`/setup`** to post panels (tickets, TOS, payment) into the right channels.
4. **Members** agree to TOS, then **open a ticket** when the shop is open.
5. **Staff** uses **`/queue`** inside a ticket to create an order and post it to the **queue** list.
6. **Staff** updates status from menus in the ticket; when done, the client can be nudged toward **vouches** and **drops**.

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
6. Fill in at least:
   - **`BOT_TOKEN`** — from the [Discord Developer Portal](https://discord.com/developers/applications) (your bot’s token).
   - **Payment lines** — `GCASH_DETAILS`, `PAYPAL_LINK`, `KOFI_LINK`, and the two QR image URLs, as placeholders in the example show.
7. Optionally set **`GUILD_ID`** to your server’s ID if you want slash commands to update **quickly** on that server only. If you skip it, commands still work but may take longer to appear everywhere.
8. Start the bot:

   ```bash
   python main.py
   ```

9. **First run** creates a local database file **`bot.db`**. Do not share it if it contains private data.

### B. Wire the server (inside Discord)

Do this **after** the bot is online and invited with enough permissions (see [Discord settings](#discord-settings-your-server-needs)).

1. Run **`/serverconfig show`** to see what is missing (managers only—see [commands](#commands-by-who-can-use-them)).
2. Use **`/serverconfig channel`**, **`/serverconfig category`**, and **`/serverconfig role`** until every slot you need is filled (queue channel, ticket categories, staff role, TOS role, etc.).
3. Put your TOS text in **`tos.txt`** (in the `bot` folder) if you use the TOS panel.
4. Staff runs **`/setup tickets`**, **`/setup tos`**, and **`/setup payment`** to post the panels into the channels you configured.

**Order matters:** configure **`/serverconfig`** before expecting tickets or queue to work.

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

### Server configuration (`/serverconfig`)

- **Channels:** Queue, shop status, transcripts, vouches, optional order notifications, Start Here, TOS, payment, warn log.
- **Categories:** New tickets, noted, processing, done (order pipeline).
- **Roles:** Staff, TOS agreed, commissions open, please vouch.
- **`/serverconfig show`:** See what is set.

### Shop

- **`/shop open` / `/shop close`:** Staff toggles whether commissions are open (and can adjust Start Here visibility when configured).
- **`/shopstatus`:** Anyone can check if the shop is open.

### Tickets and transcripts

- **Open a ticket:** Button on the panel staff posted with **`/setup tickets`** (requires TOS role + shop open).
- **Close:** Button in the ticket or **`/close`**; builds an **HTML transcript**, tries to DM the client, and posts a copy to your transcript channel when possible.

### Queue and orders

- **`/queue`:** Staff registers an order from a ticket (handler, buyer, item, price, etc.).
- **Status menu:** In the ticket, staff can move the order to **Processing** or **Done** (with template messages).
- **Templates:** Staff can override message text (`/settemplate`, `/viewtemplate`, `/listtemplates`, `/resettemplates`).
- **Loyalty:** **`/loyalty`** and **`/loyaltytop`** show progress and a simple leaderboard.

### Payments

- Panel with **GCash / PayPal / Ko-fi** buttons; each shows an ephemeral embed with your configured text/links.

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

---

## Commands by who can use them

Slash commands are typed with **`/`** in Discord. Only commands that exist for your bot will show up after it has synced.

### Everyone (any member)

| Command | What it does |
|--------|----------------|
| **`/shopstatus`** | Shows if commissions are open or closed. |
| **`/loyalty`** *member* | Shows loyalty progress for a member. |
| **`/loyaltytop`** | Top 10 clients by completed orders. |
| **`/vouches`** *member* | Lists saved vouches for a member. |
| **`/close`** | Closes the **current ticket** if you are the ticket owner **or** staff (same rules as the Close button). |

*Also:* anyone can use **payment panel buttons** (GCash / PayPal / Ko-fi) and the **TOS agree** button when those messages exist.

---

### Staff (your configured **Staff** role)

Staff commands use the role you set in **`/serverconfig role` → Staff**. If that role is missing, staff commands will error until you configure it.

| Command | What it does |
|--------|----------------|
| **`/setup tickets`** | Posts the “open a ticket” panel in **Start Here**. |
| **`/setup tos`** | Posts the TOS panel in your **TOS** channel. |
| **`/setup payment`** | Posts the payment panel in your **payment** channel. |
| **`/shop open`**, **`/shop close`** | Opens or closes the shop. |
| **`/queue`** | Registers an order from a ticket channel. |
| **`/settemplate`**, **`/viewtemplate`**, **`/listtemplates`**, **`/resettemplates`** | Manage custom message templates. |
| **`/warn`**, **`/warns`**, **`/clearwarn`**, **`/clearallwarns`** | Warning system. |
| **`/vouch`** | Manually log a vouch. |
| **`/drop`**, **`/drophistory`** | Send delivery links / view history. |
| **`/sticky`**, **`/stickyupdate`**, **`/unsticky`**, **`/stickies`**, **`/stickypreview`** | Sticky embed tools. |

*Also:* **Order status** dropdowns in tickets are meant for staff (the bot checks your staff role).

---

### Server managers (`/serverconfig`)

You can use **`/serverconfig`** if you have **Administrator**, **Manage Server**, **or** the configured **Staff** role (so managers can bootstrap the staff role).

| Command | What it does |
|--------|----------------|
| **`/serverconfig channel`** | Pick which text channel is used for each feature (queue, vouches, etc.). |
| **`/serverconfig category`** | Pick categories for tickets and order stages. |
| **`/serverconfig role`** | Pick roles for staff, TOS, shop open, please vouch. |
| **`/serverconfig show`** | Lists current choices. |

---

## Hosting the bot online

For **Render**, Railway, or similar: run **`python main.py`** as the start command from the **`bot`** folder, set the same **environment variables** as in `.env`. The keep-alive server listens on the **`PORT`** environment variable (Render sets this automatically; locally it defaults to 8080). Do **not** hardcode a different port than `PORT` or public URLs may return **502**. Check your provider’s docs for “background worker” vs “web service.”

---

## Files and folders (optional)

| Item | Role |
|------|------|
| **`main.py`** | Starts the bot. |
| **`.env`** | Secrets and payment text (never commit this). |
| **`bot.db`** | Local database (orders, tickets, warns, guild settings, etc.). |
| **`tos.txt`** | Text for the TOS panel. |
| **`templates.json`** | Default wording for queue/ticket messages (staff can override in the database). |

---

## More documentation

Extra technical notes may live under [`docs/README.md`](docs/README.md).
