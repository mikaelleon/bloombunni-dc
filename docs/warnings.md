# Warnings (`cogs/warn.py`)

## Reason presets (`/warn`)

- **`reason`** supports **autocomplete**: built-in defaults plus **custom presets** stored per guild (`WARN_REASON_TEMPLATES_JSON`).
- **Defaults** (always available): Chargeback attempt, Harassment, TOS violation, Spam / scam, Disrespectful behavior, Other (see notes).
- Staff can still **type any custom reason** in the field (not limited to the list).
- **`/warnreason`** (staff) — manage extra presets:
  - **`list`** — custom lines only (defaults are implied).
  - **`add`** — append one string (max **100** chars; max **20** custom lines per server).
  - **`remove`** — delete by **exact** text match.
  - **`reset`** — clear all custom lines (defaults remain).

`/config view` shows **Custom warn reason presets — N**. **`/config reset` → Channels & roles** also clears custom warn presets.

## `/warn` flow (staff)

1. **`add_warn`** with normalized reason (empty → `no reason specified`).
2. **Two DMs** to the target (if DMs open):
   - **`⚠️ WARNED NOTICE !`** — original style (`DEFAULT_EMBED_COLOR`).
   - **Appeal** embed (`HINT_BLUE`) + button **Open warn appeal ticket** (`WarnAppealDMView`).
3. **Staff audit log** — if **`WARN_LOG_CHANNEL`** is set, a **dedicated embed** is posted there (`📋 Warn — staff log`): member, moderator, reason text, warn ID, total vs threshold, **Issued in** (source channel). This is the **private** record; it is **not** the same embed as the old `info_embed("Warn issued", …)` line-only format.
4. **Public channel** — short plain text in the channel where `/warn` was run:  
   `⚠️ @user now has N warning(s).` + `**reason**: …`  
   If that channel **is** the warn log channel, the **public** duplicate is skipped (only the audit embed is sent there) so staff are not spammed twice.
5. Ephemeral **`success_embed("Warn logged", …)`** — reminds staff to set a warn log if missing.
6. If **`total >= threshold`**: **ban** (`Warn threshold reached`), optional auto-ban line in the log channel.

Threshold: **`WARN_THRESHOLD_KEY`**, default **3**, range **1–100** via **`/setwarnthreshold`**.

## Warn appeal tickets (nice-to-have)

- After a warn, the member can press **Open warn appeal ticket** in the DM (while still in the server).
- Creates a **private text channel** under the normal **ticket category** (`TICKET_CATEGORY`), visible to the member + **staff role** + bot.
- Stored as a **`tickets`** row with `button_id = warn_appeal`, `ticket_status = warn_appeal`, answers include **Warn ID** and **Original reason**.
- **Commission** ticket deduping (`get_open_ticket_by_user`) **ignores** warn-appeal rows, so a warn appeal does not block opening a normal ticket.
- Staff can run **`/clearwarn`** **without** `warn_id` inside that channel — the warn ID is read from the ticket answers.
- **`/close`** uses the normal ticket close + transcript flow.

**Note:** The appeal button is attached to the DM message; if the bot restarts before the user clicks, they may need to ask staff for help (no persistent global handler for arbitrary `custom_id` instances).

## `/warns` (staff)

Pager **`WarnPages`** — one embed per warn.

## `/clearwarn` (staff)

- **`warn_id`** optional when used in a **warn appeal** ticket channel (parsed from ticket answers).
- Otherwise **`warn_id`** is required.

## `/setwarnthreshold` / `/clearallwarns`

Unchanged — see earlier docs.

## Data

- Table **`warns`**: `warn_id`, `user_id`, `moderator_id`, `reason`, `created_at`.
- **`guild_string_settings`**: `warn_reason_templates_json` — JSON array of custom reason strings.

## Related

- [config.md](config.md) — warn log channel mapping.
- [tickets-and-panels.md](tickets-and-panels.md) — shared ticket category / close behavior.
