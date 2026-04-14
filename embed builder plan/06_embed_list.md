# Feature 06 — `/embed list`

**Priority:** 🟡 Medium (Lightweight utility; needed for management but low complexity)

> Displays a compact, text-based list of all embeds on the server — showing embed IDs and who created each one. No previews. Fast and functional.

---

## Command

```
/embed list
```

No parameters.

---

## Subfeatures (Sorted by Priority)

---

### 6.1 — Core List Display *(Highest)*

**What it does:** Queries the server's embed pool and returns a formatted list of all embed records.

**Output format (ephemeral embed):**

```
📋 Server Embeds — 4 total

EMB-001  ·  Created by @iara  ·  Jan 15, 2024
EMB-002  ·  Created by @kim   ·  Jan 16, 2024
EMB-003  ·  Created by @iara  ·  Feb 2, 2024
EMB-004  ·  Created by @kim   ·  Apr 14, 2026

Use /embed showlist to browse with previews.
```

**Fields shown per embed:**
- Embed ID (`EMB-XXX`)
- Creator display name (resolved from stored user ID — prefixed with `@`)
- Creation date (formatted as `MMM D, YYYY`)

**Response is ephemeral** — only the command invoker sees it.

---

### 6.2 — Creator Name Resolution *(High)*

**What it does:** The stored creator is a Discord user ID. At list-display time, the bot resolves this ID to the user's current display name.

**Handling edge cases:**
- If the creator has **left the server**: display `Unknown User` instead of the ID
- If the creator's **account was deleted**: display `Deleted User`
- Never display raw user IDs in the output — always attempt a name lookup first

---

### 6.3 — Empty State Handling *(High)*

**What it does:** If the server has no embeds yet, return a helpful empty state instead of a blank message.

**Empty state message:**
```
📋 Server Embeds — 0 total

No embeds have been created yet.
Run /embed create to get started.
```

---

### 6.4 — Sorting *(Medium)*

**What it does:** List is sorted by embed ID in **ascending order** (EMB-001 first, newest last) by default.

**Why ascending?** Older embeds are often the "important" ones (rules embed, welcome embed) — they deserve to be at the top where they're easiest to find.

**Future consideration (not in v1):** A `sort:` parameter to sort by creation date, creator, etc. Keep the architecture flexible.

---

### 6.5 — Inline Edit Shortcut *(Low)*

**What it does:** Below the embed list, include a reminder line that users can jump directly to editing any embed by ID.

**Text:**
```
To edit an embed: /embed edit id:EMB-XXX
To view with previews: /embed showlist
```

This is purely informational — no buttons needed in this command. `/embed showlist` is the richer interface.

---

## Output Limits

| Scenario | Handling |
|----------|---------|
| Server has 1–20 embeds | Full list shown in one message |
| Server has 21–50 embeds | List is split across multiple embed fields (Discord embeds support up to 25 fields) |
| Server has 50+ embeds | Show first 50, with a note: *"Showing 50 of 73. Use `/embed showlist` to paginate through all."* |

**Note:** If you're imposing a server embed limit (e.g. 50 or 100), the 50+ case may never occur. Design for it anyway in case limits change.

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|------------------|
| Embed was created but creator's account deleted | Show `Deleted User` |
| Two embeds have the same creation date | Sort by ID as tiebreaker |
| Command run in DMs | Reject with: *"This command can only be used in a server."* |

---

## Dependencies

- `01_access_control.md` — Permission check
- `02_embed_creation.md` — Embeds must exist to be listed

## Referenced By

- `07_embed_showlist.md` — Acts as the richer alternative to this command; both coexist
