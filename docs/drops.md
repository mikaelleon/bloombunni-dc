# Drops (`cogs/drop.py`)

## `/drop` (staff)

Parameters: **`member`**, **`link`** (delivery URL), optional **`order_id`**.

1. Builds **`delivery_ready_embed`**:  
   - Title: **`📦 Your Order is Ready!`**  
   - Body: completion text + vouch channel mention (`<#id>` or `#vouches` fallback).  
   - Color: **`PRIMARY`**
2. DM includes **`DropLinkView`**: link button **Open link** → `link` URL.
3. **`insert_drop(order_id, member_id, link)`**
4. Ephemeral **`success_embed("Sent", …)`**
5. If **`order_id`** matches an order with **`ticket_channel_id`**, posts **`info_embed("Drop sent", "Delivery DM sent to {mention}.")`** in that ticket.

**Failure:** DMs blocked → **`user_warn("DM blocked", …)`**

## `/drophistory` (staff)

**`list_drops_for_user`** — up to **25** lines: `` `{sent_at}` — {link} `` in **`info_embed`**.

## Completion DM (no `/drop`)

**`send_completion_delivery_dm`** — when an order is marked **completed** in the queue cog, sends the **same embed text** as above but **without** a link button (optional nudge to vouch). Used for buyers who did not receive a manual `/drop`.

## Data

Table **`drops`**: `drop_id`, `order_id`, `client_id`, `link`, `sent_at`.
