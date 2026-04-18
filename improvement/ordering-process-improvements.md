# Ordering Process — Improvement Suggestions (KISS + UI/UX)

> Focus: reduce the number of steps, decisions, and failure points a client or staff member encounters between "I want to order" and "order is complete."

---

## 1. Pre-Order Setup (Owner / Admin)

**Problem:** Setup requires the owner to configure 10+ individual slots across `/setup` and `/config`, then separately have staff deploy three different panels. There is no feedback on what is missing until something breaks at runtime.

**Improvements:**
- `/setup` should be a **single guided wizard** that does not exit until all required slots (categories, roles, channels, payment strings) are filled. Each step should show progress (e.g. "Step 3 of 8").
- After setup completes, auto-post a **configuration health embed** in the admin channel showing every required slot as ✅ or ❌ with a one-line fix hint for each missing item.
- Merge the three separate deploy commands into one: **`/deploy all`** — run it once, panels go up. Guard it with a setup-complete check.
- Quote matrix setup (`/setprice`, `/quoteextras`, `/setdiscount`, `/setcurrency`) should be part of the wizard, not a separate out-of-band step. Missing a price matrix silently breaks the client quote flow.

---

## 2. TOS Agreement

**Problem:** TOS agreement is a separate panel in a separate channel that the client must find and click before they can open a ticket. It is an invisible prerequisite — clients who miss it just see the ticket button fail with no explanation of why.

**Improvements:**
- If the client clicks a ticket button **without TOS agreed**, show an ephemeral message: *"You need to agree to our Terms of Service first — head to #tos and click the button."* with a channel link. Do not silently block.
- Consider moving TOS agreement **inline**: on first ticket button click, show a modal or ephemeral embed with the TOS text and an "I agree" button. One fewer channel the client needs to visit.

---

## 3. Ticket Opening (Client)

**Problem:** Opening a ticket involves up to five steps: click panel button → select commission type → go through quote wizard steps → fill modal → wait for channel creation. Each step is a new interaction, and any drop-off loses the client's progress entirely.

**Improvements:**
- **Collapse to two steps:** select commission type → fill one modal. Move the quote wizard (tier, character count, background, rush) into the modal as fields, not a multi-step ephemeral flow.
- If the modal submission fails a validation (missing required field), **re-open the same modal with previous answers preserved** instead of making the client start over.
- The bot currently limits one open ticket per user. When a client tries to open a second ticket, show them a **link to their existing ticket** instead of a generic rejection. ("You already have an open ticket here: #cs-fb-username-001.")
- Age gate for NSFW ticket types should explain what "age verified" means and how to get it, not just silently block.

---

## 4. Quote Display (Inside Ticket)

**Problem:** The quote is computed and displayed at ticket creation, but if prices change or the client adds extras, a staff member must manually run `/quote recalculate`. The client has no way to self-serve a revised quote.

**Improvements:**
- Allow clients to run **`/quote recalculate`** themselves inside their own ticket (scoped read-only; staff confirms before it updates the order record).
- The quote embed should display a **clear breakdown** (base price + each extra + discount = total) rather than just the total, so clients understand what they are paying for without asking.
- If the server uses a currency other than PHP, the FX conversion should appear as a secondary line, not require a separate lookup.

---

## 5. Payment Flow (Staff + Client)

**Problem:** Payment confirmation and order registration are two conceptually different steps that both live under the same `/payment confirm` command. If staff use `/queue` instead, the outcome is similar but the path is different — two routes to the same result creates inconsistency.

**Improvements:**
- **Unify the paths:** `/payment confirm` should always create the order row if one does not exist. Remove `/queue` as an alternative registration path — it should only display the queue, not register orders. One command, one outcome.
- Order registration should be **automatic on payment confirm**, using ticket metadata (client, commission type, channel name) without requiring staff to re-enter fields that the bot already has.
- After payment is confirmed, post a **visible status update in the ticket** for the client: "Payment confirmed ✅ — your order is registered. We'll claim your ticket soon." Clients currently have no signal that anything changed.
- Expose a **payment status indicator** in the ticket overview embed (e.g. "Payment: Pending / Confirmed") so both staff and client can see the current state at a glance without running a command.

---

## 6. Active Commission — Staff Workflow

**Problem:** The ticket lifecycle is driven by a mix of slash commands (`/stage`, `/revision log`, `/references`, `/noted`) and buttons (Claim, Done, Close). New staff have no single place that tells them what to do next.

**Improvements:**
- Pin a **Staff Action Panel** embed at the top of every new ticket channel with stage buttons in linear order: `Claim → Noted → Processing → Done → Close`. Grey out buttons that are not yet available based on current ticket state.
- Replace `/stage` as a standalone command with the stage buttons. The command's internal logic remains but is triggered by buttons only — one interface, one mental model.
- `/noted` currently moves the ticket to a separate category and posts to queue. This is an extra optional step that many staff skip inconsistently. Make **Noted** a stage within the same pipeline (a button on the panel) rather than a separate command.
- `/revision log` should prompt staff to specify whether the revision is **free** or **paid** at the time of logging, not rely on a background rule the staff may not remember.

---

## 7. Client Communication During Active Work

**Problem:** The "Remind Client" action sends a DM with a jump link but has no memory of whether a reminder was already sent recently. Staff can accidentally spam clients.

**Improvements:**
- The Remind Client button should show the **timestamp of the last reminder** in the ticket channel before sending. Add a **cooldown** (e.g. 24 hours) and make it visible: "Last reminded: 2 hours ago. Cooldown active."
- `/drop` (delivery link DM) should also post a **notice in the ticket channel** so there is a record visible to all parties, not just a private DM that can be missed or lost.

---

## 8. Finishing the Ticket — Done vs Close

**Problem:** Done and Close are two separate staff actions with overlapping effects (both can trigger loyalty card issuance with a duplicate guard). The distinction is not intuitive to new staff — "done" means work is finished, "close" means the channel is deleted, but both exist as separate buttons without clear labels explaining this.

**Improvements:**
- Rename the buttons to **"Mark Complete"** and **"Archive Ticket"** so the difference is self-evident.
- Loyalty card issuance should only ever fire from **Mark Complete**, not from Archive. The duplicate guard is a workaround for unclear separation of concerns — fix the root cause instead.
- If `/closeapprove` is required, the **Archive Ticket** button should be visibly disabled with a tooltip: "Waiting for client approval — client must run /closeapprove first." Do not let staff click it and get an error after the fact.
- Auto-delete timer (`DONE_TICKET_AUTO_DELETE_HOURS`) should be visible to both staff and client in the ticket after **Mark Complete**: "This ticket will be archived in 24 hours."

---

## 9. Vouching (Client)

**Problem:** `/vouch` only works inside the ticket channel, but by the time the client wants to vouch, the ticket may have moved to the "done" category and feel inaccessible. There are also three separate vouch paths (client command, staff command, legacy channel message) with different outcomes.

**Improvements:**
- Remove the restriction that `/vouch` must be run inside the ticket channel. Resolve the order by matching the client's user ID to their completed orders in the DB.
- Remove the legacy "type in vouches channel" path entirely. It produces null `order_id` rows and is a parallel mental model to the structured command. Two paths max: client `/vouch` and staff `/vouchstaff`.
- The **Please vouch** role as the gate for `/vouch` is invisible to the client — they either have it or they don't, with no explanation. Replace the role check with a DB flag tied to order completion, and show a clear in-channel prompt: "Your order is complete! Run `/vouch` to leave a public vouch."
- After `/vouch` succeeds, show the next step inline in the ticket: "Thanks! You can now leave a detailed review with `/review`." Do not rely solely on a DM.

---

## 10. Reviews (`/review`)

**Problem:** `/review` is a four-step flow (ephemeral ratings → modal text → dropdown view → submit) gated behind the Feedback pending role and a complex autocomplete that mixes registered orders and fallback tags. The multi-step flow creates drop-off risk at each step.

**Improvements:**
- Combine the four steps into **one modal** with inline rating selectors (Discord supports select menus inside modals). Fewer round-trips, less drop-off.
- Replace the **Feedback pending role gate** with a DB flag. Roles are hard to debug and invisible to clients; a database check is more reliable and easier to audit.
- The autocomplete mixes registered orders and fallback tags with no visual distinction. Label them clearly: "✅ Order #001 (registered)" vs "🔖 cs-fb-username-001 (fallback tag)" so clients are not confused by what they are selecting.
- When `/review` rejects a submission, tell the client exactly why:
  - *"You haven't vouched for this order yet."*
  - *"You've already reviewed this order."*
  - *"This order doesn't belong to your account."*
- After successful review, confirm what the **Review reward** role is (if configured): "You've been given the @Reviewer role as a thank-you!"

---

## 11. Loyalty Stamp Cards

**Problem:** Stamp cards are issued by either Done or Close, whichever runs first, with a duplicate guard as the safety net. Stamps advance through three different vouch paths. This is complexity hidden behind idempotency rather than clean design.

**Improvements:**
- Issue the stamp card **only on Mark Complete (Done)**, never on Close. Remove the duplicate guard — it becomes unnecessary once the trigger is singular.
- Advance stamps **only through client `/vouch` and staff `/vouchstaff`**. Removing the legacy vouches channel path (§9) eliminates the third stamp trigger automatically.
- When a stamp card is issued, post a **brief in-ticket notice**: "Your loyalty card has been posted in #loyalty-cards — vouch to earn your next stamp!" so clients know to look.
- The void timer (`/loyalty_card voidhours`) should appear on the card itself: "This card expires in 7 days if no vouch is submitted."

---

## 12. Error Messages & Empty States

**Problem:** Multiple failure points across the flow produce either silence (bot skips with a permission error logged) or cryptic messages. Clients and staff are left to guess what went wrong.

**Improvements:**
- Every silent skip (missing channel, missing role, permission error) should produce a **visible ephemeral message** to the triggering user: plain language, one sentence, who to contact.
- Empty embeds (no queue entries, no pricelist, no order history) should include a **next-step hint** rather than an empty list: *"No orders yet — your order will appear here after staff confirms payment."*
- The troubleshooting table in the docs (§11 of the source) represents known failure modes. Every one of those should have a corresponding in-bot error message so users never need to read the docs to recover from a common error.

---

## Summary Table

| Phase | Cut | Consolidate | Clarify |
|---|---|---|---|
| Setup | Separate deploy commands | `/deploy all` after wizard | Config health embed post-setup |
| TOS | Silent block on missing role | Inline TOS on first ticket click | Ephemeral error with channel link |
| Ticket open | Multi-step quote wizard | Type → one modal | Existing ticket link on duplicate block |
| Payment | `/queue` as registration path | `/payment confirm` does everything | Status indicator in ticket embed |
| Staff workflow | `/stage` as standalone command; `/noted` as separate command | Stage buttons on pinned panel | Disabled buttons with state labels |
| Done vs Close | Loyalty card firing from both | Loyalty only from Mark Complete | Rename buttons; show auto-delete timer |
| Vouching | Legacy vouches channel path; ticket-channel restriction | Client `/vouch` + staff `/vouchstaff` only | In-channel prompt replacing role gate |
| Reviews | 4-step flow; role gate | Single modal + DB flag | Specific rejection messages; labeled autocomplete |
| Loyalty | 3 stamp triggers; duplicate guard | Single trigger on Mark Complete | Void timer on card; in-ticket notice |
| Errors | All silent skips | — | Plain-language ephemeral messages everywhere |
