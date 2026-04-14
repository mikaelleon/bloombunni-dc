# 06 — Collectible System

Collectibles are items won from gacha draws. They are the most common type of prize and serve as a secondary economy layer — users collect them, trade them, sell them back for EC, or list them on the marketplace. They are designed to keep EC circulating and give players something to do with common pulls beyond just stacking currency.

---

## Table of Contents

1. [How Collectibles Work (Overview)](#1-how-collectibles-work-overview)
2. [Collectible Items](#2-collectible-items)
3. [Inventory](#3-inventory)
4. [Selling Collectibles](#4-selling-collectibles)
5. [Collectible Trading](#5-collectible-trading)
6. [Marketplace](#6-marketplace)
7. [Recommended Features](#7-recommended-features)
8. [Nice-to-Add Features](#8-nice-to-add-features)

---

## 1. How Collectibles Work (Overview)

```
User pulls a gacha draw → receives a collectible item
         ↓
Item is added to their inventory automatically
         ↓
User can:
  → Sell to the bot for a fixed EC value
  → Trade directly with another user
  → List on the marketplace for other users to buy
         ↓
EC flows back into the economy from sold collectibles
```

Collectibles are server-specific — they have no real-money value and exist purely within the Discord server economy. They cannot be exchanged for PC.

---

## 2. Collectible Items

**Logic:** The owner defines what collectibles exist, their names, their rarity tier, and their base EC sell value. A collectible must be created by the owner before it can appear in the gacha prize pool.

Each collectible has:
- A name (e.g., "Angel Feather")
- A rarity tier (Common, Rare, Epic)
- A base sell value in EC (what the bot pays when a user sells directly to the bot)
- An optional description or lore blurb
- An optional emoji for display purposes

### 👑 Owner

| Command | What It Does |
|---|---|
| `/collectible create <n> <tier> <sell-value>` | Creates a new collectible item and adds it to the item registry. |
| `/collectible setdesc <n> <description>` | Adds a lore description to an existing collectible. |
| `/collectible setemoji <n> <emoji>` | Sets a display emoji for the collectible. |
| `/collectible setsell <n> <ec-value>` | Updates the base EC sell value for an item. |
| `/collectible delete <n>` | Removes a collectible from the registry. Items already in player inventories remain — only new drops stop. |
| `/collectible list` | Shows all collectibles in the registry with their tier, sell value, and which banner pool(s) they are in. |
| `/collectible give @user <n> <quantity>` | Directly gives a collectible to a user. Used for event rewards or corrections. |
| `/collectible take @user <n> <quantity>` | Removes a collectible from a user's inventory. |

---

### 🛡️ Staff

| Command | What It Does |
|---|---|
| `/collectible list` | View the full item registry. |
| `/collectible give @user <n> <quantity>` | Can give items if granted permission by owner. Off by default. |

---

### 👤 User

| Command | What It Does |
|---|---|
| `/collectible info <n>` | Shows an item's description, tier, and base sell value. |
| `/collectible list` | Shows all collectibles in the registry — useful for knowing what exists before trading or buying. |

---

## 3. Inventory

**Logic:** Every user has a collectible inventory that stores all items they have received from gacha or trades. Items are grouped by name and show quantity. The inventory is private to the user unless viewed by staff/owner.

### 👑 Owner / 🛡️ Staff

| Command | What It Does |
|---|---|
| `/inventory @user` | Views another user's full collectible inventory. |

---

### 👤 User

| Command | What It Does |
|---|---|
| `/inventory` | Shows all collectibles they own, grouped by item name with quantity. Also shows total estimated EC value if all items were sold to the bot at base sell price. |

**Example inventory display:**
```
🎒 YOUR INVENTORY

🪶 Angel Feather       ×5     (Base sell: 500 EC each)
💫 Star Shard          ×3     (Base sell: 800 EC each)
🌙 Azure Wing Fragment ×1     (Base sell: 2,000 EC each)

Total estimated value: 7,900 EC
```

---

## 4. Selling Collectibles

**Logic:** Users can sell collectibles directly back to the bot for a fixed EC amount. The bot pays out of a virtual economy pool (not from other players). This is the baseline liquidity for collectibles — users always have somewhere to sell.

The sell value is set by the owner per item. It is lower than what items typically sell for on the marketplace, giving marketplace trading a reason to exist.

### 👤 User

| Command | What It Does |
|---|---|
| `/sell <item-name> <quantity>` | Sells the specified quantity of an item to the bot at the base sell rate. EC is added to their wallet immediately. |
| `/sell all <item-name>` | Sells the entire stack of an item. |

**Example:**
```
User: /sell "Angel Feather" 3
Bot:  Sold 3× Angel Feather for 1,500 EC.
      EC added to your wallet. Balance: 16,500 EC.
```

---

## 5. Collectible Trading

**Logic:** Two users can trade collectibles directly with each other. Both must agree before anything is exchanged. Trades are logged for dispute reference. EC can optionally be included in a trade as part of the deal.

### How a Trade Works

```
User A opens a trade with User B
         ↓
Both users add items (and optionally EC) to their respective side of the trade
         ↓
Either user can review the trade at any time
         ↓
Both users confirm the trade
         ↓
Bot executes the swap simultaneously — no partial transfers
         ↓
Trade is logged with a reference ID
```

If either user cancels at any point before both have confirmed, the trade is cancelled and nothing is moved.

---

### 👑 Owner / 🛡️ Staff

| Command | What It Does |
|---|---|
| `/trade log` | Shows a log of recent trades — who traded what with whom, timestamp, reference ID. |
| `/trade log <ref-id>` | Shows the full details of a specific trade. Used for disputes. |
| `/trade cancel <ref-id>` | Force-cancels a pending trade. Used if a trade is stuck or fraudulent. |

---

### 👤 User

| Command | What It Does |
|---|---|
| `/trade @user` | Opens a trade session with the specified user. The other user must confirm they want to trade before items can be added. |
| `/trade add item <n> <quantity>` | Adds items to your side of the active trade. |
| `/trade add ec <amount>` | Adds EC to your side of the active trade. |
| `/trade remove item <n> <quantity>` | Removes items from your side before confirming. |
| `/trade view` | Shows both sides of the current trade offer. |
| `/trade confirm` | Confirms your side of the trade. Once both users confirm, the swap executes. |
| `/trade cancel` | Cancels the trade entirely. Nothing is moved. |

**Safeguards:**
- A user cannot add more of an item than they own.
- A user cannot add more EC than their current balance.
- If the other user cancels, the initiating user is notified by DM.
- Trades auto-expire after 15 minutes of inactivity (configurable).

---

## 6. Marketplace

**Logic:** The marketplace is an open player-to-player shop where users list collectibles at their own asking price. Other users can browse listings and buy. The bot acts as the middleman — items and EC are held in escrow until a sale completes. The owner can take a percentage of each sale as a tax (EC sink to reduce inflation).

### How the Marketplace Works

```
Seller lists an item with a price
         ↓
Bot holds the item in escrow (removed from seller's inventory)
         ↓
Listing appears in the marketplace
         ↓
Buyer finds the listing and pays the asking price
         ↓
Bot transfers item to buyer and EC (minus tax) to seller
         ↓
Sale is logged
```

If the listing expires or the seller cancels, the item is returned to their inventory.

---

### 👑 Owner

| Command | What It Does |
|---|---|
| `/market tax set <percent>` | Sets the marketplace tax percentage. The bot takes this cut from each sale and removes it from circulation (EC sink). Default: 5%. |
| `/market tax view` | Shows the current tax rate. |
| `/market remove <listing-id>` | Force-removes a listing. Item is returned to the seller. Used for rule violations. |
| `/market log` | Shows a log of recent marketplace sales — item, price, seller, buyer, timestamp. |
| `/market setexpiry <days>` | Sets how long listings stay active before auto-expiring. Default: 7 days. |

---

### 🛡️ Staff

| Command | What It Does |
|---|---|
| `/market log` | View recent sales log. |
| `/market remove <listing-id>` | Can remove listings if granted permission. Off by default. |

---

### 👤 User

| Command | What It Does |
|---|---|
| `/market list <item-name> <quantity> <price>` | Lists items for sale. Price is the total EC for the listed quantity. Item is held in escrow immediately. |
| `/market browse` | Shows all active listings in a paginated embed, sorted by most recent. |
| `/market browse <item-name>` | Filters listings to a specific item. |
| `/market buy <listing-id>` | Purchases a listing. EC is deducted immediately, item is transferred, seller receives EC minus tax. |
| `/market cancel <listing-id>` | Cancels one of your own listings. Item is returned from escrow to your inventory. |
| `/market mylistings` | Shows all of your active listings with their IDs, item, quantity, price, and time remaining. |

**Example marketplace embed:**
```
🛒 MARKETPLACE  (Page 1 of 3)

ID: #0041  🪶 Angel Feather ×3    → 1,800 EC   (600 EC each)  by @username
ID: #0039  💫 Star Shard ×1       → 1,000 EC                  by @username2
ID: #0037  🌙 Azure Wing ×1       → 5,500 EC                  by @username3

Use /market buy <ID> to purchase.
```

**Tax example:**
```
Sale: 1,800 EC
Tax:  90 EC (5%)
Seller receives: 1,710 EC
```

---

## 7. Recommended Features

### Price History (Recommended)

**Logic:** The bot tracks the last 10 sales of each item and shows the average price. This helps buyers and sellers gauge fair market value without guessing.

| Command | Who | What It Does |
|---|---|---|
| `/market price <item-name>` | User | Shows the last 10 sale prices for an item and the rolling average. Also shows the base bot sell value as a floor reference. |

---

### Listing Notifications (Recommended)

**Logic:** Users can set a watch on a specific item. When that item is listed on the marketplace, they get a DM notification.

| Command | Who | What It Does |
|---|---|---|
| `/market watch <item-name>` | User | Adds an item to their watch list. They get a DM when it's listed. |
| `/market unwatch <item-name>` | User | Removes an item from their watch list. |
| `/market watchlist` | User | Shows all items they are currently watching. |

---

## 8. Nice-to-Add Features

### Collectible Showcase (Nice to Add)

**Logic:** Users can set a "display case" of up to 5 collectibles they want to show off on their public profile. Other users can view someone's showcase without needing inventory access.

| Command | Who | What It Does |
|---|---|---|
| `/showcase add <item-name>` | User | Adds an item to their display case (max 5). |
| `/showcase remove <item-name>` | User | Removes an item from their display case. |
| `/showcase @user` | User | Views another user's public display case. |

---

### Bulk Sell (Nice to Add)

**Logic:** Users can sell all duplicates of every item at once — keeps only 1 of each item they own and sells the rest at base price. Saves time for users with large inventories from lots of gacha pulls.

| Command | Who | What It Does |
|---|---|---|
| `/sell duplicates` | User | Sells all copies beyond 1 of every item in their inventory at base sell price. Bot shows a preview of what will be sold and asks for confirmation before executing. |

---

### Collectible Sets (Nice to Add)

**Logic:** The owner can define a "set" — a collection of specific items that, when all held simultaneously, unlock a bonus reward (EC, a role, or a coupon). The bot checks if the user holds the complete set and automatically awards the bonus.

This gives users a reason to collect specific items rather than selling everything immediately.

| Command | Who | What It Does |
|---|---|---|
| `/set create <set-name> <items...>` | Owner | Defines a collectible set with a list of required items. |
| `/set setreward <set-name> <reward>` | Owner | Sets what the user receives upon completing the set. |
| `/set list` | User | Shows all defined sets, which items are needed, and the reward for completion. |
| `/set check` | User | Checks if they currently hold all items for any set and claims the reward if so. |
| `/set check <set-name>` | User | Checks progress toward a specific set. |

**Example set:**
```
📦 SET: Celestial Collection
Required: Angel Feather, Star Shard, Azure Wing Fragment, Moonveil Shard
Reward:   5,000 EC + Celestial Collector role

Your progress:
✅ Angel Feather       (owned)
✅ Star Shard          (owned)
✅ Azure Wing Fragment (owned)
❌ Moonveil Shard      (not owned — check the marketplace!)
```
