# Cursor AI — Bot Flow Improvements Prompt

You are refactoring a Discord commission bot (Python, discord.py / cogs architecture). Apply the following improvements across the codebase. Locate relevant files yourself using the cog names and command names as search anchors.

---

## 1. Setup Wizard (`/setup`)
- Convert `/setup` into a sequential step-by-step wizard using Discord modals or paginated embeds. Do not let it finish unless all required slots (queue, ticket categories, staff role, TOS, vouches channel, feedback channel, payment text) are filled.
- After wizard completion, auto-post a checklist embed in the admin channel: green ✅ for configured slots, red ❌ for missing ones.
- Add a `/deploy all` command that runs `/deploy tos` + `/deploy payment` + `/ticketpanel` in sequence. Guard it with a setup-complete check; if setup is incomplete, send an ephemeral error listing what is missing.

## 2. Ticket Opening (client flow)
- Remove quote calculation steps from the ticket-opening flow. Ticket open = **select commission type → one modal**. Quote tools stay available as standalone commands inside the ticket.
- On modal error (missing required field), re-open the same modal with the client's previous answers pre-filled instead of restarting.
- In the opening confirmation embed (posted in the new ticket channel and DM'd to client), display the ticket channel name explicitly so the client can find it later.

## 3. Ticket Stage Panel (staff)
- On every new ticket channel, pin a **Staff Action Panel** embed immediately after ticket creation. It must contain buttons in order: `Claim → In Progress → Payment Confirm → Done → Close`.
- Disable (grey out) any button whose prerequisite stage has not been reached yet.
- Remove `/stage` as a standalone command; its logic should be called internally by the stage buttons instead.
- The "Remind Client" button must include a footer showing the timestamp of the last reminder sent for that ticket.

## 4. Automatic Order Registration
- In the payment confirm handler (`/payment confirm` or its button equivalent), automatically create the DB order row using existing ticket metadata (client ID, commission type, ticket channel name, assignee) if one does not already exist. No extra command from staff should be needed.
- Remove the silent slug fallback in `/vouch` and `/review`. If no DB order row is found, send an ephemeral error: `"This ticket has no registered order — ask staff to confirm payment first."` Do not proceed silently.

## 5. Vouch Paths
- Keep only two vouch paths: client `/vouch` and staff `/vouchstaff`. Remove the legacy "type in vouches channel" listener entirely (the `on_message` handler that removes Please Vouch and inserts a null-order_id row).
- Remove the restriction that `/vouch` must be run inside the ticket channel. Resolve the order by matching the client's user ID to their open or recently closed orders in the DB instead.
- After `/vouch` succeeds, append to the confirmation message: `"You can now leave a review with /review."` Do not rely solely on a DM.

## 6. Review Flow (`/review`)
- After `/vouch` completes, send a follow-up message in the channel with a **Leave a Review** button that opens the `/review` modal pre-filled with the order ID. This is in addition to (not replacing) the slash command.
- Replace the **Feedback pending** role gate with a DB flag (`reviewed: boolean`). Keep the role as a cosmetic reward if desired, but do not use it to gate `/review` access.
- On `/review` rejection, send a specific ephemeral reason:
  - `"You haven't vouched for this order yet."`
  - `"You've already submitted a review for this order."`

## 7. Loyalty Stamp Cards
- Decouple stamp card issuance from the Done/Close distinction. Issue the card whenever an order transitions to `done` status, regardless of which code path triggered it. Use a single internal helper (e.g. `issue_loyalty_card(order_id, client_id)`) called from all paths.
- Advance stamps only via the client `/vouch` path (and staff `/vouchstaff`). Remove stamp advancement from the legacy `on_message` vouches channel handler (which is being deleted per §5 anyway).

## 8. Error Messages & Empty States
- Audit every location where the bot silently skips an action due to a missing role, missing channel, or permission error. Replace each silent skip with an ephemeral message to the triggering user explaining what is missing and who to contact.
- For all embeds that can render empty (queue list, pricelist, order list), add a description field when the list is empty: e.g. `"No orders yet — staff will register your order after payment is confirmed."`

---

## Constraints
- Do not change the database schema beyond adding the `reviewed` boolean flag to the orders/vouches table (§6) and ensuring order rows are always created on payment confirm (§4).
- Keep all changes backward-compatible with existing slash command names that clients already know (`/vouch`, `/review`, `/quote`).
- Each change should be self-contained per cog where possible. Add a short `# CHANGED:` comment above every modified block.
