# 04 — Gacha System

The gacha system lets users spend Earned Currency (EC) or Paid Currency (PC) to draw prizes from a banner. Prizes range from common collectibles to rare MYO coupons and owner-drawn art. Rates rotate automatically every 3 hours and a pity system guarantees higher rarity pulls after a stretch of bad luck.

---

## Table of Contents

1. [How Gacha Works (Overview)](#1-how-gacha-works-overview)
2. [Banner Management](#2-banner-management)
3. [Prize Pool & Rarity Tiers](#3-prize-pool--rarity-tiers)
4. [Rate Rotation](#4-rate-rotation)
5. [Drawing](#5-drawing)
6. [Pity System](#6-pity-system)
7. [Recommended Features](#7-recommended-features)
8. [Nice-to-Add Features](#8-nice-to-add-features)

---

## 1. How Gacha Works (Overview)

```
Owner creates a banner with a prize pool and rate ranges
         ↓
Banner goes live — users can view current rates and costs
         ↓
Every 3 hours, rates randomly shift within owner-set ranges
         ↓
User spends EC or PC to draw 1 or 10 times
         ↓
Bot rolls randomly based on current rates and gives the prize
         ↓
Pity counter tracks dry streaks — guarantees rare+ after threshold
         ↓
Owner closes banner when done, optionally starts a new one
```

---

## 2. Banner Management

**Logic:** Only one banner is active at a time. A banner defines the prize pool, rate ranges per rarity tier, and how long it runs. The owner sets everything up before going live. Users cannot interact with the gacha if no banner is active.

### 👑 Owner

| Command | What It Does |
|---|---|
| `/banner create <name>` | Creates a new banner in draft mode. You configure it before going live. |
| `/banner setprize <tier> <prize>` | Adds a prize to a tier's prize pool (e.g., `/banner setprize common "Angel Feather"`). Multiple prizes per tier are allowed — the bot picks one randomly when that tier is rolled. |
| `/banner setrate <tier> <min>% <max>%` | Sets the rate range for a tier. The bot picks a random value within this range every 3 hours. |
| `/banner setcost ec <single> <ten>` | Sets the EC cost for 1 draw and 10 draws. |
| `/banner setcost pc <single> <ten>` | Sets the PC cost for 1 draw and 10 draws. |
| `/banner setpity soft <draws>` | Sets the draw count at which soft pity begins (rates quietly increase). |
| `/banner setpity hard <draws>` | Sets the draw count that guarantees an Epic or higher pull. |
| `/banner launch` | Makes the banner live. Users can now draw. |
| `/banner end` | Closes the active banner. Channel message is posted notifying users. |
| `/banner info` | Shows all details of the current banner — name, prize pool, rate ranges, costs, pity settings, total draws since launch. |
| `/banner log` | Shows a full draw history for the current banner — who drew, what they got, when. |

**Rate Validation:**
When setting rates, the bot checks that all four tiers' minimum rates add up to 100% or less, and their maximum rates add up to 100% or more. If the math is impossible to satisfy simultaneously, the bot warns the owner before allowing launch.

**Example valid rate ranges:**
```
Common:    60–75%
Rare:      15–25%
Epic:      6–12%
Legendary: 1–4%

Min total: 82% ✅ (under 100)
Max total: 116% ✅ (over 100)
→ A valid distribution is always possible within these ranges.
```

---

### 🛡️ Staff

| Command | What It Does |
|---|---|
| `/banner info` | View current banner details. |
| `/banner log` | View draw history. |

---

### 👤 User

| Command | What It Does |
|---|---|
| `/gacha info` | Shows the current banner name, prize pool by tier, current rates, costs, and countdown to next rate rotation. |
| `/gacha rates` | Shows only the current rates and the time until the next rotation. |

---

## 3. Prize Pool & Rarity Tiers

**Logic:** Prizes are grouped by rarity tier. When the bot rolls a draw and lands on a tier (e.g., Rare), it then randomly picks one prize from that tier's prize pool. This means you can have multiple different prizes at the same rarity level.

| Tier | Symbol | Suggested Rate Range | Example Prizes |
|---|---|---|---|
| **Common** | ⭐ | 60–75% | Collectible items, small EC bundles, cosmetic roles |
| **Rare** | ⭐⭐ | 15–25% | Larger EC bundles, exclusive server roles, profile flair |
| **Epic** | ⭐⭐⭐ | 6–12% | Common MYO coupons, mid-tier collectibles |
| **Legendary** | ⭐⭐⭐⭐ | 1–4% | Rare/Legendary MYO coupons, free art request from owner |

**Prize types:**
- **EC bundles** — Bot automatically adds the EC to the user's wallet on pull.
- **MYO coupons** — Bot automatically adds the coupon to the user's MYO inventory.
- **Roles** — Bot automatically assigns the role to the user on pull.
- **Art requests** — Bot DMs the owner noting that this user has won an art request and logs it. Fulfillment is manual.
- **Collectibles** — Bot adds the item to the user's collectible inventory.

---

## 4. Rate Rotation

**Logic:** Every 3 hours, the bot automatically recalculates the rates for each tier. It picks a random value within the configured min–max range for each tier and balances them so they total exactly 100%. This creates natural variance and makes some windows better than others to draw in.

The rotation is automatic — the owner does not trigger it manually.

**What happens on rotation:**
1. Bot picks a new random rate within the range for each tier.
2. Rates are normalized to sum to exactly 100%.
3. The rotation timestamp is updated.
4. The `/gacha rates` and `/gacha info` displays update automatically.

**Transparency:**
- All rate changes are logged privately with timestamps (owner can view via `/banner log`).
- Users can always see the current rates via `/gacha rates`.
- The countdown to the next rotation is always visible.

### 👑 Owner

| Command | What It Does |
|---|---|
| `/banner rotateinterval <hours>` | Changes how often rates rotate. Default is 3 hours. |
| `/banner forcerotate` | Immediately triggers a rotation outside of the normal schedule. |

---

## 5. Drawing

**Logic:** Users choose how many draws they want and which currency to pay with. The bot deducts the cost, rolls the result, and displays it as an embed. For 10 draws, all 10 results are shown together in one embed.

### 👤 User

| Command | What It Does |
|---|---|
| `/gacha draw` | Initiates 1 draw. Bot prompts: "Use EC or PC?" via two buttons. |
| `/gacha draw10` | Initiates 10 draws. Bot prompts: "Use EC or PC?" via two buttons. |

**Draw flow:**
```
User runs /gacha draw
     ↓
Bot shows two buttons: [Use Earned Currency] [Use Paid Currency]
     ↓
User clicks one
     ↓
Bot checks if user has enough of the chosen currency
     ↓
If yes: deduct cost → roll → display result
If no:  show error with current balance and how much is needed
```

**Result embed (single draw):**
```
🎰 GACHA DRAW — Batch #4 Banner

✨ ⭐⭐ RARE PULL! ✨

🎁 You received: Azure Wing Fragment (Collectible)
   Added to your inventory.

💎 PC spent: 6    |    PC remaining: 14
```

**Result embed (10 draws):**
```
🎰 10x GACHA DRAW — Batch #4 Banner

1. ⭐ Common  →  Star Shard (Collectible)
2. ⭐ Common  →  500 EC
3. ⭐⭐ Rare  →  Moonveil Role
4. ⭐ Common  →  Angel Feather (Collectible)
5. ⭐ Common  →  500 EC
6. ⭐ Common  →  Star Shard (Collectible)
7. ⭐⭐ Rare  →  1,000 EC
8. ⭐ Common  →  Angel Feather (Collectible)
9. ⭐ Common  →  500 EC
10. ⭐⭐⭐ EPIC → Common MYO Coupon 🎉

All items added to your inventory.
EC spent: 100,000  |  EC remaining: 23,400
```

---

## 6. Pity System

**Logic:** The pity system guarantees that users eventually get a high-rarity pull even on bad luck. It tracks how many draws a user has made since their last Epic or Legendary pull. At certain thresholds, the system kicks in.

**Two pity stages:**

| Stage | When It Activates | What It Does |
|---|---|---|
| **Soft pity** | After X consecutive draws with no Epic+ | Rate for Epic and Legendary quietly increases each draw (e.g., +1% per draw after threshold) |
| **Hard pity** | After Y consecutive draws with no Epic+ | Next draw is **guaranteed** Epic or Legendary, regardless of rolled rate |

**Default suggested thresholds:**
- Soft pity begins at draw **40**
- Hard pity triggers at draw **60**

These are configurable by the owner per banner.

**Pity rules:**
- Pity counter resets to 0 after any Epic or Legendary pull.
- Pity carries over between sessions (stored in the database).
- Pity resets when a new banner launches.
- Pity tracks EC draws and PC draws together — they share the same counter.

### 👑 Owner

| Command | What It Does |
|---|---|
| `/banner setpity soft <draws>` | Sets when soft pity begins. |
| `/banner setpity hard <draws>` | Sets the hard pity guarantee threshold. |
| `/banner pityreset @user` | Manually resets a specific user's pity counter. |

### 👤 User

| Command | What It Does |
|---|---|
| `/gacha pity` | Shows their current pity counter and how far they are from soft and hard pity thresholds. |

**Example pity display:**
```
🎯 YOUR PITY STATUS

Draws since last Epic+: 38
Soft pity begins at:    40 (2 draws away — rates will start increasing)
Hard pity guarantee:    60 (22 draws away)
```

---

## 7. Recommended Features

### Lucky Pull Showcase Channel (Recommended)

**Logic:** Whenever a user pulls an Epic or Legendary prize, the bot automatically posts a showcase message in a designated public channel. This creates excitement and shows the community that rare prizes do drop.

| Command | Who | What It Does |
|---|---|---|
| `/showcase setchannel #channel` | Owner | Sets which channel showcase posts appear in. |
| `/showcase off` | Owner | Disables showcase posts entirely. |
| `/gacha hidepulls` | User | Opts out of having their pulls shown in the showcase channel. |

**Example showcase post:**
```
🌟 LEGENDARY PULL! 🌟

@username just pulled a Legendary MYO Coupon from the Batch #4 Banner!
Congratulations! 🎉
```

---

### Gacha Analytics (Recommended)

**Logic:** The owner can review banner performance — how many draws were made, how many prizes of each tier dropped, and how much EC/PC was spent in total. Useful for balancing rates and evaluating banner popularity.

| Command | Who | What It Does |
|---|---|---|
| `/gacha stats` | Owner | Shows total draws, tier breakdown (how many of each rarity dropped), total EC spent, total PC spent, and legendary drop count for the current banner. |
| `/gacha stats <banner-name>` | Owner | Shows the same stats for a past banner by name. |

---

## 8. Nice-to-Add Features

### Daily Free Pull (Nice to Add)

**Logic:** Each user gets one free pull per day from a simplified free banner. This banner has lower rates and no MYO coupon prizes — only minor collectibles and small EC. It encourages daily login without devaluing the main gacha.

| Command | Who | What It Does |
|---|---|---|
| `/gacha daily` | User | Claims the daily free pull. 24-hour cooldown. Only available when a main banner is active. |
| `/gacha daily setpool` | Owner | Configures the prizes available in the free daily pull pool. |

---

### Limited / Seasonal Banners (Nice to Add)

**Logic:** The owner can create a time-limited banner that runs alongside or replaces the main banner. Limited banners can have exclusive collectibles not available in the regular pool. When the limited banner ends, its exclusive prizes are gone.

| Command | Who | What It Does |
|---|---|---|
| `/banner limited create <name> <duration>` | Owner | Creates a timed limited banner. Runs for the specified duration then auto-closes. |
| `/banner limited info` | User | Shows info on the current limited banner if one is active. |

---

### Draw History (Nice to Add)

**Logic:** Users can review their own pull history — what they pulled, when, from which banner, and which currency they used.

| Command | Who | What It Does |
|---|---|---|
| `/gacha history` | User | Shows their personal draw history, paginated. |
| `/gacha history @user` | Owner/Staff | Shows another user's draw history. |
