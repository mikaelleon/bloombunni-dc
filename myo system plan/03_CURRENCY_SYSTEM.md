# 03 — Currency System

There are two completely separate currencies in the server. Earned Currency (EC) is gained through activity and cannot be purchased. Paid Currency (PC) is gained only through real-money top-ups. They have separate wallets and are never interchangeable.

---

## Table of Contents

1. [Currency Overview](#1-currency-overview)
2. [Conversion Reference](#2-conversion-reference)
3. [Earned Currency (EC)](#3-earned-currency-ec)
4. [Paid Currency (PC)](#4-paid-currency-pc)
5. [Top-Up Packages](#5-top-up-packages)
6. [Wallet & Balance](#6-wallet--balance)
7. [Nice-to-Add Features](#7-nice-to-add-features)

---

## 1. Currency Overview

| | Earned Currency (EC) | Paid Currency (PC) |
|---|---|---|
| **How you get it** | Activity, events, games, giveaways | Real-money top-up only |
| **Can you buy it?** | No | Yes |
| **Can you sell it?** | No | No |
| **Can you transfer it?** | Yes (gifting, trading) | No |
| **Used for** | Gacha draws, casino, shop, collectible market | Gacha draws only |

---

## 2. Conversion Reference

```
EARNED CURRENCY
1,000 EC  = $1.00 USD  ≈ ₱59 PHP

PAID CURRENCY
1 PC = $0.85 USD ≈ ₱50 PHP

GACHA DRAW COSTS
1 draw  via EC  = 10,000 EC  = $10.00 USD ≈ ₱590 PHP
10 draws via EC = 100,000 EC = $100.00 USD ≈ ₱5,900 PHP

1 draw  via PC  = 6 PC  ≈ $5.10 USD ≈ ₱300 PHP  (~49% cheaper than EC)
10 draws via PC = 55 PC ≈ $46.75 USD ≈ ₱2,750 PHP (~53% cheaper than EC)
```

> PHP values are based on the current rate of **$1 USD ≈ ₱59 PHP**. Since exchange rates fluctuate, USD is always the source of truth. PHP amounts shown to users should be marked as approximate.

---

## 3. Earned Currency (EC)

**Logic:** EC is the server's activity-based economy. Users earn it through participation and spend it on gacha, casino games, the shop, and the collectible market. It is designed to be abundant but require time to accumulate in meaningful amounts.

### How EC is Earned

| Source | How It Works |
|---|---|
| **Autoresponder commands** | Specific bot commands give small EC payouts on a cooldown. |
| **Earn/daily commands** | A daily EC claim command. Fixed amount, 24-hour cooldown. |
| **Events** | Owner or staff distribute EC as event rewards via command. |
| **Giveaways** | EC is one of the possible giveaway prizes. Bot assigns it to the winner. |
| **Collectible selling** | Users sell collectibles from gacha for EC. |
| **Casino wins** | Winning casino minigames returns EC. |

---

### 👑 Owner

| Command | What It Does |
|---|---|
| `/ec give @user <amount>` | Adds EC to a user's balance. Used for event rewards or corrections. |
| `/ec take @user <amount> <reason>` | Removes EC from a user's balance. |
| `/ec set @user <amount>` | Sets a user's EC balance to an exact number. |
| `/ec setdaily <amount>` | Sets how much EC the daily command gives. |
| `/ec setcooldown <command> <duration>` | Sets the cooldown on EC-earning commands. |
| `/ec leaderboard` | Shows the top EC holders across the server. |
| `/ec log @user` | Shows a full EC transaction history for a user. |

---

### 🛡️ Staff

| Command | What It Does |
|---|---|
| `/ec give @user <amount>` | Can give EC if granted permission by owner. Off by default. |
| `/ec log @user` | View transaction history for moderation purposes. |
| `/ec leaderboard` | View the leaderboard. |

---

### 👤 User

| Command | What It Does |
|---|---|
| `/daily` | Claims the daily EC reward. 24-hour cooldown. |
| `/ec balance` | Shows their current EC balance. |
| `/ec log` | Shows their own transaction history. |
| `/ec gift @user <amount>` | Sends EC to another user. Subject to a daily gifting cap. |

---

## 4. Paid Currency (PC)

**Logic:** PC is premium currency purchased with real money. It is only added to a user's wallet by the owner after confirming payment externally (e.g., GCash, PayPal). PC can only be spent on gacha draws. It cannot be transferred, gifted, or refunded.

PC exists separately from EC at all times. There is no way to earn PC through gameplay.

---

### 👑 Owner

| Command | What It Does |
|---|---|
| `/pc give @user <amount>` | Adds PC to a user's balance after confirming real-money payment. |
| `/pc give @user <package>` | Adds PC using a named package (e.g., `standard`). Bot calculates the correct PC + bonus. |
| `/pc take @user <amount> <reason>` | Removes PC from a user's balance. Used for corrections or disputes. |
| `/pc log @user` | Shows a full PC transaction history for a user, including how PC was added and spent. |
| `/pc receipt @user <package> <payment-ref>` | Logs a payment confirmation with reference number for record-keeping. |

---

### 🛡️ Staff

| Command | What It Does |
|---|---|
| `/pc log @user` | View only — for moderation reference. |

---

### 👤 User

| Command | What It Does |
|---|---|
| `/pc balance` | Shows their current PC balance. |
| `/pc log` | Shows their own PC transaction history — how much was added, when, and how much has been spent. |

> PC cannot be gifted, transferred, or traded between users under any circumstance. If a user asks to transfer PC, the answer is always no.

---

## 5. Top-Up Packages

**Logic:** Instead of asking users to calculate how much PC they want, the owner offers fixed packages at set price points. The owner processes all payments externally and then runs the command to add PC manually.

Larger packages include bonus PC as an incentive to commit to a bigger top-up.

| Package | USD | PHP (≈₱59/USD) | Base PC | Bonus PC | Total PC | What It Buys |
|---|---|---|---|---|---|---|
| **Starter** | $5 | ₱295 | 6 PC | — | **6 PC** | 1 draw exactly |
| **Basic** | $10 | ₱590 | 12 PC | +2 PC | **14 PC** | 2 draws + 2 PC saved |
| **Standard** | $25 | ₱1,475 | 30 PC | +5 PC | **35 PC** | 5 draws + 5 PC saved |
| **Premium** | $50 | ₱2,950 | 60 PC | +12 PC | **72 PC** | 1×10-draw + 2 singles + 5 PC saved |

**Bonus PC breakdown:**
- Starter: No bonus — this is intentionally tight to nudge users toward Basic.
- Basic: +2 PC (~17% bonus)
- Standard: +5 PC (~17% bonus)
- Premium: +12 PC (~20% bonus) — best value per dollar

---

### 👑 Owner

| Command | What It Does |
|---|---|
| `/topup @user starter` | Adds 6 PC to the user. |
| `/topup @user basic` | Adds 14 PC to the user. |
| `/topup @user standard` | Adds 35 PC to the user. |
| `/topup @user premium` | Adds 72 PC to the user. |
| `/topup packages` | Displays the current package list with prices and PC amounts. |
| `/topup setbonus <package> <amount>` | Adjusts the bonus PC for a specific package. |

---

### 👤 User

| Command | What It Does |
|---|---|
| `/topup info` | Displays all available packages — USD price, PHP equivalent, total PC, and what it buys in draws. |

---

## 6. Wallet & Balance

**Logic:** Every user has a unified wallet that stores both balances. They can view both at once with one command. The wallet also shows what their balance can buy in draws.

### 👑 Owner / 🛡️ Staff

| Command | What It Does |
|---|---|
| `/wallet @user` | View another user's full wallet — EC balance, PC balance, and draw purchasing power. |

---

### 👤 User

| Command | What It Does |
|---|---|
| `/wallet` | Shows their EC balance, PC balance, and a breakdown of how many draws each balance can afford. |

**Example wallet embed:**
```
💰 YOUR WALLET

⭐ Earned Currency:   45,200 EC
   → Enough for: 4 single draws (40,000 EC), 5,200 EC remaining

💎 Paid Currency:     20 PC
   → Enough for: 3 single draws (18 PC), 2 PC remaining

Use /gacha draw or /gacha draw10 to spend.
```

---

## 7. Nice-to-Add Features

### EC Gifting Cap (Nice to Add)

**Logic:** Users can send EC to each other, but there is a daily limit on how much any one user can gift per day. This prevents EC being rapidly funneled between accounts to bypass earning systems.

| Command | Who | What It Does |
|---|---|---|
| `/ec giftcap set <amount>` | Owner | Sets the maximum EC a user can gift per day. |
| `/ec giftcap view` | Owner/Staff | Shows the current daily gift cap. |

---

### EC Leaderboard Seasons (Nice to Add)

**Logic:** EC balances are tracked in seasonal snapshots. At the end of each season, the top holders are rewarded (e.g., a coupon or exclusive role), and the leaderboard resets. Balances themselves do not reset — only the leaderboard tracking.

| Command | Who | What It Does |
|---|---|---|
| `/ec season end` | Owner | Ends the current season, rewards top holders, and resets the leaderboard. |
| `/ec season start <name>` | Owner | Starts a new named season. |
| `/ec season leaderboard` | User | Shows the current season leaderboard. |

---

### Transaction Receipts (Nice to Add)

**Logic:** Every time EC or PC is added or spent, the bot logs it with a reference ID. Users can pull a receipt for any specific transaction by ID. Useful for dispute resolution and personal record-keeping.

| Command | Who | What It Does |
|---|---|---|
| `/ec receipt <transaction-id>` | User | Shows details for a specific EC transaction. |
| `/pc receipt <transaction-id>` | User | Shows details for a specific PC transaction. |

---

### PHP Rate Update (Nice to Add)

**Logic:** Since the exchange rate fluctuates, the owner can update the stored PHP conversion rate so that the `/topup info` command always shows accurate local prices.

| Command | Who | What It Does |
|---|---|---|
| `/rate setphp <rate>` | Owner | Updates the PHP/USD rate used for display purposes. Does not affect PC pricing — PC prices are fixed in USD. |
| `/rate view` | User | Shows the current stored PHP rate and when it was last updated. |
