# Embed Builder — Feature Specification Index

> A modal-based embed creation and management system, restricted to staff, admins, and server owners.

---

## Feature Files (Sorted by Priority)

| # | File | Feature | Why This Priority |
|---|------|---------|-------------------|
| 1 | `01_access_control.md` | Access Control | Must be the first gate — nothing else should work without this |
| 2 | `02_embed_creation.md` | Embed Creation (`/embed create`) | The root command; all other features depend on embeds existing |
| 3 | `03_embed_editing.md` | Embed Editing + Live Preview | Core of the builder experience; modals + real-time feedback |
| 4 | `04_dynamic_variables.md` | Dynamic Variables | Powers personalization in all embed content fields |
| 5 | `05_newline_handling.md` | Newline Handling (+ Recommendation) | UX fix that affects all text input; resolved at the editing layer |
| 6 | `06_embed_list.md` | `/embed list` | Lightweight utility; lists IDs + creators |
| 7 | `07_embed_showlist.md` | `/embed showlist` | Enhanced paginated viewer with embed previews |

---

## System-Wide Rules (Apply to All Features)

- All commands in this system are **staff/admin/owner only** — see `01_access_control.md`
- Embed names are **auto-assigned** in format `EMB-001`, `EMB-002`, etc. — no manual naming
- Embeds are **server-scoped** — each server has its own isolated embed pool
- Dynamic variables (e.g. `{user_name}`) are **resolved at send/show time**, not at creation time
- All interactive modals follow Discord's native modal API (max 5 fields per modal, 4000 char limit per field)

---

## Recommended Reading Order

If you're implementing this from scratch:

```
01 → 02 → 03 → 04 → 05 → 06 → 07
```

Each file references others where features overlap.
