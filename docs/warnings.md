# Warnings (`cogs/warn.py`)

## `/warn` (staff)

1. **`add_warn`** with reason (default **`no reason specified`**).
2. **DM** to target: embed **`⚠️ WARNED NOTICE !`** (`_warn_notice_embed`) — plain prose with shop name, reason, **threshold**, current **total** count (`DEFAULT_EMBED_COLOR`).
3. **Public channel** (same channel as command): plain text  
   **`⚠️ {mention} now has {total} warning(s).`**  
   **`**reason**: {reason}`**
4. **`WARN_LOG_CHANNEL`**: **`info_embed("Warn issued", "{mention} — `{reason}` (ID `{wid}`) by {mod}")`**
5. Ephemeral **`success_embed("Warn logged", …)`**
6. If **`total >= threshold`**: **`ban`** user (`delete_message_days=0`), log **`warning_embed("Auto-ban", …)`** if warn log exists.

Threshold from **`WARN_THRESHOLD_KEY`** guild setting, clamped **1–100**, default **3** (`WARN_THRESHOLD_DEFAULT`).

## `/warns` (staff)

Pager **`WarnPages`** — one embed per warn: title **`Warn #{id}`**, body reason / mod / timestamp. Single page skips pager.

## `/clearwarn` (staff)

**`delete_warn(id)`** — **`success_embed("Cleared", …)`** or hint if missing.

## `/setwarnthreshold` (staff)

**`set_guild_setting(WARN_THRESHOLD_KEY)`** — **`success_embed("Saved", …)`** (range **1–100** via slash `Range`).

## `/clearallwarns` (staff)

**`clear_warns_user`** — reports count removed.

## Data

Table **`warns`**: auto-increment id, `user_id`, `moderator_id`, `reason`, `created_at`.
