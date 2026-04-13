# Stickies (`cogs/sticky.py`)

Stickies keep a **single embed** pinned to the **bottom** of a channel by **deleting and reposting** after normal user messages (not bots).

## Behavior

- **`on_message`**: if channel id ∈ **`sticky_channels`** cache and a DB row exists, waits **1.5s** under a per-channel **asyncio.Lock**, deletes **`last_message_id`** if possible, sends new embed, updates **`last_message_id`**.

## Commands (staff)

| Command | Purpose |
|---------|---------|
| **`/sticky`** | Set sticky on a **TextChannel**: title, description, optional hex **color** (default `#242429`), **image_url**, **footer**, **thumbnail_url**. Validates image URLs start with **`http`**. Stores in **`sticky_messages`**, refreshes cache. |
| **`/stickyupdate`** | Patch fields on existing sticky. |
| **`/unsticky`** | Remove sticky for channel. |
| **`/stickies`** | Pager listing channels with stickies. |
| **`/stickypreview`** | Preview embed from DB row. |

## Embed builder

**`embed_from_sticky_row`**: title, description, color from hex (fallback **`DEFAULT_STICKY_COLOR`**), optional footer, **`set_image`**, **`set_thumbnail`**.

## Startup

**`on_ready`** in **`main.py`** calls **`refresh_sticky_cache`** to repopulate **`sticky_channels`**.

**`cog_load`** also refreshes cache.
