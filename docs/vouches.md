# Vouches (`cogs/vouch.py`)

## Automatic vouch (`on_message` listener)

When a message is sent in the configured **`VOUCHES_CHANNEL`**:

- Author must have the **`PLEASE_VOUCH_ROLE`** role.
- Role is **removed** (`reason="Vouched"`).
- Row inserted: **`insert_vouch(user_id, None, message[:2000])`** (no order id).
- If user has active loyalty stamp card, card stamp/image is advanced by runtime hook (`apply_vouch_to_loyalty_card`).
- Public reply (not embed):  
  **`✅ Thanks for vouching, {mention}! Your PlsVouch role has been removed.`**

Bots and DMs are ignored.

## `/vouch` (staff)

Parameters: **`member`**, **`order_id`**, **`message`**.

- Inserts vouch with order id.
- If member has active loyalty stamp card, card stamp/image is advanced by runtime hook.
- Tries to **remove** PlsVouch from member; if not present, odd path tries add+remove (to clear role state).
- If **`VOUCHES_CHANNEL`** is set, posts embed:

**Embed**

- Title: **`⭐ Vouch`**
- Description: `**{display_name}**\n{message}\nOrder: `{order_id}``
- Color: **`PRIMARY`**

- Ephemeral **`success_embed("Logged", "Vouch posted.")`**

## `/vouches`

Lists **`list_vouches_for_user`** — paged embeds (5 per page) with **`VouchPages`**:

- Title: **`Vouches for {display_name}`**
- Description lines: **`#{vouch_id}`** — timestamp — message excerpt.

Empty: **`info_embed("Vouches", "No vouches found.")`**

## Data

Table **`vouches`**: `vouch_id`, `client_id`, `order_id`, `message`, `created_at`.
