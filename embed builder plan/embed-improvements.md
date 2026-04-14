# Embed System — Improvements Over Mimu
### Sorted by Priority · One Section Per Feature

---

> **What this document is:** A breakdown of every meaningful improvement your embed system can make over Mimu's, ranked by how much impact they have. Each feature explains what Mimu does (or fails to do), what the improvement is, and how it works — simply.

---

## Priority Scale

| Label | Meaning |
|---|---|
| 🔴 Critical | Fixes a real pain point in Mimu. Users will notice immediately. |
| 🟠 High | Meaningful upgrade that saves real time or effort. |
| 🟡 Medium | Nice quality-of-life improvement. Makes the system feel polished. |
| 🟢 Low | Power-user feature. Not needed day-to-day but very useful when needed. |

---

---

# 1. Editing a Posted Embed 🔴 Critical

## What Mimu Does
Once you run `/embed show`, the embed is posted to the channel and **locked forever**. Mimu cannot touch it again. If you made a typo or want to update the rules embed, you have to delete the old message manually, edit the embed, and repost it — breaking any pins or links to the original message.

## The Improvement
When your bot posts an embed, it **saves the message ID and channel ID** of the posted message. Later, if a staff member edits the embed and wants to push those changes live, they can run a command and the bot will **silently edit the already-posted message** with the new content — no reposting, no broken pins.

## How It Works

**Step 1 — Tracking posts:**
Every time `/embed show` is used to post an embed, the bot stores:
- Which embed ID was posted (`EMB-003`)
- The Discord message ID of the posted message
- The channel it was posted in

This is called a **post record**. One embed can have multiple post records (e.g. the same welcome embed posted in `#welcome` and `#rules-summary`).

**Step 2 — Editing the live message:**
After a staff member edits an embed via the builder, they see a new button in the confirmation:

```
✅ Saved.

[ 🔄 Push to Live Posts ]   [ Skip ]
```

Clicking "Push to Live Posts" shows them a list of every channel the embed is currently posted in. They can push the update to all of them at once, or pick specific ones.

**Step 3 — What "pushing" does:**
The bot calls Discord's message edit API using the stored message ID. The existing message is updated in-place — same message, same timestamp, same pin status, just new content.

**Step 4 — Failure handling:**
If the bot can no longer edit a message (e.g. it was manually deleted, or the bot lost channel permissions), that post record is flagged as "stale" and removed from the list with a warning:
> *"Could not update the post in #welcome — the message may have been deleted or bot permissions changed."*

---

### Subfeatures (Sorted by Priority)

**1.1 — Post Record Tracking** *(Highest)*
Store message ID + channel ID every time an embed is posted. No post records = no live editing. Everything else depends on this.

**1.2 — Push to Live Posts Button** *(High)*
The one-click option to push edits to all tracked posts at once, shown after every save.

**1.3 — Selective Push** *(Medium)*
If an embed is posted in 3 channels, let the staff member choose to push to only 1 or 2 of them instead of all.

**1.4 — Stale Post Detection** *(Medium)*
Detect and clean up post records where the original message no longer exists (deleted manually, channel deleted, etc.). Show stale records clearly in the push UI so staff know.

**1.5 — Post History Log** *(Low)*
A record of every time an embed was posted and every time it was pushed/updated — who did it, when, to which channel. Useful for audits.

---

---

# 2. Embed Templates 🔴 Critical

## What Mimu Does
Every embed starts completely blank. You build everything from scratch — title, color, description, images — every single time, even for common use cases like welcome messages.

## The Improvement
Offer a set of **pre-built starting templates** that staff can choose from when creating a new embed. Instead of starting from a blank slate, they pick a template (e.g. "Welcome Message") and get a pre-filled embed with appropriate structure, placeholder text, and a sensible color — ready to customize.

## How It Works

**When `/embed create` is run**, instead of immediately making a blank embed, the bot first asks:

```
Start from a template, or build from scratch?

[ 👋 Welcome ]  [ 👋 Goodbye ]  [ 📜 Rules ]  [ ⚡ Boost ]  [ 📢 Announcement ]  [ ⬜ Blank ]
```

Selecting a template creates the embed with **pre-filled placeholder content** that staff just swap out.

**Example — Welcome template pre-fill:**

| Field | Pre-filled value |
|---|---|
| Color | `#57F287` (Discord green) |
| Title | `Welcome to {server_name}!` |
| Description | `Hey {user_mention}, glad you're here!{newline}{newline}📜 Check out our rules.{newline}💬 Introduce yourself!` |
| Thumbnail | `{user_avatar}` |
| Footer | `You are member #{server_membercount}` |

Staff only need to tweak the description and colors — the structural work is done.

**Templates are read-only blueprints** — they're never stored as actual server embeds. Selecting one just pre-fills the builder fields. The actual embed record is still created fresh with a new `EMB-XXX` ID.

---

### Subfeatures (Sorted by Priority)

**2.1 — Built-In Template Set** *(Highest)*
Ship with at minimum: Welcome, Goodbye, Rules, Boost, Announcement, and Blank.

**2.2 — Template Preview Before Selecting** *(High)*
When hovering over or clicking a template button, show a rendered preview of what the embed will look like before committing. Staff can see it populated with example values (e.g. `{user_name}` shown as `"ExampleUser"`).

**2.3 — Save a Server's Own Embed as a Template** *(Medium)*
Let staff "save as template" any existing embed — so if they've built a great announcement layout, future announcements can start from that instead of the built-in blank one. These custom templates are server-specific.

**2.4 — Template Categories** *(Low)*
As the template list grows (especially with custom ones), group them: Built-in / Custom / Seasonal.

---

---

# 3. Embed Cloning (Duplicate) 🔴 Critical

## What Mimu Does
No duplication feature. If you want two similar embeds — say, a goodbye embed that looks like your welcome embed — you start from scratch on the second one.

## The Improvement
A single command to **duplicate any existing embed** into a new record with a new ID. Every field is copied over exactly — the staff member then only edits what's different.

## How It Works

**Command:**
```
/embed clone id:EMB-001
```

**What happens:**
1. Bot reads all fields from `EMB-001`
2. Creates a new embed record with the next available ID (e.g. `EMB-005`)
3. Copies every field (title, description, color, images, footer, etc.) over to `EMB-005`
4. Assigns the running staff member as the creator of `EMB-005`
5. Bot confirms:
   > *"EMB-001 cloned → EMB-005. Open the builder to make changes."*
   With an [ ✏️ Edit EMB-005 ] button to jump straight into editing.

**The original embed is never touched.** Cloning is purely additive.

---

### Subfeatures (Sorted by Priority)

**3.1 — Full Field Copy** *(Highest)*
All fields — including images, colors, variables — are carried over exactly.

**3.2 — Open Builder on Clone** *(High)*
Immediately offer to open the builder for the new clone so staff can make changes right away without a separate command.

**3.3 — Clone with Rename Prompt** *(Medium)*
Since your IDs are auto-assigned and not named, cloning doesn't need a name step. But consider adding an optional internal label/note field (see Feature 5) so the clone can be labeled differently from the original.

---

---

# 4. Auto-Update All Instances of a Posted Embed 🟠 High

## What Mimu Does
No connection between the embed configuration and any posted messages. Once posted, the embed is a dead copy.

## The Improvement
An optional "live sync" mode per embed. When enabled, **any edit made to the embed automatically pushes to every posted instance** — no manual "push" step needed.

## How It Works

Each embed has a toggle in the builder:

```
[ 🔄 Auto-sync: ON ]   ← toggles between ON / OFF
```

When **auto-sync is ON:**
- Every time a modal is submitted and a field is saved, the bot immediately edits all tracked posted messages with the updated content
- No "Push to Live Posts" button needed — it happens in the background
- A small status line below the preview shows: *"Auto-sync active — 3 live posts will update on save."*

When **auto-sync is OFF (default):**
- Edits stay in draft until staff manually push them (Feature 1)
- Useful when you're in the middle of a multi-step edit and don't want half-finished changes going live

**Why OFF by default?**
If you're mid-edit and auto-sync is on, every individual field save triggers a Discord API call. This is noisy and could briefly show a broken/incomplete embed to members (e.g., the color changed but the description hasn't been updated yet).

---

### Subfeatures (Sorted by Priority)

**4.1 — Per-Embed Auto-Sync Toggle** *(Highest)*
Stored per embed, defaults to OFF. Staff can flip it on for embeds that should always reflect the latest version (e.g. a server info embed that gets updated monthly).

**4.2 — Sync Status Indicator** *(High)*
Show in the builder how many live posts this embed has, and whether auto-sync is on. E.g.: *"2 live posts · Auto-sync ON"*

**4.3 — Sync Error Notifications** *(Medium)*
If an auto-sync update fails (message deleted, permissions lost), send an ephemeral notification to the staff member who triggered the save, specifying which post failed.

---

---

# 5. Internal Labels / Notes on Embeds 🟠 High

## What Mimu Does
Embeds are identified only by their name (e.g. `greet_embed`). No way to add context about what an embed is for, who requested it, or what event triggers it.

## The Improvement
An optional **internal label and note** per embed — visible only in management commands (`/embed list`, `/embed showlist`), never in the posted embed itself. Staff can describe what the embed is for without that text appearing publicly.

## How It Works

In the builder, add a new button: `📝 Internal Note`

Clicking it opens a modal with two fields:

| Field | Purpose | Max Length |
|---|---|---|
| Label | Short display name for the embed list (e.g. "Welcome — Main Server") | 50 chars |
| Note | Longer context (e.g. "Triggered by autoresponder !welcome. Last reviewed April 2026.") | 500 chars |

**Where these appear:**

In `/embed list`:
```
EMB-003  ·  Welcome — Main Server  ·  Created by @kim  ·  Jan 16, 2024
```

In `/embed showlist`, below the preview:
```
📝 Welcome — Main Server
Triggered by autoresponder !welcome. Last reviewed April 2026.
```

**These fields are 100% internal.** They are never included in the Discord embed that gets posted.

---

### Subfeatures (Sorted by Priority)

**5.1 — Label Field** *(Highest)*
Short, human-readable name for the embed. Makes `/embed list` far more readable than just `EMB-001`, `EMB-002`.

**5.2 — Note Field** *(High)*
Longer free-text field for any context staff want to remember about the embed.

**5.3 — Filter by Label in List Commands** *(Low)*
`/embed list filter:welcome` — shows only embeds whose label contains "welcome". Useful when you have 20+ embeds.

---

---

# 6. Embed Scheduling 🟠 High

## What Mimu Does
No scheduling. You manually run `/embed show` whenever you want an embed posted. If you want it posted at midnight, someone has to be awake.

## The Improvement
**Schedule an embed to post itself** to a specific channel at a specific date and time. Set it and forget it.

## How It Works

**Command:**
```
/embed schedule id:EMB-003 channel:#announcements date:2026-04-20 time:18:00
```

Or, via a button in the builder: `📅 Schedule Post`

**What you configure:**
- Which embed
- Which channel
- Date and time (uses the server's configured timezone, or UTC if none set)
- Optional: repeat (once / daily / weekly / monthly — see subfeatures)

**Once scheduled:**
- An entry is saved: "Post EMB-003 to #announcements on April 20 at 6:00 PM"
- At the scheduled time, the bot posts the embed exactly as `/embed show` would
- A post record is created (Feature 1) so the post can be edited later

**Viewing upcoming schedules:**
```
/embed schedule list
```
Returns an ephemeral list:
```
Upcoming Scheduled Posts

EMB-003  →  #announcements  ·  Apr 20, 2026 at 6:00 PM
EMB-007  →  #general        ·  Apr 21, 2026 at 12:00 PM
```

**Cancelling:**
```
/embed schedule cancel id:EMB-003
```
Or a Cancel button next to each entry in the schedule list.

---

### Subfeatures (Sorted by Priority)

**6.1 — One-Time Scheduling** *(Highest)*
Post once at a specified date and time. The most common use case (event announcements, patch notes, etc.).

**6.2 — Schedule via Builder Button** *(High)*
In addition to the slash command, add a `📅 Schedule` button in the builder interface so staff don't need to memorize the command syntax.

**6.3 — Timezone Configuration** *(High)*
Allow the server owner to set a server-wide timezone (`/embed config timezone America/New_York`). All scheduled times are interpreted in that timezone.

**6.4 — Recurring Schedules** *(Medium)*
Options: daily, weekly (pick day of week), monthly (pick date of month). Useful for things like a weekly game night announcement embed.

**6.5 — Schedule Conflict Warning** *(Low)*
If two embeds are scheduled for the same channel within 5 minutes of each other, warn the staff member before confirming.

---

---

# 7. Rich Variable Formatting 🟠 High

## What Mimu Does
Variables return their raw value with no formatting options. `{server_membercount}` returns `21844` — a plain number with no comma separation, no ability to customize the output.

## The Improvement
Support **formatting modifiers** inside variable calls using a colon separator — letting staff control how a variable's value is displayed without needing to manually update anything.

## How It Works

Formatting is added after the variable name, separated by `:`:

```
{variable_name:format}
```

**Supported formats:**

| Variable | Format | Output |
|---|---|---|
| `{server_membercount}` | `{server_membercount:,}` | `21,844` (comma-separated) |
| `{server_membercount}` | `{server_membercount:ordinal}` | `21,844th` |
| `{user_name}` | `{user_name:upper}` | `JOHNDOE` |
| `{user_name}` | `{user_name:lower}` | `johndoe` |
| `{user_name}` | `{user_name:title}` | `Johndoe` |
| `{date}` | `{date:short}` | `Apr 14, 2026` |
| `{date}` | `{date:long}` | `Tuesday, April 14, 2026` |
| `{date}` | `{date:relative}` | `today` / `yesterday` / `3 days ago` |
| `{server_boosttier}` | `{server_boosttier:label}` | `Level 2` instead of `2` |

**No format = current behavior** — plain raw value, same as Mimu. All formats are optional and backward-compatible.

**In the preview:** Variables with format modifiers show as `{server_membercount:,}` (raw) in the builder preview, with a note that they'll be formatted on posting.

---

### Subfeatures (Sorted by Priority)

**7.1 — Number Formatting (`:,`)** *(Highest)*
Comma-separated numbers. The single most useful format — member counts look terrible without it.

**7.2 — Text Case Formatting (`:upper`, `:lower`, `:title`)** *(High)*
Useful for making usernames match the embed's tone.

**7.3 — Date Formatting (`:short`, `:long`, `:relative`)** *(High)*
Different date styles for different embed types (a birthday embed wants `:long`; a log embed might want `:short`).

**7.4 — Label Formatting (`:label`, `:ordinal`)** *(Medium)*
Makes boost tier and member count display more readable for members reading the embed.

**7.5 — Format Validation in Modal** *(Medium)*
If a staff member types `{server_membercount:invalid_format}`, warn them: *"Unknown format `:invalid_format` for `{server_membercount}`. Valid options: `:,` `:ordinal`."*

---

---

# 8. Embed Version History 🟡 Medium

## What Mimu Does
No history. Every save overwrites the previous version permanently. If a staff member accidentally clears the description or sets the wrong color, there's no going back.

## The Improvement
Keep a **rolling history of the last 10 saved versions** of each embed. Staff can view what the embed looked like at any point and restore a previous version with one click.

## How It Works

**Every time a field is saved**, the bot snapshots the entire current embed state and stores it as a version entry. Each version records:
- What changed (e.g. "Description updated")
- Who changed it
- When

**Viewing history:**
```
/embed history id:EMB-003
```

Returns an ephemeral list:
```
Version History — EMB-003

v5  ·  Today at 3:44 PM   ·  Description updated  ·  by @kim       ← current
v4  ·  Today at 3:41 PM   ·  Color changed         ·  by @kim
v3  ·  Apr 12 at 11:02 AM ·  Title updated         ·  by @iara
v2  ·  Apr 12 at 10:55 AM ·  Image added           ·  by @iara
v1  ·  Apr 12 at 10:30 AM ·  Embed created         ·  by @iara

[ Preview v4 ]   [ Restore v4 ]
```

**Previewing a version:**
Shows a rendered embed preview of that version's state.

**Restoring a version:**
Copies all fields from the selected version back into the current embed. Creates a new version entry: `v6 · Restored from v4 · by @kim`.

**History limit:** Only the last 10 versions are kept per embed. Older versions are automatically pruned.

---

### Subfeatures (Sorted by Priority)

**8.1 — Auto-Snapshot on Every Save** *(Highest)*
Every field save creates a new snapshot. Transparent — no staff action required.

**8.2 — Restore from Version** *(High)*
One-click restore to any stored version. Requires a confirmation step.

**8.3 — Version Preview** *(High)*
Preview any historical version as a rendered embed before deciding whether to restore it.

**8.4 — Change Summary per Version** *(Medium)*
Each version entry describes what changed in plain language: "Description updated", "Color changed from #FF0000 to #5865F2", "Image removed". Makes the history readable at a glance.

**8.5 — Version Pruning Control** *(Low)*
The 10-version limit is a practical cap. Document it clearly. Don't make it configurable in v1 — keep it simple.

---

---

# 9. Embed Export & Import 🟡 Medium

## What Mimu Does
No way to copy embeds between servers or back them up. If a server gets nuked or reset, all embeds are gone.

## The Improvement
**Export** an embed (or all embeds) as a JSON file. **Import** that file into any server your bot is in to recreate the embeds exactly.

## How It Works

**Exporting:**
```
/embed export id:EMB-003
```
Bot sends an ephemeral message with a `.json` file attached. The JSON contains all field values for that embed.

**Export all:**
```
/embed export all
```
Bot sends a single `.json` file containing every embed in the server.

**Importing:**
```
/embed import
```
Bot prompts the staff member to attach a `.json` file (the one they got from export). The bot reads the file, validates it, and recreates the embed(s) with new auto-assigned IDs.

**What gets preserved on import:**
- All field content (title, description, color, images, etc.)
- Internal labels and notes (Feature 5)

**What does NOT transfer:**
- The original embed ID (new IDs are assigned)
- Creator attribution (import sets the importing user as creator)
- Post records (those are message-specific and don't transfer)
- Version history (starts fresh)

**Validation on import:**
- If the JSON is malformed or not a valid embed export: reject with a clear error
- If image URLs in the imported embed are from a server that no longer hosts them: import still works, but image fields may be broken (user's responsibility)

---

### Subfeatures (Sorted by Priority)

**9.1 — Single Embed Export** *(Highest)*
Export one embed by ID. The most common use case (sharing a well-designed embed between servers).

**9.2 — Single Embed Import** *(Highest)*
Import a single embed from a `.json` file.

**9.3 — Bulk Export (All Embeds)** *(High)*
Export all embeds as one file. Useful as a backup before major changes.

**9.4 — Bulk Import** *(Medium)*
Import a multi-embed JSON file, creating all embeds in sequence. Show a summary of what was created.

**9.5 — Import Preview Before Committing** *(Medium)*
Before actually creating the embed(s), show a preview of what will be imported and ask for confirmation.

---

---

# 10. Embed Search 🟡 Medium

## What Mimu Does
`/embed list` gives a flat list of embed names. With 10+ embeds, finding the one you want means scrolling through all of them.

## The Improvement
A **search command** that filters embeds by any text — matching against the embed's internal label (Feature 5), description content, or title.

## How It Works

```
/embed search query:welcome
```

Returns all embeds whose label, title, or description contains the word "welcome" — rendered as a compact ephemeral list identical to `/embed list` but filtered.

**Search is case-insensitive** and matches partial words (`welc` finds "welcome").

**If no results:**
> *"No embeds found matching 'welcome'. Try a broader search or run `/embed list` to see all."*

---

### Subfeatures (Sorted by Priority)

**10.1 — Content Search (Label + Title + Description)** *(Highest)*
The core search. Searches the three most useful fields.

**10.2 — Filter by Creator** *(Medium)*
`/embed search creator:@kim` — shows only embeds created by a specific user.

**10.3 — Filter by Date Range** *(Low)*
`/embed search created-after:2026-01-01` — useful for finding recently created embeds in large servers.

---

---

# 11. Per-Embed Permissions 🟡 Medium

## What Mimu Does
Embed management is all-or-nothing: either you have access to all embed commands or none.

## The Improvement
Allow the server owner or admins to **restrict specific embeds** so only certain roles can edit or delete them — even among staff.

## How It Works

On any embed, an admin can run:
```
/embed permissions id:EMB-003 edit-roles:@Moderator @Admin
/embed permissions id:EMB-003 delete-roles:@Admin
```

This means:
- `@Moderator` and `@Admin` can edit `EMB-003`
- Only `@Admin` can delete it
- A `@Staff` member who doesn't have either role can **view** EMB-003 (in list/showlist) but cannot edit or delete it

**Default behavior (no permissions set):** Anyone who passes the global access control check (Feature 01 in the main spec) can do anything to any embed. Per-embed permissions are **opt-in** — you only need them if you want finer control.

**Use case:** The rules embed and the welcome embed are "sacred" — only admins should be allowed to change them. Regular staff can create and manage their own embeds freely, but not touch the core ones.

---

### Subfeatures (Sorted by Priority)

**11.1 — Edit Role Restriction** *(Highest)*
Lock editing of a specific embed to certain roles.

**11.2 — Delete Role Restriction** *(High)*
Separately restrict who can delete (often stricter than edit).

**11.3 — View Permissions in Showlist** *(Medium)*
In `/embed showlist`, show a small lock icon on embeds the viewing user can see but not edit/delete. Makes permissions visible without being obtrusive.

**11.4 — Permission Inheritance from Config** *(Low)*
Allow the admin to set a "default restricted" mode where all new embeds start locked to admin-only, and staff must be explicitly granted access per embed. Inverts the default for high-security servers.

---

---

# 12. Embed Usage Statistics 🟡 Medium

## What Mimu Does
No tracking. You have no idea how many times an embed has been posted, which embeds are actively used, or which ones are sitting there forgotten.

## The Improvement
Track basic usage data per embed and surface it in a simple stats command.

## How It Works

```
/embed stats id:EMB-003
```

Returns an ephemeral summary:
```
📊 Stats — EMB-003 (Welcome — Main Server)

Total times posted:     14
Last posted:            Apr 14, 2026 at 3:22 PM by @kim
Total live instances:   2  (#welcome, #announcements)
Auto-syncs triggered:   6
Versions saved:         5
Created:                Jan 16, 2024 by @iara
```

**Server-wide summary:**
```
/embed stats
```
Returns a table of all embeds with their post counts — sorted by most-used first. Good for identifying dead embeds that can be cleaned up.

---

### Subfeatures (Sorted by Priority)

**12.1 — Post Count Tracking** *(Highest)*
Increment a counter every time `/embed show` or a scheduled post fires.

**12.2 — Last Posted Info** *(High)*
Who posted it and when, at a glance.

**12.3 — Live Instance Count** *(Medium)*
How many tracked live posts currently exist for this embed (from Feature 1).

**12.4 — Server-Wide Usage Summary** *(Medium)*
`/embed stats` with no ID gives an overview of all embeds ranked by usage.

**12.5 — Zero-Usage Warning in List** *(Low)*
In `/embed list`, flag embeds that have never been posted with a small `· Never posted` note. Makes it easy to find and clean up test or abandoned embeds.

---

---

# 13. Embed Pinning / Quick Access 🟢 Low

## What Mimu Does
All embeds are equal in the list. The most important ones (welcome, rules) are buried in the same flat list as test embeds you made yesterday.

## The Improvement
Let staff **pin up to 5 embeds** so they always appear at the top of `/embed list` and `/embed showlist`, regardless of ID order.

## How It Works

```
/embed pin id:EMB-001
/embed unpin id:EMB-001
```

Pinned embeds show at the top of all list views with a 📌 indicator:

```
📋 Server Embeds — 6 total

📌 EMB-001  ·  Welcome — Main Server     ← pinned
📌 EMB-002  ·  Rules Embed               ← pinned
────────────────────────────────────────
   EMB-003  ·  Test embed                ← normal
   EMB-004  ·  Boost Message             ← normal
```

**Pin limit:** 5 pinned embeds per server. Prevents abuse and keeps the "quick access" concept meaningful.

---

### Subfeatures (Sorted by Priority)

**13.1 — Pin/Unpin Commands** *(Highest)*
`/embed pin` and `/embed unpin`. Simple toggle.

**13.2 — Pinned-First Ordering in All List Views** *(High)*
Pinned embeds always render at the top, separated visually from unpinned ones.

**13.3 — Pin in Builder** *(Low)*
A `📌 Pin` toggle button available directly in the embed builder, so you can pin immediately after creation.

---

---

# 14. Embed Expiry (Auto-Delete or Auto-Replace) 🟢 Low

## What Mimu Does
No time-based automation. Embeds and their posted messages exist forever unless manually deleted.

## The Improvement
Optionally set an **expiry** on a posted embed — after a specified date, the bot either **deletes** the posted message or **replaces** it with a different embed.

## How It Works

When using `/embed show` or scheduling a post (Feature 6), optionally add an expiry:

```
/embed show id:EMB-005 channel:#events expires:2026-05-01 on-expire:delete
/embed show id:EMB-005 channel:#events expires:2026-05-01 on-expire:replace-with:EMB-006
```

**On-expire actions:**

| Action | What Happens |
|---|---|
| `delete` | The posted Discord message is deleted at the expiry time |
| `replace-with:EMB-XXX` | The message is edited in-place to show the content of a different embed (e.g. swap "Event is upcoming" → "Event has ended") |
| `archive` | Message is kept but a reaction or footer note is appended: *"This announcement has expired."* |

**Use case example:**
Post an event announcement embed with `expires:2026-05-01 on-expire:replace-with:EMB-006` where `EMB-006` is the "This event has ended" version. The swap happens automatically at midnight.

---

### Subfeatures (Sorted by Priority)

**14.1 — Expire-Delete** *(Highest)*
Simplest case. Delete the message on expiry. Useful for temporary announcements.

**14.2 — Expire-Replace** *(High)*
Swap to a different embed on expiry. The most useful for event workflows.

**14.3 — Expiry Confirmation and Warning** *(Medium)*
When setting an expiry, confirm: *"EMB-005 will expire in #events on May 1, 2026. Action: delete."* Also send a warning to the staff team 24 hours before expiry fires, in case they forgot.

**14.4 — View All Active Expiries** *(Low)*
`/embed expiry list` — shows all posts that have active expiry timers. Lets staff audit what's going to happen and when.

---

---

# 15. Webhook Sender 🟢 Low

## What Mimu Does
Premium servers can send embeds via webhook, allowing them to appear as a custom name/avatar instead of the bot itself. Non-premium servers can only post as the bot.

## The Improvement
Make webhook sending **available to all servers** (not behind a paywall) and add **per-embed webhook configuration** so each embed can have its own custom sender identity.

## How It Works

In the embed builder, add a `🔗 Sender Identity` button that opens a modal:

| Field | Purpose | Example |
|---|---|---|
| Webhook Name | The display name of the sender | `Server Staff` / `Event Bot` |
| Webhook Avatar URL | Profile picture for the webhook message | `https://i.imgur.com/...` |

When the embed is posted, the bot **creates a temporary webhook** in the target channel (or reuses an existing one), sends the embed through it using the configured name and avatar, then leaves the webhook in place for future use (deleting and recreating webhooks is slow).

**Result:** The embed appears to come from "Server Staff" with a custom icon — not from your bot.

**Fallback:** If the bot lacks the "Manage Webhooks" permission in a channel, it falls back to posting as itself and warns the staff member.

---

### Subfeatures (Sorted by Priority)

**15.1 — Per-Embed Sender Identity Config** *(Highest)*
Each embed stores its own webhook name and avatar. Useful when you have a welcome bot persona and a moderation bot persona sharing the same bot.

**15.2 — Webhook Reuse (Performance)** *(High)*
Cache created webhooks per channel so the bot doesn't create a new one every time. Check if a webhook already exists in the channel before creating.

**15.3 — Permission Check and Fallback** *(High)*
Gracefully fall back to standard bot posting if `MANAGE_WEBHOOKS` is unavailable, with a clear warning.

**15.4 — Default Server Webhook Identity** *(Low)*
Let admins set a server-wide default webhook name/avatar that all embeds use unless overridden at the embed level.

---

---

## Quick Reference — All Features

| # | Feature | Priority | What Mimu Lacks |
|---|---|---|---|
| 1 | Editing a Posted Embed | 🔴 Critical | Posted embeds are locked forever |
| 2 | Embed Templates | 🔴 Critical | Every embed starts completely blank |
| 3 | Embed Cloning | 🔴 Critical | No way to duplicate an existing embed |
| 4 | Auto-Update All Instances | 🟠 High | No link between embed config and posted messages |
| 5 | Internal Labels / Notes | 🟠 High | Embeds have no internal metadata |
| 6 | Embed Scheduling | 🟠 High | Posts must be done manually in real-time |
| 7 | Rich Variable Formatting | 🟠 High | Variables have no output formatting control |
| 8 | Embed Version History | 🟡 Medium | Saves are permanent with no undo |
| 9 | Embed Export & Import | 🟡 Medium | No backup or cross-server transfer |
| 10 | Embed Search | 🟡 Medium | Flat list only; no filtering |
| 11 | Per-Embed Permissions | 🟡 Medium | Access is all-or-nothing per server |
| 12 | Embed Usage Statistics | 🟡 Medium | No tracking of embed activity |
| 13 | Embed Pinning / Quick Access | 🟢 Low | All embeds are equal in lists |
| 14 | Embed Expiry | 🟢 Low | No time-based automation |
| 15 | Webhook Sender | 🟢 Low | Webhook posting is premium-only |
