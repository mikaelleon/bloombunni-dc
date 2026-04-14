# Feature 02 — Embed Creation (`/embed create`)

**Priority:** 🔴 High (Root command — all other features depend on embeds existing)

> The entry point for the entire embed system. Creates a new, blank embed record with an auto-assigned ID and opens the interactive builder.

---

## Command

```
/embed create
```

No parameters. The embed name/ID is **automatically assigned** — the user does not pick it.

---

## Subfeatures (Sorted by Priority)

---

### 2.1 — Auto-Incremented Embed ID Assignment *(Highest)*

**What it does:** When `/embed create` is run, the bot queries the server's embed pool and assigns the next available ID in the sequence.

**Format:** `EMB-001`, `EMB-002`, `EMB-003` ... `EMB-999`

**Rules:**
- IDs are **per-server** — two different servers can both have `EMB-001` with no conflict
- IDs are **never reused** — if `EMB-003` is deleted, the next new embed becomes `EMB-004`, not `EMB-003`
- IDs are **zero-padded** to 3 digits (e.g. `EMB-007`, not `EMB-7`)
- If a server somehow exceeds 999 embeds in lifetime count, extend to 4 digits (`EMB-1000`) without breaking anything

**Implementation note:** Store a `last_assigned_id` counter per server in the database. Increment it on every create, regardless of deletions.

---

### 2.2 — Creation Confirmation + Builder Launch *(Highest)*

**What it does:** Immediately after ID assignment, the bot sends an ephemeral confirmation message to the creator. This message also serves as the **embed builder interface** — it contains labeled buttons for each editable field.

**Confirmation message content:**
- The assigned embed ID (e.g. `Embed EMB-004 created!`)
- A row of action buttons (see below)

**Builder Buttons:**

| Button Label | Opens Modal For |
|---|---|
| ✏️ Author | Author text + icon URL |
| 🔤 Title | Title text |
| 📝 Description | Description body |
| 🖼️ Image | Large image URL |
| 📌 Thumbnail | Small corner image URL |
| 🎨 Color | Hex color code |
| 📋 Footer | Footer text + icon URL |
| ⏱️ Timestamp | Toggle yes/no |

Each button triggers a **Discord modal** (interactive text form) for that specific field. See `03_embed_editing.md` for modal specs.

**Additionally, these control buttons are always present:**
- 👁️ **Preview** — Shows the current embed state (see `03_embed_editing.md` §3.3)
- ✅ **Done** — Closes the builder session and saves the embed as finalized
- 🗑️ **Discard** — Deletes the embed record entirely (with a confirmation prompt)

---

### 2.3 — Blank Embed Defaults *(High)*

**What it does:** A freshly created embed starts with sensible, visible defaults so the preview doesn't look completely empty.

**Default values on creation:**

| Field | Default Value |
|---|---|
| Title | *(empty — no title shown)* |
| Description | *(empty)* |
| Color | `#5865F2` (Discord blurple) |
| All other fields | *(empty / not set)* |

**Why a default color?** An embed with no color has no left-border accent, which looks unintentional. Starting with blurple signals the embed exists and is editable.

---

### 2.4 — Creator Attribution *(Medium)*

**What it does:** Stores the Discord user ID of whoever ran `/embed create` alongside the embed record.

**Used by:**
- `/embed list` to display "Created by @Username" (see `06_embed_list.md`)
- Audit log (see `01_access_control.md` §1.4)

**Not exposed in the embed itself** — this is metadata only. The creator's name will never appear in the posted embed unless they manually add it to the Author field.

---

### 2.5 — Builder Session Timeout *(Medium)*

**What it does:** If the builder confirmation message (with buttons) goes unused for **15 minutes**, the session is considered abandoned.

**On timeout:**
- Buttons are **disabled** (grayed out)
- A follow-up ephemeral message states: *"Builder session expired. The embed EMB-XXX was saved with its current state. Use `/embed edit` to continue editing."*
- The embed record is **kept** (not deleted) — whatever was filled in is preserved

**Why keep it instead of deleting?** The user may have filled in several fields before stepping away. Discarding their work on timeout is more frustrating than letting them resume with `/embed edit`.

---

## Data Model (Per Embed Record)

```
embed_id        : "EMB-004"           (string, server-scoped unique)
server_id       : "1234567890"        (Discord guild ID)
created_by      : "9876543210"        (Discord user ID)
created_at      : 2024-01-15T10:30Z  (ISO timestamp)
last_edited_at  : 2024-01-15T10:45Z  (ISO timestamp)
status          : "draft" | "active" (draft = still in builder, active = finalized)

fields:
  author_text   : string | null
  author_icon   : url | null
  title         : string | null
  description   : string | null
  footer_text   : string | null
  footer_icon   : url | null
  thumbnail_url : url | null
  image_url     : url | null
  color         : hex string         (default: "#5865F2")
  timestamp     : boolean            (default: false)
```

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|------------------|
| User runs `/embed create` twice quickly | Two separate embed records created with sequential IDs — no deduplication |
| Server is at their embed limit (if you impose one) | Bot rejects creation with a clear message stating the limit and current count |
| Database write fails during creation | Bot responds with a generic error; no ID is assigned; user can retry |

---

## Dependencies

- `01_access_control.md` — Permission check runs before anything else

## Referenced By

- `03_embed_editing.md` — Editing opens from the builder launched here
- `06_embed_list.md` — Lists embeds created by this command
- `07_embed_showlist.md` — Previews embeds created by this command
