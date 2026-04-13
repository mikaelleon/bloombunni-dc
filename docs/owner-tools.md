# Owner tools (`cogs/owner_tools.py`)

## `/purge_bot_dms`

**Who:** **`@is_guild_owner()`** — **server owner** only (not the same as “bot owner” in `.env` unless that user owns the guild).

**Parameters:** **`user`** — a **Member** in the current server (target of DM cleanup).

**Behavior:**

1. Defer ephemeral.
2. Rejects if **`user`** is a bot.
3. Opens DM channel with **`user.create_dm()`**.
4. Iterates DM **`history`** newest-first, up to **`_MAX_MESSAGES_SCAN` (15_000)** messages.
5. Deletes messages whose **`author`** is the bot; small delay every 5 deletes for rate limits.
6. Ephemeral **`success_embed("DM purge finished", …)`** with scanned/deleted/skipped counts; if scan hit cap, suggests running again.

**Errors:** cannot open DM, cannot read history, etc. → **`user_warn`** with explanation.

**Logging:** INFO line with guild id, owner id, target id, deleted/failed/scanned counts.
