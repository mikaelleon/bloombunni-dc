# Mika Shop — Feature Improvement List
### Sorted by Priority · One Section Per Feature

---

> **What this document is:** A breakdown of every meaningful improvement that can be made to each existing feature, ranked by how much impact they have on running a real commission shop. Each entry explains what the current system does, what's missing, and exactly how the improvement works — simply.

---

## Priority Scale (Same as Original)

| Label | Meaning |
|---|---|
| `P0` | Without this, something will break or fail silently in production |
| `P1` | Makes the core commission flow safer, clearer, and more complete |
| `P2` | Meaningfully improves operator control, client experience, or moderation |
| `P3` | Quality-of-life — makes daily operation smoother |
| `P4` | Power-user or maintenance utility — rarely needed but valuable when you do |

---
---

# Feature 1 — Core Runtime and Reliability

**What it currently does:** Boots the bot, loads cogs, syncs slash commands, registers persistent views, and handles errors globally.

**What it's missing:** The current setup boots and either works or silently fails with vague errors. There's no way to know the bot's health without checking logs manually, no warning when something loads wrong, and no protection against cascading failures from a single bad startup step.

---

### Improvements (Sorted by Priority)

---

#### 1.1 — Full Environment Validation on Startup `P0`

**Problem:** Currently only `BOT_TOKEN` is validated. If any other required variable is missing (e.g. `SYNC_GUILD_ID`, database path), the bot either crashes halfway through startup or runs in a broken state without telling anyone why.

**Improvement:** On boot, before anything else loads, the bot checks every required environment variable and configuration value. If anything is missing or malformed, it logs a clear list of what's wrong and exits immediately with a readable error instead of a Python traceback.

**How it works:**
- Define a list of required env vars and their expected formats (e.g. `BOT_TOKEN` = non-empty string, `DATABASE_PATH` = valid writable path)
- On startup, iterate through the list and collect all failures
- If any failures exist: print a formatted report ("Missing: BOT_TOKEN, DATABASE_PATH") and exit — don't attempt to start
- If all pass: proceed to normal boot

This prevents the bot from starting in a half-broken state that's harder to debug than a clean failure.

---

#### 1.2 — Startup Health Report to Owner `P0`

**Problem:** When the bot boots, you have no idea whether everything loaded correctly unless you read the terminal logs. If a cog fails silently, you only find out when someone tries to use a command and it's missing.

**Improvement:** After boot completes, the bot sends a **private DM to the bot owner** with a structured boot report.

**How it works:**
- After all cogs load, compile a report:
  - ✅ Cogs that loaded successfully
  - ❌ Cogs that failed (with the error)
  - ✅/❌ Database initialization result
  - ✅/❌ Persistent view registration results
  - Slash command sync status
- Send this as a DM embed to the bot owner's Discord account
- If the owner's DM is closed, fall back to a designated `#bot-logs` channel

**Result:** Every time the bot starts, you know within seconds whether it's fully operational or partially broken — without reading terminal output.

---

#### 1.3 — Designated Error Alert Channel `P0`

**Problem:** Global error handling currently catches failures but has nowhere to send them except the console. If the bot is hosted remotely, errors are invisible unless you're actively watching logs.

**Improvement:** Add a configurable `error_channel` in the bot config. Any unhandled runtime error — not just startup errors — gets posted there as an embed with full context.

**How it works:**
- Staff/owner configures a private `#bot-errors` channel ID
- The global error handler sends an embed to this channel whenever an exception is caught:
  - Command name
  - User who triggered it
  - Guild and channel
  - The error type and message
  - A short traceback (last 3 lines — enough to identify the source)
- Errors are rate-limited to avoid spam (max 1 alert per unique error per 5 minutes)

---

#### 1.4 — Cog Hot-Reload Without Restart `P2`

**Problem:** If you push a bug fix to a single cog (e.g., the payment module), the entire bot must restart to apply it. This drops all active sessions, persistent view states need to re-register, and there's downtime.

**Improvement:** A `/reload` owner-only command that reloads a specific cog without restarting the whole bot.

**How it works:**
- `/reload cog:[cog_name]` — unloads the named cog and reloads it from disk
- The command is owner-only
- On success: confirms the reload with the cog name and load time
- On failure: shows the error and keeps the old cog loaded (no partial state)
- `/reload all` reloads every cog in sequence

**Use case:** You find a bug in the quote calculator at 2pm. Fix it, push the file, run `/reload quotes` — shop keeps running, nobody notices.

---

#### 1.5 — Startup Task Retry Logic `P2`

**Problem:** Startup rehydration tasks (`refresh_status_message`, `refresh_sticky_cache`) run once and if they fail — due to a rate limit, network hiccup, or Discord being briefly unavailable — they silently don't run. The bot starts in a stale state.

**Improvement:** Wrap rehydration tasks in a retry loop with exponential backoff.

**How it works:**
- Each startup task that can fail is wrapped: try → wait → retry (up to 3 times)
- Wait times between retries: 2s, 5s, 15s
- If all 3 attempts fail: log the failure, send an alert (see 1.3), and continue — don't block the whole boot
- Success on any attempt: log it and move on

---

#### 1.6 — Graceful Shutdown Handling `P3`

**Problem:** When the bot process is killed (server restart, deployment update), it cuts off mid-operation. Any in-progress database write, message edit, or channel rename may be left incomplete.

**Improvement:** Catch shutdown signals (`SIGTERM`, `SIGINT`) and run a cleanup sequence before exiting.

**How it works:**
- Register a signal handler that fires before the process exits
- Cleanup sequence: flush any pending database writes, post a "bot is restarting" status update if a status channel is configured, then exit cleanly
- Cleanup has a 10-second timeout — if it doesn't finish, hard exit anyway

---
---

# Feature 2 — Server Configuration and Setup Wizard

**What it currently does:** `/setup` guided flows and `/config view` let staff map channels, roles, and payment settings. `/config reset` clears groups of settings.

**What it's missing:** You can see the current config and reset it, but you can't see what it looked like before a reset, validate whether the config actually makes sense, or back it up before making changes.

---

### Improvements (Sorted by Priority)

---

#### 2.1 — Config Validation / Health Check `P0`

**Problem:** The config can be in a technically valid but logically broken state. For example: payment channel is set, but GCash details are missing. TOS channel is configured, but the TOS panel was never deployed. The bot accepts this and runs — then breaks at the moment a client tries to use a feature.

**Improvement:** `/config check` (or run automatically after any `/config` change) validates that the entire config is logically consistent and flags problems.

**How it works:**
- Runs a series of rules against the current config:
  - "If payment channel is set → at least one payment method (GCash/PayPal/Ko-fi) must also be configured"
  - "If shop is open → TOS role must exist in the server"
  - "If ticket types are configured → ticket category must be set"
  - "If warn threshold is set → warn-log channel must be set"
- Output is an ephemeral embed listing:
  - ✅ Checks that passed
  - ⚠️ Warnings (things that might cause issues)
  - ❌ Errors (things that will definitely break)
- Auto-runs after every `/setup` completion and posts a summary

---

#### 2.2 — Setup Completion Progress Indicator `P1`

**Problem:** `/setup` has multiple flows (Tickets & Panels, Queue & Orders, Shop & TOS, Payment, Channels & Roles) but there's no way to tell at a glance how much of the setup is done. New server owners don't know what they've missed.

**Improvement:** `/config progress` shows a visual checklist of all required setup steps and which ones are done.

**How it works:**
- Evaluates the config against a checklist of required steps:
  ```
  Setup Progress — Mika Shop

  ✅ Bot token and environment
  ✅ Staff role configured
  ✅ Ticket category set
  ✅ TOS role set
  ✅ TOS panel deployed
  ❌ Payment method (GCash/PayPal/Ko-fi) — at least one required
  ❌ Queue channel not set
  ⚠️  No transcript channel — ticket transcripts will not be saved

  Progress: 5 / 7 required steps complete
  Run /setup to continue.
  ```
- Required vs. optional steps are clearly distinguished (❌ vs ⚠️)
- Shown automatically after first setup and available on demand

---

#### 2.3 — Config Change Log `P2`

**Problem:** If a staff member accidentally resets the wrong config group (e.g., `/config reset payment` when they meant to reset something else), there's no record of what it was before the reset. Recovery requires reconfiguring from scratch.

**Improvement:** Every config change is logged — what setting changed, what the old value was, what the new value is, who made the change, and when.

**How it works:**
- A `config_audit_log` table in the database stores: `guild_id`, `changed_by` (user ID), `key`, `old_value`, `new_value`, `timestamp`
- On every `/config` write or `/config reset`, the old value is snapshotted before the write
- `/config log` shows the last 20 config changes in a paged embed (staff-only)
- `/config restore` lets the owner roll back to a previous config snapshot (last 5 full snapshots stored)

---

#### 2.4 — Config Export and Import `P2`

**Problem:** If the bot is moved to a new server, or the database is lost, the entire setup has to be redone from scratch. There's no way to back up the configuration.

**Improvement:** `/config export` saves the full guild config as a `.json` file. `/config import` recreates it.

**How it works:**
- `/config export` — bot sends an ephemeral message with a `.json` file attached containing all config values (channels mapped by name, not ID, so they can be remapped on import)
- `/config import` — staff attaches the `.json` file; bot shows a preview of what will be set and asks for confirmation before applying
- Channel/role references are matched by name — if a channel doesn't exist in the new server, that field is flagged as unmatched and skipped

---

#### 2.5 — Per-Section Config Reset Confirmation `P3`

**Problem:** `/config reset payment` immediately wipes all payment configuration. There's no "are you sure?" step. A single misfire deletes GCash number, PayPal email, Ko-fi URL, and all QR codes.

**Improvement:** Every `/config reset` asks for confirmation before executing, with a summary of exactly what will be deleted.

**How it works:**
- Running `/config reset payment` shows an ephemeral embed:
  ```
  ⚠️ This will permanently clear:
  · GCash number: 09XX-XXX-XXXX
  · PayPal email: example@mail.com
  · Ko-fi URL: ko-fi.com/example
  · 2 QR image URLs

  [ Confirm Reset ]   [ Cancel ]
  ```
- "Confirm Reset" executes the wipe
- "Cancel" dismisses with no changes
- Buttons expire after 60 seconds to prevent accidental late clicks

---
---

# Feature 3 — Shop Gate and TOS Compliance

**What it currently does:** `/shop open` and `/shop close` toggle commission availability. `/deploy tos` posts the TOS panel with an agreement button. Agreement is logged and a role is assigned.

**What it's missing:** TOS is static — if you update it, existing agreers aren't re-prompted. There's no way to open or close the shop on a schedule. When the shop is closed, clients have no path forward.

---

### Improvements (Sorted by Priority)

---

#### 3.1 — TOS Version Tracking and Force Re-Agreement `P1`

**Problem:** The current TOS system logs that a user agreed, but has no concept of which version they agreed to. If you update your TOS, every existing user is still marked as "agreed" — even to terms they've never seen.

**Improvement:** Attach a version number to the TOS. When the TOS is updated and the version bumps, all previous agreements are invalidated — users must agree again before they can open a ticket.

**How it works:**
- TOS has a version number stored in config (starts at `1`)
- Every agreement log entry stores the TOS version the user agreed to
- When the owner runs `/tos update version:[new_version]`, the TOS version bumps
- Next time a user tries to open a ticket: the bot checks if their logged TOS version matches the current one
- If it doesn't match: bot blocks the ticket and DMs the user a link back to the TOS panel with a note: *"Our Terms of Service have been updated. Please re-read and agree before opening a new ticket."*
- Re-agreement updates their log entry to the current version

---

#### 3.2 — Scheduled Shop Open / Close `P2`

**Problem:** If your commission hours are 9am–6pm, someone has to manually run `/shop open` and `/shop close` every day. Forgetting to close means clients can submit outside your hours.

**Improvement:** `/shop schedule` lets the owner set automatic open and close times.

**How it works:**
- `/shop schedule open:09:00 close:18:00 timezone:Asia/Manila days:Mon,Tue,Wed,Thu,Fri`
- Bot runs a background task that checks the current time every minute
- At the configured open time: automatically runs the same logic as `/shop open` (posts status, opens channel permissions)
- At the configured close time: automatically runs the same logic as `/shop close`
- `/shop schedule view` shows the current schedule
- `/shop schedule clear` removes the schedule and returns to manual control
- Manual `/shop open` and `/shop close` still work and override the schedule for that day

---

#### 3.3 — Closed Shop Waitlist `P2`

**Problem:** When the shop is closed, clients who try to open a ticket just get a "shop is closed" error and have no path forward. Many of them leave and don't come back.

**Improvement:** When the shop is closed, clients can join a **waitlist** to be notified when it reopens.

**How it works:**
- When a client attempts to open a ticket while shop is closed, they see: *"Commissions are currently closed. Would you like to be notified when they reopen?"* with a [ 🔔 Notify Me ] button
- Clicking it adds their user ID to a `waitlist` table in the database (only once per user)
- When `/shop open` runs (manually or via schedule), the bot DMs all waitlisted users: *"Commissions are now open! Click here to open a ticket: [link to ticket panel channel]"*
- After the notification is sent, users are removed from the waitlist
- `/waitlist view` shows staff how many users are waiting
- `/waitlist clear` clears the list without notifying (for cancellation scenarios)

---

#### 3.4 — Custom Close Message Per Shop Close `P3`

**Problem:** `/shop close` always posts the same generic "commissions are closed" message. When you close for a specific reason (holiday, art block, moving), you can't communicate context to clients.

**Improvement:** `/shop close reason:[text]` lets the owner attach a custom reason that's included in the status message.

**How it works:**
- `/shop close reason:Taking a break for Golden Week! Reopening May 6.`
- The shop status embed includes a "Reason" field with the provided text
- If no reason is given, the field is omitted (same behavior as current)
- The reason is stored and shown in `/shopstatus` until the shop reopens

---

#### 3.5 — TOS Agreement Statistics `P3`

**Problem:** No visibility into TOS adoption. You don't know how many users have agreed, when the last agreement was, or how agreement rates change over time.

**Improvement:** `/tos stats` shows agreement metrics for the server.

**How it works:**
- `/tos stats` returns an ephemeral embed:
  ```
  TOS Agreement Stats

  Total agreers (all time):   247
  Current version (v2):       183
  Previous version (v1):      64 (outdated — will be re-prompted)
  Last agreement:             Today at 2:14 PM by @user
  Agreements this week:       12
  ```

---
---

# Feature 4 — Ticket Panels and Intake Flow

**What it currently does:** Configurable ticket buttons open commission tickets via modal-based intake forms. One-open-ticket rule, shop/TOS gate, age gate, and staff shortcuts are in place.

**What it's missing:** Once a ticket is open, there's no way to search for it, no internal notes for staff, no inactivity handling, and the one-open-ticket error doesn't tell the client where their existing ticket is.

---

### Improvements (Sorted by Priority)

---

#### 4.1 — Helpful One-Open-Ticket Error `P1`

**Problem:** When a client tries to open a second ticket, they get blocked with a generic "you already have an open ticket" error. They have to scroll through the server to find their existing ticket channel — especially frustrating in large servers.

**Improvement:** The error message tells the client exactly where their open ticket is.

**How it works:**
- When the one-open-ticket check fires, the bot looks up the client's existing ticket channel from the database
- Error message: *"You already have an open ticket: [#ticket-username]. Please continue there."* (with a clickable channel link)
- If the ticket channel was somehow deleted but the DB record wasn't cleaned up, the bot detects this and allows them to open a new one

---

#### 4.2 — Ticket Inactivity Auto-Close `P1`

**Problem:** Old tickets with no activity sit open forever, cluttering the ticket category. There's no automatic way to clean them up. Staff have to manually `/close` every abandoned ticket.

**Improvement:** A background task watches for inactive tickets and auto-closes them after a configurable period.

**How it works:**
- Configurable inactivity threshold per server: `/config set ticket_inactivity_days:14`
- A background task runs once per day checking all open tickets for their last message timestamp
- Tickets inactive for the threshold period get a **warning first**:
  - Bot posts in the ticket: *"⚠️ This ticket has been inactive for 14 days and will be automatically closed in 48 hours. Reply here to keep it open."*
- If still no activity after 48 hours: bot closes the ticket with closure reason "Auto-closed: inactivity" and runs the same pipeline as `/close` (transcript, DM, channel deletion)
- Staff can exempt a ticket from auto-close with an `/exempt` flag

---

#### 4.3 — Internal Staff Notes per Ticket `P2`

**Problem:** There's no way for staff to leave private notes on a ticket — context that's visible to other staff but not the client. If staff member A handles the intake and staff member B checks the status later, there's no handoff mechanism.

**Improvement:** `/note add [text]` posts a staff-only note inside the ticket channel.

**How it works:**
- `/note add message:Client has a history of excessive revisions — clarify limits upfront.`
- Bot posts the note in the ticket channel as a distinct embed (different color, 🔒 icon, "Staff Note — visible to staff only" header)
- Notes are NOT included in the client-facing HTML transcript
- `/note list` shows all notes on the current ticket in a private ephemeral embed
- Notes are stored in the database and linked to the ticket ID

---

#### 4.4 — Ticket Assignment to Staff Member `P2`

**Problem:** In multi-staff shops, there's no record of which staff member is responsible for a ticket. Tickets can be handled by different staff members inconsistently, and there's no accountability for who committed to what.

**Improvement:** `/assign @staff_member` assigns a ticket to a specific person.

**How it works:**
- `/assign @kim` inside a ticket sets Kim as the assigned staff member for that ticket
- The bot updates the ticket's staff shortcuts embed to show "Assigned to: @kim"
- Kim receives a DM notification: *"You've been assigned to ticket #ticket-username."*
- `/assign` with no user unassigns (back to unassigned state)
- `/mytickets` shows a staff member all tickets currently assigned to them
- The assigned staff member is included in the transcript and order record

---

#### 4.5 — Ticket Search `P2`

**Problem:** There's no way to find a specific ticket without knowing the channel name or scrolling through the ticket category. In shops with high volume, finding a specific client's old ticket is painful.

**Improvement:** `/ticket search` filters tickets by client, status, date, or commission type.

**How it works:**
- `/ticket search client:@username` — all tickets for that user (open and closed)
- `/ticket search status:open` — all currently open tickets
- `/ticket search type:bust` — all tickets of a specific commission type
- `/ticket search created-after:2026-01-01` — tickets opened after a date
- Results show as a paged ephemeral embed with ticket ID, client name, status, commission type, and a clickable channel link (for open tickets) or "closed" label

---

#### 4.6 — Intake Form Validation `P3`

**Problem:** Modal intake forms accept any text input — including empty answers on optional fields, or one-word answers where more detail is needed. Staff then have to ask follow-up questions to get the actual required info.

**Improvement:** Define minimum requirements per form field.

**How it works:**
- In `/ticketform set`, each field can have an optional `min_length:[n]` requirement
- If a client submits a form with a field below the minimum, the bot rejects the submission and tells them specifically which field needs more detail: *"Please provide more detail for 'Commission Description' (minimum 20 characters)."*
- The form is re-shown for them to fix it
- Required vs. optional fields are clearly marked in the modal placeholder text

---
---

# Feature 5 — Quotes and Price Matrix

**What it currently does:** Step-by-step quote calculator, shared compute path for auto-quotes, base price matrix, extras, role discounts, public pricelist, and in-ticket recalculation.

**What it's missing:** Quotes have no expiry, clients have no way to formally accept or reject a quote, and there's no history of past quotes per client.

---

### Improvements (Sorted by Priority)

---

#### 5.1 — Client Quote Approval Flow `P1`

**Problem:** After a quote is generated in-ticket, the client either agrees informally (typing "ok") or just proceeds to payment. There's no formal record of them accepting the quoted price. This creates disputes later: *"I didn't agree to that price."*

**Improvement:** The quote embed includes an **Accept Quote** and **Request Changes** button that the client (ticket owner) can click.

**How it works:**
- When a quote is posted in the ticket (via auto-quote or `/quote calculator`), two buttons appear below it:
  - [ ✅ Accept Quote ] — for the ticket owner only
  - [ 🔄 Request Changes ] — opens a modal for the client to describe what they want changed
- Clicking **Accept Quote**:
  - Records the acceptance in the database with a timestamp
  - Updates the quote embed to show "✅ Accepted by @client at [time]"
  - Buttons are disabled (can't un-accept)
  - Unlocks the **Pay** button / payment instructions
- Clicking **Request Changes**:
  - Client types their change request in a modal
  - Bot posts the request as a message in the ticket for staff to see
  - Staff recalculates with `/quote recalculate` and a new quote embed replaces the old one
- Payment confirmation (`/payment confirm`) checks that a quote has been accepted first — if not, it warns staff

---

#### 5.2 — Quote Expiry `P1`

**Problem:** Quotes don't expire. If a client was quoted in January and comes back in June, the old quote is still "valid" — even if your prices have changed, the PHP/USD rate shifted, or your policies updated.

**Improvement:** Quotes automatically expire after a configurable number of days.

**How it works:**
- Configurable expiry per server: `/config set quote_expiry_days:14` (default: 14 days)
- Each quote embed shows its expiry date: *"This quote is valid until May 1, 2026."*
- A background task checks for expired quotes daily
- On expiry: the quote embed is updated to show "⛔ Expired — please request a new quote"
- Buttons (Accept Quote, Pay) are disabled on expired quotes
- Client receives a DM: *"Your quote in [ticket channel] has expired. Please ask staff to generate a new one."*
- Staff can manually extend a quote: `/quote extend id:[quote_id] days:7`

---

#### 5.3 — Quote History per Client `P2`

**Problem:** There's no record of past quotes generated for a client. If a returning client wants the same commission as before, staff have to recalculate everything from scratch. If there's a dispute about a past price, there's no log.

**Improvement:** Every generated quote is stored and linked to the client's user ID.

**How it works:**
- Database stores every quote: who it was for, which ticket, all line items, the final total, and when it was generated
- `/quote history client:@username` shows staff all quotes ever generated for that client (paged)
- `/myquotes` shows a client their own quote history (last 10, ephemeral)
- Each quote entry shows: date, commission type, tier, total, status (accepted/expired/pending)
- From the history, staff can click **Reuse** to pre-fill the calculator with the same parameters as a past quote (still recalculates at current prices — not locked to old price)

---

#### 5.4 — Quote Comparison on Recalculate `P2`

**Problem:** When `/quote recalculate` is run inside a ticket (e.g., client added a character), the new quote replaces the old one. There's no way to see what changed — the client sees a new total with no context for why it's different.

**Improvement:** When recalculating, show a diff between the old quote and the new one.

**How it works:**
- Before recalculating, the bot snapshots the current quote
- After recalculation, the new quote embed includes a "Changes from Previous Quote" section:
  ```
  Changes from Previous Quote
  Characters:    1 → 2           (+₱500)
  Rush fee:      None → Included (+₱300)
  ─────────────────────────────────────
  Previous total: ₱1,200
  New total:      ₱2,000         (+₱800)
  ```
- Client can see exactly what drove the price change — no surprises, no disputes

---

#### 5.5 — Bundle / Multi-Character Discount `P3`

**Problem:** Clients who order multiple commissions at once (e.g., 3 characters in the same order) don't get any incentive for bundling. The quote calculator handles multiple characters but doesn't support a bundle rate.

**Improvement:** Configurable bundle discount that applies automatically when a quote reaches a certain character count or total.

**How it works:**
- `/setdiscount bundle threshold:[n_characters] discount:[percent]`
- Example: "3+ characters in one order → 10% off the character add-on fees"
- Calculator detects when the threshold is met and applies the discount automatically
- The quote breakdown shows the bundle discount as a line item: `Bundle discount (3+ chars): -₱150`
- Bundle discounts stack with role discounts (Boostie/Reseller) — total discount is capped at a configurable max (e.g. 25%)

---
---

# Feature 6 — Payment Panel and Payment Confirmation

**What it currently does:** Payment method panel with GCash/PayPal/Ko-fi buttons, ephemeral payment detail displays, and `/payment confirm` to register the order.

**What it's missing:** Payment is confirmed by staff manually with no proof required. There's no way to track payment status between "sent" and "confirmed," and clients have no reminder if they forget to pay.

---

### Improvements (Sorted by Priority)

---

#### 6.1 — Payment Proof Upload `P1`

**Problem:** `/payment confirm` is purely staff-operated — there's no mechanism for clients to submit proof of payment. The workflow relies on staff noticing an incoming payment and running the command. This creates delays and requires staff to be actively watching.

**Improvement:** Clients can submit payment proof (screenshot) directly inside the ticket.

**How it works:**
- After the payment panel is viewed, a **Submit Payment Proof** button appears (visible only to the ticket owner)
- Client clicks it → a modal opens asking for:
  - Reference number / transaction ID
  - Amount paid
  - Screenshot (they drag-drop an image into the modal, or paste a URL)
- On submit: bot posts a structured "Payment Submitted" embed in the ticket:
  ```
  💳 Payment Proof Submitted

  From:       @client
  Amount:     ₱2,000
  Reference:  GCash #12345678
  Screenshot: [attached image]
  Status:     Pending Verification ⏳
  ```
- Staff see this embed and can click [ ✅ Confirm ] or [ ❌ Reject ] directly on it
- Confirm = runs the existing `/payment confirm` pipeline
- Reject = opens a modal for a rejection reason, which DMs the client

---

#### 6.2 — Payment Status States `P1`

**Problem:** Payment is binary: unconfirmed or confirmed. There's no "pending review" state. Staff can't mark a payment as "I've seen it, checking" without fully confirming it.

**Improvement:** Payment moves through three states: **Pending → Verified → Rejected.**

**How it works:**
- Pending: Client submitted proof but staff haven't acted yet
- Verified: Staff confirmed — order is registered and moves to the queue
- Rejected: Staff rejected with a reason — client is notified and can resubmit
- The ticket's payment embed updates its status field to reflect the current state
- The ticket channel name can optionally be prefixed with the payment state (e.g. `[PENDING]` → removed on verification)

---

#### 6.3 — Payment Deadline Reminder `P2`

**Problem:** Clients sometimes forget to pay after receiving a quote. The ticket sits open indefinitely with no payment and no action. Staff have to manually follow up.

**Improvement:** Automatic payment reminders after a configurable delay.

**How it works:**
- When a quote is accepted by the client (Feature 5.1) but payment isn't submitted within X hours, the bot sends a reminder
- Configurable: `/config set payment_reminder_hours:24`
- First reminder (24h): DM to client + a message in the ticket: *"Just a friendly reminder that payment is still pending for your commission. Please submit proof when ready, or let us know if you have questions."*
- Second reminder (48h): Same DM + a message in the ticket tagged with staff
- If still unpaid after a third threshold (configurable): ticket is flagged for staff review (not auto-closed — staff decides)
- Reminders stop as soon as payment proof is submitted

---

#### 6.4 — Payment Receipt to Client `P2`

**Problem:** After staff confirm payment, the client receives no confirmation of their own. They have to check the ticket to see if their payment was acknowledged. For clients paying via GCash, this is especially anxiety-inducing.

**Improvement:** When payment is confirmed, the client receives an automatic DM receipt.

**How it works:**
- Immediately after `/payment confirm` or the "Confirm" button on a payment proof:
- Bot DMs the client:
  ```
  ✅ Payment Confirmed — Mika Shop

  Order ID:      #MKA-2026-042
  Commission:    Fullbody, 2 characters
  Amount paid:   ₱2,000
  Confirmed by:  @staff
  Date:          April 14, 2026 at 3:22 PM

  Your order is now in the queue. We'll update you as work progresses.
  ```
- If DM is closed, falls back to posting the receipt in the ticket

---

#### 6.5 — Refund Tracking `P3`

**Problem:** There's no way to log refunds inside the bot. If an order is cancelled and a refund is issued, there's no record of it in the order history — only a manual note if staff remember to write one.

**Improvement:** `/refund order:[order_id] amount:[amount] reason:[text]` logs a refund against an order.

**How it works:**
- Creates a refund record in the database linked to the order ID
- Posts a refund embed in the ticket:
  ```
  💸 Refund Issued

  Order:      #MKA-2026-042
  Amount:     ₱2,000 (full refund)
  Reason:     Order cancelled at client request
  Issued by:  @staff
  ```
- Client receives a DM notification of the refund
- The order's status is updated to "Refunded"
- `/refund history` shows all refunds issued (staff only)

---
---

# Feature 7 — Queue and Order Lifecycle

**What it currently does:** Orders are registered manually or via payment confirm, get an auto-generated ID, move through Noted → Processing → Done status stages, and send template-driven messages at each stage.

**What it's missing:** Clients have no visibility into where they are in the queue. Staff have no analytics on throughput. There's no way to manage queue capacity or prioritize orders.

---

### Improvements (Sorted by Priority)

---

#### 7.1 — Queue Position Display to Client `P1`

**Problem:** Once an order is registered, the client has no idea where they are in the queue. They can't tell if they're next or if there are 15 people ahead of them. This leads to "how much longer?" messages — extra noise for staff.

**Improvement:** Clients can check their position with `/myorder` and the queue card shows live position.

**How it works:**
- `/myorder` (available to all server members) shows the client their active order:
  ```
  Your Order — #MKA-2026-042

  Commission:    Fullbody, 2 characters
  Status:        Processing 🎨
  Queue position: #3 of 8 active orders
  In queue since: April 14, 2026
  ```
- Queue position is recalculated dynamically — as orders ahead complete, their position drops
- The queue card in the queue channel also shows each order's position number
- Position is based on registration time (FIFO) — rush orders are always listed above standard regardless of registration time

---

#### 7.2 — Queue Capacity Limit `P1`

**Problem:** There's no limit on how many active orders the queue can hold. During a popular slot opening, the artist could be flooded with more orders than they can handle. The only protection is manually closing the shop — which requires someone to be watching.

**Improvement:** Configurable max active orders — new orders are rejected (with a helpful message) once the limit is hit.

**How it works:**
- `/config set queue_capacity:10`
- When a new order would be registered and the queue is at capacity:
  - `/payment confirm` fails with a message to the staff member: *"Queue is full (10/10 active orders). Complete some existing orders before accepting new ones, or increase the capacity limit."*
  - The shop can be manually or automatically closed to prevent new tickets
- `/queue capacity` shows current usage: *"Queue: 8 / 10 slots used"*
- When capacity is set to `0`, the limit is disabled (current behavior)

---

#### 7.3 — Rush / Priority Queue Lane `P2`

**Problem:** Rush orders are currently just regular orders with a rush fee applied to the quote. In the queue, they sit in the same list as standard orders in registration order — there's no mechanism to actually prioritize them in production.

**Improvement:** Rush orders are automatically placed at the top of the queue, above all standard orders.

**How it works:**
- When the quote has a rush fee applied, the order is tagged `priority:rush` in the database
- In the queue channel, rush orders are displayed in a separate section at the top with a ⚡ tag:
  ```
  ⚡ RUSH ORDERS (2)
  #MKA-2026-045 — @client — Bust, 1 char
  #MKA-2026-043 — @client — Chibi, 1 char

  STANDARD QUEUE (6)
  #MKA-2026-038 — @client — Fullbody, 2 char
  ...
  ```
- Queue position numbering is separate for rush and standard lanes
- Staff can manually promote a standard order to rush with `/queue promote id:[order_id]`

---

#### 7.4 — Queue Pause / Artist Hiatus Mode `P2`

**Problem:** If the artist needs a break (illness, vacation, burnout), there's no way to pause the queue. You can close the shop (no new tickets), but existing orders in the queue just sit there with no status update.

**Improvement:** `/queue pause reason:[text] until:[date]` pauses all queue processing and notifies all active clients.

**How it works:**
- Running `/queue pause`:
  - Sets a `queue_paused` flag in the database
  - All order status dropdowns are disabled (staff can't accidentally move orders while paused)
  - A "Queue Paused" banner is added to the top of the queue channel embed
  - Optional: DMs all clients with active orders: *"Our queue is temporarily on hold until [date]. We appreciate your patience!"*
- `/queue resume` clears the pause flag and re-enables status dropdowns
- `/queue status` shows whether the queue is active or paused and since when

---

#### 7.5 — Queue Analytics `P3`

**Problem:** There's no visibility into how the shop is performing. How many orders were completed this month? What's the average time from registration to completion? Which commission types are most popular?

**Improvement:** `/queue stats` shows a summary of queue performance metrics.

**How it works:**
- `/queue stats` — ephemeral embed with:
  ```
  Queue Stats — April 2026

  Orders completed this month:   12
  Orders completed total:        87
  Average completion time:       4.2 days
  Longest open order:            #MKA-2026-010 (18 days)
  Most popular type:             Fullbody (38%)
  Rush orders this month:        3 (25%)
  Refunds issued:                1
  ```
- `/queue stats period:all-time` shows lifetime stats
- `/queue stats period:last-30-days` for a rolling window

---

#### 7.6 — Client Order History `P3`

**Problem:** Returning clients can't look up their own past orders. Staff can't easily see a client's full order history without searching through the database manually.

**Improvement:** `/orderhistory` shows a paged list of all orders for a user.

**How it works:**
- `/orderhistory` (client-facing, shows own orders) or `/orderhistory client:@username` (staff-facing)
- Each entry shows: order ID, commission type, registration date, completion date, status, total paid
- Paged embed, 5 orders per page
- Total order count and total spent shown at the top: *"7 orders · ₱14,500 total"*

---
---

# Feature 8 — Ticket Progress, References, and Closure

**What it currently does:** `/stage` posts WIP updates. `/revision log` tracks revisions with fee logic. `/references add` and `/references view` track URLs. `/close` generates an HTML transcript and cleans up the channel.

**What it's missing:** Clients have no structured way to give feedback after their order is done. There's no milestone approval flow. Transcript search doesn't exist.

---

### Improvements (Sorted by Priority)

---

#### 8.1 — Client Approval Gate Before Closure `P1`

**Problem:** `/close` can be run by staff at any time — including before the client has acknowledged receiving their commission. A ticket can be closed while the client is offline, and they have no input into whether they're satisfied.

**Improvement:** Before final closure, the client must click a "Confirm Receipt" button.

**How it works:**
- When staff click the close button or run `/close`, instead of immediately closing:
  - Bot posts in the ticket: *"@client — Your commission is complete! Please confirm receipt to close this ticket."* with a [ ✅ Confirm Receipt ] and [ 🔄 Request Final Revision ] button
  - The **ticket is not closed yet** — it's in a "pending client confirmation" state
  - Client clicks **Confirm Receipt**: ticket closes normally, runs the full pipeline
  - Client clicks **Request Final Revision**: bot notifies staff, close is cancelled, ticket stays open
  - If client doesn't respond within 48 hours: ticket auto-closes anyway with a note in the transcript ("Client did not confirm — auto-closed after 48 hours")
- Staff can force-close at any time with `/close force` (bypasses the client gate — for abandoned tickets, dispute resolutions, etc.)

---

#### 8.2 — Post-Closure Feedback / Rating `P2`

**Problem:** After a ticket closes, there's no structured way for clients to rate the experience or leave feedback. Vouches are optional and unformatted. Staff have no systematic signal for what's going well or poorly.

**Improvement:** After closure, clients receive a DM with a simple feedback form.

**How it works:**
- After the ticket is fully closed and the channel is deleted, bot DMs the client:
  ```
  How was your experience with Mika Shop?

  ⭐⭐⭐⭐⭐  (clickable star rating buttons)

  [ Leave a Comment ] (optional)
  ```
- Clicking a star rating records it to the database
- Clicking "Leave a Comment" opens a short modal for free-text feedback (max 300 chars)
- Feedback is NOT posted publicly — it goes to a private `#feedback-log` channel (configurable)
- `/feedback stats` shows average rating, rating distribution, and recent comments (staff only)
- Clients who rated 5 stars get a gentle prompt: *"Enjoyed your experience? Consider leaving a vouch in #vouches!"* with a link

---

#### 8.3 — Structured Revision Request Form `P2`

**Problem:** `/revision log` tracks that a revision happened and whether it's free or paid, but clients currently request revisions by just typing in the ticket channel. There's no structure — staff have to parse freeform text to understand what the client actually wants changed.

**Improvement:** Clients can submit a structured revision request via a button.

**How it works:**
- After each `/stage` WIP update, a **Request Revision** button appears for the ticket owner
- Clicking it opens a modal with fields:
  - What needs to change? (paragraph, required)
  - Which part of the piece? (short text — e.g., "left hand", "background color")
  - Is this within your included revisions? (yes/no — informational, staff decides)
- Bot posts a formatted "Revision Requested" embed in the ticket:
  ```
  🔄 Revision Requested

  Part:     Left hand
  Details:  The fingers look a bit short, can we lengthen them?
  Revision: 2 of 2 free (last free revision)
  ```
- `/revision log` still works as-is for staff to formally log and track it
- The structured request reduces back-and-forth by front-loading the needed info

---

#### 8.4 — WIP Milestone Checkpoints `P3`

**Problem:** `/stage` posts a WIP update message, but all stages are treated equally with no defined workflow. There's no concept of a client "approving" sketch before lineart begins, or approving lineart before coloring.

**Improvement:** Configurable milestone stages that require client acknowledgment before the next stage begins.

**How it works:**
- `/config set milestone_stages:Sketch,Lineart,Coloring,Final`
- Each milestone has an "approval required" flag (configurable per stage)
- When staff run `/stage stage:Sketch`, bot posts the WIP update and (if approval is required for that stage) shows the client an **[ ✅ Approve Sketch ]** button
- Staff can't post the next stage until the client approves the current one (or staff force-advance with `/stage force`)
- Approvals are logged in the transcript: *"Sketch approved by @client at 3:44 PM"*
- Use case: artist never starts lineart on a pose the client hasn't approved — preventing expensive rework

---
---

# Feature 9 — Loyalty and Completion Nudge

**What it currently does:** Increments a loyalty counter on order completion, shows progress and milestone context, has a leaderboard, sends a completion DM nudge, and triggers hard-coded milestone rewards.

**What it's missing:** Loyalty is a number with no identity. There are no named tiers, no reward redemption, and no history of how loyalty was earned.

---

### Improvements (Sorted by Priority)

---

#### 9.1 — Named Loyalty Tiers `P2`

**Problem:** Loyalty is just a counter. "You have 7 loyalty points" means nothing emotionally. Milestones are hard-coded with no visual identity. Clients have no sense of progression or status.

**Improvement:** Named tiers with visual identity and role rewards.

**How it works:**
- Owner configures tier names and thresholds: `/loyalty tier add name:Bronze threshold:3 role:@BronzeBuyer`
- Example tier structure (fully configurable):
  - 🥉 **Bronze** — 3 orders
  - 🥈 **Silver** — 7 orders
  - 🥇 **Gold** — 15 orders
  - 💎 **Diamond** — 30 orders
- When a client hits a tier: they receive a DM announcement, the tier role is auto-assigned, and the bot posts a celebration embed in a configurable `#milestones` channel
- `/loyalty` now shows: *"You're a 🥈 Silver client — 2 more orders to reach 🥇 Gold!"*
- `/loyaltytop` leaderboard shows tier badges next to names

---

#### 9.2 — Loyalty History Log `P2`

**Problem:** Clients can see their loyalty count but not how they earned it. If the count seems wrong, there's no audit trail. Staff can't verify whether a loyalty increment was missed.

**Improvement:** Every loyalty increment is logged with the linked order.

**How it works:**
- `/loyalty history` (client) or `/loyalty history client:@username` (staff) shows:
  ```
  Loyalty History — @client

  +1  Order #MKA-2026-042   April 14, 2026   Fullbody
  +1  Order #MKA-2026-031   March 3, 2026    Chibi
  +1  Order #MKA-2026-015   Jan 22, 2026     Bust
  ────────────────────────────────────────────────
  Total: 3 (🥉 Bronze)
  ```
- Manual adjustments by staff (`/loyalty adjust client:@user amount:+1 reason:Bonus`) are also logged and clearly marked as manual

---

#### 9.3 — Loyalty Reward Redemption `P3`

**Problem:** Milestones give a Discord role and a message — but the actual benefit of loyalty (a discount, a freebie, a priority slot) has to be handled manually by staff. There's no in-bot redemption flow.

**Improvement:** Clients can redeem loyalty-based rewards directly with a bot command.

**How it works:**
- Owner configures redeemable rewards: `/loyalty reward add name:10% Discount cost:5 type:discount value:10`
- Types: `discount` (applies % off next quote), `priority` (jumps queue), `freebie` (TBD by owner)
- Client redeems: `/loyalty redeem reward:10% Discount`
- Bot checks they have enough loyalty points, deducts the cost, marks the reward as pending
- When the client opens their next ticket, the bot automatically flags: *"@client has a pending 10% discount to redeem on this order."*
- Staff can apply it during quoting

---
---

# Feature 10 — Warning System and Appeals

**What it currently does:** `/warn` with reason, dual DM flow, warn-log channel, auto-ban threshold, `/warns` and `/clearwarn`, custom reason presets, and appeal ticket creation from DM button.

**What it's missing:** All warnings are treated equally regardless of severity. There's no expiry for minor warnings. Appeal status is untracked after the ticket opens.

---

### Improvements (Sorted by Priority)

---

#### 10.1 — Warning Severity Levels `P2`

**Problem:** Every warning is the same — a minor "please don't spam" warning counts the same as a "charged back their payment" warning toward the auto-ban threshold. One incident shouldn't count the same as a serious offense.

**Improvement:** Warnings have configurable severity: **Minor, Major, Critical.** Severity affects threshold weight.

**How it works:**
- `/warn @user severity:minor reason:Spamming in shop channel`
- Severity weights toward threshold:
  - Minor = 0.5 (2 minors = 1 point toward ban threshold)
  - Major = 1.0 (current behavior)
  - Critical = 2.0 (counts double)
- The warn DM to the user includes the severity label and adapts its tone accordingly
- `/warns @user` shows severity per warn entry with colored labels
- `/setwarnthreshold` works against the weighted total, not the raw count

---

#### 10.2 — Warning Expiry `P2`

**Problem:** Minor warnings stay on a user's record forever. A user who was warned once two years ago for something minor still has that warning counting toward a ban threshold today.

**Improvement:** Warnings can have an expiry period after which they no longer count toward the threshold.

**How it works:**
- Configurable globally: `/config set warn_expiry_days:90` (default: never expires, current behavior)
- Or per-severity: Minor warns expire in 30 days, Major in 90 days, Critical never
- Expired warns are still visible in `/warns` but marked as "⏱️ Expired — no longer active"
- Expired warns don't count toward the ban threshold
- Staff can manually expire a warn early: `/clearwarn` with an optional `expire-only` flag that keeps the record but deactivates it

---

#### 10.3 — Appeal Status Tracking `P2`

**Problem:** When a user appeals via the DM button, a warn-appeal ticket is created — but after that, there's no tracking of what happened to the appeal. Was it resolved? Denied? Ignored? The warn record doesn't reflect the outcome.

**Improvement:** Appeals have a status that's tracked on the warn record and updated when the appeal resolves.

**How it works:**
- When an appeal ticket is opened, the warn record is updated: `appeal_status: pending`
- When staff close the appeal ticket, they're prompted: "How did this appeal resolve?"
  - Options: Warn Upheld / Warn Reduced / Warn Cleared
- The selection is logged against the warn record
- `/warns @user` shows appeal outcomes per warn entry: *"Warn #3 — Appealed: Warn Cleared on Apr 14"*
- Cleared appeals remove the warn from threshold calculation retroactively

---

#### 10.4 — Configurable Threshold Action `P2`

**Problem:** The warn threshold currently only triggers an auto-ban. For minor accumulated warnings, a ban is a very heavy first automatic action. Some servers want a mute or a kick instead.

**Improvement:** The threshold action is configurable — choose between timeout, kick, or ban.

**How it works:**
- `/setwarnthreshold threshold:5 action:timeout duration:24h`
- `/setwarnthreshold threshold:5 action:kick`
- `/setwarnthreshold threshold:5 action:ban`
- The staff warn-log embed shows the current threshold and configured action clearly
- When the threshold is hit, the bot takes the configured action and logs it

---
---

# Feature 11 — Vouch System

**What it currently does:** Auto-listens in the vouch channel, removes the "please vouch" role, allows staff to log vouches with an optional order ID, and shows paged vouch history.

**What it's missing:** Anyone can leave a vouch — even non-clients. Vouches are unstructured text with no rating. There's no verification that the vouch is genuine.

---

### Improvements (Sorted by Priority)

---

#### 11.1 — Vouch Verification (Must Be a Real Client) `P2`

**Problem:** Currently anyone in the server can post in the vouch channel and it counts as a vouch. This means competitors, friends, or the owner themselves could post fake vouches. There's no validation that the voucher was actually a client.

**Improvement:** Auto-vouches are only counted if the sender has at least one completed order in the bot's database.

**How it works:**
- When a message is posted in the vouch channel, the bot checks the `orders` table for a completed order linked to that user's Discord ID
- If found: vouch is accepted, "please vouch" role removed (current behavior)
- If not found: bot removes the message silently and DMs the user: *"Vouches are limited to verified clients. If you've commissioned here, your order may not be linked yet — please ask staff to link your order ID to your account."*
- Staff can manually verify a user: `/vouch verify @user reason:Paid via external platform`
- The `/vouch` staff command (for manually logging vouches) remains unrestricted — staff are trusted to use it legitimately

---

#### 11.2 — Star Rating on Vouches `P2`

**Problem:** Vouches are free text — there's no consistent, comparable metric. You can't say "average rating: 4.8 stars" because every vouch is just a paragraph.

**Improvement:** Vouches include a 1–5 star rating alongside the text.

**How it works:**
- When a user posts in the vouch channel, the bot replies with a prompt (visible only to them): *"Thanks for vouching! How would you rate your experience? (React below)"* with ⭐ to ⭐⭐⭐⭐⭐ as reaction options (or buttons)
- The rating is stored with the vouch record
- `/vouches @user` shows ratings per vouch and an average: *"4 vouches · Avg rating: ⭐4.75"*
- A server-wide `/vouch stats` shows overall average rating across all vouches

---

#### 11.3 — Vouch Showcase Auto-Post `P3`

**Problem:** Vouches pile up in the vouch channel as plain messages. There's no formatted, shareable presentation of the best feedback. New visitors to the server see a wall of text instead of a clean, professional showcase.

**Improvement:** When a new vouch is submitted, the bot automatically posts a formatted vouch card in a separate `#vouch-showcase` channel.

**How it works:**
- Separate from the vouch submission channel, a `#vouch-showcase` channel is configured
- For every accepted vouch, the bot posts a formatted embed:
  ```
  ⭐⭐⭐⭐⭐  — @client
  "Absolutely love my commission! The detail on the background was incredible.
  Delivered ahead of schedule too. 100% recommending!"
  
  Order: #MKA-2026-042 · Fullbody · April 14, 2026
  ```
- Only accepted, verified vouches appear here
- Staff can suppress a specific vouch from the showcase with a `/vouch hide id:[vouch_id]` command (for borderline or low-effort vouches)

---
---

# Feature 12 — Sticky Messages

**What it currently does:** Creates a sticky embed per channel that gets reposted to the bottom after every user message. Handles race conditions, cache on startup.

**What it's missing:** Every channel can only have one sticky. Stickies have no scheduling, no cooldown, and no way to temporarily disable without deleting.

---

### Improvements (Sorted by Priority)

---

#### 12.1 — Sticky Cooldown `P2`

**Problem:** In high-traffic channels, the sticky is reposted on every single message — potentially dozens of times per minute. This is noisy, expensive in API calls, and the sticky becomes a spammy presence in the channel instead of a helpful anchor.

**Improvement:** Configurable minimum time between sticky reposts.

**How it works:**
- `/sticky` gains an optional `cooldown:[seconds]` parameter (default: 60 seconds)
- After a repost, the sticky engine ignores new messages until the cooldown expires
- The last message timestamp (not the sticky itself) triggers the repost — so if 20 messages come in within the cooldown window, the sticky only reposts once when the cooldown expires
- Configurable per channel: `/stickyupdate channel:#general cooldown:120`

---

#### 12.2 — Sticky Pause (Without Deleting) `P3`

**Problem:** If you want to temporarily disable a sticky (e.g., during an event where the channel is being used differently), the only option is `/unsticky` — which deletes the sticky config. You'd have to recreate it afterward.

**Improvement:** `/sticky pause channel:#channel` temporarily disables the sticky without removing its config.

**How it works:**
- Sets a `paused: true` flag on the sticky record
- The repost engine skips paused stickies
- The existing sticky message in the channel is left in place (not deleted)
- `/sticky resume channel:#channel` re-enables it — next user message triggers a fresh repost
- `/stickies` shows pause state for each sticky in the list

---

#### 12.3 — Sticky Scheduling (Time-Based Activation) `P3`

**Problem:** Some stickies are only relevant at certain times — a "commissions are open" sticky shouldn't appear at 2am when the artist is offline.

**Improvement:** Stickies can be configured to only be active during specific hours.

**How it works:**
- `/sticky channel:#shop-chat active-hours:09:00-18:00 timezone:Asia/Manila`
- Outside those hours, the sticky is automatically paused (won't repost)
- During active hours, it behaves normally
- The `active-hours` setting is optional — if not set, sticky is always active (current behavior)

---
---

# Feature 13 — Drops and Delivery

**What it currently does:** `/drop` sends a delivery DM with a link button and logs it. `/drophistory` for staff. Ticket notification on drop. Fallback DM on order completion.

**What it's missing:** There's no confirmation that the client actually received or opened the delivery. Multiple files can't be delivered together. If the DM is blocked, the delivery silently fails.

---

### Improvements (Sorted by Priority)

---

#### 13.1 — DM Failure Fallback to Ticket `P1`

**Problem:** If a client has DMs disabled from non-friends, `/drop` silently fails — the delivery is logged as sent but the client never received it. Staff have no indication this happened unless they manually check.

**Improvement:** If the delivery DM fails, automatically post it in the ticket channel instead and alert staff.

**How it works:**
- After attempting the DM, if Discord returns a "cannot send to this user" error:
  - Bot posts in the ticket channel: *"@client — We couldn't send your delivery via DM. Your files are here instead:"* followed by the delivery content
  - Bot also notifies staff: *"⚠️ Delivery DM failed for @client — posted in ticket instead."*
  - Delivery log records the failure mode: `delivery_method: ticket_fallback`
- If there's no open ticket anymore (already closed): bot sends the content to the client's last known ticket transcript or flags it for staff

---

#### 13.2 — Client Delivery Confirmation `P2`

**Problem:** Delivery is logged as complete the moment the DM is sent. But "sent" ≠ "received and accepted." Clients can claim they never got the file, or that the link was broken, and there's no proof of acknowledgment.

**Improvement:** The delivery DM includes a **Confirm Receipt** button that the client clicks.

**How it works:**
- The delivery DM includes: *"Please click below to confirm you received your commission."* with a [ ✅ Confirm Receipt ] button
- When clicked: logged in the database with a timestamp. Staff can see confirmation status in `/drophistory`
- If not confirmed within 48 hours: bot sends a follow-up DM reminder once
- If still not confirmed after 72 hours: staff are alerted in the ticket (or staff log channel)
- Delivery record shows: `received: confirmed at 3:44 PM` or `received: unconfirmed`

---

#### 13.3 — Delivery Deadline Tracking `P3`

**Problem:** There's no record of whether a delivery was on time relative to when the order was placed. Rush orders especially have an implied deadline — was it honored?

**Improvement:** Track delivery date against order registration date and flag late deliveries.

**How it works:**
- Rush orders get a target delivery date based on the rush fee tier configuration
- Standard orders get a target based on configurable `average_completion_days`
- When `/drop` is run, the bot calculates: was this on time?
- The drop log record includes: `on_time: true/false`, `days_taken: 4`, `target_days: 3`
- `/queue stats` includes an "On-time delivery rate" metric (Feature 7.5)
- Late deliveries are never surfaced publicly — only in staff analytics

---
---

# Feature 14 — Owner-only DM Maintenance

**What it currently does:** `/purge_bot_dms` scans and deletes bot DMs with a cap, progress-safe looping, and summary metrics.

**What it's missing:** The utility only works on-demand. There's no backup capability, no database health check, and no data export.

---

### Improvements (Sorted by Priority)

---

#### 14.1 — Database Backup Command `P0`

**Problem:** There's no way to download or back up the SQLite database from inside Discord. If the hosting server fails and there's no external backup, all guild data — orders, tickets, vouches, loyalty, config — is gone.

**Improvement:** `/db backup` sends the owner a copy of the database file as a DM attachment.

**How it works:**
- Owner-only command
- Bot sends a DM to the owner with the `.sqlite` file attached
- File is sent directly from the bot's file system — no intermediate storage
- If the file is too large for a Discord attachment (> 25MB), the bot either: compresses it first, or sends a notice that the backup needs to be done via server file access
- `/db backup schedule:daily` sets a daily auto-backup (bot DMs the owner the file every day at a configured time)

---

#### 14.2 — Guild Data Export `P2`

**Problem:** If a server owner wants their full data (for legal reasons, to migrate to a different bot, or as a record), there's no way to get it. The only option is direct database access.

**Improvement:** `/export guild` generates a comprehensive JSON export of all data for the current guild.

**How it works:**
- Pulls all records from all tables scoped to the current `guild_id`
- Assembles them into a structured `.json` file: config, orders, tickets, vouches, loyalty, warnings, quotes
- Sends the file as an ephemeral attachment to the command invoker
- Owner-only, since the export contains sensitive data (payment details, user IDs, warn records)

---

#### 14.3 — Database Health Check `P3`

**Problem:** As the database grows, orphaned records can accumulate (e.g., a ticket record whose channel was deleted, an order record with no linked ticket). These don't cause crashes but they inflate the DB and can cause confusing query results.

**Improvement:** `/db check` runs a health audit and reports findings.

**How it works:**
- Checks for: orphaned ticket records (channel no longer exists), orphaned order records (no linked ticket), duplicate panel records, stale wizard sessions older than 24 hours, broken persist_panel pointers
- Reports findings as a structured list:
  ```
  Database Health Check

  ✅ Schema integrity: OK
  ⚠️  3 orphaned ticket records (channels deleted)
  ⚠️  1 stale wizard session (22 hours old)
  ✅ No duplicate panels
  ✅ No orphaned orders

  Run /db clean to remove flagged records.
  ```
- `/db clean` removes only the flagged orphaned records (with a confirmation step)

---
---

# Feature 15 — Data Layer and Persistence

**What it currently does:** SQLite schema covering all production tables, guild-scoped helpers, startup migrations for schema evolution, reset helpers, and operational state tables.

**What it's missing:** Migrations aren't versioned (can't tell which migrations have run). There's no soft-delete safety net. No performance monitoring for slow queries.

---

### Improvements (Sorted by Priority)

---

#### 15.1 — Migration Version Tracking `P0`

**Problem:** Startup migrations run every boot and use conditional logic (`IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`) to be idempotent — which works, but means every boot runs every migration check even for already-applied changes. It's slow as migrations accumulate and there's no record of which schema version the DB is at.

**Improvement:** A migration versioning table tracks which migrations have run. Only new ones execute.

**How it works:**
- A `schema_migrations` table stores: `version` (integer), `name` (string), `applied_at` (timestamp)
- Migrations are numbered files: `001_initial_schema.py`, `002_add_loyalty_tier.py`, etc.
- On startup: compare the list of migration files against the `schema_migrations` table
- Only run migrations whose version number isn't in the table
- After each migration runs successfully: insert a record into `schema_migrations`
- Result: startup is fast (only new migrations run), and you always know exactly what schema version the DB is at

---

#### 15.2 — Soft Deletes on Critical Records `P1`

**Problem:** When a ticket, order, or warn is deleted, it's a hard delete — the row is gone from the database permanently. If a deletion was a mistake (staff ran `/clearwarn` on the wrong user, or a ticket was closed prematurely), recovery is impossible without a database backup.

**Improvement:** Deletions on critical tables set a `deleted_at` timestamp instead of removing the row.

**How it works:**
- Tables affected: `tickets`, `orders`, `warns`, `vouches`, `loyalty`
- Instead of `DELETE FROM tickets WHERE id = ?`, the operation runs `UPDATE tickets SET deleted_at = NOW() WHERE id = ?`
- All normal queries add a `WHERE deleted_at IS NULL` filter — soft-deleted records are invisible in normal operation
- A record remains recoverable for 30 days — after that, a scheduled cleanup task hard-deletes it
- Owner recovery command: `/db recover type:warn id:[warn_id]` — clears the `deleted_at` and restores the record

---

#### 15.3 — Query Performance Logging `P3`

**Problem:** As the database grows with orders, tickets, and vouches, some queries may become slow — especially unindexed searches by user ID or guild ID. There's no visibility into which queries are slow.

**Improvement:** Log any query that takes longer than a configurable threshold.

**How it works:**
- Wrap DB query execution in a timer
- If a query exceeds the threshold (default: 200ms), log it: the query, its parameters (sanitized), and execution time
- Logs go to a `slow_query.log` file, not to Discord (too noisy for a channel)
- `/db slowqueries` shows the top 10 slowest queries recorded in the last 7 days (owner-only)
- Use case: identifies which tables need indexes added as the bot scales

---

---

## Summary — All Improvements by Original Feature

| Feature | Total Improvements | Highest Priority |
|---|---|---|
| 1 — Core Runtime | 6 | `P0` — Environment validation, Startup health report, Error alert channel |
| 2 — Config & Setup | 5 | `P0` — Config validation / health check |
| 3 — Shop Gate & TOS | 5 | `P1` — TOS version tracking + re-agreement |
| 4 — Ticket Panels | 6 | `P1` — Helpful one-open-ticket error, Inactivity auto-close |
| 5 — Quotes | 5 | `P1` — Client quote approval flow, Quote expiry |
| 6 — Payment | 5 | `P1` — Payment proof upload, Payment status states |
| 7 — Queue & Orders | 6 | `P1` — Queue position display, Capacity limit |
| 8 — Progress & Closure | 4 | `P1` — Client approval gate before closure |
| 9 — Loyalty | 3 | `P2` — Named loyalty tiers, Loyalty history |
| 10 — Warnings | 4 | `P2` — Warning severity levels, Warning expiry |
| 11 — Vouches | 3 | `P2` — Vouch verification, Star ratings |
| 12 — Sticky Messages | 3 | `P2` — Sticky cooldown |
| 13 — Drops & Delivery | 3 | `P1` — DM failure fallback to ticket |
| 14 — DM Maintenance | 3 | `P0` — Database backup command |
| 15 — Data Layer | 3 | `P0` — Migration version tracking, Soft deletes |
| **Total** | **65** | |
