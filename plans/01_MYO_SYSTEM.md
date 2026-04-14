# 01 — MYO System

The MYO (Make Your Own) system lets users design their own species character using a coupon they have obtained. The owner reviews and approves or rejects each submission. This entire system is separate from general server commands and only applies to the species category.

---

## Table of Contents

1. [Species TOS Gate](#1-species-tos-gate)
2. [MYO Coupon Types](#2-myo-coupon-types)
3. [Coupon Acquisition](#3-coupon-acquisition)
4. [Coupon Inventory](#4-coupon-inventory)
5. [MYO Submission](#5-myo-submission)
6. [Approval Workflow](#6-approval-workflow)
7. [Masterlist](#7-masterlist)
8. [Blacklist](#8-blacklist)
9. [Nice-to-Add Features](#9-nice-to-add-features)

---

## 1. Species TOS Gate

**Logic:** Before a user can use any MYO command, they must accept the species Terms of Service. This is a one-time step that is logged with a timestamp. If the TOS is updated, users who accepted an older version are flagged and must re-accept.

This is separate from the general server TOS.

---

### 👑 Owner

| Command | What It Does |
|---|---|
| `/species-tos set <text or link>` | Sets or updates the current species TOS. Triggers a version bump. |
| `/species-tos version` | Shows the current TOS version number and when it was last updated. |
| `/species-tos check @user` | Shows whether a user has accepted the TOS and which version they accepted. |
| `/species-tos forceaccept @user` | Manually marks a user as having accepted (for edge cases). |
| `/species-tos reset @user` | Clears a user's acceptance, forcing them to re-accept before using commands. |

### 🛡️ Staff

| Command | What It Does |
|---|---|
| `/species-tos check @user` | View only — confirms acceptance status for moderation purposes. |

### 👤 User

| Command | What It Does |
|---|---|
| `/species-tos accept` | Displays the current TOS text and a confirmation button. Logs acceptance with timestamp on confirm. |
| `/species-tos status` | Shows whether they have accepted, which version, and when. |

> **Rule:** Any MYO command run by a user who has not accepted the TOS returns a prompt telling them to run `/species-tos accept` first. No exceptions.

---

## 2. MYO Coupon Types

**Logic:** Coupons determine what rarity of traits a user is allowed to use in their design. Higher tier coupons include all traits from lower tiers. Each coupon has a unique ID generated on creation so it can be tracked individually.

| Tier | Allowed Traits | Visual Color |
|---|---|---|
| **Common** | Common traits only | ⬜ White / Grey |
| **Rare** | Rare + Common traits | 🟦 Blue |
| **Legendary** | Legendary + Rare + Common traits | 🟨 Gold |

> A coupon is consumed (removed from inventory) the moment a submission using it is **approved**. If a submission is denied or pending, the coupon is held but not consumed yet.

---

## 3. Coupon Acquisition

**Logic:** Coupons can only be obtained through official channels. Creating a character without a valid coupon is not allowed.

### 👑 Owner

| Command | What It Does |
|---|---|
| `/myo give @user <tier>` | Directly gives a coupon to a user. Used for sales, gifts, or event rewards. |
| `/myo give @user <tier> <quantity>` | Gives multiple coupons at once. |
| `/myo revoke @user <coupon-id>` | Removes a specific coupon from a user's inventory. Used for errors or rule violations. |

### 🛡️ Staff

| Command | What It Does |
|---|---|
| `/myo give @user <tier>` | Can give coupons if granted permission by owner. Off by default. |

### 👤 User

Coupons are received automatically. Users cannot generate their own coupons. Acquisition methods:

| Method | How It Works |
|---|---|
| **Direct purchase** | Owner processes payment externally (GCash, PayPal) and runs `/myo give`. |
| **Server shop** | User spends EC in the shop to buy a coupon. Bot handles the transfer. |
| **Giveaways** | Bot auto-assigns coupon to winner at giveaway end. |
| **Events/games** | Owner or staff run `/myo give` as the event reward. |
| **Random drops** | Bot randomly drops a coupon in configured channels. User must claim it via button before it expires. |

---

## 4. Coupon Inventory

**Logic:** Each user has a personal coupon inventory. Coupons sit here until used in a submission or transferred. Each coupon shows its unique ID, tier, and how it was obtained.

### 👑 Owner / 🛡️ Staff

| Command | What It Does |
|---|---|
| `/myo inventory @user` | View another user's coupon inventory. |

### 👤 User

| Command | What It Does |
|---|---|
| `/myo inventory` | Shows all coupons they own — ID, tier, acquisition method, date received. |

---

## 5. MYO Submission

**Logic:** When a user wants to create their character, they submit a form using one of their coupons. The bot collects all required info, holds the coupon as "in use," and posts the submission to a private staff review channel.

A user can only have **one pending submission at a time.** They cannot submit again until their current submission is resolved.

### 👤 User

| Command | What It Does |
|---|---|
| `/myo submit` | Opens a guided step-by-step form (see fields below). |
| `/myo status` | Shows whether their submission is pending, approved, or denied and why. |
| `/myo withdraw` | Cancels a pending submission and returns the coupon to inventory. |

**Submission Form Fields:**

| Field | What the User Provides |
|---|---|
| Coupon ID | Which coupon they are using for this submission. |
| Character Name | The name of their character. |
| Design Image | A direct image link (Imgur, etc.) showing the full design. |
| Toyhouse Link | Link to the character's Toyhouse profile. |
| Trait List | A written list of all traits used in the design. |
| Notes (optional) | Any extra context for the reviewer. |

> After submitting, the bot replies with a confirmation embed showing all submitted info and a submission reference number.

---

## 6. Approval Workflow

**Logic:** Every submission is posted to a private staff channel as an embed. The owner reviews it and takes action using buttons. The submitter is notified by DM of the result.

### Staff Review Channel Embed

The embed shows:
- Submitter username and ID
- Submission reference number
- Coupon tier and ID used
- Character name and Toyhouse link
- Design image (displayed inline)
- Declared trait list
- Timestamp of submission
- Whether the user is a First Time Owner (FTO) — auto-flagged by bot

Action buttons on the embed:

| Button | What Happens |
|---|---|
| ✅ **Approve** | Coupon is consumed. Character is added to masterlist. Submitter gets a DM with approval. |
| 🔁 **Request Changes** | Opens a text prompt for the reviewer to type feedback. Coupon stays held. Submitter gets a DM with the feedback. |
| ❌ **Deny** | Opens a text prompt for denial reason. Coupon is returned to user inventory. Submitter gets a DM with the reason. |

### 👑 Owner

| Command | What It Does |
|---|---|
| `/myo approve <ref-number>` | Approves a submission by reference number (alternative to button). |
| `/myo deny <ref-number> <reason>` | Denies a submission by reference number. |
| `/myo changes <ref-number> <feedback>` | Requests changes by reference number. |
| `/myo reviewlog` | Shows a full log of all reviewed submissions — reference number, action taken, reviewer, timestamp. |

### 🛡️ Staff

Staff can view submissions in the review channel but **cannot approve or deny by default.** Owner can grant approval permission per staff member:

| Command | What It Does |
|---|---|
| `/myo staffpermit @user on/off` | Grants or revokes a staff member's ability to approve/deny submissions. |

---

## 7. Masterlist

**Logic:** Every approved character is stored in the bot's masterlist. This is the official record of all valid species characters. It can be searched and updated.

### 👑 Owner / 🛡️ Staff

| Command | What It Does |
|---|---|
| `/masterlist view @user` | Shows all approved characters owned by a user. |
| `/masterlist search <name>` | Searches masterlist by character name. |
| `/masterlist transfer <char-id> @newowner` | Transfers a character's ownership record to another user. |
| `/masterlist void <char-id> <reason>` | Marks a character as voided. Record is kept but flagged as inactive. |
| `/masterlist edit <char-id>` | Updates a character's name or Toyhouse link. |

### 👤 User

| Command | What It Does |
|---|---|
| `/masterlist me` | Shows all characters they own on the masterlist. |
| `/masterlist view <char-id>` | Shows the public info for a specific character. |

---

## 8. Blacklist

**Logic:** A blacklisted user is blocked from all MYO commands. Their existing characters remain on the masterlist but they cannot submit, claim coupons, or participate in MYO events.

### 👑 Owner

| Command | What It Does |
|---|---|
| `/blacklist add @user <reason>` | Adds user to the blacklist. They are immediately blocked from all MYO commands and notified by DM. |
| `/blacklist remove @user` | Removes a user from the blacklist. Restores full access. |
| `/blacklist view` | Shows all currently blacklisted users with reasons and dates. |
| `/blacklist check @user` | Checks whether a specific user is blacklisted. |

### 🛡️ Staff

| Command | What It Does |
|---|---|
| `/blacklist check @user` | View only. |

### 👤 User

If a blacklisted user runs any MYO command, they receive:
> ❌ You are currently blacklisted and cannot use MYO commands. If you believe this is an error, please contact the server owner.

---

## 9. Nice-to-Add Features

These are not required for launch but improve the experience as the community grows.

### Trait Pre-Check (Nice to Add)

**Logic:** When a user submits, the bot cross-references the traits they declared against the allowed list for their coupon tier. If they declared a trait above their tier, the bot adds a warning flag to the review embed. It does not block the submission — the owner still makes the final call.

> Example: User with a Common coupon declares "glowing wings" which is a Rare trait. The embed shows: ⚠️ *Possible trait violation detected: "glowing wings" may be above Common tier.*

---

### FTO (First Time Owner) Auto-Tag (Nice to Add)

**Logic:** The bot checks the masterlist when a submission comes in. If the user has never had an approved character before, the review embed is tagged with 🌱 FTO. The owner can optionally configure an automatic reward for FTOs on first approval (e.g., a bonus Common coupon).

---

### Submission History (Nice to Add)

**Logic:** A full log of every submission a user has made — what they submitted, when, and what the outcome was. Useful for dispute resolution.

| Command | Who | What It Does |
|---|---|---|
| `/myo history` | User | Shows their own submission history. |
| `/myo history @user` | Owner/Staff | Shows another user's full submission history. |

---

### Species TOS Version Control (Nice to Add)

**Logic:** Every time the owner updates the TOS, the version number increments. The bot tracks which version each user accepted. If a user's accepted version is behind the current version, they are flagged and prompted to re-accept before using MYO commands.

| Command | Who | What It Does |
|---|---|---|
| `/species-tos outdated` | Owner/Staff | Lists all users who have not accepted the current TOS version. |
| `/species-tos broadcast` | Owner | Sends a DM to all outdated users prompting them to re-accept. |

---

### Character Cap Per User (Nice to Add)

**Logic:** The owner sets a maximum number of approved characters any one user can have. When a user hits the cap, the bot blocks their next submission and tells them to void or transfer a character first.

| Command | Who | What It Does |
|---|---|---|
| `/myo cap set <number>` | Owner | Sets the global character cap. |
| `/myo cap override @user <number>` | Owner | Sets a custom cap for a specific user. |
| `/myo cap view` | Owner/Staff | Shows the current cap and any user overrides. |
