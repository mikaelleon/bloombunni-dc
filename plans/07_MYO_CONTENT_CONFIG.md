# 07 — MYO System: Content & Configuration (Patch Update)

This file documents the owner-facing configuration tools added to the MYO system. All commands in this file use the `/myo` prefix to keep them fully separate from any server-wide bot features that share similar names (e.g., a general `/embed` command will not conflict with `/myo embed`).

---

## Table of Contents

1. [Command Prefix Rule](#1-command-prefix-rule)
2. [MYO Embed Builder](#2-myo-embed-builder)
3. [Species Guide Manager](#3-species-guide-manager)
4. [Visual & Image Manager](#4-visual--image-manager)
5. [Trait Sheet Configurator](#5-trait-sheet-configurator)
6. [Species TOS Configurator](#6-species-tos-configurator)
7. [MYO Announcement System](#7-myo-announcement-system)
8. [New Member DM Onboarding](#8-new-member-dm-onboarding)
9. [Nice-to-Add Features](#9-nice-to-add-features)

---

## 1. Command Prefix Rule

**Logic:** Every command that belongs to the MYO system uses `/myo` as its root prefix. This prevents collisions with any existing or future server-wide bot commands that share the same action words (embed, announce, welcome, etc.).

**Pattern:**
```
/myo <subsystem> <action> <arguments>

Examples:
/myo embed create
/myo guide post
/myo announce post
/myo dm preview
```

This applies to every command in this file without exception. If a command exists in the general server bot (e.g., `/embed`), it is a completely different command from its `/myo` counterpart and they do not share config or data.

---

## 2. MYO Embed Builder

**Logic:** The owner creates and manages rich embeds for the species category entirely through commands. Each embed is saved under a shortname. They can be posted to a channel, edited, and reposted without manually touching the channel messages.

This is separate from any server-wide embed builder the general bot may have. `/myo embed` only manages embeds for the species category.

---

### 👑 Owner

| Command | What It Does |
|---|---|
| `/myo embed create <shortname>` | Opens a guided prompt to build a new embed. Fields: title, description, color (hex), footer text, thumbnail URL, image URL. |
| `/myo embed edit <shortname>` | Re-opens the prompt for an existing embed. On save, the live posted message is updated automatically if it was posted via this system. |
| `/myo embed delete <shortname>` | Removes the embed from the registry. Optionally deletes the posted channel message. |
| `/myo embed post <shortname> #channel` | Posts the embed to the specified channel. The message ID is saved so future edits update it in place. |
| `/myo embed repost <shortname>` | Deletes the old posted message and sends a fresh one. Useful if the message got buried or the channel was reorganized. |
| `/myo embed list` | Shows all saved embeds — shortname, title, which channel it's posted in, and when it was last edited. |
| `/myo embed preview <shortname>` | Sends the embed as an ephemeral message visible only to the owner, for review before posting. |

**Embed fields available during create/edit:**

| Field | Notes |
|---|---|
| Title | Plain text, shown at the top of the embed |
| Description | Main body text. Supports Discord markdown (bold, italics, links) |
| Color | Hex code (e.g., `#A8D8EA`). Shown as the left border color |
| Footer | Small text at the bottom of the embed |
| Auto-timestamp | Toggle — adds "Last updated: [date]" to the footer automatically on each edit |
| Thumbnail URL | Small image in the top-right corner |
| Image URL | Large image displayed in the embed body |
| Template | Optional — apply a saved style template (see Section 9) |

---

## 3. Species Guide Manager

**Logic:** The owner designates one channel as the species guide channel and builds it out using named guide cards. Each card is a separate embed covering one topic. Cards can be created, edited, reordered, and deleted without clearing the whole channel.

---

### 👑 Owner

| Command | What It Does |
|---|---|
| `/myo guide setchannel #channel` | Sets which channel is the species guide channel. All guide cards are posted here. |
| `/myo guide create <shortname>` | Creates a new guide card using the same embed builder prompt as `/myo embed create`. Posts it to the guide channel automatically. |
| `/myo guide edit <shortname>` | Edits a guide card and updates the live message in the channel. |
| `/myo guide delete <shortname>` | Removes the card from the channel and the registry. |
| `/myo guide reorder <shortname> <position>` | Moves a card to a specific position in the guide channel. Bot reposts all cards in the correct order. |
| `/myo guide divider <text>` | Posts a plain text divider message between cards (e.g., a section header or decorative line). Saved as part of the card order. |
| `/myo guide list` | Shows all guide cards in their current order — shortname, title, position number. |
| `/myo guide rebuild` | Deletes and reposts all guide cards in order. Use this if the channel gets cluttered with other messages. |

---

### 👤 User

| Command | What It Does |
|---|---|
| `/myo guide` | Posts an ephemeral reply with a link to the guide channel. Quick pointer for users who can't find it. |

---

## 4. Visual & Image Manager

**Logic:** The owner stores image URLs (trait sheets, MYO reference sheets, visual guides) under named shortnames. Images can be posted to any channel on demand or embedded inside guide cards and embeds.

---

### 👑 Owner

| Command | What It Does |
|---|---|
| `/myo image add <shortname> <url>` | Saves an image URL under a name. |
| `/myo image setcaption <shortname> <text>` | Adds a caption that appears below the image when posted. |
| `/myo image post <shortname> #channel` | Posts the image (and caption if set) to a channel as a standalone message. |
| `/myo image update <shortname> <new-url>` | Replaces the stored URL. Does not auto-update previously posted messages — use repost. |
| `/myo image repost <shortname>` | Deletes the old posted message and sends a fresh one with the updated URL. |
| `/myo image delete <shortname>` | Removes from registry. Does not delete already-posted channel messages. |
| `/myo image list` | Shows all stored images — shortname, caption if set, last posted channel. |
| `/myo image group create <groupname>` | Creates an image group. |
| `/myo image group add <groupname> <shortname>` | Adds an image to a group. |
| `/myo image group post <groupname> #channel` | Posts all images in the group to a channel in sequence. |
| `/myo image group list` | Shows all groups and which images are in each. |

---

## 5. Trait Sheet Configurator

**Logic:** The owner defines the official trait list per rarity tier inside the bot. This is the source of truth used during submission pre-checks (see `01_MYO_SYSTEM.md` — Section 9, Trait Pre-Check). It also generates a viewable trait list embed that can be posted to the guide channel.

---

### 👑 Owner

| Command | What It Does |
|---|---|
| `/myo trait add <tier> <trait-name>` | Adds a trait to a rarity tier (Common / Rare / Legendary). |
| `/myo trait remove <tier> <trait-name>` | Removes a trait from a tier. |
| `/myo trait rename <tier> <old-name> <new-name>` | Renames a trait without removing it. |
| `/myo trait list` | Shows all traits organized by tier as an ephemeral embed. |
| `/myo trait post #channel` | Posts the full trait list as an embed to the specified channel. Saves the message ID for future refreshes. |
| `/myo trait refresh` | Edits the live trait list message with any changes made since it was last posted. |

### 👤 User

| Command | What It Does |
|---|---|
| `/myo trait list` | Shows the full trait list organized by tier as an ephemeral reply. |

---

## 6. Species TOS Configurator

**Logic:** The species TOS is built and managed entirely through bot commands. It is stored as a set of named sections (like paragraphs or rules) that together form the full TOS embed. When the owner updates any section, the version number increments automatically and users who had accepted the old version are flagged.

This is separate from any server-wide TOS the general bot manages.

---

### 👑 Owner

| Command | What It Does |
|---|---|
| `/myo tos addsection <title> <text>` | Adds a new section to the TOS. Each section becomes a field in the TOS embed. |
| `/myo tos editsection <title> <new-text>` | Updates a specific section by its title without touching other sections. |
| `/myo tos removesection <title>` | Deletes a section from the TOS. |
| `/myo tos reorder <title> <position>` | Moves a section to a different position in the TOS embed. |
| `/myo tos post #channel` | Posts the full TOS as an embed. Saves the message ID. |
| `/myo tos refresh` | Edits the live TOS message with current sections and bumps the version number. |
| `/myo tos version` | Shows the current TOS version number and when it was last updated. |
| `/myo tos outdated` | Lists all users who accepted an older TOS version and have not re-accepted the current one. |
| `/myo tos broadcast` | Sends a DM to all outdated users prompting them to re-accept before their MYO commands are re-enabled. |

### 👤 User

| Command | What It Does |
|---|---|
| `/myo tos view` | Shows the current species TOS as an ephemeral embed. |
| `/myo tos accept` | Displays the TOS with a confirm button. Logs acceptance with timestamp and version number on confirm. |
| `/myo tos status` | Shows whether they have accepted, which version, and when. |

---

## 7. MYO Announcement System

**Logic:** The owner posts species-specific announcements using a styled embed template. This is separate from any server-wide announcement command the general bot has. `/myo announce` only posts to the designated MYO announcement channel.

---

### 👑 Owner

| Command | What It Does |
|---|---|
| `/myo announce setchannel #channel` | Sets the channel where MYO announcements are posted. |
| `/myo announce settemplate <color> <footer>` | Sets the default color and footer text applied to all announcement embeds automatically. |
| `/myo announce setping @role` | Sets a role that gets pinged whenever an announcement is posted. Leave blank to post without a ping. |
| `/myo announce post <title> <body>` | Posts a styled announcement embed to the announcement channel. Uses the saved template automatically. |
| `/myo announce post <title> <body> --image <url>` | Posts an announcement with an attached image. |
| `/myo announce preview <title> <body>` | Sends the announcement as an ephemeral message for the owner to review before posting publicly. |
| `/myo announce edit <message-id> <new-body>` | Edits a previously posted announcement by its Discord message ID. |

---

## 8. New Member DM Onboarding

**Logic:** When a user accepts the species TOS for the first time, the bot automatically sends them a DM containing a full onboarding package. This replaces a welcome card in the channel — nothing is posted publicly. The DM is the welcome.

The DM is a single embed (or a short sequence of embeds if the content is long) with link buttons for external resources. The owner configures exactly what goes in it.

---

### How It Works

```
User runs /myo tos accept and confirms
         ↓
Bot logs acceptance with timestamp and version number
         ↓
Bot sends a DM to the user with the onboarding embed(s) and link buttons
         ↓
If the user's DMs are closed, the bot posts an ephemeral reply instead:
"Please enable DMs so we can send you the onboarding resources!"
```

The DM is only sent on **first-time acceptance**. Re-accepting after a TOS update does not re-send the DM.

---

### DM Content (Configurable by Owner)

The DM is made up of sections the owner builds out via commands. Each section can have a title, body text, and optional link buttons.

**Default DM structure (owner fills in the content):**

```
📬 Welcome to [Species Name]!

[Welcome message body set by owner]

── Resources ──
[Button: Full MYO Guide]      → links to Google Docs, Toyhouse World, etc.
[Button: Toyhouse World]      → species Toyhouse page
[Button: Visual Trait Guide]  → image or doc link
[Button: Species TOS]         → link to TOS post or external doc

── Channel Directory ──
[Body text listing key channels set by owner]

── Quick Reminders ──
[Body text with TOS highlights or rules set by owner]

── FAQ ──
[Button: Read the FAQ]        → link to FAQ channel or external doc
```

All of this is configured by the owner. No hardcoded content.

---

### 👑 Owner

| Command | What It Does |
|---|---|
| `/myo dm setwelcome <text>` | Sets the opening welcome message body shown at the top of the DM. |
| `/myo dm addsection <title> <text>` | Adds a named section to the DM (e.g., "Quick Reminders," "Channel Directory"). |
| `/myo dm editsection <title> <new-text>` | Edits an existing section's body text. |
| `/myo dm removesection <title>` | Removes a section from the DM. |
| `/myo dm reorder <title> <position>` | Moves a section to a different position in the DM. |
| `/myo dm addbutton <label> <url>` | Adds a link button to the DM (e.g., label: "Full MYO Guide", url: Google Docs link). |
| `/myo dm removebutton <label>` | Removes a link button by its label. |
| `/myo dm setcolor <hex>` | Sets the embed color for the DM. |
| `/myo dm setfooter <text>` | Sets the footer text on the DM embed. |
| `/myo dm preview` | Sends the current DM to the owner as a real DM so they can see exactly what new members receive. |
| `/myo dm test @user` | Sends the current DM to a specific user. Used for testing with staff before going live. |
| `/myo dm resend @user` | Manually re-sends the onboarding DM to a user. For users who missed it or had DMs closed. |

---

### 👤 User

| Command | What It Does |
|---|---|
| `/myo dm resend` | Re-requests the onboarding DM be sent to themselves. Useful if they deleted it or missed it. |

---

## 9. Nice-to-Add Features

### FAQ Manager (Nice to Add)

**Logic:** The owner builds a FAQ as a set of question-answer pairs. The full FAQ can be posted as an embed. Users can also search it by keyword and get matching answers as an ephemeral reply.

| Command | Who | What It Does |
|---|---|---|
| `/myo faq add <question> <answer>` | Owner | Adds a Q&A entry. |
| `/myo faq edit <question> <new-answer>` | Owner | Updates an answer. |
| `/myo faq remove <question>` | Owner | Deletes a Q&A entry. |
| `/myo faq post #channel` | Owner | Posts the full FAQ as an embed. Saves message ID for refreshes. |
| `/myo faq refresh` | Owner | Edits the live FAQ message with current entries. |
| `/myo faq <keyword>` | User | Searches the FAQ by keyword. Returns matching entries as an ephemeral reply. |

---

### Lore / Worldbuilding Posts (Nice to Add)

**Logic:** The owner posts dedicated lore entries in a designated lore channel. Each entry is a named embed with optional tags. Users can search lore entries by keyword.

| Command | Who | What It Does |
|---|---|---|
| `/myo lore setchannel #channel` | Owner | Sets the lore channel. |
| `/myo lore create <title>` | Owner | Creates a lore entry using the embed builder prompt. Posts to lore channel. |
| `/myo lore edit <title>` | Owner | Edits a lore entry and updates the live message. |
| `/myo lore tag <title> <tag>` | Owner | Tags a lore entry (e.g., "history," "geography," "characters") for search filtering. |
| `/myo lore delete <title>` | Owner | Removes the entry from the channel and registry. |
| `/myo lore list` | Owner/Staff | Lists all entries with titles and tags. |
| `/myo lore search <keyword>` | User | Returns matching lore entries as an ephemeral embed. |

---

### Changelog (Nice to Add)

**Logic:** The bot maintains a running changelog of every species update — TOS changes, new traits, rule adjustments, etc. Entries are timestamped automatically on creation. Users can view the most recent entries on demand.

| Command | Who | What It Does |
|---|---|---|
| `/myo changelog add <text>` | Owner | Logs an update entry with an automatic timestamp. |
| `/myo changelog post #channel` | Owner | Posts the full changelog as a paginated embed to a channel. |
| `/myo changelog` | User | Shows the last 10 changelog entries as an ephemeral reply. |

---

### Embed Template Library (Nice to Add)

**Logic:** The owner saves reusable style templates (color, footer, thumbnail) that can be applied to any new MYO embed or guide card. Keeps the species category visually consistent without reconfiguring style settings every time.

| Command | Who | What It Does |
|---|---|---|
| `/myo template save <name> <color> <footer> <thumbnail-url>` | Owner | Saves a style template. |
| `/myo template list` | Owner | Lists all saved templates. |
| `/myo template delete <name>` | Owner | Deletes a template. |
| `/myo template preview <name>` | Owner | Sends a preview embed using the template as an ephemeral message. |

Applying a template during embed creation:
```
/myo embed create <shortname> --template <name>
/myo guide create <shortname> --template <name>
```

The template pre-fills color, footer, and thumbnail. The owner can still override individual fields after applying.
