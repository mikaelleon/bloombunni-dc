# Vouches and reviews (`cogs/vouch.py`)

## Automatic vouch (`on_message` listener)

When a message is sent in the configured **`VOUCHES_CHANNEL`**:

- Author must have the **`PLEASE_VOUCH_ROLE`** role.
- Role is **removed** (`reason="Vouched"`).
- Row inserted: **`insert_vouch(user_id, None, message[:2000])`** (no order id).
- If user has active loyalty stamp card, card stamp/image is advanced by runtime hook (`apply_vouch_to_loyalty_card`).
- Public reply (not embed):  
  **`✅ Thanks for vouching, {mention}! Your PlsVouch role has been removed.`**

Bots and DMs are ignored.

## Client `/vouch` (ticket channel only)

- Requires **`PLEASE_VOUCH_ROLE`**.
- Must run in a **text channel** that has an **open ticket** record and where **`client_id`** is the invoker.
- **Order ID resolution:**
  - If an **`orders`** row exists for **`ticket_channel_id`** + this client → use that **`order_id`** (“registered order”).
  - Else → use **current channel name** as fallback tag (e.g. slug `cs-fb-user-001`) (“ticket-name fallback”).
- Inserts **`insert_vouch(client_id, order_id, message)`**.
- Posts embed to **`VOUCHES_CHANNEL`** with owner mention, optional **`staff`** mention, optional **`proof`** image.
- May add **`FEEDBACK_PENDING_ROLE`**; DMs short **`/review`** instructions.
- Loyalty hook: **`apply_vouch_to_loyalty_card`** when configured.

Ephemeral success includes which **order_id** and source were used.

## Staff `/vouchstaff`

Parameters: **`member`**, **`order_id`** (autocomplete), **`message`**.

- Staff-only (`@is_staff`).
- Inserts vouch with order id; same PlsVouch strip / vouches-channel embed behavior as legacy staff path.
- Loyalty hook as above.

## Client `/review`

- Typically requires **`FEEDBACK_PENDING_ROLE`** when that slot is configured.
- **`order_id`** autocomplete merges:
  - Reviewable **registered orders** (same logic as queue pipeline), and
  - **Fallback tags** from **`vouches.order_id`** for that client, excluding rows already in **`commission_reviews`**.
- **`review_cmd`** accepts the order if either:
  - **`get_order(order_id)`** shows **`client_id`** = invoker, or
  - **`has_vouch_for_order(client_id, order_id)`** (fallback tag from prior **`/vouch`**).
- Multi-step UI: numeric ratings (1–5) → modal (two text fields) → dropdowns → **`insert_commission_review`**; embed to **`FEEDBACK_CHANNEL`**; optional **`REVIEW_REWARD_ROLE`**; discount code DM.

## `/vouches`

Lists **`list_vouches_for_user`** — paged embeds (5 per page) with **`VouchPages`**.

Empty: **`info_embed("Vouches", "No vouches found.")`**

## Data

- Table **`vouches`**: `vouch_id`, `client_id`, `order_id`, `message`, `created_at`.
- Table **`commission_reviews`**: stores **`/review`** submissions (see **`database.py`** migration for columns).
