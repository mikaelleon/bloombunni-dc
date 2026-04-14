# Embed Buttons & Role Assignment — Improvements Over Mimu
### Sorted by Priority · One Section Per Feature

---

> **What this document is:** A breakdown of every meaningful improvement your bot can make over Mimu's button and role-assignment system — ranked by impact. Each entry explains what Mimu does (or fails to do), what the improvement is, and exactly how it works — simply.

---

## Priority Scale

| Label | Meaning |
|---|---|
| 🔴 Critical | Fixes a real, daily pain point. Staff will notice this immediately. |
| 🟠 High | Major upgrade that saves real time or prevents real problems. |
| 🟡 Medium | Polished quality-of-life improvement. |
| 🟢 Low | Power-user feature. Not needed often, but very useful when you do. |

---

## How Mimu's Button System Currently Works (Quick Reference)

Before the improvements, here's what Mimu currently offers so comparisons are clear:

- Buttons are created as named objects and attached to messages using the `{addbutton:button_name}` variable
- Buttons can be used in autoresponders and the `/send` command
- Role panels combine an embed + one or more `{addbutton:}` calls to make a role-selector message
- Button actions are limited: assign role, remove role, or toggle role
- Buttons have a label, optional emoji, and a style (color)
- No conditions — every button works the same for every user
- No feedback beyond Discord's default button interaction acknowledgment
- No analytics on button usage

---
---

# 1. Button Builder Interface 🔴 Critical

## What Mimu Does
Buttons are created and edited entirely through slash commands with many separate parameters. To create a button you type the entire configuration in one command. There's no interactive builder, no preview, and editing requires remembering the exact command syntax.

## The Improvement
A fully interactive **button builder** — the same modal-and-preview approach as the embed builder. Staff click through a guided interface instead of typing long commands, and see exactly what the button will look like before it goes live.

## How It Works

**Command:**
```
/button create
```

No parameters. The bot opens an **interactive builder interface** with buttons for each configurable property:

```
[ 🏷️ Label ]   [ 😀 Emoji ]   [ 🎨 Style ]   [ ⚡ Action ]   [ 🔒 Conditions ]

[ 👁️ Preview ]   [ ✅ Done ]   [ 🗑️ Discard ]
```

Each button opens a modal for that property. The preview updates live every time a field is saved — staff see the exact button as it'll appear in Discord (color, label, emoji, disabled state) without posting it anywhere.

**Auto-assigned ID:** Just like embeds, buttons get an auto-assigned ID: `BTN-001`, `BTN-002`, etc. No manual naming required.

**What each modal covers:**

| Builder Button | What You Configure |
|---|---|
| 🏷️ Label | The text on the button (e.g. "🎮 Gamer") |
| 😀 Emoji | An emoji prefix shown before the label (optional) |
| 🎨 Style | Button color: Blue (Primary), Grey (Secondary), Green (Success), Red (Danger) |
| ⚡ Action | What the button does when clicked — see Feature 2 |
| 🔒 Conditions | Who can use this button and under what circumstances — see Feature 5 |

---

### Subfeatures (Sorted by Priority)

**1.1 — Auto-Assigned Button IDs** *(Highest)*
`BTN-001`, `BTN-002`, etc. — same pattern as embeds. No manual naming, no collision, no 16-character limit.

**1.2 — Live Button Preview in Builder** *(Highest)*
The builder message shows a real-time render of how the button looks — label, emoji, color — updating on every change before anything is posted.

**1.3 — Internal Label / Note per Button** *(High)*
Same as embeds: a staff-only label (e.g. "Gamer role — no restrictions") and a longer note (e.g. "Paired with EMB-003, updated April 2026"). Never shown publicly.

**1.4 — Button Edit Command** *(High)*
`/button edit id:BTN-003` reopens the full builder for any existing button. `/button edit id:BTN-003 field:style` opens just that field's modal.

**1.5 — Button Clone** *(Medium)*
`/button clone id:BTN-001` duplicates all properties into a new `BTN-XXX`. Useful when you have many similar role buttons that differ only in label and role assignment.

**1.6 — Builder Session Lock** *(Medium)*
Only one active builder session per button at a time. If someone else is editing `BTN-003`, a second staff member sees: *"BTN-003 is currently being edited by @Username."*

**1.7 — Button List Command** *(Medium)*
`/button list` — same style as `/embed list`. Shows all button IDs, their labels, their action type, and who created them.

---
---

# 2. Button Action Types 🔴 Critical

## What Mimu Does
Buttons can do exactly three things: assign a role, remove a role, or toggle a role (assign if not present, remove if present). That's the entire action set. There's no chaining, no multi-role actions, no non-role actions.

## The Improvement
Expand the action system to cover **8 distinct action types** — including multi-role actions, channel access grants, DM responses, and custom embed posts — all configurable from the button builder.

## How It Works

When the ⚡ **Action** button is clicked in the builder, a select menu appears listing all available action types. Staff pick one and fill in the details via modal.

**All Available Action Types:**

---

### Action Type 1 — Assign Role *(Already in Mimu)*
Gives the user a role when they click the button.

**Config:** Pick a role from a dropdown.
**Behavior:** User gains the role. If they already have it: optionally show a message like *"You already have this role."*

---

### Action Type 2 — Remove Role *(Already in Mimu)*
Removes a role from the user.

**Config:** Pick a role.
**Behavior:** Role is removed. If user doesn't have it: optionally show *"You don't have this role."*

---

### Action Type 3 — Toggle Role *(Already in Mimu)*
Assigns if the user doesn't have the role, removes it if they do. One button does both directions.

**Config:** Pick a role.
**Behavior:** Adds or removes depending on current state. Response message adjusts: *"✅ Role added."* or *"❌ Role removed."*

---

### Action Type 4 — Multi-Role Assign *(New)*
Assigns **multiple roles at once** from a single button click.

**Why Mimu can't do this:** Each button maps to exactly one role. To assign 3 roles, you need 3 buttons — cluttering the panel.

**How it works:**
- Config: select up to 5 roles to assign together
- Example use case: a "Content Creator" button that simultaneously assigns `@Content Creator`, `@Announcements`, and `@Media Pings` in one click
- Each role in the batch is assigned only if the user doesn't already have it

---

### Action Type 5 — Role Swap *(New)*
Replaces one role with another. Used in tiered systems or exclusive choices.

**Why it matters:** Without this, if you want a "switch from Free to Premium" button, you need separate Remove and Assign buttons, and users have to click both.

**How it works:**
- Config: "Remove [Role A] and assign [Role B]"
- Example: a game difficulty selector where picking "Hard" removes `@Easy Mode` and gives `@Hard Mode` simultaneously
- If the user doesn't have Role A, only Role B is assigned (no error)

---

### Action Type 6 — Exclusive Role Select *(New)*
Assigns a role **and removes all other roles in a defined group.** Essential for "pick exactly one" panels.

**Why it matters:** Mimu has no concept of mutual exclusivity between buttons. If you have a color role panel (Red, Blue, Green) with toggle buttons, a user can have all three colors at once — that's usually not the intent.

**How it works:**
- Buttons are grouped into an "exclusive group" (configured when building the panel — see Feature 4)
- Clicking any button in the group: assigns that button's role, removes all other roles in the group
- Example: a Pronouns panel. Clicking "She/Her" assigns `@she/her`, removes `@he/him` and `@they/them`
- If the user clicks their current role: it's removed (opt-out), leaving them with no role from that group

---

### Action Type 7 — DM Response *(New)*
When clicked, sends the user a **private DM** with a configured message instead of (or in addition to) modifying roles.

**Use case:** A "Get Rules" button on a welcome panel that DMs the user the full rules text. A "Get My Order Status" button that DMs them their current order info.

**How it works:**
- Config: a text field for the DM content (supports variables like `{user_name}`, `{server_name}`)
- Optionally combine with a role action: assign a role AND send a DM
- If the user's DMs are closed: falls back to an ephemeral message in the channel
- DM content can include a reference to an embed: `{embed:EMB-003}` sends the configured embed as a DM

---

### Action Type 8 — Post Embed in Channel *(New)*
When clicked, posts a configured embed to a **specific channel** (not just a DM).

**Use case:** An "Introduce Yourself" button in a welcome channel that, when clicked, posts a welcome embed in `#introductions` with the user's name and avatar.

**How it works:**
- Config: which embed to post (select from existing embed IDs) and which channel to post it to
- The posted embed resolves variables at click time — `{user_name}`, `{user_mention}`, `{user_avatar}` reflect the clicking user
- Optionally: restrict how often this can be triggered per user (e.g. once per day, once ever — prevents spam)
- The button itself is visible to everyone; only the resulting post uses the user's context

---

### Subfeatures (Sorted by Priority)

**2.1 — Toggle Role (Parity with Mimu)** *(Highest)*
Fully replicated from Mimu — no regression.

**2.2 — Multi-Role Assign** *(Highest)*
Single click, multiple roles. The #1 most-requested capability for role panels.

**2.3 — Exclusive Role Select** *(High)*
Mutual exclusivity within a group. Essential for color/pronoun/region panels.

**2.4 — Role Swap** *(High)*
One-click upgrade/downgrade between roles without needing two separate buttons.

**2.5 — DM Response** *(Medium)*
Private message delivery from a public button. Keeps channels clean.

**2.6 — Post Embed in Channel** *(Medium)*
Dynamic public embed post triggered by a user button click.

**2.7 — Action Preview in Builder** *(Medium)*
After configuring an action, the builder preview shows a short plain-English description of what will happen: *"Clicking this button will: Assign @Gamer, Remove @Lurker."* Staff can read it as a sanity check before saving.

---
---

# 3. Button Response Messages 🔴 Critical

## What Mimu Does
When a button is clicked, Discord shows a generic interaction acknowledgment. Mimu doesn't customize what the user sees after clicking — there's no branded confirmation, no error feedback, nothing tailored to the action taken.

## The Improvement
Every button click triggers a **configurable ephemeral response message** — visible only to the user who clicked. Different messages for success, already-has-role, doesn't-have-role, and conditions not met. All customizable.

## How It Works

In the button builder, a **🗨️ Responses** section (accessed via a button) lets staff set messages for each possible outcome.

**Response slots per button:**

| Slot | When It Fires | Default If Not Configured |
|---|---|---|
| **On Success** | Action completed normally | *"✅ Done!"* |
| **On Already Has Role** | User clicked Assign but already has the role | *"You already have this role."* |
| **On Role Removed** | Toggle/Remove completed | *"Role removed."* |
| **On Conditions Not Met** | User failed a requirement (see Feature 5) | *"You don't meet the requirements for this role."* |
| **On Cooldown** | User clicked too soon after the last click | *"Please wait before using this button again."* |
| **On Max Reached** | Role is at capacity (see Feature 5) | *"This role is currently full."* |

**Variables are supported** in all response messages — `{user_name}`, `{server_name}`, the role name (`{role_name}`), etc.

**Example custom responses:**
- On Success: *"Welcome to the Gamers crew, {user_name}! 🎮"*
- On Already Has Role: *"You're already a Gamer — nice."*
- On Conditions Not Met: *"This role requires the @Verified role first. Get verified in #verification."*

**All responses are ephemeral** — only the clicking user sees them. Never clutters the channel.

---

### Subfeatures (Sorted by Priority)

**3.1 — Success Response (Customizable)** *(Highest)*
The most visible response. Branded confirmation instead of a generic Discord ack.

**3.2 — Already-Has / Doesn't-Have Responses** *(High)*
Helpful context instead of a silent no-op. Users know what happened and what to do.

**3.3 — Conditions-Not-Met Response** *(High)*
The single most important error message. When a user can't get a role, they deserve to know why and what the path forward is. See Feature 5 for conditions.

**3.4 — Variable Support in Responses** *(Medium)*
Makes responses feel personal. `{user_name}` in a welcome message goes a long way.

**3.5 — Cooldown Response with Time Remaining** *(Medium)*
Show how long until the user can click again: *"Please wait 4 minutes before using this button again."* Not just a vague rejection.

**3.6 — Response Preview in Builder** *(Low)*
While editing response messages in the builder, a small preview shows the rendered text with example variable values filled in.

---
---

# 4. Panel Builder (Embed + Buttons Together) 🔴 Critical

## What Mimu Does
To create a panel (an embed with buttons), you use the `/send` command with the `{embed:name}` variable combined with one or more `{addbutton:name}` variables. Each button is created separately, the embed is created separately, and then they're combined in the send command. There's no unified panel concept — the panel only exists at post time, not as a reusable saved object.

## The Improvement
A **Panel** is a first-class object — a saved combination of one embed and up to 25 buttons, arranged in rows, with a preview. Panels are built in an interactive interface, saved by ID, and posted or edited as a unit.

## How It Works

**Creating a panel:**
```
/panel create
```

The bot opens a panel builder interface showing:
- A slot for an embed (click to pick from existing embeds, or create inline)
- Up to 5 rows of up to 5 buttons each
- Drag-and-drop-style ordering via "Move Up / Move Down" controls on each button slot

**The panel builder UI:**

```
Panel Builder — PANEL-001

[ 📋 Set Embed: EMB-003 "Welcome Panel" ]

Row 1:  [ BTN-001 🎮 Gamer ] [ BTN-002 📖 Reader ] [ BTN-003 🎵 Music ] [ + Add ]
Row 2:  [ BTN-004 🔔 Announcements ] [ + Add ]
Row 3:  [ + Add Row ]

[ 👁️ Preview ]   [ 📤 Post Panel ]   [ ✅ Done ]   [ 🗑️ Discard ]
```

**The preview** renders the full panel — the embed above, the button rows below — exactly as it will look when posted to a channel.

**Posting a panel:**
```
/panel show id:PANEL-001 channel:#roles
```
Or directly from the builder via the "Post Panel" button, which shows a channel selector.

**Editing a posted panel:**
Just like embeds, the bot tracks the message ID of every posted panel. Editing the panel config and clicking "Push to Live Posts" updates the message in place — buttons and embed together — without reposting.

---

### Subfeatures (Sorted by Priority)

**4.1 — Panel as a Saved Object (PANEL-XXX)** *(Highest)*
Panels have their own auto-incremented ID, stored in the database. Not a one-time command output — a persistent, reusable configuration.

**4.2 — Button Row Layout Control** *(Highest)*
Up to 5 rows of up to 5 buttons per row. Staff can add/remove buttons per row and reorder them. Mimu has no control over button row placement.

**4.3 — Live Panel Preview** *(High)*
Full preview of the combined embed + button rows before posting — same live-update behavior as the embed builder.

**4.4 — Edit Posted Panel In Place** *(High)*
Track posted message IDs. Push config changes to live panels without deleting and reposting. Preserves message history, pins, and links.

**4.5 — Panel List and Showlist** *(High)*
`/panel list` — compact list of all panels with IDs and labels.
`/panel showlist` — paginated browser with full rendered previews, same as `/embed showlist`.

**4.6 — Exclusive Button Groups within a Panel** *(High)*
Mark certain buttons in a panel as part of a mutually exclusive group (e.g. "color roles" group). Any button in the group automatically uses the Exclusive Role Select action type (Feature 2, Action Type 6). Configured at the panel level, not per-button.

**4.7 — Panel Clone** *(Medium)*
`/panel clone id:PANEL-001` — duplicates the panel config (embed reference + all button assignments + layout) into a new `PANEL-XXX`. Useful for making a "variant" panel (e.g. a condensed version of a full role panel for mobile).

**4.8 — Embed-Only Panel (No Buttons)** *(Low)*
A panel with no buttons is just a managed embed post — still tracked as a panel so it benefits from the "edit in place" system. Useful for announcement embeds you'll update over time.

---
---

# 5. Button Conditions and Access Control 🟠 High

## What Mimu Does
No conditions. Every button works the same for every user at all times. You can't restrict a role button to users who already have a specific role, limit how many people get a role, set a cooldown between clicks, or require any kind of prerequisite.

## The Improvement
Each button can have configurable **conditions** that are evaluated before the action fires. If conditions aren't met, the action is blocked and the user sees the "Conditions Not Met" response (Feature 3).

## How It Works

In the button builder, the 🔒 **Conditions** button opens a modal where staff configure zero or more conditions. All configured conditions must pass for the button to fire.

**Available Conditions:**

---

### Condition 1 — Required Role
User must have (or must not have) a specific role to use this button.

**Config:** Pick a role; toggle "must have" or "must not have."

**Examples:**
- "Must have @Verified" — only verified users can get any other roles
- "Must not have @Banned from Roles" — revoked users can't self-assign
- "Must have @Nitro Booster" — a special role only boosters can get

---

### Condition 2 — Role Capacity Limit
The role can only have a maximum number of members at any time.

**Config:** Enter a number (e.g. "Max 50 members").

**How it works:**
- Before assigning the role, the bot counts how many members currently have it
- If at or above the cap: blocks the action and shows the "Max Reached" response
- When someone removes the role (via another button, or it's revoked), capacity opens back up
- `/button capacity id:BTN-007` shows current count vs. cap at any time

**Use case:** Limited event slots ("Raid Team" — max 20 members), exclusive tester roles, etc.

---

### Condition 3 — Cooldown Per User
A user can only click this button once per configured time window.

**Config:** Duration (e.g. 10 minutes, 1 hour, 24 hours, 7 days, once-ever).

**"Once-ever" mode:** The user can click the button exactly once across all time. They can never use it again — even if the role is removed. Use case: one-time welcome bonus roles, first-join event roles.

**How it works:**
- The bot stores the last click timestamp per (user, button) pair in the database
- On click: checks timestamp against the configured cooldown
- If within cooldown: blocks action, tells user how long to wait
- The cooldown is per-user — not per-role or per-server

---

### Condition 4 — Server Membership Duration
User must have been in the server for at least X days before they can use this button.

**Config:** Minimum days in the server (e.g. 7 days, 30 days).

**How it works:**
- Checks the user's join date against `today - minimum_days`
- If they joined too recently: blocks with a message showing how many days remain
- Use case: "OG member" exclusive roles, anti-raid protection on role panels

---

### Condition 5 — Account Age Minimum
User's Discord account must be at least X days old.

**Config:** Minimum account age in days.

**How it works:**
- Checks Discord account creation date (extracted from the user's snowflake ID)
- Blocks new/suspicious accounts from self-assigning roles on invite-abuse-prone panels
- Use case: any public-facing role panel on a large server

---

### Condition 6 — Active Shop Hours Only
Button only functions during configured active hours.

**Config:** Start time, end time, timezone (same as the shop schedule system).

**Outside hours:** Button appears in the panel but is visually disabled (greyed out) and shows: *"This button is only available Mon–Fri, 9AM–6PM PHT."*

**Use case:** Event registration panels that should only be active during a specific window. Slot claims on commission panels.

---

### Subfeatures (Sorted by Priority)

**5.1 — Required Role Condition** *(Highest)*
The single most requested feature for role panels. Gate roles behind other roles.

**5.2 — Role Capacity Limit** *(High)*
Limited-slot roles. No other Discord bot does this well at the button level.

**5.3 — Per-User Cooldown** *(High)*
Prevents rapid-fire role toggling and abuse.

**5.4 — Once-Ever Mode** *(High)*
True one-time buttons. Can't be replicated with cooldowns alone.

**5.5 — Server Membership Duration** *(Medium)*
Anti-raid protection. Simple but highly effective.

**5.6 — Account Age Minimum** *(Medium)*
First line of defense against bot accounts and alt abuse on public panels.

**5.7 — Conditions Preview in Builder** *(Medium)*
After configuring conditions, the builder shows a plain-English summary: *"Users must: Have @Verified · Be in server 7+ days · Have not used this button before."*

**5.8 — Active Hours Condition** *(Low)*
Time-gated buttons. Useful for event panels and commission slot opens.

---
---

# 6. Select Menu Roles (Dropdown Role Selector) 🟠 High

## What Mimu Does
Role selection is buttons only. If you have 15 color roles, you need 15 buttons — which takes up 3 full button rows and dominates the panel visually. There's no dropdown alternative.

## The Improvement
Support **Discord Select Menus** (dropdowns) as an alternative to button rows for role assignment. A single dropdown can list up to 25 role options in a clean, compact menu.

## How It Works

In the panel builder, instead of adding a button to a row, staff can add a **Select Menu Row** — a full-width dropdown that replaces an entire button row.

**Creating a select menu:**
```
/selectmenu create
```
Opens a builder for the dropdown specifically:
- **Placeholder text:** the greyed text shown before a selection is made (e.g. "Pick your color role...")
- **Min selections:** minimum options a user must pick (usually 0 or 1)
- **Max selections:** maximum options at once (e.g. 1 for exclusive, up to 25 for multi-select)
- **Options:** each option has a label, optional emoji, optional description, and a role to assign

**Example — Color Role dropdown:**
```
Pick your color role...  ▼
  🔴  Red
  🔵  Blue
  🟢  Green
  🟡  Yellow
  🟣  Purple
  ⚫  Black
```

**Behavior:**
- User opens the dropdown, picks one (or more, depending on max selections config)
- Confirms with the "Select" button (Discord's default behavior)
- Bot processes each selected option: assigns the corresponding role
- Deselected options from a previous interaction have their roles removed (if "sync" mode is on)

**Sync mode:** If a user previously selected Blue and now selects Red, sync mode removes `@Blue` and assigns `@Red`. Without sync, roles only accumulate.

**Select menus and buttons can coexist on the same panel** — e.g., a panel with a color dropdown in row 1 and notification toggle buttons in rows 2–3.

---

### Subfeatures (Sorted by Priority)

**6.1 — Single-Select Dropdown (Pick Exactly One)** *(Highest)*
Max selections = 1. Classic "pick one exclusive role" use case. Replaces entire button rows for large role sets.

**6.2 — Multi-Select Dropdown (Pick Multiple)** *(High)*
Max selections > 1. Users pick up to N roles at once. Great for interest/ping role panels.

**6.3 — Option Descriptions** *(High)*
Each dropdown option can have a short description (max 100 chars) shown below the label. Example: `🎨 Artist` — *"For members who share their artwork."* Provides context without cluttering the panel embed.

**6.4 — Sync Mode (Remove Deselected Roles)** *(High)*
When the user changes their selection, previously selected roles are removed. Keeps the user's role state in sync with their dropdown choice.

**6.5 — Minimum Selection Enforcement** *(Medium)*
Configure a minimum — user must pick at least 1 option before the dropdown submits. Useful for required profile-building panels.

**6.6 — Conditions on Select Menus** *(Medium)*
Same condition system as buttons (Feature 5) applies to the whole select menu — required role, cooldown, account age, etc.

**6.7 — Per-Option Conditions** *(Low)*
Individual options within a dropdown can have their own conditions — e.g., the "Premium" option in a tier dropdown only appears for Nitro Boosters. Non-eligible options are shown as disabled in the menu (greyed out with a tooltip explaining why).

---
---

# 7. Button and Panel Analytics 🟠 High

## What Mimu Does
No tracking at all. Buttons are posted and interactions happen invisibly. You have no idea which roles are most popular, which buttons get clicked, how many people have used a panel, or whether the role distribution is balanced.

## The Improvement
Every button click is logged. A simple analytics command surfaces usage data per button, per panel, and per role.

## How It Works

**Per-button stats:**
```
/button stats id:BTN-003
```
```
📊 Stats — BTN-003 (🎮 Gamer)

Total clicks (all time):     342
Unique users who clicked:    289
Current role holders:        267 (via this button)
Clicks this month:           41
Last clicked:                Today at 3:22 PM by @user
Conditions blocked:          18 clicks (5%)
Cooldown blocked:            7 clicks
```

**Per-panel stats:**
```
/panel stats id:PANEL-001
```
Shows the same metrics for every button in the panel, ranked by click count — so you can see at a glance which roles are most popular and which buttons nobody touches.

**Role distribution view:**
```
/panel stats id:PANEL-001 view:roles
```
Shows each role's current member count as a bar chart (ASCII or embed fields):
```
🎮 Gamer          ████████████████████ 267
📖 Reader         ██████████ 134
🎵 Music          ███████ 98
🔔 Announcements  ████ 54
```

---

### Subfeatures (Sorted by Priority)

**7.1 — Click Count per Button** *(Highest)*
Total and monthly click counts. The baseline metric.

**7.2 — Unique User Count** *(High)*
Distinguishes between "342 total clicks" and "289 unique people used this button." Tells you reach vs. repeat usage.

**7.3 — Conditions Block Rate** *(High)*
How often users are hitting the conditions gate. A high block rate signals that users are trying to get a role they can't have — which might mean the conditions should be relaxed, or the panel description needs to explain requirements better.

**7.4 — Role Distribution Chart** *(Medium)*
Visual breakdown of how many people have each role in a panel. Identifies imbalances — if 90% of users picked the same option, maybe you need more variety.

**7.5 — Server-Wide Button Report** *(Medium)*
`/button stats all` — a ranked list of every button by total clicks. Quickly surfaces underused buttons that can be removed.

**7.6 — Export Stats as CSV** *(Low)*
`/button stats id:BTN-003 export:csv` — sends a `.csv` file with daily click counts for the last 90 days. For server owners who want to visualize trends externally.

---
---

# 8. Panel Version History and Safe Editing 🟠 High

## What Mimu Does
No history. If you accidentally save the wrong button to a panel, add the wrong role action, or delete a button that was actively being used — it's permanent. The only recovery is rebuilding from scratch.

## The Improvement
Panels (and their buttons) have a **rolling version history**. Every save creates a snapshot. Staff can preview and restore any previous version.

## How It Works

Every time a panel or button is saved, the bot snapshots the entire state. This includes the embed reference, every button configuration, row layout, conditions, and response messages.

**Viewing panel history:**
```
/panel history id:PANEL-001
```
```
Version History — PANEL-001

v4  ·  Today at 3:44 PM  ·  BTN-003 action changed  ·  by @kim     ← current
v3  ·  Today at 3:41 PM  ·  BTN-005 added           ·  by @kim
v2  ·  Apr 12 at 11:02   ·  EMB-003 reassigned      ·  by @iara
v1  ·  Apr 12 at 10:30   ·  Panel created            ·  by @iara

[ Preview v3 ]   [ Restore v3 ]
```

**Previewing a version:** Shows the rendered panel (embed + button layout) as it was at that point in time.

**Restoring:** Copies all config from the selected version back to the current state. Creates a new version entry: *"v5 — Restored from v3."*

**Button-level history:**
`/button history id:BTN-003` — same but scoped to a single button's configuration changes.

---

### Subfeatures (Sorted by Priority)

**8.1 — Auto-Snapshot on Every Save** *(Highest)*
No staff action required. Every save silently creates a version.

**8.2 — Version Preview** *(High)*
Render any historical version as a full panel preview before deciding to restore.

**8.3 — One-Click Restore** *(High)*
Restore with a confirmation step. Creates a new version entry so the restore itself is auditable.

**8.4 — Change Summary per Version** *(Medium)*
Each version entry describes what changed: "BTN-003 action changed from Toggle Role to Exclusive Select," "BTN-005 added," "Conditions updated." Readable at a glance.

**8.5 — 10-Version Cap** *(Medium)*
Keep the last 10 versions per panel and per button. Older ones are pruned automatically. Keeps the database clean.

---
---

# 9. Role Assignment Log and Audit Trail 🟠 High

## What Mimu Does
No logging. Role assignments via button happen silently. If a user gains a role they shouldn't have, or claims they never clicked a button, there's no record to reference. Moderation of button-based role abuse has no evidence trail.

## The Improvement
Every button click that results in a role change is logged — who clicked, which button, which panel, which role was added or removed, and when.

## How It Works

**Log destination:** A configurable private `#role-assignment-log` channel. The bot posts an embed for each role change event:

```
🔘 Role Assigned via Button

User:     @username (#0001)
Button:   BTN-003 (🎮 Gamer)
Panel:    PANEL-001 (Welcome Panel)
Role:     @Gamer
Action:   Assigned
Channel:  #get-roles
Time:     April 14, 2026 at 3:22 PM
```

**Lookup commands:**
- `/rolelog user:@username` — all role changes for a specific user via buttons
- `/rolelog button:BTN-003` — all interactions with a specific button
- `/rolelog role:@Gamer` — all assign/remove events for a specific role via buttons

**Blocked attempts are also logged** (optionally, togglable to reduce noise):
```
🚫 Role Assignment Blocked

User:     @username
Button:   BTN-009 (💎 Premium)
Reason:   Conditions not met — Missing @Verified role
Time:     April 14, 2026 at 3:25 PM
```

---

### Subfeatures (Sorted by Priority)

**9.1 — Role Change Log Channel** *(Highest)*
All assign and remove events posted to a configurable private channel.

**9.2 — User Role History Lookup** *(High)*
`/rolelog user:@username` — all role changes via buttons, paged, newest first.

**9.3 — Blocked Attempt Logging (Toggleable)** *(Medium)*
Log failed attempts separately. Toggle off if a high-traffic panel makes it too noisy.

**9.4 — Log Retention and Pruning** *(Medium)*
Logs are stored in the database. Entries older than 90 days are auto-pruned (configurable). Prevents unbounded growth.

**9.5 — Role Abuse Detection** *(Low)*
If a user triggers more than N button interactions within a short window (e.g. 20 clicks in 60 seconds), the bot flags it as suspicious, blocks further clicks from that user for a cooldown period, and alerts staff: *"⚠️ @user is interacting with role buttons unusually fast — possible abuse."*

---
---

# 10. Button Import / Export and Cross-Panel Reuse 🟡 Medium

## What Mimu Does
Buttons are created per-server with no portability. If you want the same button (same label, action, conditions) on multiple panels, you create it multiple times. There's no way to share button configs between servers.

## The Improvement
Buttons and panels can be **exported as JSON** and imported into any server. A button can also be **linked to multiple panels** without duplicating its config.

## How It Works

**Export:**
```
/button export id:BTN-003
/panel export id:PANEL-001
```
Bot sends a `.json` file with the full config. For a panel export, all linked button configs are included in the same file.

**Import:**
```
/button import
/panel import
```
Staff attach the `.json` file. Bot previews what will be created and asks for confirmation. New IDs are assigned on import.

**Reuse — Linking one button to multiple panels:**
A button with ID `BTN-003` doesn't have to be duplicated to appear in two panels. In the panel builder, when adding a button to a row, staff can either:
- Create a new button inline
- **Link an existing button by ID** — the panel references `BTN-003` directly

When `BTN-003`'s config is edited (label, action, conditions), the change is reflected in every panel that references it — without touching each panel individually.

**Use case:** A universal "📢 Announcements" notification button that appears at the bottom of every role panel in the server. Edit it once, it updates everywhere.

---

### Subfeatures (Sorted by Priority)

**10.1 — Button Export / Import** *(Highest)*
Portable button configs. Share between servers or back up.

**10.2 — Panel Export / Import** *(Highest)*
Full panel (embed reference + all buttons + layout) as one exportable unit.

**10.3 — Shared Button References Across Panels** *(High)*
One button, many panels. Edit once, update everywhere. No duplication.

**10.4 — Import Preview Before Commit** *(Medium)*
See what will be created before confirming the import.

**10.5 — Export All Buttons / All Panels** *(Medium)*
Bulk export for full server backup.

---
---

# 11. Panel Scheduling and Expiry 🟡 Medium

## What Mimu Does
Panels are posted manually. There's no way to schedule a panel to post itself at a future time, or to have a panel automatically expire after an event ends.

## The Improvement
Panels can be **scheduled** to post at a future date and **expire** (auto-disable or auto-delete) at a configured time.

## How It Works

**Scheduling:**
```
/panel schedule id:PANEL-001 channel:#events date:2026-05-01 time:18:00
```
At the configured time, the bot posts the panel exactly as `/panel show` would. Post is tracked for live editing (from Feature 4).

**Expiry:**
When scheduling (or when using `/panel show`), add an expiry:
```
/panel show id:PANEL-001 channel:#events expires:2026-05-03 on-expire:disable
```

**On-expire actions:**

| Action | What Happens |
|---|---|
| `disable` | All buttons on the panel are disabled (greyed out). Panel message stays. A note is appended to the embed footer: *"Registration closed."* |
| `delete` | The posted panel message is deleted entirely |
| `replace-with:PANEL-XXX` | The message is swapped for a different panel (e.g. "Event registration" → "Event full / registration closed") |

**Use case:** Post an event registration panel on May 1 and have it auto-disable on May 3 when slots close — without anyone manually touching it.

**Viewing scheduled panels:**
```
/panel schedule list
```
Shows all panels with active schedules or expiry timers.

---

### Subfeatures (Sorted by Priority)

**11.1 — One-Time Scheduling** *(Highest)*
Post a panel at a future date and time. Most common use case.

**11.2 — Expiry with Disable Action** *(High)*
Buttons grey out after expiry. Panel stays but becomes non-interactive. Clean, informative.

**11.3 — Expiry with Replace Action** *(High)*
Swap to a different panel on expiry. Event-based role panels (before/after open).

**11.4 — Expiry Warning to Staff** *(Medium)*
24 hours before an expiry fires, staff receive an ephemeral reminder in the configured log channel: *"PANEL-001 in #events will expire tomorrow at 6:00 PM. Action: disable."*

**11.5 — Schedule List View** *(Medium)*
`/panel schedule list` — all active schedules and expiries in one overview.

---
---

# 12. Persistent Buttons After Bot Restart 🟡 Medium

## What Mimu Does
Mimu's buttons use Discord's persistent component system — buttons registered on startup continue to work after a restart. However, if a button's action or configuration has changed in the bot's memory, the persistent handler may respond with the old behavior or fail silently until the panel is reposted.

## The Improvement
Buttons always pull their configuration **live from the database** at click time — never from cached memory. This means button behavior is always current, even after a restart, a config update, or a hot-reload.

## How It Works

**Current problem with memory-cached buttons:**
- Bot restarts → memory is cleared → persistent views are re-registered on boot
- But if the button config was changed between restarts (e.g. a new condition was added) and the persistent view re-registration uses stale code, the button runs the old behavior until the panel is manually reposted

**The improvement:**
- Every button interaction handler is a thin wrapper that: 1) receives the interaction, 2) reads the button's config from the database by the button ID, 3) evaluates conditions, 4) runs the action
- No config is cached in memory — the DB is the single source of truth at all times
- This means you can update a button's conditions or response messages at 3pm and the very next click — even on a message posted 6 months ago — uses the new config

**Why this matters:**
- A staff member updates the "Exclusive" condition on a role panel button
- Under memory-cached system: existing posted panels might use old behavior until reposted
- Under DB-live system: the update is reflected immediately on all existing posted panels, no repost needed

---

### Subfeatures (Sorted by Priority)

**12.1 — Live DB Lookup on Every Click** *(Highest)*
Config is always read from the database, never from initialized memory. Instant config propagation.

**12.2 — Button-Not-Found Handling** *(High)*
If a button ID no longer exists in the database (the button was deleted but the panel message is still live), the interaction returns a clear ephemeral error: *"This button is no longer active."* No silent failure.

**12.3 — Panel-Disabled State Persistence** *(High)*
If a panel is expired or manually disabled, that state is stored in the database. After a bot restart, all expired panels remain disabled — their buttons return "This panel is no longer active" without needing to re-disable them.

---
---

# 13. Per-Button Role Removal on Panel Edit 🟡 Medium

## What Mimu Does
No management of existing role holders when buttons or panels change. If you remove a button from a panel (e.g. you're retiring a color option), everyone who has that role keeps it forever — there's no cleanup mechanism.

## The Improvement
When a button is removed from a panel, staff are offered the option to **retroactively remove that role from all current holders.**

## How It Works

When staff remove a button from a panel (via the panel builder), the bot asks:

```
You're removing BTN-005 (🟣 Purple) from PANEL-001.

@Purple is currently assigned to 34 members via this button.

What should happen to existing role holders?

[ Keep their roles ]   [ Remove @Purple from all 34 members ]
```

Selecting "Remove roles":
- The bot iterates through all members with `@Purple` and removes it
- A progress indicator in the ephemeral builder message shows the sweep: *"Removing @Purple from members: 34/34 done."*
- A summary is logged: *"Retroactive role removal: @Purple removed from 34 members on Apr 14 by @kim."*
- The audit log (Feature 9) records each individual removal with the reason "Panel button removed"

**Keep their roles** (default): No change to existing holders. The role just can no longer be self-assigned going forward.

---

### Subfeatures (Sorted by Priority)

**13.1 — Retroactive Remove Prompt on Button Deletion** *(Highest)*
The key interaction — give staff the choice, don't make it automatic.

**13.2 — Member Count in Prompt** *(High)*
Show exactly how many people would be affected before confirming. Prevents surprise.

**13.3 — Removal Audit Log Entry** *(High)*
Record the retroactive sweep — who authorized it, when, how many members affected.

**13.4 — Undo Window** *(Low)*
After a retroactive removal, a 5-minute undo button appears in the ephemeral builder. Clicking it re-assigns the role to all affected members (from the stored list). Prevents fat-finger disasters.

---
---

# 14. Temporary / Timed Role Buttons 🟢 Low

## What Mimu Does
Role assignments are permanent — clicking a button gives you a role and you keep it until it's removed manually, by another button, or by a staff member. There's no concept of a time-limited role assignment via button.

## The Improvement
Buttons can optionally assign a role **for a limited time.** After the configured duration, the role is automatically removed from the user.

## How It Works

In the button builder's action config (Feature 2), when setting up an Assign or Toggle action, an optional **Duration** field appears:

| Duration | What It Means |
|---|---|
| (blank) | Role is permanent — current behavior |
| `1h` | Role is removed after 1 hour |
| `24h` | Role is removed after 24 hours |
| `7d` | Role is removed after 7 days |

**When a user clicks a timed button:**
- Role is assigned immediately
- A timed expiry record is saved: `(user, role, expire_at)`
- A background task runs every minute checking for expired role assignments
- When the time is up: role is removed and the user receives a DM: *"Your temporary @Event Attendee role has expired."*

**The button response message** (Feature 3) automatically includes the expiry time when a duration is configured: *"✅ @Event Attendee assigned! This role expires in 24 hours."*

**Staff can view active temporary role assignments:**
```
/temproles list
```
Shows all users with active timed roles and when each expires.

**Staff can extend or cancel:**
```
/temproles extend user:@username role:@EventAttendee duration:12h
/temproles revoke user:@username role:@EventAttendee
```

---

### Subfeatures (Sorted by Priority)

**14.1 — Timed Role Expiry Engine** *(Highest)*
Background task that processes expired role assignments. The foundation that makes everything else in this feature work.

**14.2 — DM Notification on Expiry** *(High)*
User is told when their timed role expires — they're not surprised to find it missing later.

**14.3 — Duration in Success Response** *(High)*
The click confirmation tells the user how long they have the role.

**14.4 — Active Temp Role List** *(Medium)*
`/temproles list` for staff visibility into who has timed roles and when they expire.

**14.5 — Staff Extend / Revoke Controls** *(Medium)*
Manual override for edge cases — event that's running long, early exit, etc.

---
---

## Quick Reference — All Features

| # | Feature | Priority | What Mimu Lacks |
|---|---|---|---|
| 1 | Button Builder Interface | 🔴 Critical | Buttons only configurable via raw slash commands |
| 2 | Button Action Types | 🔴 Critical | Only 3 actions: assign, remove, toggle |
| 3 | Button Response Messages | 🔴 Critical | No custom feedback on click — generic Discord ack only |
| 4 | Panel Builder | 🔴 Critical | No saved panel concept — one-time send command only |
| 5 | Button Conditions | 🟠 High | Every button works for every user with no restrictions |
| 6 | Select Menu Role Dropdowns | 🟠 High | Buttons only — no dropdown alternative |
| 7 | Button and Panel Analytics | 🟠 High | No tracking of any button or role interaction |
| 8 | Panel Version History | 🟠 High | All saves are permanent — no undo |
| 9 | Role Assignment Audit Log | 🟠 High | No record of who clicked what, when |
| 10 | Button Import / Export | 🟡 Medium | No portability or cross-panel reuse |
| 11 | Panel Scheduling and Expiry | 🟡 Medium | Panels must be posted and removed manually |
| 12 | Persistent Buttons After Restart | 🟡 Medium | Config changes may not reflect on live buttons |
| 13 | Retroactive Role Removal on Edit | 🟡 Medium | Removing a button leaves all role holders untouched |
| 14 | Temporary / Timed Role Buttons | 🟢 Low | All role assignments are permanent |
