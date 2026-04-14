# Feature 04 — Dynamic Variables

**Priority:** 🟠 Medium-High (Powers personalization; needed before any welcome/goodbye/boost embeds go live)

> Allows embed text fields to contain placeholder tokens that are resolved to real values at the moment the embed is triggered or posted.

---

## How Variables Work

Variables are written inside curly braces anywhere in a text field:

```
Welcome, {user_name}! You are member #{server_membercount}.
```

When the embed is **triggered** (e.g. a new member joins, a boost event fires, or `/embed show` is run), the bot replaces each variable token with its real value before sending the embed.

Variables are **never resolved during editing or preview** — the preview always shows the raw token (e.g. `{user_name}`). This is intentional: the value isn't known until the embed is triggered.

---

## Subfeatures (Sorted by Priority)

---

### 4.1 — Core Variable Set *(Highest)*

**What it does:** Defines the base set of supported variables available in all embeds.

**Supported Variables:**

| Variable | Resolves To | Context Required |
|---|---|---|
| `{user_name}` | Display name of the triggering user | User event (join, leave, boost) |
| `{user_tag}` | Full tag of the user (e.g. `username#0000` or new format) | User event |
| `{user_avatar}` | Direct URL of the user's avatar image | User event |
| `{user_id}` | Discord user ID (numeric string) | User event |
| `{user_mention}` | Mentions the user in-message (`@Username`) | User event |
| `{server_name}` | The guild's display name | Any |
| `{server_icon}` | Direct URL of the server's icon | Any |
| `{server_membercount}` | Total current member count | Any |
| `{server_boostcount}` | Total number of active boosts on the server | Any |
| `{server_boosttier}` | The server's current boost tier (0, 1, 2, or 3) | Any |
| `{date}` | Current date in `MMMM D, YYYY` format (e.g. `April 14, 2026`) | Any |
| `{time}` | Current time in `HH:MM UTC` | Any |
| `{newline}` | A line break character | Any (text fields only) |

**"Context Required" note:** Variables marked "User event" will resolve to empty string (or a fallback) if the embed is sent via `/embed show` (manual post) rather than an event trigger, since there's no triggering user in that case.

---

### 4.2 — Variable Syntax Validation *(High)*

**What it does:** When a staff member submits a modal containing variables, the bot scans the text for anything inside `{}` and checks it against the known variable list.

**On unknown variable detected:**
- Bot sends an ephemeral warning (not an error — it still saves):
  > *"⚠️ Unknown variable `{servar_name}` found in Description. This will display as raw text when triggered. Did you mean `{server_name}`?"*
- The embed is saved as-is — it's not blocked. The warning is advisory.

**Why warn instead of block?** Staff may intentionally write `{custom_thing}` if they plan to implement new variables later. Blocking them would be frustrating.

**Typo detection:** For close-but-wrong variable names, suggest the closest valid variable (simple string distance check). Not required for v1 — flag as "nice to have."

---

### 4.3 — Variable Field Eligibility *(Medium)*

**What it does:** Defines which embed fields support variables and which don't.

**Variables supported in:**
- Author Text ✅
- Title ✅
- Description ✅
- Footer Text ✅
- Author Icon URL ✅ (specifically for `{user_avatar}`, `{server_icon}`)
- Thumbnail URL ✅ (specifically for `{user_avatar}`, `{server_icon}`)
- Image URL ✅ (specifically for `{user_avatar}`, `{server_icon}`)
- Footer Icon URL ✅

**Variables NOT supported in:**
- Color — hex codes are static values; no variable resolution here
- Timestamp — boolean toggle, no text input

**Image URL variable note:** If a URL field resolves to a non-URL (e.g. `{user_name}` used in the Image URL field resolves to `"JohnDoe"` which is not a valid image URL), the image silently fails to render. This is a user configuration error — document it clearly but don't block at creation time.

---

### 4.4 — Variable Reference Panel in Builder *(Medium)*

**What it does:** In the builder interface (the button panel from §2.2), include a small **"Variables" info button** that, when clicked, sends an ephemeral message listing all available variables and what they return.

**Button label:** `📖 Variables`

**Output format (ephemeral message):**
```
Available Variables

User Variables (available in event-triggered embeds):
  {user_name}        → User's display name
  {user_tag}         → User's full tag
  {user_avatar}      → User's avatar URL
  {user_id}          → User's Discord ID
  {user_mention}     → @Mentions the user

Server Variables (available in all embeds):
  {server_name}      → Server name
  {server_icon}      → Server icon URL
  {server_membercount} → Total member count
  {server_boostcount}  → Total boost count
  {server_boosttier}   → Boost tier (0–3)
  {date}             → Today's date
  {time}             → Current time (UTC)
  {newline}          → Line break
```

**Why:** Staff shouldn't have to leave Discord and look up documentation every time they forget a variable name.

---

### 4.5 — Resolution Fallbacks *(Low)*

**What it does:** Defines what happens when a variable cannot be resolved (e.g. `{user_name}` in a manually-posted embed with no triggering user).

**Fallback behavior:**

| Scenario | Fallback |
|---|---|
| User variable used in `/embed show` (no user context) | Resolves to empty string `""` |
| `{user_avatar}` with no user context, used in image URL | Image field is omitted from the sent embed |
| `{server_icon}` but server has no icon set | Image field is omitted from the sent embed |
| Unknown variable (e.g. typo) | Left as raw text — `{servar_name}` appears literally |

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|------------------|
| Variable used inside another variable's resolved text | Not supported — no recursive resolution. Resolved in one pass. |
| Same variable used multiple times in one field | All instances are replaced — not just the first |
| `{newline}` used in a URL field (image, icon) | Stripped/ignored — newlines in URLs are invalid |
| User's display name contains `{}` characters | No conflict — variable parsing only looks for known token strings |

---

## Dependencies

- `03_embed_editing.md` — Variables are validated at the modal input stage

## Referenced By

- `05_newline_handling.md` — `{newline}` is a variable; its handling is detailed there
