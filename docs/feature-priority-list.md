# Mika Shop Feature Priority List

This document lists bot features from `docs/`, sorted by implementation priority.
Priority model:

- `P0` = must-have for stable production operation
- `P1` = core business flow for commissions
- `P2` = high-value quality, moderation, and operator control
- `P3` = quality-of-life and retention features
- `P4` = owner-only maintenance utilities

---

## Feature 1: Core Runtime and Reliability (`P0`)

Purpose: keep bot online, synced, and recoverable after restart.

Subfeatures by priority:

- `P0` Initialize database on startup (`init_db`) and validate required config (`BOT_TOKEN`)
- `P0` Load all production cogs in fixed startup order
- `P0` Sync slash command tree in one scope at a time: global by default, or guild-only via `SYNC_GUILD_ID` for fast testing
- `P0` Register persistent views on boot (`TOSAgreeView`, `PaymentView`, ticket close views, order status views)
- `P0` Global app-command error handling for permission failures, sync mismatch, and generic runtime errors
- `P1` Startup rehydration tasks (`refresh_status_message`, `refresh_sticky_cache`)
- `P2` First-join setup hint message for unconfigured guilds
- `P2` Slash interaction logging (`cmd`, guild, channel, user)

---

## Feature 2: Server Configuration and Setup Wizard (`P0`)

Purpose: map channels/roles quickly and safely per guild.

Subfeatures by priority:

- `P0` `/config view` full configuration audit (channels, categories, roles, payment strings, warn threshold, order prefix)
- `P0` `/setup` guided flows: Tickets & Panels, Queue & Orders, Shop & TOS, Payment, Channels & Roles
- `P0` Permission gate for config commands (Admin/Manage Server/staff role)
- `P1` `/config payment` subcommands for GCash/PayPal/Ko-fi details and QR URLs
- `P1` `/config reset` grouped reset options (`tickets`, `queue`, `shop`, `payment`, `channels_roles`, `pricing`)
- `P2` Paged output for long config responses
- `P2` Session tracking (`wizard_sessions`) for setup continuity metadata
- `P3` `/setup_resume` operator guidance when ephemeral state cannot be restored

---

## Feature 3: Shop Gate and TOS Compliance (`P0`)

Purpose: enforce onboarding and open/closed commission state.

Subfeatures by priority:

- `P0` `/shop open` and `/shop close` with persisted state and moderator trace
- `P0` Public status output via `/shopstatus`
- `P0` TOS agreement panel (`/deploy tos`) with persistent `I Have Read & Agree to the TOS` button
- `P0` Role assignment on TOS agreement and agreement logging
- `P1` Start-here channel permission automation on shop open/close
- `P2` Persistent panel pointer tracking (`persist_panels` for `shop_status` and `tos`)

---

## Feature 4: Ticket Panels and Intake Flow (`P1`)

Purpose: convert buyers into structured ticket records.

Subfeatures by priority:

- `P1` `/ticketpanel` post/update configurable panel embed in selected channel
- `P1` `/ticketbutton add/remove/list` with max 5 ticket types per guild
- `P1` One-open-ticket rule per user for commission tickets
- `P1` Shop-open and TOS-role gate checks before ticket creation
- `P1` Modal-based intake with configurable forms (`/ticketform set/reset/preview`)
- `P1` Configurable commission-type options (`/ticketform setoptions/resetoptions`)
- `P1` Channel creation under configured category with user+staff overwrites
- `P1` Optional ticket-type age gate (`/ticketbutton agegate`) using age-verified role
- `P2` Dynamic panel refresh when button definitions change
- `P2` Staff shortcuts embed auto-posted in each new ticket

---

## Feature 5: Quotes and Price Matrix (`P1`)

Purpose: standardized quoting with transparent fee logic.

Subfeatures by priority:

- `P1` `/quote calculator` step-by-step quote wizard (type, tier, characters, background, rush, currency, payment method)
- `P1` Shared compute path for calculator and ticket auto-quote (`compute_quote_totals`)
- `P1` `/setprice` for base matrix control per commission type and rendering tier
- `P1` `/quoteextras` for character/background add-ons and brand name
- `P1` `/setdiscount` role-based discounts (Boostie/Reseller)
- `P1` `/pricelist` public base pricing view
- `P1` `/quote recalculate` for in-ticket quote refresh with snapshot updates
- `P2` Payment settlement breakdown (artist amount, processor fee, total to send)
- `P2` Downpayment policy from threshold logic (PHP/USD)
- `P2` Optional FX lines via `/setcurrency`

---

## Feature 6: Payment Panel and Payment Confirmation (`P1`)

Purpose: make payment instructions actionable and link payment to order pipeline.

Subfeatures by priority:

- `P1` `/deploy payment` posts payment method panel with persistent buttons
- `P1` Button handlers for GCash, PayPal, Ko-fi with ephemeral detail embeds
- `P1` Strict deploy validation that all payment config fields exist
- `P1` Graceful missing-config hints per payment button
- `P1` `/payment confirm` inside ticket to mark payment and/or register order
- `P2` Ticket payment embed with total due, processor-fee context, and payment hints

---

## Feature 7: Queue and Order Lifecycle (`P1`)

Purpose: move paid commissions through clear production statuses.

Subfeatures by priority:

- `P1` `/queue` command to register orders manually from ticket channel
- `P1` Shared registration pipeline (`register_order_in_ticket_channel`) for `/queue` and `/payment confirm`
- `P1` Order ID generation with monthly sequence and custom prefix (`/setorderprefix`)
- `P1` Queue card creation and persistent queue message updates
- `P1` In-ticket status dropdown (`OrderStatusView`) for Processing/Completed transitions
- `P1` Ticket channel recategorization and renaming across Noted -> Processing -> Done
- `P1` Template-driven messaging for queue and status updates
- `P2` Template management suite (`/settemplate`, `/viewtemplate`, `/listtemplates`, `/resettemplates`)
- `P2` Startup re-registration of status dropdown views

---

## Feature 8: Ticket Progress, References, and Closure (`P1`)

Purpose: track execution details and close tickets cleanly with records.

Subfeatures by priority:

- `P1` `/stage` WIP status updates in-ticket
- `P1` `/revision log` with free-then-paid revision fee logic
- `P1` `/references add` and `/references view` URL tracking
- `P1` `/close` and close button for staff or ticket owner
- `P1` HTML transcript generation and transcript channel posting
- `P1` Ticket owner DM attempt on close
- `P1` Countdown + channel deletion finalize flow
- `P2` Warn-appeal ticket compatibility with same close/transcript pipeline

---

## Feature 9: Loyalty and Completion Nudge (`P2`)

Purpose: reward repeat buyers and close loop after fulfillment.

Subfeatures by priority:

- `P2` Loyalty counter increment when order moves to Completed
- `P2` `/loyalty` progress display with next milestone context
- `P2` `/loyaltytop` leaderboard
- `P2` Completion DM nudge flow (from queue completion path)
- `P3` Milestone-based reward messaging (hard-coded milestone map)
- `P1` Loyalty stamp card issuance on ticket close (`LC-XXX` auto ID + thread post)
- `P1` Vouch-driven stamp-state image progression for active cards
- `P1` Configurable loyalty card channel with optional auto-create behavior
- `P1` Configurable void timer (first-vouch deadline) and auto-void cleanup loop
- `P1` Card cleanup on member leave and manual remove/abandon commands

---

## Feature 10: Warning System and Appeals (`P2`)

Purpose: moderation with audit visibility and appeal path.

Subfeatures by priority:

- `P2` `/warn` command with stored reason and moderator
- `P2` Dual DM flow to warned member (notice + appeal prompt)
- `P2` Warn audit embed in configured warn-log channel
- `P2` Public warn line in source channel (with dedupe behavior when source is warn-log)
- `P2` Warn threshold auto-ban support (`/setwarnthreshold`)
- `P2` `/warns` review and `/clearwarn` action flow
- `P2` `/clearallwarns` bulk cleanup path
- `P2` Custom reason preset management (`/warnreason list/add/remove/reset`)
- `P2` Warn-appeal ticket creation from DM button (`warn_appeal` ticket type)

---

## Feature 11: Vouch System (`P2`)

Purpose: collect social proof and clear vouch-request role friction.

Subfeatures by priority:

- `P2` Auto-vouch listener in configured vouch channel
- `P2` Automatic `PLEASE_VOUCH_ROLE` removal on successful vouch message
- `P2` Staff `/vouch` command with optional order ID linkage
- `P2` `/vouches` paged history lookup per member
- `P3` Vouch embed posting in dedicated channel for staff-logged entries

---

## Feature 12: Sticky Messages (`P3`)

Purpose: keep critical channel instructions always visible at bottom.

Subfeatures by priority:

- `P3` `/sticky` create sticky embed per channel
- `P3` Repost engine on user messages (delete previous sticky then repost)
- `P3` Per-channel lock to avoid sticky race conditions
- `P3` `/stickyupdate`, `/unsticky`, `/stickypreview`, `/stickies`
- `P3` Startup sticky cache refresh for resilience

---

## Feature 13: Drops and Delivery (`P3`)

Purpose: structured delivery message and delivery history.

Subfeatures by priority:

- `P3` `/drop` sends delivery DM with link button and logs record
- `P3` `/drophistory` review for staff
- `P3` Ticket notification when drop sent for linked order
- `P3` Fallback completion DM without manual link (auto path on order completion)

---

## Feature 14: Owner-only DM Maintenance (`P4`)

Purpose: recover from bot DM clutter and support cleanup operations.

Subfeatures by priority:

- `P4` `/purge_bot_dms` server-owner-only cleanup command
- `P4` Large DM history scanning with cap and progress-safe looping
- `P4` Summary metrics (scanned/deleted/skipped) in ephemeral result
- `P4` Error-safe handling for blocked DM/history access

---

## Feature 15: Data Layer and Persistence (`P0`)

Purpose: durable storage for every production flow.

Subfeatures by priority:

- `P0` SQLite schema for tickets, orders, warns, vouches, loyalty, drops, templates, panel persistence, guild settings
- `P0` Quote tables (`quote_guild_settings`, `quote_base_price`, `quote_role_discount`, `quote_currency`)
- `P0` Guild-scoped integer/string setting helpers
- `P0` Startup migrations for ticket/button schema evolution
- `P1` Reset helpers for targeted cleanup (`clear_quote_data_for_guild`, grouped config resets)
- `P1` Operational state tables (`guild_flags`, `wizard_sessions`, `persist_panels`)

---

## Feature 16: Builder Systems (`P1`)

Purpose: reduce slash parameter friction with interactive editing flows.

Subfeatures by priority:

- `P1` `/embed` interactive builder (`create`, `edit`, `list`, `showlist`, `show`)
- `P1` `/embed importfile` (`.md` / `.json`) for fast embed seeding and updates
- `P1` `/button` interactive builder (`create`, `edit`, `clone`, `list`, `post`)
- `P1` `/ar` interactive builder (`create`, `edit`, `delete`, `list`, `pause`, `resume`)
- `P1` `/ar` expanded ops (`showlist`, `search`, `stats`, `export`, `import`, `setembed`)
- `P1` ID-based objects with auto-increment IDs (`EMB-XXX`, `BTN-XXX`, `AR-XXX`)
- `P1` Runtime execution for active autoresponders (message trigger + match modes + cooldown/conditions)
- `P1` Runtime event triggers for autoresponders (member join/leave and role-assigned)
- `P2` ID autocomplete pickers in edit/post/delete-style commands
- `P2` Conditions editor UX (dropdown role/channel selectors instead of manual IDs)
- `P2` Auto-dismiss short ephemeral confirmation toasts (10s) for builder micro-updates

---

## Suggested Build Order (Simple)

- `Phase 1` (`P0`): Core runtime, DB, setup/config, shop+TOS gate
- `Phase 2` (`P1`): Tickets, quotes, payments, queue, close/transcripts
- `Phase 3` (`P2`): Loyalty, warnings/appeals, vouches
- `Phase 4` (`P3`): Stickies, drops, polish
- `Phase 5` (`P4`): owner-only utilities

