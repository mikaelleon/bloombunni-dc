# Feature 03 — Embed Editing + Live Preview

**Priority:** 🔴 High (Core of the builder UX — where users actually build their embeds)

> Covers the full editing system: modal-based field input, the `/embed edit` command for post-creation edits, and the live preview system.

---

## Commands

```
/embed edit id:[EMB-XXX]          — Opens the full builder interface for an existing embed
/embed edit id:[EMB-XXX] field:[fieldname]  — Opens the modal for a specific field directly
```

---

## Subfeatures (Sorted by Priority)

---

### 3.1 — Modal-Based Field Input *(Highest)*

**What it does:** Every editable embed field uses a **Discord modal** (a native pop-up form). Clicking any edit button opens that field's modal, the user fills it in and hits Submit, and the embed is updated immediately.

**Why modals over slash command parameters?**
- Modals allow **real line breaks** — the user presses Enter and gets an actual new line in their description. No workarounds needed.
- Modals have a **large text area** (up to 4000 characters for long fields), making them much easier to work with than a single-line slash command argument.
- Modals are **native Discord UI** — they feel familiar and don't require the user to learn special syntax.
- For the newline problem specifically: the modal completely eliminates it. See `05_newline_handling.md` for the full recommendation.

**Modal specs per field:**

| Field | Input Type | Max Length | Placeholder Text |
|---|---|---|---|
| Author Text | Short text | 256 chars | `e.g. Server Staff` |
| Author Icon | Short text (URL) | 512 chars | `e.g. https://imgur.com/...` |
| Title | Short text | 256 chars | `e.g. Welcome to the server!` |
| Description | Paragraph (multi-line) | 4000 chars | `Write your embed body here...` |
| Footer Text | Short text | 2048 chars | `e.g. We now have {server_membercount} members` |
| Footer Icon | Short text (URL) | 512 chars | `e.g. https://imgur.com/...` |
| Thumbnail URL | Short text (URL) | 512 chars | `e.g. {server_icon} or direct image URL` |
| Image URL | Short text (URL) | 512 chars | `e.g. https://imgur.com/...` |
| Color | Short text | 7 chars | `e.g. #5865F2` |

**Timestamp** is a toggle button (not a modal) — clicking it flips between enabled/disabled and updates immediately.

**On submit behavior:**
1. Bot validates the input (see §3.2)
2. On pass: embed record is updated in the database
3. Bot updates the live preview (see §3.3) in the same message
4. No separate "saved" confirmation needed — the preview updating IS the confirmation

**On dismiss (user closes modal without submitting):**
- Nothing changes. Embed is untouched.

---

### 3.2 — Input Validation *(Highest)*

**What it does:** Before saving any modal submission, the bot validates the input and rejects invalid values with a clear, specific error.

**Validation rules:**

| Field | Validation |
|---|---|
| Color | Must be a valid hex code (`#RRGGBB` format). Strip leading `#` if user forgets it, then validate. |
| Author Icon / Thumbnail / Image / Footer Icon | Must be a direct image URL ending in `.png`, `.jpg`, `.jpeg`, `.gif`, or `.webp`. Also accept URLs containing Discord CDN (`cdn.discordapp.com`) or Imgur (`i.imgur.com`). |
| Description | No validation beyond length — any text is valid, including `{variables}` |
| Title / Author Text / Footer Text | No validation beyond length |

**On validation failure:**
- Bot sends an **ephemeral error** (does NOT close the builder or lose the user's work)
- Error message names the field and explains the problem:
  > *"Invalid color for the Color field. Please use a hex code like `#FF5733`."*
  > *"Invalid image URL for Thumbnail. Use a direct link ending in `.png`, `.jpg`, or `.gif`."*
- User can try again by clicking the same button

---

### 3.3 — Live Embed Preview *(High)*

**What it does:** The builder interface message (the one with all the buttons) includes a **rendered preview** of the embed-in-progress directly below the buttons. Every time a field is saved, this preview updates automatically — no command needed.

**How it works technically:**
- The builder message is initially sent with an empty/default embed attached
- Each time a field is saved via modal submit, the bot **edits that same message** (using the message ID stored in the session) to update the embed preview with the new values
- The buttons remain in place above the updated preview

**What the preview shows:**
- The actual Discord embed rendered exactly as it will appear when posted — color bar, author, title, description, image, thumbnail, footer, timestamp
- Dynamic variables (e.g. `{user_name}`) are shown as-is in the preview (not resolved), with a small italic note below the preview: *"Variables will be resolved when the embed is triggered."*

**Preview limitations (be transparent about these):**
- If an image URL is provided but the image fails to load (broken link), the preview will show a broken image icon — this is expected behavior and signals to the user the URL is bad
- Variables are not resolved in the preview — they display as raw text (e.g. `{server_membercount}`)

---

### 3.4 — Partial Editing (Field-Specific Edit) *(Medium)*

**What it does:** Allows a staff member to edit a **single specific field** of an existing embed without opening the full builder.

**Command:**
```
/embed edit id:EMB-003 field:description
/embed edit id:EMB-003 field:color
/embed edit id:EMB-003 field:title
```

**Available field names:** `author`, `title`, `description`, `footer`, `thumbnail`, `image`, `color`, `timestamp`

**Behavior:**
- Opens the modal for that specific field immediately
- On submit, saves and updates the embed record
- Responds with an ephemeral confirmation: *"EMB-003 — description updated."*
- Does NOT open the full builder interface (no button panel shown)

**Use case:** Quick fixes. If you just need to change the color of an existing embed, you don't want to re-open the entire builder just for one field.

---

### 3.5 — Clear / Remove a Field *(Medium)*

**What it does:** Allows removal of a field entirely (setting it back to empty/null) rather than just replacing its value.

**How to trigger:**
- In the field's modal, submit with the **text area left blank**
- Bot detects the empty submission and removes that field from the embed

**Behavior:**
- Embed record: field set to `null`
- Preview: field no longer appears in the embed
- Ephemeral confirmation: *"Image removed from EMB-003."*

**Exception:** Color cannot be set to null — if the color modal is submitted blank, the color resets to the default (`#5865F2`) rather than being removed entirely (an embed with no color is technically valid in Discord but looks unpolished).

---

### 3.6 — Edit Session Continuity *(Low)*

**What it does:** Ensures the builder interface message persists and remains interactive across multiple edit rounds without going stale.

**Rules:**
- Only **one builder session per embed** can be active at a time. If a second staff member tries to open the same embed's builder while another session is active, they get an ephemeral warning: *"EMB-003 is currently being edited by @Username. Try again in a moment."*
- A session is considered **closed** when: the Done button is clicked, the session times out (15 min), or the editing user leaves the server
- The Done button dismisses the button panel and sends a final ephemeral confirmation: *"EMB-003 saved and ready to use."*

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|------------------|
| User edits an embed that doesn't exist | Ephemeral error: *"No embed found with ID EMB-XXX on this server."* |
| Image URL is valid format but image is actually broken | Preview shows broken image; bot does not block saving — it's the user's responsibility |
| User submits a 4000-char description | Valid — Discord's embed description limit is 4096. Warn at 4000 to leave buffer. |
| Timestamp toggled but no footer set | Timestamp still shows (Discord renders it independently of footer) — no error |

---

## Dependencies

- `01_access_control.md` — Permission check
- `02_embed_creation.md` — Embeds must exist before they can be edited
- `04_dynamic_variables.md` — Variables entered in modals are validated for syntax here
- `05_newline_handling.md` — Newline solution is implemented within this feature's modal system

## Referenced By

- `06_embed_list.md` — List links to edit commands
- `07_embed_showlist.md` — Show list may surface an "Edit" button per embed
