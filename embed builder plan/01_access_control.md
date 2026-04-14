# Feature 01 — Access Control

**Priority:** 🔴 Highest (Gate for all other features)

> All embed commands are restricted. No embed feature should be reachable by regular members.

---

## Why This Is Priority #1

Every other feature in this system assumes that only trusted users are operating it. If access control isn't the first thing checked on every command, a regular member could create, delete, or post embeds. Build the permission check as a shared middleware/guard that all `/embed` commands run through before doing anything.

---

## Subfeatures (Sorted by Priority)

---

### 1.1 — Role-Based Permission Check *(Highest)*

**What it does:** Before executing any `/embed` command, the bot checks if the user invoking it holds one of the allowed roles or positions.

**Allowed roles:**
- Server **Owner**
- Server **Administrator** (has the `ADMINISTRATOR` Discord permission flag)
- Any role explicitly designated as **Staff** (configured separately — see 1.3)

**Behavior on failure:**
- Bot replies with an **ephemeral error message** (visible only to the invoker)
- Message should be clear but not aggressive, e.g.:
  > *"You don't have permission to use embed commands. This feature is limited to staff and above."*
- The failed attempt is **not logged publicly** — only the invoker sees it

**Implementation note:** Run this check as a single reusable function (e.g. `hasEmbedPermission(user, guild)`) called at the top of every embed command handler.

---

### 1.2 — Ephemeral Responses for All Embed Management Commands *(High)*

**What it does:** All `/embed` command responses (creation confirmations, edit modals, lists, delete confirmations) are sent as **ephemeral** — meaning only the staff member who ran the command sees them.

**Why:** Embed management is internal. Regular members should never see "Embed EMB-003 was deleted" or editing confirmations cluttering the channel.

**Exception:** `/embed show` (the command that posts an embed to a channel) sends the actual embed as a **public message** — that's the intended output.

---

### 1.3 — Staff Role Configuration *(Medium)*

**What it does:** Allows the server owner or admin to designate which roles count as "staff" for embed access.

**Command:** `/embed config staffrole role:@RoleName`

**Behavior:**
- Adds the selected role to an allow-list stored per server
- Multiple roles can be added (run the command multiple times)
- To remove a role: `/embed config staffrole remove role:@RoleName`
- To view current staff roles: `/embed config staffrole list`

**Fallback:** If no staff roles are configured, only Server Owner and Administrators can use embed commands.

---

### 1.4 — Audit Log Entry on Sensitive Actions *(Low)*

**What it does:** Logs sensitive embed actions to an internal audit trail (not Discord's audit log — your own stored log).

**Logged actions:**
- Embed created (who, when, assigned ID)
- Embed deleted (who, when, which ID)
- Embed posted to a channel (who, when, which channel, which ID)

**Not logged:**
- Edit attempts (too noisy)
- List/preview commands (read-only, low risk)

**Where logs go:** Stored in your database against the server ID. Not surfaced to users by default — only queryable by the owner via a future `/embed logs` command (out of scope for now, but design with it in mind).

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|------------------|
| User has both a staff role and is banned from the server | Discord handles this — banned users can't invoke commands |
| Staff role is deleted from the server | Bot gracefully ignores the missing role ID and falls back to admin/owner only |
| User is a bot | Bots cannot invoke slash commands — no handling needed |
| Server owner transfers ownership mid-session | New owner gains access immediately; old owner loses it on next command check |

---

## Dependencies

- None. This feature has no upstream dependencies — it is the upstream.

## Referenced By

- All other features in this system
