# Situational flows (owner, staff, client)

This document describes **who does what** in common situations. It complements [`README.md`](../README.md) (overview and command lists) with **end-to-end behavior**, not every slash option.

**Roles referenced**

- **Owner / admin:** server owner or **Administrator** (some commands also allow **Manage Server** or configured **Staff** for `/config`).
- **Staff:** members with the **Staff** role from [`/config view`](config.md) / **`/setup`**.
- **Client:** commission buyer in your server (usually the person who opened a ticket).

**Configured slots that matter for newer flows**

- **Please vouch** → client gets this when work is done (e.g. after order marked complete); required to use **client** `/vouch`.
- **Feedback pending** → bot may assign after client `/vouch`; gates **`/review`**.
- **Review reward** → optional role after a completed **`/review`**.
- **Vouches channel** → public vouch posts (and legacy “type in channel to clear PlsVouch” behavior).
- **Feedback channel** → private review inbox for the owner (embed from **`/review`**).

---

## 1. First-time server wiring (owner / admin)

| Situation | Owner / admin | Staff | Client |
|-----------|---------------|-------|--------|
| Bot invited; nothing works yet | Run **`/setup`** or map slots via **`/config`**; set **queue**, **ticket categories**, **staff**, **TOS**, **vouches**, **payment** text (`/config payment` …). | Wait until channels exist; then deploy panels. | Nothing yet. |
| Panels missing | — | **`/deploy tos`**, **`/deploy payment`**, **`/ticketpanel`** + **`/ticketbutton add`** per ticket type. | Sees buttons when shop open + TOS agreed. |
| Quote prices empty | Can grant staff access to pricing. | **`/setprice`**, **`/quoteextras`**, **`/setdiscount`**, **`/setcurrency`** as needed. | **`/quote calculator`** / **`/pricelist`** only work after matrix exists. |
| Loyalty stamp cards | **`/loyalty_card`** (channel, images, optional void timer). | — | Sees cards only after staff workflow posts them (see below). |
| Vouch + review pipeline | In **`/setup`**, map **Please vouch**, **Feedback pending**, **Review reward**, **Vouches** channel, **Feedback** channel. | — | Client flow fails softly if roles/channels missing (bot skips assign/post with permission errors). |

---

## 2. Shop open → client opens a ticket

| Situation | Owner / admin | Staff | Client |
|-----------|---------------|-------|--------|
| Commissions closed | **`/shop open`** (or staff). | Same. | Sees “shop closed” until open. |
| Client opens ticket | — | Eventually **`/queue`** or **`/payment confirm`** registers order; ticket overview + ops buttons appear. | Uses panel button → commission type → quote steps → modal; gets ticket channel + overview embed. |

**Ticket channel name** often looks like a slug (e.g. `cs-fb-username-001`). That name is used as a **fallback order tag** if no DB order row is linked yet.

---

## 3. Inside the ticket (staff + client)

| Situation | Owner / admin | Staff | Client |
|-----------|---------------|-------|--------|
| Claim work | — | **Claim Ticket** → moves channel to **processing**, records assignee, pings client + staff. | Sees claim notice. |
| WIP / payment / revisions | — | **`/stage`**, **`/payment confirm`**, **`/revision log`**, **`/references`**, quote tools as documented. | Replies in thread; **`/closeapprove`** when asked. |
| Remind inactive client | — | **Remind Client** (DM with jump link) or ping in channel. | Gets DM if DMs open. |
| Mark work finished (no close yet) | — | **Done** → moves ticket to **done** category, sets status; **loyalty stamp card** is issued to configured channel (does not wait for **Close**). | Can **`/vouch`** from this ticket without typing an order ID (see §5). |
| Close ticket | — | **Close Ticket** or **`/close`** (rules: staff vs client approval may apply). | May use **`/closeapprove`** first if your workflow requires it. |
| Transcript | — | Transcript generated; copy to transcript channel when possible. | May receive DM copy. |

---

## 4. Queue and order visibility (staff + client)

| Situation | Owner / admin | Staff | Client |
|-----------|---------------|-------|--------|
| Order registered | — | **`/queue`** / **`/payment confirm`** ties **order_id** + **ticket channel** in DB when successful. | Sees queue card updates when staff use **`/stage`** / close flows (per server templates). |
| Order not registered yet | — | Prefer registering order so **`/vouch`** / **`/review`** tie cleanly; fallback still works (§5). | **`/vouch`** can still log using **ticket channel name** as tag. |

---

## 5. Vouches (client vs staff vs channel)

### A. Client **`/vouch`** (in ticket channel)

| Step | Who | What happens |
|------|-----|----------------|
| 1 | Client | Must have **Please vouch** role; run **`/vouch`** **inside own ticket** (not DMs). |
| 2 | Bot | Resolves **order_id** from DB order for this ticket + client, or **fallback** = current channel name (slug). |
| 3 | Bot | Inserts **`vouches`** row, posts embed to **vouches** channel (owner + optional **staff** mention), optional **proof** image. |
| 4 | Bot | May add **Feedback pending**; DMs short **/review** instructions; runs loyalty stamp hook if configured. |

### B. Staff **`/vouchstaff`**

| Step | Who | What happens |
|------|-----|----------------|
| 1 | Staff | **`/vouchstaff`** with **member**, **order_id**, **message** (autocomplete on client’s orders). |
| 2 | Bot | Same DB + vouches channel behavior as before; for manual logging when client did not use **`/vouch`**. |

### C. Legacy: typing in **vouches channel**

| Step | Who | What happens |
|------|-----|----------------|
| 1 | Client | Has **Please vouch**, posts message in **vouches** channel. |
| 2 | Bot | Removes **Please vouch**, inserts vouch (**order_id** may be null), may advance loyalty card. |

---

## 6. Reviews (`/review`) — client + owner inbox

| Situation | Owner / admin | Staff | Client |
|-----------|---------------|-------|--------|
| After **`/vouch`** | Reads **`/review`** submissions in **feedback channel** (embed with ratings + text + dropdown answers). | Not the primary audience for that channel (configure visibility via Discord channel permissions). | Needs **Feedback pending** (if configured); runs **`/review order_id:`** with autocomplete. |
| Order ID choice | — | — | Autocomplete lists **registered orders** and **fallback tags** from prior vouches; already-reviewed orders/tags hidden. |
| Fallback tag review | — | — | If client vouched with **ticket-name fallback** (no DB order), **`/review`** still works if that tag exists in their **`vouches`** history and not yet reviewed. |
| After submit | — | — | **Feedback pending** removed, **Review reward** optional, **discount code** DM. |

---

## 7. Loyalty stamp cards (all roles)

| Trigger | Owner / admin | Staff | Client |
|---------|---------------|-------|--------|
| Card posted | Configures channel/images/void (**`/loyalty_card`**). | **Done** or **ticket close** can issue card (see code: **Done** does not wait for close). | Sees card + thread in configured channel; stamps advance on **vouch** completion. |
| Vouch completes | — | — | **`/vouch`** in ticket, vouches channel message, or staff **`/vouchstaff`** can advance stamps. |

---

## 8. Builders & autoresponders (staff / owner)

| Situation | Owner / admin | Staff | Client |
|-----------|---------------|-------|--------|
| **`/embed`**, **`/button`** | Full access + **`/embed config staffrole`**. | If role allow-listed: create/post embeds and buttons. | Clicks posted buttons; ephemeral feedback. |
| **`/ar`** | Full access. | Staff role can manage ARs per checks. | Triggered by messages or events (join/leave/role), not a “client command.” |

---

## 9. Troubleshooting quick map

| Symptom | Likely cause |
|---------|----------------|
| **`/vouch`** “ticket only” | Command run outside ticket text channel. |
| **`/vouch`** “not your ticket” | Wrong user or wrong channel. |
| **`/review`** rejects order | Tag not in your vouch history, or already reviewed for that tag. |
| No loyalty card | Loyalty channel/images not configured, or **Done**/close path did not run. |
| Duplicate slash commands | See **`README.md`** → “Slash command duplicate fix checklist” and `.env` sync vars. |

---

## See also

- [`README.md`](../README.md) — progress, full command tables, setup.
- [`vouches.md`](vouches.md) — technical detail for `cogs/vouch.py`.
- [`tickets-and-panels.md`](tickets-and-panels.md) — ticket UI and commands.
- [`queue-templates-loyalty.md`](queue-templates-loyalty.md) — queue + loyalty stamp cards.
- [`config.md`](config.md) — `/config` and reset groups.
