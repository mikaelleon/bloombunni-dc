# Autoresponder System — Full Feature Specification
### Core Mimu Features (Kept) + Improvements
### Sorted by Priority · One Section Per Feature

---

> **What this document is:** The complete autoresponder feature spec for the custom bot. Every feature Mimu has that we want to keep is marked **✅ Parity**. Everything we're building on top of or improving is marked **✅ Improved** or **➕ New**. Nothing from Mimu gets dropped — this extends it.

---

## How to Read This Document

| Tag | Meaning |
|---|---|
| ✅ **Parity** | Exists in Mimu, implemented the same way |
| ✅ **Improved** | Exists in Mimu, but works better here |
| ➕ **New** | Does not exist in Mimu at all |

## Priority Scale

| Label | Meaning |
|---|---|
| 🔴 Critical | Core to the system functioning at all |
| 🟠 High | Major capability or significant improvement |
| 🟡 Medium | Quality-of-life; makes things noticeably better |
| 🟢 Low | Power-user feature; useful in specific situations |

---

## Quick Reference — Mimu's Full Feature Set

Everything Mimu can do, at a glance, so nothing gets missed:

| Mimu Feature | Status in Custom Bot |
|---|---|
| `/autoresponder add trigger: reply:` | ✅ Improved — builder interface instead |
| `/autoresponder editreply` | ✅ Improved — modal-based, field-targeted |
| `/autoresponder remove` | ✅ Parity |
| `/autoresponder list` | ✅ Improved — with status, labels, filter |
| `/autoresponder editmatchmode` | ✅ Parity + more modes |
| Match modes: exact, startswith, endswith, includes | ✅ Parity |
| All user/server/channel/message placeholders | ✅ Parity |
| `[$N]` `[$N+]` `[$N-Z]` argument variables | ✅ Parity |
| `{range:}` / `[range]` — up to 4 | ✅ Parity |
| `{choose:}` / `[choice]` — up to 4 | ✅ Parity |
| `{weightedchoose:}` | ✅ Parity |
| `{lockedchoose:}` / `[lockedchoice]` | ✅ Parity |
| `{requirearg:}` with type validation | ✅ Parity |
| `{embed:}` / `{embed:#hexcolor}` | ✅ Parity |
| `{dm}` — redirect response to DM | ✅ Parity |
| `{sendto:#channel}` — redirect to channel | ✅ Parity |
| `{delete}` — delete triggering message | ✅ Parity |
| `{delete_reply:N}` — delete bot reply after N seconds | ✅ Parity |
| `{silent}` — suppress error messages | ✅ Parity |
| `{cooldown:}` — per-user cooldown in seconds | ✅ Improved — also configurable in builder |
| `{requirerole:}` | ✅ Parity |
| `{denyrole:}` | ✅ Parity |
| `{requirechannel:}` | ✅ Parity |
| `{denychannel:}` | ✅ Parity |
| `{requireuser:}` | ✅ Parity |
| `{requireperm:}` | ✅ Parity |
| `{denyperm:}` | ✅ Parity |
| `{requirebal:}` | ✅ Parity |
| `{requireitem:}` | ✅ Parity |
| `{addrole:}` with optional user arg | ✅ Parity |
| `{removerole:}` with optional user arg | ✅ Parity |
| `{modifybal:}` with math operators and user arg | ✅ Parity |
| `{modifyinv:}` with add/remove and user arg | ✅ Parity |
| `{setnick:}` with optional user arg | ✅ Parity |
| `{react:}` and `{reactreply:}` | ✅ Parity |
| `{addbutton:name}` — attach button to response | ✅ Improved — picker-based, no syntax required |
| `{addlinkbutton:label\|url}` — link button | ✅ Parity |
| `/buttonresponder add` — static button creation | ✅ Improved — builder interface |
| Button: name, reply, label, emoji, color | ✅ Parity |
| Button limitations: none / limited / strict | ✅ Parity |
| Button invoker_only | ✅ Parity |
| `/send content:{embed:}{addbutton:} channel:#ch` | ✅ Improved — panel builder replaces this |

---
---

# 1. Autoresponder Creation and Basic Management 🔴 Critical

## What Mimu Does

Creating an AR requires typing the full trigger and response in one slash command:
```
/autoresponder add trigger:hi mimu! reply:hey cutie!
```
Editing the response is a separate command. Editing the matchmode is another separate command. There is no preview, no interactive interface, and errors in the original command require a full re-type.

```
/autoresponder editreply trigger:hi mimu! reply:heya there, cutie!
/autoresponder editmatchmode trigger:hi mimu! matchmode:startswith
/autoresponder remove trigger:hi mimu!
/autoresponder list
```

## The Improvement

All creation and editing happens in an **interactive builder interface** — buttons open modals for each field, a live preview updates after every change, and the AR is saved automatically. The trigger and matchmode are configured in the same builder session, not across three separate commands.

## How It Works

```
/ar create
```

Opens the builder message with a button for every configurable property:

```
Autoresponder Builder — AR-001

[ ⚡ Trigger + Matchmode ]   [ 💬 Response ]   [ 📋 Embed ]
[ 🔘 Buttons ]               [ ⚙️ Functions ]   [ 🔒 Conditions ]
[ 📖 Variables Reference ]

[ 👁️ Preview ]   [ ✅ Done ]   [ 🗑️ Discard ]
```

**Auto-assigned IDs:** `AR-001`, `AR-002`, etc. No manual naming. No 16-character limits.

**Preview** renders the full response — text, embed, buttons — exactly as a member would see it, updating live after every field save.

---

### Subfeatures (Sorted by Priority)

**1.1 — `/ar create` with Builder Interface** *(Highest)* ✅ Improved
Interactive modal builder instead of a single slash command string. Trigger, matchmode, response, and all functions configured in one unified session.

**1.2 — Auto-Assigned AR IDs** *(Highest)* ➕ New
`AR-001`, `AR-002`, etc. Consistent with embed (`EMB-XXX`) and button (`BTN-XXX`) ID patterns.

**1.3 — Live Response Preview** *(Highest)* ➕ New
Full rendered preview of the response (text + embed + buttons) before the AR goes live. Updates after every modal save.

**1.4 — `/ar edit id:AR-003`** *(High)* ✅ Improved
Reopens the full builder for any existing AR. Optional field targeting: `/ar edit id:AR-003 field:trigger` opens just the trigger modal.

**1.5 — `/ar delete id:AR-003`** *(High)* ✅ Parity (with confirmation step)
Adds a confirmation prompt before deletion: shows a summary of what the AR does and asks "Are you sure?" Prevents accidental deletion.

**1.6 — `/ar list`** *(High)* ✅ Improved
Compact table of all ARs — ID, internal label, trigger summary, creator, and status (Active/Paused/Disabled). Mimu's list shows only trigger phrases in a flat text list.

**1.7 — Internal Label and Note per AR** *(Medium)* ➕ New
Staff-only label (e.g. "Welcome FAQ trigger") and a longer note (e.g. "Fires in #general only. Pairs with EMB-003."). Never visible to members.

**1.8 — Builder Session Lock** *(Medium)* ➕ New
Only one active builder session per AR at a time. A second staff member sees: *"AR-003 is currently being edited by @Username."*

---
---

# 2. Trigger and Matchmode System 🔴 Critical

## What Mimu Does

Triggers are set in `/autoresponder add`. Matchmode is set separately in a second command after creation:

```
/autoresponder editmatchmode trigger:hi mimu! matchmode:startswith
```

**Four matchmodes available:**
- **Exact** — full message must match the trigger exactly (case-insensitive). Default.
- **Startswith** — message begins with the trigger. Used for commands with arguments (e.g. `!cuddle @user`)
- **Endswith** — message ends with the trigger
- **Includes** — message contains the trigger anywhere (e.g. anti-swear)

One trigger per AR. No way to have multiple triggers map to the same response.

## The Improvement

Matchmode is set in the same builder session as the trigger — no second command needed. Multiple trigger phrases can be assigned to one AR (trigger groups). Two new matchmodes are added. Non-message event triggers (member join, leave, role assigned, reaction) are added as trigger types.

## How It Works

The ⚡ **Trigger + Matchmode** button in the builder opens a modal with:
- A **trigger type selector** (Message / Member Join / Member Leave / Role Assigned / Reaction)
- The trigger phrase(s) input
- The matchmode selector (for message triggers)

---

### Matchmodes ✅ Parity + Improved

**2.1 — Exact** *(Parity)*
Full message must equal the trigger exactly. Case-insensitive. Default.

**2.2 — Startswith** *(Parity)*
Message begins with trigger. Used for argument-based commands (`!kiss @user`, `.verify @user`).

**2.3 — Endswith** *(Parity)*
Message ends with trigger.

**2.4 — Includes** *(Parity)*
Message contains the trigger anywhere. Used for keyword detection, anti-swear.

**2.5 — Word Boundary** *(New)* ➕
Like `includes` but only matches the trigger as a whole word — not as part of another word. `!help` won't fire on `!helpful`. Prevents accidental partial matches.

---

### Trigger Groups ✅ Improved

**2.6 — Multiple Phrases → One AR** *(Highest)* ➕ New

**The problem with Mimu:** One trigger = one AR. If "how do I pay", "payment method", "how to pay", and "where do I send money" should all give the same payment embed, you need four separate ARs in Mimu — four things to update every time the response changes.

**The improvement:** In the Trigger modal, staff enter multiple phrases (one per line). All of them map to the same AR and the same response. Edit the response once — all triggers update.

The AR list shows the group collapsed: *"Triggers: 'how to pay' + 3 others"*

---

### Non-Message Event Triggers ➕ New

**2.7 — Member Join Trigger** *(High)*
Fires automatically when a new member joins the server. No message needed from the member. Pairs with `{user_mention}`, `{user_avatar}` for personalized welcome responses.

**Why this instead of a separate welcome system:** It goes through the full AR function system — same conditions, embed attachments, button attachments, cooldowns, and logging as any message-triggered AR. One unified system.

**2.8 — Member Leave Trigger** *(High)*
Fires when a member leaves (voluntarily or kicked — not banned). `{user_name}` is resolved at leave time from the stored username. `{server_membercount}` reflects the updated count.

**2.9 — Role Assigned Trigger** *(High)*
Fires when a specific role is assigned to a member — whether by button, staff command, or any other method.

Config: pick which role assignment triggers this AR.

Use cases:
- `@Verified` assigned → post a greeting in `#verified-chat` mentioning the user
- `@Nitro Booster` assigned → fire the boost congratulations embed
- `@Commission Client` assigned → DM the user with onboarding info

**How it works:** Bot listens to Discord's `member_update` event. On role add: checks if any AR has that role configured as its trigger. Fires the matching AR.

**2.10 — Reaction Added Trigger** *(Medium)*
Fires when a specific emoji reaction is added to any message in a configured channel (or a specific pinned message ID).

Config: emoji, channel (optional), specific message ID (optional).

---

### Trigger Priority ➕ New

**2.11 — Priority Ordering** *(Medium)*

**The problem:** If two ARs could both match the same message (AR-001 triggers on "commission" and AR-002 triggers on "commission price"), Mimu's behavior is undefined — staff have no control over which one fires.

**The improvement:** Each AR has an optional priority number (1 = highest). When multiple ARs match:
- Higher priority fires first
- If equal priority: more specific match wins (longer trigger phrase beats shorter)
- If still tied: both fire (configurable — "fire all" vs. "fire one")

Set in the builder's ⚙️ Behavior section.

---
---

# 3. Placeholders (Variables) 🔴 Critical

## What Mimu Does

Mimu has a rich, well-documented placeholder system. All of these are fully supported in the custom bot. This section lists every placeholder from Mimu's docs and marks additions.

## The Full Placeholder List

### User / Author Information ✅ Parity (all)

All user placeholders support the **extended function form** — `{placeholder:[$1]}` or `{placeholder:user_id}` — to target a different user (the first argument, or a specific user ID). This is preserved exactly.

| Placeholder | Returns | Status |
|---|---|---|
| `{user}` | User's @mention | ✅ Parity |
| `{user_tag}` | Username (tags deprecated by Discord) | ✅ Parity |
| `{user_name}` | Username | ✅ Parity |
| `{user_avatar}` | Avatar URL | ✅ Parity |
| `{user_discrim}` | Discriminator (deprecated) | ✅ Parity |
| `{user_id}` | User ID | ✅ Parity |
| `{user_nick}` | Server nickname | ✅ Parity |
| `{user_joindate}` | Date joined server | ✅ Parity |
| `{user_createdate}` | Date account created | ✅ Parity |
| `{user_displaycolor}` | Hex color in server | ✅ Parity |
| `{user_boostsince}` | Date boosting since | ✅ Parity |
| `{user_balance}` | Server currency balance | ✅ Parity |
| `{user_balance_locale}` | Balance with comma separator | ✅ Parity |
| `{user_item:name}` | Quantity + name of an inventory item | ✅ Parity |
| `{user_item_count:name}` | Quantity only of an inventory item | ✅ Parity |
| `{user_inventory}` | Full inventory list | ✅ Parity |

---

### Server Information ✅ Parity (all)

| Placeholder | Returns | Status |
|---|---|---|
| `{server_name}` | Server name | ✅ Parity |
| `{server_id}` | Server ID | ✅ Parity |
| `{server_membercount}` | Total member count | ✅ Parity |
| `{server_membercount_ordinal}` | Ordinal count (e.g. 203rd) | ✅ Parity |
| `{server_membercount_nobots}` | Member count without bots | ✅ Parity |
| `{server_membercount_nobots_ordinal}` | Ordinal without bots | ✅ Parity |
| `{server_botcount}` | Bot count | ✅ Parity |
| `{server_botcount_ordinal}` | Ordinal bot count | ✅ Parity |
| `{server_icon}` | Server icon URL | ✅ Parity |
| `{server_rolecount}` | Total role count | ✅ Parity |
| `{server_channelcount}` | Total channel count | ✅ Parity |
| `{server_randommember}` | Random member @mention | ✅ Parity |
| `{server_randommember_tag}` | Random member username | ✅ Parity |
| `{server_randommember_nobots}` | Random non-bot @mention | ✅ Parity |
| `{server_owner}` | Owner @mention | ✅ Parity |
| `{server_owner_id}` | Owner user ID | ✅ Parity |
| `{server_createdate}` | Server creation date | ✅ Parity |
| `{server_boostlevel}` | Boost tier (0–3) | ✅ Parity |
| `{server_boostcount}` | Number of boosts | ✅ Parity |
| `{server_nextboostlevel}` | Next boost tier | ✅ Parity |
| `{server_nextboostlevel_required}` | Boosts needed for next level | ✅ Parity |
| `{server_nextboostlevel_until_required}` | Remaining boosts needed | ✅ Parity |
| `{server_prefix}` | Server prefix (always `/`) | ✅ Parity |
| `{server_currency}` | Server currency emoji/name | ✅ Parity |

---

### Channel Information ✅ Parity (all)

| Placeholder | Returns | Status |
|---|---|---|
| `{channel}` | Channel mention (#channel-name) | ✅ Parity |
| `{channel_name}` | Channel name without # | ✅ Parity |
| `{channel_createdate}` | Channel creation date | ✅ Parity |

---

### Message Information ✅ Parity (all)

| Placeholder | Returns | Status |
|---|---|---|
| `{message_id}` | ID of the triggering message | ✅ Parity |
| `{message_content}` | Full content of the triggering message (same as `[$1+]` but includes the trigger word) | ✅ Parity |
| `{message_link}` | Direct link to the triggering message | ✅ Parity |

---

### Misc ✅ Parity (all)

| Placeholder | Returns | Status |
|---|---|---|
| `{date}` | Current date and time | ✅ Parity |
| `{newline}` | Line break (for slash command inputs where Enter submits) | ✅ Parity |

---

### Advanced Argument Placeholders ✅ Parity (all)

These only work when matchmode is not `exact` — the user types something after the trigger, and these reference those extra words.

| Placeholder | What It Returns | Example |
|---|---|---|
| `[$1]` | The 1st word after the trigger | `.cuddle [$1]` → user types `.cuddle @kim` → `[$1]` = `@kim` |
| `[$2]`, `[$3]`... | The Nth word after the trigger | |
| `[$1+]` | First word and everything after | `.say [$1+]` → everything the user wrote after `.say` |
| `[$2+]` | Second word and everything after | |
| `[$3-5]` | The 3rd, 4th, and 5th words | |
| `[range]` | Result of the `{range:}` function | |
| `[range1]`, `[range2]`, `[range3]` | Additional ranges | |
| `[choice]` | Result of the `{choose:}` function | |
| `[choice1]`, `[choice2]`, `[choice3]` | Additional choices | |
| `[lockedchoice]` | Result of `{lockedchoose:}` | |

---

### New Placeholders ➕ New

| Placeholder | Returns | Notes |
|---|---|---|
| `{trigger.channel}` | Channel where trigger fired | Use in cross-channel redirect ARs |
| `{trigger.channel_mention}` | Clickable channel link | |
| `{trigger.timestamp}` | When the trigger fired | |
| `{var.name}` | Value of a custom server variable | See Feature 4 — Custom Variables |
| `{counter.name}` | Current value of a counter variable | See Feature 4 — Counter Variables |
| `{if:condition\|true\|false}` | Conditional output | See Feature 4 — Conditional Variables |

---
---

# 4. Functions 🔴 Critical

## What Mimu Does

Functions are variables that perform actions rather than display information. They're embedded in the response string using `{}` syntax. Full list from Mimu's docs, all preserved.

## The Full Function List

### Formatting and Redirecting ✅ Parity (all)

**`{dm}`** — Redirects the entire response to the triggering user's DMs instead of the channel.

**`{sendto:#channel}`** — Sends the response to a different channel instead of where the trigger was used. Example: `{sendto:#logs}` sends the AR response to `#logs`.

**`{embed}`** — Wraps the text response in a plain Discord embed (no color, no title).
**`{embed:#hexcolor}`** — Embed with a custom left-border color. Example: `{embed:#ec948a}`
**`{embed:embed_name}`** — Uses a premade embed created with the embed system. ✅ Improved: references by embed ID (e.g. `{embed:EMB-003}`) — no manual name needed.

**`{silent}`** — Suppresses long-form error messages (permission errors, missing argument errors). ⚠️ Should only be used as a final polish step — errors are intentional guidance.
**`{silent:custom message}`** — Suppresses the error and shows a custom message instead.

---

### Auto-Deletions ✅ Parity (all)

**`{delete}`** — Deletes the triggering message. Used to keep channels clean after a command-like AR fires (e.g. `!rules` → bot posts rules → `{delete}` removes the `!rules` message).

**`{delete_reply:N}`** — Deletes the bot's own reply after N seconds. Example: `{delete_reply:10}` removes the response after 10 seconds.

---

### Permission / Access Control Functions ✅ Parity (all)

All of these can be stacked — use multiple in one AR to allow multiple roles, deny multiple channels, etc.

| Function | What It Does |
|---|---|
| `{requireuser:username}` or `{requireuser:user_id}` | AR only fires for a specific user |
| `{requireperm:permission}` | AR only fires if user has the Discord permission |
| `{requirechannel:#channel}` or `{requirechannel:channel_id}` | AR only fires in that channel |
| `{requirerole:@role}` or `{requirerole:role_id}` | AR only fires for users with that role |
| `{denychannel:#channel}` | AR ignores trigger in that channel |
| `{denyperm:permission}` | AR ignores trigger if user has that permission |
| `{denyrole:@role}` | AR ignores trigger if user has that role |
| `{requirebal:amount}` | AR only fires if user's balance is at least N |
| `{requireitem:item}` | AR only fires if user has item in inventory |
| `{requireitem:item\|amount}` | Requires specific quantity |
| `{requireitem:item\|amount\|[$1]}` | Checks another user's inventory |

---

### Miscellaneous Action Functions ✅ Parity (all)

**`{modifybal:+N}`** — Adds N to user's balance.
**`{modifybal:-N}`** — Subtracts N from balance.
**`{modifybal:=N}`** — Sets balance to exactly N.
**`{modifybal:*N}`** — Multiplies balance by N.
**`{modifybal:/N}`** — Divides balance by N.
**`{modifybal:+N|user}`** — Modifies another user's balance. Accepts username, user ID, or `[$1]`. Max ±100,000 per action, max 3 users.

**`{modifyinv:item|+N}`** — Adds N of an item to inventory.
**`{modifyinv:item|-N}`** — Removes N of an item.
**`{modifyinv:item|N|user}`** — Modifies another user's inventory.

**`{cooldown:N}`** — Sets a per-user cooldown of N seconds. If the same user triggers the AR within the cooldown window, it silently ignores them. Note: cooldowns appear in the user's `/cooldowns` list.

**`{addrole:@role}`** — Assigns a role to the triggering user.
**`{addrole:@role|[$1]}`** — Assigns a role to the user specified in the first argument.

**`{removerole:@role}`** — Removes a role from the triggering user.
**`{removerole:@role|[$1]}`** — Removes a role from a specified user.

**`{setnick:nickname}`** — Sets the triggering user's server nickname.
**`{setnick:nickname|[$1]}`** — Sets another user's nickname.

**`{react::emoji:}`** — Reacts to the triggering message with an emoji.
**`{reactreply::emoji:}`** — Reacts to the bot's reply message with an emoji.

**`{addbutton:button_name}`** ✅ Improved — Attaches a button to the response. In the custom bot, this is done via the button picker in the builder (no syntax required) but the function is also supported in raw response text for compatibility.

**`{addlinkbutton:label|url}`** ✅ Parity — Attaches a link-style button that opens a URL when clicked.

---

### Advanced Functions ✅ Parity (all)

**`{range:min-max}`**
Picks a random number between min and max. Stores the result in `[range]`.
- Up to 4 ranges: `{range:}`, `{range1:}`, `{range2:}`, `{range3:}`
- Must be declared before referencing `[range]` in the response
- Example: `{range:10-100} {modifybal:[range]} You earned [range] coins!`

**`{choose:option1|option2|option3}`**
Picks one option from a pipe-separated list. Stores result in `[choice]`.
- Up to 4 choose groups: `{choose:}`, `{choose1:}`, `{choose2:}`, `{choose3:}`
- Repeat an option to increase its probability: `{choose:rare|common|common|common}`
- Can embed ranges in choices: `{choose:[range]|[range1]|[range2]}`

**`{weightedchoose:20%|50%|30%}`**
Sets explicit percentage weights for a corresponding `{choose:}` list. Order must match the choose options.

**`{lockedchoose:a|b|c|d|e|f}`**
Forces a choice from this list that corresponds to the position of the result chosen in `{choose:}`. If `{choose:}` picked the 3rd option, `{lockedchoose:}` picks the 3rd option from its own list. Stores in `[lockedchoice]`.
- Up to 4: `{lockedchoose:}`, `{lockedchoose1:}`, `{lockedchoose2:}`, `{lockedchoose3:}`

**`{requirearg:N}`**
Requires the user to have provided at least N arguments. Shows a clear error if they haven't.

**`{requirearg:N|type}`**
Also validates the type. Supported types:
- `user` — must be a valid @mention or username
- `channel` — must be a valid channel
- `role` — must be a valid @role
- `number` — must be a numeric value
- `color` — must be a valid hex code

Best practice: always use `{requirearg:}` when building argument-based ARs. It gives users a readable error instead of a broken response.

---

### New Functions ➕ New

**`{escape_mentions}`** — Strips all role and user mentions from `[$N]` arguments before they appear in the response. Prevents users from abusing argument-based ARs to cold-ping roles the bot has permission to mention. *(In Mimu, the recommended workaround is using `{embed:}` since embeds suppress mentions — this function makes it explicit.)*

**`{require_no_role:@role}`** — The inverse of `{requirerole:}`. AR only fires if the user does NOT have this role. Same as `{denyrole:}` but with explicit error messaging rather than silent skip.

**`{once}`** — AR fires for a user exactly once, ever. After that, their triggers are permanently ignored. Stored per (user, AR) pair in the database. Use case: first-join onboarding, one-time welcome bonus.

**`{globalcooldown:N}`** — One cooldown shared across all users. The AR can only fire once per N seconds server-wide, regardless of who triggers it. Prevents channel flooding when many users type the same trigger simultaneously.

---
---

# 5. Button Responders 🔴 Critical

## What Mimu Does

**Static button responders** are created with:
```
/buttonresponder add name:role_panel1 reply:{addrole:@pink}{embed} you now have the pink role! label:pink color:grey emoji::pink_heart:
```

They support the same function system as message ARs (`{addrole:}`, `{removerole:}`, `{embed:}`, `{cooldown:}`, `{requirerole:}`, etc.).

**Settings:**
- `name` — reference ID (not what's shown on the button)
- `reply` — the response when clicked (supports all functions)
- `label` — text shown on the button
- `emoji` — emoji shown on the button (must have label, emoji, or both)
- `color` — Blue (default), Green, Grey, Red

**`limitations` setting:**
- **None** — button never disables
- **Limited** — button disables for that specific user after they click it
- **Strict** — all buttons in the same message disable for everyone after any one click

**`invoker_only` setting:**
- **No limit** — any server member can click the button
- **Invoker only** — only the person who triggered the AR (or who joined/boosted) can click it

**Attaching buttons to a message** (static panels):
```
/send content:{embed:choose_color}{addbutton:role_panel1}{addbutton:role_panel2}{addbutton:role_panel3} channel:#choose-roles
```

## The Improvement

Button responders get a full **interactive builder interface** — same as the main AR builder. The `/send` panel command is replaced by the **Panel Builder** system (a dedicated panel object, not a one-time send command). All existing Mimu button behavior (limitations, invoker_only, full function access) is preserved and extended.

## How It Works

**Creating a button:**
```
/button create
```
Opens the button builder — modal fields for label, emoji, color, reply, limitations, and invoker_only. Live button preview renders after every change.

**Creating a panel (embed + buttons):**
```
/panel create
```
Panel builder — pick an embed by ID, add button rows (up to 5 rows of 5 buttons each), preview the full combined result, then post it.

---

### Subfeatures (Sorted by Priority)

**5.1 — Button Builder Interface** *(Highest)* ✅ Improved
Interactive modal builder instead of a raw slash command string. Same fields as Mimu (name, reply, label, emoji, color, limitations, invoker_only) — just configured interactively with a live preview.

**5.2 — Full Function Parity in Button Reply** *(Highest)* ✅ Parity
`{addrole:}`, `{removerole:}`, `{embed:}`, `{cooldown:}`, `{requirerole:}`, `{denyrole:}`, `{modifybal:}`, `{sendto:}`, `{dm}` — all functions available in message ARs also work in button replies.

**5.3 — Limitations: None / Limited / Strict** *(Highest)* ✅ Parity
All three limitation modes preserved exactly as Mimu implements them.

**5.4 — Invoker Only Mode** *(Highest)* ✅ Parity
Only the person who triggered the parent AR (or who joined, boosted, etc.) can click the button. Preserved exactly.

**5.5 — Panel Builder (Replaces `/send`)** *(High)* ✅ Improved
A saved Panel object (`PANEL-001`, etc.) that stores the embed + button layout. Posted with `/panel show`. Editable in place after posting. No more one-shot `/send` commands.

**5.6 — Button Auto-ID** *(High)* ➕ New
Buttons get auto-assigned IDs (`BTN-001`, etc.) in addition to their display name/label. Referenced in panels by ID — no manual name collision issues.

**5.7 — Live Button Preview** *(High)* ➕ New
See the rendered button (color, label, emoji) and the full response preview before posting.

**5.8 — Edit Posted Panel In Place** *(High)* ➕ New
Bot tracks the message ID of every posted panel. After editing a panel's config, push changes to all live posted messages without deleting and reposting.

**5.9 — Button Clone** *(Medium)* ➕ New
`/button clone id:BTN-001` — duplicate all properties into a new button. Useful for panels with many similar buttons that differ only in label and role.

**5.10 — Button Version History** *(Medium)* ➕ New
Last 10 snapshots per button, same as embeds. Preview and restore any version.

---
---

# 6. Argument System 🔴 Critical

## What Mimu Does

When the matchmode is not `exact`, extra words the user typed after (or around) the trigger are captured as numbered arguments.

```
[$1]     — first word after trigger
[$2]     — second word
[$1+]    — first word and everything after
[$2+]    — second word and everything after
[$3-5]   — words 3, 4, and 5
```

These can be used in the response directly AND in functions:
- `{addrole:@verified|[$1]}` — give the role to the user mentioned in the argument
- `{user_joindate:[$1]}` — show the join date of the mentioned user
- `{requirearg:1|user}` — validate that `[$1]` is a valid user mention

The `{requirearg:}` function validates argument presence and type. Types: `user`, `channel`, `role`, `color`, `number`.

**Important security note from Mimu's docs:** If using `{requirearg:}` without a type (or not using it at all), always wrap responses in `{embed:}` — embeds suppress role mentions, preventing users from exploiting your AR to ping roles by passing them as arguments.

## The Improvement

The argument system is preserved completely. Two improvements are added: `{escape_mentions}` makes argument sanitization explicit without requiring `{embed:}`, and the builder's Variables Reference panel lists all argument placeholders with examples.

---

### Subfeatures (Sorted by Priority)

**6.1 — `[$N]`, `[$N+]`, `[$N-Z]` Argument Placeholders** *(Highest)* ✅ Parity
Full parity with Mimu. Works identically across all non-exact matchmodes.

**6.2 — `{requirearg:N}` and `{requirearg:N|type}`** *(Highest)* ✅ Parity
All types preserved: `user`, `channel`, `role`, `color`, `number`. Error messages shown when wrong type is provided.

**6.3 — Extended User Placeholders with Argument Target** *(High)* ✅ Parity
`{user_joindate:[$1]}`, `{user_balance:[$1]}`, `{user_nick:[$1]}` — any user placeholder can be retargeted to a different user via argument. Preserved exactly.

**6.4 — `{escape_mentions}` Function** *(High)* ➕ New
Strips @role and @everyone mentions from arguments before they appear in the response. The recommended approach instead of forcing every argument AR into an embed.

**6.5 — Argument Reference in Variables Panel** *(Medium)* ➕ New
The builder's 📖 Variables Reference button lists all `[$N]` variants with examples. Staff don't need to consult external docs.

---
---

# 7. Random / Dynamic Response System 🟠 High

## What Mimu Does

Three functions for random/variable responses:

- **`{range:min-max}`** — random number in a range. Up to 4: `{range:}`, `{range1:}`, `{range2:}`, `{range3:}`. Result stored in `[range]`, `[range1]`, etc.
- **`{choose:a|b|c}`** — random pick from a list. Up to 4. Result in `[choice]`, `[choice1]`, etc. Repeat options to increase probability.
- **`{weightedchoose:20%|50%|30%}`** — explicit percentage weights for a `{choose:}` list.
- **`{lockedchoose:a|b|c}`** — deterministically picks the option at the same position as `{choose:}` picked. Used for correlated choices (e.g., if `{choose:}` picked option 3, `{lockedchoose:}` also picks option 3 from its list).

These can be nested — ranges inside choices, choices inside ranges. Extremely powerful for randomized currency games, loot tables, etc.

## The Improvement

Full parity. Added: a **response tester** in the builder that runs the AR's response 5 times and shows the 5 different random outputs, so staff can see the distribution without live-testing in a channel.

---

### Subfeatures (Sorted by Priority)

**7.1 — `{range:}` (up to 4)** *(Highest)* ✅ Parity
Random number from min–max. Stored in `[range]`. Declare before referencing.

**7.2 — `{choose:}` with Repeat-for-Probability (up to 4)** *(Highest)* ✅ Parity
Random pick from pipe-separated list. Repeat options to skew probability.

**7.3 — `{weightedchoose:}`** *(High)* ✅ Parity
Explicit percentage weights — cleaner than repeating options.

**7.4 — `{lockedchoose:}`** *(High)* ✅ Parity
Deterministic correlated choice — position-matched to `{choose:}`. Preserved exactly.

**7.5 — Range-in-Choice / Choice-in-Range Nesting** *(Medium)* ✅ Parity
`{range:}` values usable inside `{choose:}` and vice versa. Enables rarity-weighted loot tables.

**7.6 — Response Tester in Builder** *(Medium)* ➕ New
A "🎲 Test Response" button in the builder runs the AR's response 5 times and shows all 5 outputs side by side — so staff can verify the random distribution is working as intended before going live.

---
---

# 8. Custom Variables and Conditionals 🟠 High

## What Mimu Does

The variable/placeholder set is fixed. You can't define your own reusable values, and there's no conditional logic (`if/else`) within a response.

## The Improvement

Three new variable types that work everywhere — in AR responses, embed fields, and button replies.

## How It Works

### Custom Server Variables ➕ New

Define a named value once; use it anywhere with `{var.name}`.

```
/var create name:artist_name value:Mika
/var create name:commission_email value:mika@example.com
/var create name:turnaround value:3–5 business days
```

In any AR response or embed:
```
Hi! I'm {var.artist_name}. Commissions take {var.turnaround}.
Contact: {var.commission_email}
```

**Updating:** `/var edit name:turnaround value:2–3 business days` — updates everywhere the variable is used instantly. Change your turnaround time in one place; every AR and embed that references it reflects the change immediately.

**Managing:** `/var list` — all server variables, their values, and which ARs reference them.

---

### Counter Variables ➕ New

A number stored per server that increments (or decrements) every time an AR fires.

```
/var counter create name:welcome_count
/var counter create name:slots_remaining start:10
```

In the AR response: `{counter.welcome_count}` — outputs the current count, then increments by 1.

**Manual control:**
- `/var counter set name:slots_remaining value:10` — reset to 10
- `/var counter reset name:welcome_count` — back to 0
- `/var counter adjust name:slots_remaining amount:-1` — decrement without firing an AR

**Use cases:**
- *"Welcome! You are visitor #{counter.welcome_count} to read this message!"*
- *"Slot {counter.slot_claimed} of 10 claimed."*
- *"Only {counter.slots_remaining} slots left!"*

---

### Conditional Variables ➕ New

A variable whose output depends on a condition evaluated at fire time.

**Syntax:**
```
{if:condition|true_output|false_output}
```

**Supported conditions:**

| Condition | Example |
|---|---|
| User has role | `{if:user_has_role:@Booster|Thanks for boosting!|Help us reach Level 2!}` |
| User doesn't have role | `{if:not_user_has_role:@Verified|Get verified first!|Welcome back!}` |
| Boost tier comparison | `{if:server_boostlevel>=2|We're Level {server_boostlevel}!|Help us reach Level 2!}` |
| Member count comparison | `{if:server_membercount>1000|Huge server!|Growing community!}` |
| Argument equals value | `{if:[$1]==red|🔴 Red selected.|Pick a valid color.}` |
| Channel match | `{if:channel==#general|You're in general!|This isn't general.}` |

**Nested** (up to 2 levels):
```
{if:user_has_role:@Booster|{if:server_boostlevel>=2|Level 2+ Booster!|Level 1 Booster!}|Not a booster.}
```

**Use case:** One AR for both staff and non-staff. One welcome message that changes based on whether the joiner is a bot. One `{if:user_has_role:@Verified|...}` that gives different instructions depending on status.

---

### Subfeatures (Sorted by Priority)

**8.1 — Custom Server Variables (`{var.name}`)** *(Highest)*
Define once, use everywhere. The #1 maintenance improvement for large AR setups.

**8.2 — Counter Variables (`{counter.name}`)** *(High)*
Self-incrementing numbers. Slot trackers, visit counters, milestone counters.

**8.3 — Conditional Variables (`{if:condition|true|false}`)** *(High)*
Role-aware, context-sensitive responses from one AR. Eliminates duplicate ARs for "same trigger, different audience."

**8.4 — Variable Reference Panel in Builder** *(Medium)*
The 📖 Variables button in the builder lists all variables — including custom vars, counters, and conditionals with examples.

**8.5 — Nested Conditional Support (2 levels)** *(Low)*
Enough for "if A and B" logic without becoming unmaintainable.

---
---

# 9. Conditions Builder (No-Syntax Alternative to Functions) 🟠 High

## What Mimu Does

Access control is done entirely through functions inline in the response string:
```
{requirerole:@Mods}{cooldown:300}{requirechannel:#commands}
```

These must be typed in the right order (functions run left to right), and forgetting one means the AR fires incorrectly. There's no visual overview of what restrictions are active.

## The Improvement

The 🔒 **Conditions** button in the builder opens a dedicated conditions editor — a visual alternative to typing function variables. Staff see all active conditions at a glance and configure them through modals, not through text.

**This doesn't remove the function syntax** — `{requirerole:}`, `{denyrole:}`, `{cooldown:}`, etc. all still work exactly as in Mimu. The Conditions builder is an alternative for staff who prefer not to type functions manually.

## How It Works

The Conditions modal shows a checklist of all active conditions:

```
Active Conditions — AR-003

✅ Required role: @Mods
✅ Denied role: @Muted
✅ Cooldown: 300 seconds (per user)
✅ Required channel: #commands
❌ Global cooldown: not set
❌ Account age: not set

[ + Add Condition ]   [ Remove Selected ]
```

Clicking "Add Condition" shows a select menu of all available condition types. Staff pick one and fill in the value via modal.

**Conditions available in the builder (all implemented as their equivalent functions under the hood):**

| Builder Condition | Equivalent Function |
|---|---|
| Required role | `{requirerole:}` |
| Denied role | `{denyrole:}` |
| Required channel | `{requirechannel:}` |
| Denied channel | `{denychannel:}` |
| Required permission | `{requireperm:}` |
| Denied permission | `{denyperm:}` |
| Required balance | `{requirebal:}` |
| Required item | `{requireitem:}` |
| Per-user cooldown | `{cooldown:}` |
| Once-ever (per user) | `{once}` (new) |
| Global cooldown | `{globalcooldown:}` (new) |
| Server membership duration | *(new condition)* |
| Account age minimum | *(new condition)* |

---

### Subfeatures (Sorted by Priority)

**9.1 — Visual Conditions Editor in Builder** *(Highest)* ✅ Improved
See all active conditions in one panel instead of buried in the response string.

**9.2 — Conditions-Not-Met Fallback Response** *(High)* ➕ New
Configure a custom response shown when any condition blocks the AR — separate from Mimu's default error messages. Ephemeral by default.

**9.3 — Server Membership Duration Condition** *(Medium)* ➕ New
User must have been in the server for at least X days. Anti-raid protection for role-assignment ARs.

**9.4 — Account Age Minimum Condition** *(Medium)* ➕ New
Discord account must be at least X days old. Blocks day-old alts from triggering ARs.

**9.5 — Global Cooldown** *(Medium)* ➕ New
One cooldown shared across all users. Prevents channel flooding when many users trigger simultaneously.

---
---

# 10. AR Chaining and Flows 🟠 High

## What Mimu Does

Each AR is fully independent. One trigger → one response. No connection between ARs. No multi-step flows.

**The closest Mimu gets:** Button responders attached to an AR response can have their own reply, creating a two-step interaction (trigger → AR fires with button → user clicks button → button reply fires). That's the full depth.

## The Improvement

ARs can explicitly **chain** — the completion of one AR can automatically trigger another. The most powerful mode is **button-gated chaining**: buttons in the AR response, when clicked, fire a different AR instead of (or in addition to) a role action.

## How It Works

In the builder's ⚙️ Behavior section, a **"Then:" field** picks the next AR to fire after this one completes.

**Chain modes:**
- **Auto:** AR-002 fires immediately after AR-001's response is sent
- **Auto (delayed):** AR-002 fires after 1s, 2s, or 5s
- **Button-gated:** A button in AR-001's response, when clicked, fires AR-002

**Button-gated example:**
```
AR-001 response: "What are you here for?"
  Button [🎨 Commissions] → fires AR-002
  Button [🎮 Gaming]      → fires AR-003
  Button [📢 Updates]     → fires AR-004

AR-002: Commission-specific welcome + role-select panel
AR-003: Gaming channel list + gaming role buttons
AR-004: Notification opt-in panel
```

Full guided onboarding tree — entirely within the AR system.

**Safeguards:**
- Maximum chain depth: **5 steps** — prevents infinite chains
- Loop detection: if AR-001 → AR-002 → AR-001 is configured, the builder rejects it: *"AR-001 is already in this chain. This would create a loop."*

---

### Subfeatures (Sorted by Priority)

**10.1 — Button-Gated Chain Trigger** *(Highest)*
The most powerful mode. User's button choice determines which AR branch fires next.

**10.2 — Auto-Chain with Delay** *(High)*
Sequential multi-message onboarding flows with pacing.

**10.3 — Loop Detection** *(High)*
Validated at setup time. Infinite loops would spam the channel.

**10.4 — Chain Depth Limit (5)** *(Medium)*
Keeps flows manageable. Documented clearly.

**10.5 — Chain Visualization in Builder** *(Medium)*
Simple flowchart shown in the builder: `AR-001 → AR-002 → [end]`.

---
---

# 11. AR Management Suite 🟠 High

## What Mimu Does

`/autoresponder list` returns a flat list of trigger phrases. No filtering, no status, no preview. Editing requires knowing the trigger phrase exactly.

## The Improvement

A full management suite — compact list with status, paginated visual browser, search, pause without delete, and bulk tools.

## How It Works

**`/ar list`** — compact table:
```
AR List — 12 total

AR-001  ·  👋 Welcome         ·  Trigger: Member Join  ·  by @iara  ·  Active
AR-002  ·  📋 Payment FAQ     ·  Trigger: "how to pay" ·  by @kim   ·  Active
AR-003  ·  🎫 Verify Claim    ·  Trigger: "!verify"    ·  by @kim   ·  Paused ⏸️
```

**`/ar showlist`** — paginated browser:
- One AR per page
- Rendered preview of the full response (text + embed + buttons)
- Metadata: trigger(s), conditions, creator, creation date, fire count
- Action buttons: ✏️ Edit, ⏸️ Pause, 🗑️ Delete, 📊 Stats

**`/ar search`**:
```
/ar search query:payment
/ar search trigger:!rules
/ar search creator:@kim
/ar search status:paused
```

**`/ar pause id:AR-003`** — disables without deleting. Config preserved. ⏸️ shown in list.
**`/ar resume id:AR-003`** — re-enables.

---

### Subfeatures (Sorted by Priority)

**11.1 — Pause / Resume** *(Highest)* ➕ New
Disable without deleting. The most-needed management tool.

**11.2 — `/ar showlist` Paginated Browser** *(High)* ➕ New
Visual preview of every AR's full response.

**11.3 — `/ar search`** *(High)* ➕ New
Essential at 20+ ARs.

**11.4 — Status Column in List** *(Medium)* ➕ New
Active / Paused / Disabled at a glance.

**11.5 — Bulk Enable/Disable by Channel or Role** *(Medium)* ➕ New
`/ar disable channel:#general` — disables all ARs targeting that channel without editing each one.

---
---

# 12. AR Analytics 🟡 Medium

## What Mimu Does

No tracking. ARs fire invisibly with no record.

## The Improvement

Every AR fire is logged. A stats command surfaces usage per AR and across all ARs.

## How It Works

```
/ar stats id:AR-004
```
```
📊 Stats — AR-004 (❓ Payment FAQ)

Total fires (all time):       156
Unique users who triggered:   89
Fires this month:             23
Last fired:                   Today at 3:22 PM by @user
Conditions blocked:           12 fires (7%)
Cooldown blocked:             8 fires
Top trigger phrase:           "how to pay" (61%)
```

**`/ar stats`** (no ID) — all ARs ranked by fire count. Shows 💤 next to ARs that have never fired or haven't fired in 30 days.

---

### Subfeatures (Sorted by Priority)

**12.1 — Fire Count per AR** *(Highest)* ➕ New
Total and monthly. The baseline metric.

**12.2 — Unique User Count** *(High)* ➕ New
Reach vs. repeat-use distinction.

**12.3 — Conditions Block Rate** *(High)* ➕ New
High block rate = users can't tell they don't qualify → UX problem.

**12.4 — Top Trigger Phrase (for Trigger Groups)** *(Medium)* ➕ New
Which phrase in the group gets used most.

**12.5 — Zero-Fire Flag** *(Medium)* ➕ New
💤 next to dead ARs in the list. Easy cleanup signal.

---
---

# 13. AR Version History 🟡 Medium

## What Mimu Does

No history. Saves are permanent overwrites.

## The Improvement

Last 10 snapshots per AR — same system as embeds, buttons, and panels. Every save creates a version. Preview and restore any version.

```
/ar history id:AR-004
```
```
Version History — AR-004

v5  ·  Today at 3:44 PM   ·  Trigger group updated   ·  by @kim    ← current
v4  ·  Today at 3:41 PM   ·  Response text changed    ·  by @kim
v3  ·  Apr 12 at 11:02    ·  Embed swapped: EMB-005   ·  by @iara
v1  ·  Apr 12 at 10:30    ·  AR created               ·  by @iara

[ Preview v4 ]   [ Restore v4 ]
```

---

### Subfeatures (Sorted by Priority)

**13.1 — Auto-Snapshot on Every Save** *(Highest)* ➕ New
Silent, automatic. No staff action required.

**13.2 — Version Preview** *(High)* ➕ New
Full AR state as it was at that version before deciding to restore.

**13.3 — One-Click Restore** *(High)* ➕ New
Restore creates a new version entry — the restore is auditable.

**13.4 — Change Summary per Version** *(Medium)* ➕ New
Each entry says what changed: "Trigger updated," "Embed swapped." Readable at a glance.

---
---

# 14. AR Templates 🟡 Medium

## What Mimu Does

No templates. Every AR starts blank.

## The Improvement

Pre-built starting configurations for the most common AR use cases.

**Available templates (selectable at `/ar create` time):**

| Template | Pre-fills |
|---|---|
| 👋 Welcome | Member Join trigger · `{user_mention}` · `{user_avatar}` thumbnail · once-ever |
| 👋 Goodbye | Member Leave trigger · `{user_name}` · `{server_membercount}` |
| 🎫 Role Claim | Keyword trigger (editable) · ephemeral response · toggle role button · once-ever |
| ❓ FAQ Answer | Trigger group (3 empty slots) · ephemeral reply · global cooldown 5 min |
| 💰 Currency Command | Keyword trigger · `{range:}` · `{modifybal:[range]}` · `{cooldown:}` |
| 💎 Boost Reward | Role Assigned trigger: @Nitro Booster · `{addrole:}` reward · `{dm}` |
| 📋 Onboarding Flow | 3-step chain pre-linked: welcome → rules → role selector |
| ⬜ Blank | Empty — build from scratch |

---

### Subfeatures (Sorted by Priority)

**14.1 — Built-In Template Set** *(Highest)* ➕ New
Welcome, Goodbye, Role Claim, FAQ, Currency Command, Boost Reward, Blank.

**14.2 — Template Preview Before Selecting** *(High)* ➕ New
See the full AR config (trigger type, response preview, conditions) before committing.

**14.3 — Multi-AR Templates (Onboarding Flow)** *(High)* ➕ New
One template creates multiple linked ARs at once.

**14.4 — Save Any AR as a Template** *(Medium)* ➕ New
`/ar save-as-template id:AR-003` — saves as a reusable server-specific template.

---
---

# 15. AR Export and Import 🟡 Medium

## What Mimu Does

No portability. ARs cannot be backed up or transferred between servers.

## The Improvement

Export any AR as a `.json` file. Import to recreate in the same or a different server.

**Export:**
```
/ar export id:AR-004
/ar export all
```

**Import:**
```
/ar import
```

Attach the `.json` file → bot shows a preview of what will be created → confirm → ARs created with new IDs.

**What transfers:** Trigger config, response text, all functions, conditions, chain links.
**What doesn't transfer:** Embed/button references (flagged as unlinked — staff re-link manually), creator attribution, fire counts.

**Chain-aware export:** Exporting a chained AR automatically includes all ARs in the chain in the same file, with chain structure preserved on import.

---

### Subfeatures (Sorted by Priority)

**15.1 — Single AR Export / Import** *(Highest)* ➕ New
Most common use: share a well-designed AR between servers.

**15.2 — Bulk Export / Import** *(High)* ➕ New
Full server backup. Restore everything.

**15.3 — Import Preview with Unlinked Asset Warning** *(High)* ➕ New
Shows which embeds and buttons need re-linking before commit.

**15.4 — Chain-Aware Export** *(Medium)* ➕ New
Chained ARs exported together in one file, chain intact.

---
---

## Complete Feature Status Summary

| # | Feature | Priority | Status |
|---|---|---|---|
| 1 | Creation and Basic Management | 🔴 Critical | ✅ Improved |
| 2 | Trigger and Matchmode System | 🔴 Critical | ✅ Improved + ➕ New modes |
| 3 | Placeholders (Variables) | 🔴 Critical | ✅ Parity + ➕ New vars |
| 4 | Functions | 🔴 Critical | ✅ Parity + ➕ New functions |
| 5 | Button Responders | 🔴 Critical | ✅ Improved + ➕ New |
| 6 | Argument System (`[$N]`) | 🔴 Critical | ✅ Parity + ➕ `{escape_mentions}` |
| 7 | Random / Dynamic Responses | 🟠 High | ✅ Parity + ➕ Response tester |
| 8 | Custom Variables and Conditionals | 🟠 High | ➕ New |
| 9 | Conditions Builder | 🟠 High | ✅ Improved + ➕ New conditions |
| 10 | AR Chaining and Flows | 🟠 High | ➕ New |
| 11 | Management Suite | 🟠 High | ✅ Improved |
| 12 | Analytics | 🟡 Medium | ➕ New |
| 13 | Version History | 🟡 Medium | ➕ New |
| 14 | Templates | 🟡 Medium | ➕ New |
| 15 | Export and Import | 🟡 Medium | ➕ New |
