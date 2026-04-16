# Queue, templates, and loyalty (`cogs/queue.py`)

Orders are **`orders`** table rows keyed by **`order_id`** (`PREFIX-MMYY-####`). The **queue channel** holds one **embed per order** (message edited as status changes). Staff update status via a **persistent Select** on the **ticket** channel (`OrderStatusView`).

## Registering orders

### Path A — `/payment confirm` (typical)

See [tickets-and-panels.md](tickets-and-panels.md). Calls **`register_order_in_ticket_channel`**.

### Path B — `/queue` (staff)

Explicit registration: **`handler`**, **`buyer`**, **`amount`**, **`item`**, **`mop`**, **`price`**, **`channel`** (ticket text channel). Same **`register_order_in_ticket_channel`** pipeline.

### `register_order_in_ticket_channel` (logic)

1. Validates ticket channel is under a **configured ticket category** (`ticket_category_ids`).
2. Builds **`order_id`** = `{prefix}-MMYY-{monthly_seq}`; prefix from **`ORDER_ID_PREFIX`** or **MIKA**.
3. **`insert_order`**, **`update_ticket_order`**, renames channel toward **`noted_{slug}.{order_number}`** under **Noted** category if possible.
4. Posts placeholder message in **queue channel**, stores **`queue_message_id`**, then **edits** to full **`queue_embed`** body from **`build_queue_entry_text`**.
5. Sends **noted** title/description templates to the ticket + **OrderStatusView** (staff-only header text: `ςωϑ — staff only | do not touch .!`).
6. **`bot.add_view`** for the dropdown.

**Queue card body** is assembled from **`templates.json`** / DB overrides: keys like `noted_queue_header`, `noted_queue_channel`, `noted_queue_buyer`, `noted_queue_item`, `noted_queue_price`, `noted_queue_handler`, `noted_queue_status`, `processing_label`, `completed_label`, etc. Placeholders include `{buyer}`, `{handler}`, `{item}`, `{queue_link}`, `{vouches_channel}`, `{channel_name}`, etc.

**Embed:** `queue_embed(order, body)` → **`discord.Embed(description=body, color=PRIMARY)`** (no title).

### Order status dropdown

- **`custom_id`** pattern: `ordst|{order_id}|{queue_message_id}` (truncated to 100 chars).
- Only **staff role** may use it.
- **Processing:** updates DB, rewrites queue embed, renames ticket toward **`processing_{slug}.{n}`**, sends **`processing_message`** template in ticket.
- **Completed:** marks **Done**, rewrites queue embed, moves channel to **Done** category (`done_{slug}.{n}`), sends **`completed_message`**, adds **Please vouch** role, **`increment_loyalty`**, optional **milestone DM** (`LOYALTY_MILESTONES`: 5 / 10 / 20 orders), then **`send_completion_delivery_dm`** from **drop** cog.
- **Ticket close follow-up:** separate close pipeline now can issue loyalty stamp card posts/threads in configured loyalty card channel (`cogs/loyalty_cards.py`).

## Template commands

| Command | Purpose |
|---------|---------|
| **`/settemplate`** | Upserts **`message_templates`** for a key in `TEMPLATE_KEYS` (from `templates.json` keys). Shows **dummy preview**. |
| **`/viewtemplate`** | Shows raw content + preview; labels source **database override** vs **templates.json default**. |
| **`/listtemplates`** | Pager (content chunks) listing each key and **custom** vs **default** snippet. |
| **`/resettemplates`** | Confirmation view → **`delete_all_message_templates`**. |

**`resolve_template`** replaces `{name}` placeholders when present in kwargs.

## Loyalty

| Command | Output |
|---------|--------|
| **`/loyalty`** | **`info_embed("Loyalty", …)`** — completed count, next milestone, ASCII progress bar. |
| **`/loyaltytop`** | Top **10** from **`loyalty`** table. |

Milestone rewards are **hard-coded** in `LOYALTY_MILESTONES` (e.g. 5 → “10% discount on next order”).

## Loyalty stamp cards (`/loyalty_card`)

- Trigger source: when ticket is closed, bot can post `LC-XXX` card message with image state `0` and create per-card thread.
- Stamp source: when user completes vouch (`vouches` channel listener or `/vouch`), active card image/message updates to next stamp state.
- Image states are owner/admin configurable (`stamp_index` 0..N).
- Channel behavior: owner/admin can set channel manually, or enable auto-create.
- Void behavior: optional first-vouch timer (`voidhours`); if expired with 0 stamps, card is voided/removed.
- Lifecycle: cards removed on member leave or manual remove/abandon command; LC number recycled for future allocation.

## Other

| Command | Purpose |
|---------|---------|
| **`/setorderprefix`** | Sets **`ORDER_ID_PREFIX`** string (sanitized `[A-Za-z0-9_-]`, max 24). |

## Startup

**`register_order_status_views`** re-attaches **`OrderStatusView`** for orders that still have a **`queue_message_id`** so dropdowns work after restart.
