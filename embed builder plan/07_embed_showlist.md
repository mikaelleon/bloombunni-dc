# Feature 07 — `/embed showlist`

**Priority:** 🟢 Medium-Low (Enhanced UX; builds on all prior features; higher complexity)

> A paginated, interactive browser for all server embeds — showing a live rendered preview of each embed as the user navigates through IDs.

---

## Command

```
/embed showlist
```

No parameters. Opens the paginated embed browser.

---

## Subfeatures (Sorted by Priority)

---

### 7.1 — Paginated Navigation *(Highest)*

**What it does:** Displays one embed at a time with navigation buttons to move between them.

**Navigation buttons:**

```
[ ⏮ First ]  [ ◀ Prev ]  [ EMB-002 / 4 ]  [ Next ▶ ]  [ Last ⏭ ]
```

- **First / Last** — Jumps to the first or last embed in the list
- **Prev / Next** — Moves one embed backward or forward
- **Center label** — Shows current position (e.g. `EMB-002 / 4` = viewing embed 2 of 4 total)
- All buttons are **disabled** when at the boundary (e.g. Prev and First are disabled on the first embed)

**Response is ephemeral** — only the command invoker sees the browser.

**Ordering:** Same ascending ID order as `/embed list` — `EMB-001` first.

---

### 7.2 — Live Embed Preview Per Page *(Highest)*

**What it does:** Each page of the browser displays the **actual rendered embed** for the current ID — not a text summary, but the real embed as it would appear if posted.

**What's shown:**
- The full Discord embed (color bar, author, title, description, image, thumbnail, footer, timestamp) rendered exactly
- Below or above the embed: a small metadata line:
  ```
  EMB-002  ·  Created by @kim  ·  Jan 16, 2024  ·  Last edited Apr 14, 2026
  ```

**Variable handling in previews:**
- Variables (e.g. `{user_name}`) are shown as raw tokens — not resolved
- A small italicized note below the preview: *"Variables shown as-is. They resolve when the embed is triggered."*

**Empty embed handling:**
- If an embed has no fields set at all (e.g. just created, nothing filled in), show a placeholder:
  > *"This embed is empty. Use /embed edit to add content."*
- Still show the color bar if a color is set (since that's meaningful even with no other content)

---

### 7.3 — Action Buttons Per Embed *(High)*

**What it does:** Alongside the navigation buttons, include quick-action buttons for the currently viewed embed.

**Action buttons:**

| Button | Action |
|---|---|
| ✏️ Edit | Runs the equivalent of `/embed edit id:EMB-XXX` — opens the full builder for this embed |
| 📤 Post | Runs the equivalent of `/embed show id:EMB-XXX` — posts this embed to a specified channel |
| 🗑️ Delete | Deletes this embed (with confirmation prompt — see §7.4) |

**"Post" button flow:**
1. User clicks Post
2. Bot sends an ephemeral follow-up: *"Which channel should EMB-002 be posted to?"* with a **channel select menu**
3. User picks a channel
4. Bot posts the embed there and confirms: *"EMB-002 posted to #welcome."*

---

### 7.4 — Delete Confirmation in Browser *(High)*

**What it does:** Clicking the Delete button in the browser triggers a confirmation step before permanently deleting the embed.

**Confirmation message (ephemeral, replaces the browser momentarily):**
```
⚠️ Delete EMB-002?
This cannot be undone. The embed will be permanently removed.

[ Yes, Delete ]  [ Cancel ]
```

**On confirm:**
- Embed is deleted from the database
- Browser automatically advances to the next embed (or previous, if deleting the last one)
- If it was the only embed: browser shows the empty state (§7.6)
- Audit log entry is created (see `01_access_control.md` §1.4)

**On cancel:**
- Browser returns to normal with the embed still intact

---

### 7.5 — Jump to Specific Embed *(Medium)*

**What it does:** Adds a "Go to" button that lets the user jump directly to a specific embed ID without clicking through pages.

**Button label:** `🔍 Go to ID`

**Flow:**
1. User clicks "Go to ID"
2. Bot opens a short modal with one field: *"Enter embed ID (e.g. EMB-007)"*
3. User submits
4. Browser jumps to that embed

**On invalid ID entered:**
- Ephemeral error: *"No embed found with ID EMB-XXX on this server."*
- Browser stays on its current page

---

### 7.6 — Empty State *(Medium)*

**What it does:** If `/embed showlist` is run but the server has no embeds, show a helpful empty state instead of a blank or broken browser.

**Empty state message:**
```
📋 No Embeds Yet

This server doesn't have any embeds.
Run /embed create to make your first one.
```

No navigation buttons are shown in the empty state — there's nothing to navigate.

---

### 7.7 — Browser Session Timeout *(Low)*

**What it does:** If the browser message goes unused for **10 minutes**, all navigation and action buttons are disabled to prevent stale interactions.

**On timeout:**
- Buttons gray out
- Small text added below: *"Session expired. Run /embed showlist again to reopen."*

**Why 10 minutes (shorter than the builder's 15)?** The browser is read-only by default — if a user walks away, there's less risk of unintended state changes. But sessions still need to expire to prevent Discord button interaction errors on old messages.

---

## Layout Reference

```
┌─────────────────────────────────────────────────────┐
│ [Rendered embed preview here — color, fields, etc.] │
└─────────────────────────────────────────────────────┘
  EMB-002  ·  Created by @kim  ·  Jan 16, 2024

  ✏️ Edit    📤 Post    🗑️ Delete    🔍 Go to ID

  ⏮ First   ◀ Prev   [EMB-002 / 4]   Next ▶   Last ⏭
```

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|------------------|
| Only 1 embed exists | All nav buttons disabled (First/Prev/Next/Last are all grayed out). Action buttons still work. |
| User navigates to a deleted embed (race condition with another editor) | Browser detects the missing ID and skips to next available, showing a brief notice |
| Post button used but bot lacks perms in target channel | Ephemeral error specifying the missing permission |
| Two staff members have the same embed browser open simultaneously | Each has their own independent ephemeral session — no conflict |

---

## Dependencies

- `01_access_control.md` — Permission check
- `02_embed_creation.md` — Embeds must exist to browse
- `03_embed_editing.md` — Edit button in browser invokes the editing system
- `04_dynamic_variables.md` — Variable display behavior in previews

## Referenced By

- `06_embed_list.md` — References `/embed showlist` as the richer alternative
