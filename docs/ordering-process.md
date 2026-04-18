# Commission ordering process — full guide

This document explains **end-to-end how ordering works** in the Mika Shop bot: from server setup through tickets, queue, payment, staff workflow, **Done** vs **close**, vouching, reviews, and loyalty. It is written for **three audiences**:

| Audience | Typical responsibilities |
|----------|-------------------------|
| **Owner / administrator** | Wire channels, categories, roles; configure payment copy; optional loyalty stamp cards; access private **feedback** inbox for reviews. |
| **Staff** | Open/close shop, deploy panels, register orders, move tickets through pipeline, run WIP tools, press **Done** / **Close**, optional **`/noted`**, manual **`/vouchstaff`**. |
| **Client (buyer)** | Agree to TOS, open ticket, pay per your rules, communicate in ticket, **`/closeapprove`** when asked, **`/vouch`** and **`/review`** when eligible. |

For a shorter **who-does-what** table format, see [`situational-flows.md`](situational-flows.md). This file goes **deeper** on sequence, dependencies, and meaning of each step.

---

## 1. Concepts and glossary

### 1.1 Ticket

A **private text channel** the bot creates for one commission request. The bot stores a **ticket row** keyed by **channel ID**, including client, button used, answers, quote snapshot, payment state, WIP stage, and links to queue data.

### 1.2 Order

An **`orders`** table row: **`order_id`** (string, often prefixed per server), **client**, **handler**, item/price/MOP, **`ticket_channel_id`**, **status**, optional **queue_message_id** for the public queue card.

- **Registered order:** Row exists and **`ticket_channel_id`** points at this ticket. Best case for clean **`/vouch`** / **`/review`** linking.
- **Fallback tag:** If no row matches the ticket yet, client **`/vouch`** can still log using the **ticket channel’s name** (e.g. `cs-fb-username-001`) as the stored **`order_id`** for that vouch. **`/review`** can still work off that tag if it appears in the client’s vouch history.

### 1.3 Queue

The **queue channel** holds embeds or messages representing active work. Staff commands such as **`/queue`**, **`/payment confirm`**, and **`/stage`** update order status and may edit the **queue message** tied to the order (behavior depends on templates and server configuration).

### 1.4 Categories (typical pipeline)

Configured in **`/setup`** / **`/config`**:

| Category slot | Role in the story |
|-----------------|-------------------|
| **New tickets** | Where brand-new ticket channels are created. |
| **Noted orders** | Optional resting place after staff acknowledge intake (see **`/noted`**). |
| **Processing** | Active work; **Claim Ticket** moves here. |
| **Done** | Work finished; **Done** button moves here and can trigger **loyalty stamp card** issuance. |

### 1.5 Roles most relevant to ordering and feedback

| Role (config key) | Purpose |
|-------------------|---------|
| **Staff** | Ticket commands, queue, payment confirm, shop toggle, most moderation. |
| **TOS agreed** | Required to open tickets (after **`/deploy tos`** panel). |
| **Commissions open** | Often paired with shop-open flow so only eligible users see commission UI. |
| **Please vouch** | Given when you want the client to leave a public vouch; **required** for **client** **`/vouch`**. |
| **Feedback pending** | Optional; after **`/vouch`**, bot may assign so client can run **`/review`**. |
| **Review reward** | Optional; bot may assign after a completed **`/review`**. |
| **Age verified** | Optional; required for ticket buttons with **age gate** (NSFW). |

### 1.6 Channels most relevant

| Channel | Purpose |
|---------|---------|
| **Start here / panel** | Ticket panel lives here (`/ticketpanel`, `/ticketbutton`). |
| **TOS** | Terms panel (`/deploy tos`). |
| **Payment** | Payment info panel (`/deploy payment`). |
| **Queue** | Public order line-up. |
| **Vouches** | Public vouch embeds from **`/vouch`** / **`/vouchstaff`**; also legacy “type here to clear Please vouch”. |
| **Feedback** | Owner-oriented inbox: **`/review`** submissions (restrict channel permissions so only owner/staff you trust see it). |
| **Transcripts** | HTML transcript copies on close when configured. |
| **Loyalty cards** | Stamp card posts + threads (`/loyalty_card`). |

---

## 2. Phase A — Before anyone orders (owner / admin)

### 2.1 Bot and permissions

- Bot online; **`BOT_TOKEN`** set (see project [`README.md`](../README.md)).
- **Message Content Intent** and **Server Members Intent** enabled in the Developer Portal (vouch channel listener, members for roles).
- Bot role **high enough** in the role list to **manage channels** and **assign roles** it must grant.

### 2.2 Configuration

1. Run **`/config view`** or **`/setup`** and fill:
   - Ticket **categories** (new, noted, processing, done).
   - **Queue** channel (and optional order notifications).
   - **Staff** role.
   - **TOS** channel + **TOS agreed** role; **shop status** channel + **commissions open** if you use that pattern.
   - **Payment** channel + all **`/config payment`** strings (GCash body, PayPal/Ko-fi links, QR URLs).
   - **Vouches** channel, **Feedback** channel.
   - **Please vouch**, **Feedback pending**, **Review reward** roles.
   - **Transcript** channel.
2. Set **quote matrix** (staff): **`/setprice`**, **`/quoteextras`**, **`/setdiscount`**, **`/setcurrency`** so **`/quote calculator`** and ticket quotes work.

### 2.3 Deploy panels (staff or owner)

- **`/deploy tos`** — TOS agree button in TOS channel.
- **`/deploy payment`** — payment buttons in payment channel.
- **`/ticketpanel`** and **`/ticketbutton add`** — ticket types on the start-here channel.

### 2.4 Optional: loyalty stamp cards (owner / admin)

- **`/loyalty_card`** subcommands: destination **channel**, **images** per stamp index, optional **void** timer.
- Without images (and without repo `lcstates` defaults), cards may not post—see [`queue-templates-loyalty.md`](queue-templates-loyalty.md).

### 2.5 Open the shop (staff)

- **`/shop open`** — clients can open tickets when other gates (TOS, shop state) pass.
- **`/shopstatus`** — anyone can verify open/closed.

**Client at this phase:** waits until panel is visible and shop is open; agrees to TOS via button to get **TOS agreed** role.

---

## 3. Phase B — Opening a ticket (client + bot)

### 3.1 Preconditions

- **Shop open** (staff).
- Client has **TOS agreed** role.
- If the ticket **button** has **age gate**, client needs **Age verified** and configured verification channel flow.

### 3.2 Panel interaction

1. Client clicks a **ticket button** on the panel.
2. Bot checks: not over **one open ticket per user per guild** (except special cases like warn appeals).
3. **Commission type** selection (and related UI) runs.
4. **Quote wizard** steps: rendering tier, character count, background, rush (as implemented for that server).
5. **Modal** collects fields configured for that button (e.g. mode of payment, reference links, notes).

### 3.3 What the bot creates

- A **new text channel** under the **new tickets** category (or as configured).
- Channel name is often a **slug** such as `type-tier-username-001` (helps humans scan the list).
- Embeds typically include:
  - **Quote** (PHP + optional FX) from **`quote_compute`**.
  - **Welcome / overview** (ticket ID, selections, staff action row: **Claim**, **Done**, **Remind**, **Close** — see [`tickets-and-panels.md`](tickets-and-panels.md)).
  - **Awaiting payment** block with due lines and payment hints.
  - **Staff shortcuts** text listing key slash commands.

**Staff:** no order row exists until **`/queue`** or **`/payment confirm`** (or equivalent registration) succeeds.

**Client:** reads quote, uses **payment panel** in the payment channel if paying outside Discord; stays in ticket for questions.

---

## 4. Phase C — Registering the order and payment (staff + client)

### 4.1 `/payment confirm` (in ticket)

- Run by **staff** inside the ticket.
- If an **order** already exists: updates payment / progress flags as implemented.
- If **no order** yet: creates order via queue integration (**`register_order_in_ticket_channel`**), creates/updates **queue card**, may rename channel toward **noted** pattern, posts templates and **order status** UI where applicable.

### 4.2 `/queue` (alternative path)

- Staff registers order fields explicitly from the ticket (buyer, item, price, etc.) when that fits your workflow.

### 4.3 After registration

- **`orders.ticket_channel_id`** links the ticket channel to the **order_id**.
- Queue message may show **Noted** / **Processing** / **Done** depending on templates and later commands.
- Client sees updates in ticket; public queue channel shows the commission line (per your template).

**Owner:** usually not involved day-to-day unless they are also staff.

---

## 5. Phase D — Active commission (staff + client)

### 5.1 Moving the ticket through categories

| Action | Who | Effect |
|--------|-----|--------|
| **Claim Ticket** | Staff | Moves channel to **processing** category, sets ticket status, records assignee, notifies client and staff. |
| **`/noted`** | Staff | Moves ticket to **noted orders** category, sets status **noted**, posts formatted summary line to **queue** channel (layout described in code/templates). |
| **`/stage`** | Staff | Updates WIP stage in DB, posts stage embed; may refresh queue card. |
| **`/revision log`** | Staff | Logs revision; pricing rules apply after free revisions. |
| **`/references`** | Staff | Stores reference URLs on the ticket. |
| **`/quote recalculate`** | Staff | Refreshes quote embed from snapshot. |

### 5.2 Client responsibilities

- Answer questions, approve quotes, submit **`/closeapprove`** when your rules require client approval before staff close.

### 5.3 Delivery (optional to “ordering,” but common)

- Staff **`/drop`** sends delivery link DM; **`/drophistory`** lists past drops.

---

## 6. Phase E — Finishing the ticket (staff + client)

### 6.1 Client closure approval (when enforced)

- For **staff** closing, the bot may require **`close_approved_by_client`** on the ticket.
- Client runs **`/closeapprove`** in the ticket so staff can use **Close** or **`/close`**.

### 6.2 **Done** (staff)

- **Done** is a **staff/admin** button on the welcome **TicketOps** view.
- Implementation **defers the interaction first** (avoids Discord “Unknown interaction” if work takes time).
- Effects typically include:
  - Move channel to **done** category.
  - Set ticket status (e.g. **done_hold**).
  - **Loyalty stamp card:** if configured, **`issue_loyalty_card_for_ticket_closure`** runs here so the client does **not** need to wait for **Close** to see a card.
  - Optional **auto-delete timer** for the channel if **`DONE_TICKET_AUTO_DELETE_HOURS`** is set (owner config).

### 6.3 **Close** (staff or client)

- **Close Ticket** button or **`/close`** runs the **close pipeline**: transcript generation, DM attempt, post to **transcript** channel, DB close, channel deletion after countdown (see tickets cog).
- Loyalty card may **also** issue on close if not already issued (idempotent guard per ticket avoids duplicates).

### 6.4 Queue / order completion

- Closing flow may mark order **Done** and **strikethrough** or update the queue message (per current `tickets` / `queue` integration).

**Owner:** ensure transcript and loyalty channels exist if you rely on archives and cards.

---

## 7. Phase F — Vouching (client, staff, legacy channel)

### 7.1 When does “Please vouch” appear?

- Typically after **order completion** paths in your queue/ticket templates (e.g. when order moves to **Done** or when completion message runs). Exact moment is template + queue integration—align your **Please vouch** role assignment with when you want clients to praise publicly.

### 7.2 Client **`/vouch`** (preferred path)

**Where:** Only in the **client’s own ticket channel** (private ticket).

**Requirements:**

- User has **Please vouch** role.
- Ticket record exists for this channel and **client_id** matches the user.

**Parameters (conceptually):**

- **`message`** — public-facing vouch text.
- **`staff`** (optional) — member to thank (handler).
- **`proof`** (optional) — image attachment.

**Order ID handling (automatic):**

1. Bot loads **order** for **`ticket_channel_id` + client** from DB.
2. If found → **`order_id`** = that row (**registered order**).
3. If not found → **`order_id`** = **current channel name** (**ticket-name fallback**).

**Effects:**

- Inserts into **`vouches`** table.
- Posts embed to **vouches** channel (mentions **owner**; optional **staff**).
- May add **Feedback pending** role.
- DMs client with **`/review`** instructions (if DMs closed, user still sees in-server follow-up when possible).
- Runs **loyalty stamp** advancement if an active card exists.

### 7.3 Staff **`/vouchstaff`**

- For logging a vouch on behalf of a **member** with explicit **order_id** (autocomplete).
- Same downstream behaviors (vouches channel embed, PlsVouch cleanup, loyalty hook) as designed for staff use.

### 7.4 Legacy: typing in **vouches** channel

- If user has **Please vouch** and sends **any message** in the configured **vouches** channel:
  - Role removed.
  - Vouch stored with **no order_id** (or null).
  - Loyalty stamp may still advance.
- Does **not** replace the structured **client `/vouch`** embed path; it is a simple alternative.

---

## 8. Phase G — Reviews (`/review`) (client + owner)

### 8.1 Gate

- If **Feedback pending** role is configured, client typically must have it after **`/vouch`** to start **`/review`**.

### 8.2 Choosing the order

- **`order_id`** autocomplete combines:
  - **Registered orders** the client can still review (not already in **`commission_reviews`**), and
  - **Fallback tags** from prior **`vouches`** for that user (same exclusion if already reviewed).

### 8.3 Validation

- Accept if **`get_order(order_id)`** shows the client as buyer, **or** **`has_vouch_for_order(client, order_id)`** for fallback tags.

### 8.4 UI flow (high level)

1. **Ephemeral** message: four **1–5** rating selectors (artwork quality, communication, turnaround, process smoothness).
2. **Modal:** two paragraph fields (enjoyed most; improvements).
3. **View:** three dropdowns (commission again; recommend; testimonial consent).
4. **Submit** → insert **`commission_reviews`**, post **embed** to **feedback** channel, remove **Feedback pending**, optional **Review reward**, **discount code** DM.

**Owner / admin:** restrict **feedback** channel so only you (and trusted staff) see raw feedback.

---

## 9. Phase H — Loyalty (two layers)

### 9.1 Simple loyalty table

- **`/loyalty`**, **`/loyaltytop`** — completed order counts and milestones (queue completion path may increment—see queue docs).

### 9.2 Loyalty **stamp cards**

- **Issuance:** **Done** or **ticket close** (whichever runs the issue function first; duplicate guard per ticket).
- **Stamps:** Advance when a **vouch** completes (client `/vouch`, vouches-channel message, or **`/vouchstaff`** path that hits loyalty hook).
- **Void:** Optional timer if client never vouches—see **`/loyalty_card voidhours`**.

---

## 10. End-to-end timeline (typical)

1. **Owner** configures server; **staff** deploy panels and open shop.  
2. **Client** agrees TOS, opens ticket, gets quote + payment instructions.  
3. **Staff** confirms payment / registers order; work moves **Noted → Processing** (claim) as needed.  
4. **Staff** delivers work, uses **stage / revision / references** as needed.  
5. **Client** approves closure if required (**`/closeapprove`**).  
6. **Staff** presses **Done** (loyalty card may post); later **Close** (transcript).  
7. **Client** receives **Please vouch**, runs **`/vouch`** in ticket (or uses vouches channel legacy).  
8. **Client** gets **Feedback pending**, runs **`/review`**; **owner** reads **feedback** channel; client may get **reward** role + **discount** DM.

---

## 11. Troubleshooting (ordering-specific)

| Issue | What to check |
|-------|----------------|
| Cannot open ticket | Shop closed, missing TOS role, age gate, or already one open ticket. |
| No order row | Staff never ran **`/payment confirm`** / **`/queue`**; fallback vouch tag still possible. |
| **`/vouch`** fails “ticket only” | Run inside the **ticket** channel, not general chat. |
| **`/vouch`** “not your ticket” | Wrong account or wrong channel. |
| **`/review`** empty autocomplete | Everything already reviewed, or no vouch/order to tie to. |
| No loyalty card | **`/loyalty_card`** channel/images not set, or **Done**/close did not run. |
| Button errors after restart | Persistent views re-registered on startup; old messages may need panel refresh (see [`README.md`](../README.md) duplicate slash section). |

---

## 12. Related documentation

| Document | Contents |
|----------|----------|
| [`README.md`](../README.md) | Setup, command tables, progress. |
| [`situational-flows.md`](situational-flows.md) | Compact role × situation tables. |
| [`tickets-and-panels.md`](tickets-and-panels.md) | Ticket UI, `/payment confirm`, persistence. |
| [`queue-templates-loyalty.md`](queue-templates-loyalty.md) | Queue messages, completion, loyalty cards. |
| [`vouches.md`](vouches.md) | `cogs/vouch.py` behavior detail. |
| [`config.md`](config.md) | `/config` reset groups and keys. |
| [`setup-wizard.md`](setup-wizard.md) | `/setup` wizard steps. |
| [`database-reference.md`](database-reference.md) | `tickets`, `orders`, `vouches`, `commission_reviews`. |

---

*This guide reflects the bot’s intended behavior at time of writing; always verify against **`/config view`** and the latest cog code if you customize heavily.*
