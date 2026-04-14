# 02 — Batch & Slot System

A batch is a timed window during which users can claim a slot and submit their MYO design. The owner controls when batches open and how many slots are available. When the timer runs out, the channel automatically locks and users can no longer submit until the next batch opens.

---

## Table of Contents

1. [How a Batch Works (Overview)](#1-how-a-batch-works-overview)
2. [Batch Management](#2-batch-management)
3. [Slot Claiming](#3-slot-claiming)
4. [Timer & Auto-Close](#4-timer--auto-close)
5. [Post-Close Behavior](#5-post-close-behavior)
6. [Recommended Features](#6-recommended-features)
7. [Nice-to-Add Features](#7-nice-to-add-features)

---

## 1. How a Batch Works (Overview)

```
Owner opens batch
     ↓
Bot posts announcement with slot count + live countdown timer
     ↓
Users claim slots (first come, first served)
     ↓
Users submit their MYO form before the timer runs out
     ↓
Timer expires → channel auto-locks → unclaimed / unsubmitted slots are forfeited
     ↓
Owner reviews submissions in the private staff channel
     ↓
Owner sets next batch date (or leaves as TBA)
```

**Key rules:**
- One slot per user per batch. No exceptions.
- Claiming a slot does not mean submitting. The user must also complete their form before time runs out.
- Slots do not carry over to the next batch if unused.

---

## 2. Batch Management

### 👑 Owner

| Command | What It Does |
|---|---|
| `/batch open <slots> <duration>` | Opens a new batch. `slots` is the number of available spots. `duration` is how long it stays open (e.g., `2d`, `12h`, or a specific date/time). |
| `/batch close early` | Manually triggers the close sequence before the timer expires. Useful if all slots fill up fast. |
| `/batch pause` | Freezes the timer and locks the channel without closing the batch. Slots stay as-is. No new claims during pause. |
| `/batch resume` | Unfreezes the timer and reopens the channel from where it paused. |
| `/batch setnext <date>` | Sets the estimated date for the next batch. Shown to users in the post-close embed and in the locked-channel prompt. |
| `/batch setnext clear` | Clears the next batch date, reverting it to "TBA." |
| `/batch info` | Shows the current batch status — batch number, slots filled, time remaining, tier restrictions if any. |
| `/batch history` | Shows a log of all past batches — number, date, slots filled, submissions received, approval rate. |

**On `/batch open`, the bot automatically:**
- Increments the batch number (e.g., Batch #4)
- Posts an announcement embed in the submissions channel containing:
  - Batch number
  - Total slots available
  - Live Discord countdown timer (auto-adjusts to each user's timezone)
  - Instructions on how to claim a slot
- Opens channel permissions so the default member role can send messages and use commands

---

### 🛡️ Staff

Staff can view batch info but cannot open, close, or configure batches by default.

| Command | What It Does |
|---|---|
| `/batch info` | View current batch status. |
| `/batch history` | View past batch logs. |

---

### 👤 User

| Command | What It Does |
|---|---|
| `/batch info` | Shows current batch status, slots remaining, and time left. |

---

## 3. Slot Claiming

**Logic:** When a user claims a slot, the bot checks three things in order before confirming. If any check fails, the claim is blocked with an explanation.

**Checks (in order):**
1. Is the batch currently open and not paused?
2. Are there slots remaining?
3. Has this user already claimed a slot in this batch?

If all three pass:
- The user's ID is recorded against this batch
- The slot counter in the announcement embed updates (e.g., 7/10 remaining)
- The user receives an ephemeral confirmation with the submission deadline

---

### 👑 Owner

| Command | What It Does |
|---|---|
| `/slot forceclaim @user` | Manually assigns a slot to a user. Bypasses all checks. Used for special cases. |
| `/slot revoke @user` | Removes a user's claimed slot and returns it to the pool. |
| `/slot list` | Shows all users who have claimed slots in the current batch and whether they have submitted. |

---

### 🛡️ Staff

| Command | What It Does |
|---|---|
| `/slot list` | View who has claimed slots and submitted. |
| `/slot revoke @user` | Can revoke slots if granted permission by owner. Off by default. |

---

### 👤 User

| Command | What It Does |
|---|---|
| `/slot claim` | Claims a slot in the current batch. Fails if batch is closed, full, or they already have a slot. |
| `/slot cancel` | Voluntarily gives up their slot before the timer expires. Slot returns to the pool. They cannot reclaim in the same batch. |
| `/slot status` | Shows whether they have a slot in the current batch and whether they have submitted. |

---

## 4. Timer & Auto-Close

**Logic:** The bot runs a background timer from the moment the batch is opened. When it hits zero, the close sequence fires automatically without any input from the owner.

**Auto-close sequence (in order):**

1. **Channel permissions are updated** — the default member role loses the ability to send messages and use slash commands in the submissions channel.
2. **A closing embed is posted** in the channel:
   - Batch number and that it is now closed
   - How many slots were filled vs. the total (e.g., 8/10 filled)
   - Next batch date if set, or "TBA" if not
3. **Unclaimed slots are discarded** — the 2 unfilled slots in the example above disappear. They are not saved for the next batch.
4. **Users who claimed a slot but never submitted are flagged** — they receive a DM:
   > ⏰ Batch #4 has closed. You claimed a slot but did not submit your design before the deadline. Your slot has been forfeited.

---

## 5. Post-Close Behavior

**Logic:** After the batch closes, the channel is locked. Any user who tries to run a slot or submission command receives a contextual message rather than a generic error.

**What users see when they try to use commands after close:**

```
❌ Batch #4 is now closed. Submissions are no longer being accepted.

📅 Next batch opens approximately: May 5, 2026.

Watch the announcements channel for updates.
```

If no next date has been set:
```
❌ Batch #4 is now closed. Submissions are no longer being accepted.

📅 Next batch date: TBA — watch the announcements channel for updates.
```

---

## 6. Recommended Features

### Slot Waitlist

**Logic:** Once all slots are filled, users can join a waitlist. If a claimed slot is cancelled or revoked before the deadline, the next person in the waitlist is automatically offered the slot via DM. The waitlist resets with each new batch — it is not carried over.

| Command | Who | What It Does |
|---|---|---|
| `/slot waitlist` | User | Joins the waitlist for the current batch. Only available after slots are full. |
| `/slot waitlist leave` | User | Removes themselves from the waitlist. |
| `/slot waitlist view` | Owner/Staff | Shows the current waitlist in order. |

**When a slot opens up:**
- Bot DMs the first person on the waitlist: *"A slot has opened in Batch #4! You have 30 minutes to claim it with `/slot claim` before it passes to the next person."*
- If they don't claim within the window, it automatically moves to the next person on the list.

---

### Batch Reminder DMs

**Logic:** The bot sends automatic DM reminders to all users who have claimed a slot but have not yet submitted. Keeps people from forgetting the deadline.

Reminders fire at configurable intervals before close (default: 24 hours and 1 hour before).

| Command | Who | What It Does |
|---|---|---|
| `/batch reminders on/off` | Owner | Toggles reminder DMs on or off for the current batch. |
| `/batch reminderset <intervals>` | Owner | Sets when reminders fire (e.g., `24h 1h`). |

**DM content:**
> ⏰ Reminder: Batch #4 closes in **1 hour**. You have a slot reserved but haven't submitted yet. Run `/myo submit` before time runs out!

---

### Per-Batch Tier Restriction

**Logic:** The owner can restrict a batch so that only specific MYO coupon tiers are eligible. For example, running a Legendary-only batch for special occasions. The bot rejects submissions using ineligible tiers and explains why.

| Command | Who | What It Does |
|---|---|---|
| `/batch open <slots> <duration> --tiers <tiers>` | Owner | Opens a batch restricted to specified tiers (e.g., `rare legendary`). |

The batch announcement embed clearly states which tiers are eligible. If no tier restriction is set, all tiers are accepted.

---

## 7. Nice-to-Add Features

### Slot Hold Timer (Nice to Add)

**Logic:** After a user claims a slot, they have a short grace period (default: 30 minutes) to begin their submission. If they do nothing within that window, their slot is auto-released back to the pool or passed to the waitlist. Prevents users from claiming slots with no intent to submit during high-demand batches.

| Command | Who | What It Does |
|---|---|---|
| `/batch holdtimer set <duration>` | Owner | Sets how long a user has to begin their submission after claiming. |
| `/batch holdtimer off` | Owner | Disables the hold timer entirely. |

---

### Batch Ping Role (Nice to Add)

**Logic:** Users opt into a role that gets pinged whenever a new batch opens. They opt in and out themselves. The owner does not assign it manually.

| Command | Who | What It Does |
|---|---|---|
| `/batch notify` | User | Toggles the batch ping role on or off for themselves. |
| `/batch pingset @role` | Owner | Sets which role gets pinged on batch open. |

---

### Cross-Batch Character Cap (Nice to Add)

**Logic:** The owner sets a global maximum number of approved characters any user can have. When a user hits the cap, the bot blocks their slot claim with an explanation. The owner can override the cap per user.

| Command | Who | What It Does |
|---|---|---|
| `/batch cap set <number>` | Owner | Sets the global character cap per user. |
| `/batch cap override @user <number>` | Owner | Sets a custom cap for a specific user. |
| `/batch cap check @user` | Owner/Staff | Shows how many characters a user has vs. the cap. |

---

### Batch Pause Announcement (Nice to Add)

**Logic:** When the owner pauses a batch, the bot automatically posts a notice in the submissions channel and edits the batch embed to show a paused state.

Batch embed updates to show:
```
⏸ Batch #4 is temporarily paused. The timer has been frozen.
The batch will resume when the owner unpauses it.
```
On resume, the embed updates back to the normal countdown view.
