# 05 — Casino Minigames

The casino is a set of EC-only minigames. Paid Currency (PC) is never used here — this keeps real-money gambling out of the equation entirely. All games use Earned Currency only. There are five games ranging from pure chance to light strategy.

---

## Table of Contents

1. [General Casino Rules](#1-general-casino-rules)
2. [Coinflip](#2-coinflip)
3. [Slots](#3-slots)
4. [Number Guess](#4-number-guess)
5. [High Card](#5-high-card)
6. [Blackjack](#6-blackjack)
7. [Casino Configuration (Owner)](#7-casino-configuration-owner)
8. [Recommended Features](#8-recommended-features)
9. [Nice-to-Add Features](#9-nice-to-add-features)

---

## 1. General Casino Rules

These rules apply to every game.

- **EC only.** PC cannot be bet or won in any casino game.
- **Minimum bet** — configurable per game by the owner. Default: 500 EC.
- **Maximum bet** — configurable per game. Default: 50,000 EC.
- **Daily loss limit** — each user has a cap on how much EC they can lose per day across all games combined. Once hit, they are blocked from casino games until the next day. Configurable by owner.
- **Win cooldown** — after winning, a user must wait a short period before re-betting that win. Default: 10 minutes. Reduces compulsive looping.
- **No negative balance** — the bot will never let a user bet more than their current EC balance.

---

## 2. Coinflip

**Skill level:** None — pure chance.
**Speed:** Instant.

### How It Works

The user bets an amount of EC and picks a side: heads or tails. The bot flips a coin. 50/50 chance. Correct guess doubles the bet. Wrong guess loses the bet.

```
User: /coinflip 5000 heads
Bot:  🪙 Flipping...
      Result: TAILS
      ❌ Wrong call. You lost 5,000 EC.
```

```
User: /coinflip 5000 heads
Bot:  🪙 Flipping...
      Result: HEADS
      ✅ Correct! You won 5,000 EC.
```

| Outcome | Payout |
|---|---|
| Correct guess | +1× bet (doubles bet) |
| Wrong guess | −1× bet (loses bet) |

### 👤 User

| Command | What It Does |
|---|---|
| `/coinflip <amount> <heads/tails>` | Places a coinflip bet. |

---

## 3. Slots

**Skill level:** None — pure chance.
**Speed:** Instant.

### How It Works

The user bets EC and spins three reels. Each reel randomly lands on a symbol. Matching symbols across the three reels pays out a multiplier based on symbol rarity. No match means the bet is lost.

**Symbols and payouts:**

| Result | Payout |
|---|---|
| 3× Common symbol (e.g., 🌟🌟🌟) | 2× bet |
| 3× Rare symbol (e.g., 💎💎💎) | 5× bet |
| 3× Jackpot symbol (e.g., 👑👑👑) | 20× bet |
| 2× of any matching symbol | 0.5× bet (returns half the bet) |
| No match | Lose bet |

Symbol frequency on each reel (configurable):
- Common symbols: appear most often
- Rare symbols: appear less often
- Jackpot symbol: appears rarely

```
User: /slots 3000
Bot:  🎰 Spinning...
      [ 🌟 | 💎 | 🌟 ]
      No match. ❌ You lost 3,000 EC.
```

```
User: /slots 3000
Bot:  🎰 Spinning...
      [ 💎 | 💎 | 💎 ]
      ⭐⭐ Rare match! ✅ You won 15,000 EC (5× your bet)!
```

### 👤 User

| Command | What It Does |
|---|---|
| `/slots <amount>` | Places a slots bet and spins. |

---

## 4. Number Guess

**Skill level:** None — pure chance.
**Speed:** Instant.

### How It Works

The user bets EC and picks a number between 1 and 10. The bot picks a random number in the same range. If they match, the user wins a large multiplier. If not, they lose the bet.

The high payout exists because the odds of winning are 1 in 10 (10%).

```
User: /guess 2000 7
Bot:  🎲 The number was... 3
      ❌ Wrong. You lost 2,000 EC.
```

```
User: /guess 2000 7
Bot:  🎲 The number was... 7
      🎉 Correct! You won 16,000 EC (8× your bet)!
```

| Outcome | Payout |
|---|---|
| Correct guess (1 in 10 chance) | 8× bet |
| Wrong guess | Lose bet |

> The 8× payout on a 10% chance gives the house a small 20% edge, keeping the game sustainable for the server economy.

### 👤 User

| Command | What It Does |
|---|---|
| `/guess <amount> <1–10>` | Places a guess bet. |

---

## 5. High Card

**Skill level:** None — pure chance.
**Speed:** Instant.

### How It Works

The user bets EC. The bot deals one card to the user and one to itself simultaneously. The higher card wins. If both cards have the same rank, the suit breaks the tie.

**Card ranking (low to high):**
```
2  3  4  5  6  7  8  9  10  J  Q  K  A
```

**Suit ranking as tiebreaker (low to high):**
```
♣ Clubs < ♦ Diamonds < ♥ Hearts < ♠ Spades
```

A true tie (identical rank AND suit) is impossible in a standard deck shuffle, so every hand has a definitive winner.

```
User: /highcard 4000
Bot:  🃏 Drawing cards...

      Your card:    Q♥
      Dealer card:  Q♦

      ♥ Hearts beats ♦ Diamonds on tiebreak.
      ✅ You win! +4,000 EC.
```

```
User: /highcard 4000
Bot:  🃏 Drawing cards...

      Your card:    7♠
      Dealer card:  A♣

      ❌ Dealer wins. You lost 4,000 EC.
```

| Outcome | Payout |
|---|---|
| Your card is higher | +1× bet |
| Dealer's card is higher | −1× bet |

High Card is the fastest and simplest game — pure 50/50 chance with instant results. Good for users who just want a quick bet.

### 👤 User

| Command | What It Does |
|---|---|
| `/highcard <amount>` | Places a high card bet. |

---

## 6. Blackjack

**Skill level:** Low to medium — player decisions affect outcome.
**Speed:** Short (a few back-and-forth interactions).

### How It Works

The goal is to build a hand value as close to 21 as possible without going over. The user plays against the bot acting as the dealer. Both start with 2 cards. The user makes decisions on their hand; the dealer follows fixed automatic rules.

**Card values:**
```
2–10      = face value
J, Q, K   = 10
Ace       = 11, automatically becomes 1 if 11 would bust you
```

**A round step by step:**
```
1. User bets with /blackjack <amount>
2. Bot deals 2 cards to user (both shown) and 2 to itself (one shown, one hidden)
3. User chooses an action via buttons
4. Once user stands or busts, dealer reveals hidden card and plays out their hand
5. Whoever is closest to 21 without busting wins
```

---

### Player Actions (button-based)

| Button | What It Does |
|---|---|
| **Hit** | Draws one more card. User can hit multiple times. |
| **Stand** | Locks the hand. Dealer now plays automatically. |
| **Double Down** | Doubles the bet amount, draws exactly one more card, then auto-stands. Only available on the first action. |

---

### Dealer Rules (automatic — no player input)

- Dealer always hits on 16 or under.
- Dealer always stands on 17 or above.
- Dealer has no choice — the rules are fixed and always followed.

---

### Outcomes and Payouts

| Result | Payout |
|---|---|
| User busts (goes over 21) | Lose bet immediately — no dealer reveal needed |
| Dealer busts, user did not | +1× bet |
| User is closer to 21 | +1× bet |
| Dealer is closer to 21 | Lose bet |
| Tie (same hand value) | Bet is returned — no win, no loss |
| Blackjack (Ace + 10-value card on first 2 cards) | +1.5× bet (e.g., bet 10,000 EC → win 15,000 EC) |

---

### Example Round

```
User: /blackjack 10000

🃏 BLACKJACK — Bet: 10,000 EC

YOUR HAND:   [K♠] [7♦]  = 17
DEALER:      [A♣] [?]

> [ Hit ] [ Stand ] [ Double Down ]

--- User clicks Stand ---

🤖 Dealer reveals: [A♣] [6♥] = 17
🤖 Dealer must hit on 16 or less... dealer stands on 17.

YOUR HAND:    17
DEALER HAND:  17

🤝 It's a tie (push)! Your 10,000 EC bet has been returned.
```

```
YOUR HAND:   [A♠] [K♦]  = 21 (Blackjack!)
DEALER:      [9♣] [?]

🎉 BLACKJACK! You win 15,000 EC (1.5× your bet).
```

### 👤 User

| Command | What It Does |
|---|---|
| `/blackjack <amount>` | Places a blackjack bet and starts the round. |

---

## 7. Casino Configuration (Owner)

All settings below apply globally to all casino games unless specified otherwise.

### 👑 Owner

| Command | What It Does |
|---|---|
| `/casino setmin <game> <amount>` | Sets the minimum bet for a specific game. |
| `/casino setmax <game> <amount>` | Sets the maximum bet for a specific game. |
| `/casino setloss <daily-amount>` | Sets the daily EC loss limit per user across all games. |
| `/casino setcooldown <minutes>` | Sets the win cooldown — how long after winning before the user can bet again. |
| `/casino enable <game>` | Enables a specific game. |
| `/casino disable <game>` | Disables a specific game — users get a message that it's temporarily unavailable. |
| `/casino disableall` | Shuts down all casino games. |
| `/casino enableall` | Re-enables all casino games. |
| `/casino stats` | Shows total EC won and lost across all games since the last reset, and a per-game breakdown. |
| `/casino stats @user` | Shows a specific user's win/loss history across all games. |
| `/casino resetstats` | Resets the global casino stats counter. |

---

### 🛡️ Staff

| Command | What It Does |
|---|---|
| `/casino stats` | View global casino stats. |
| `/casino stats @user` | View a user's casino stats. |

---

### 👤 User

| Command | What It Does |
|---|---|
| `/casino stats` | Shows their own win/loss totals and breakdown by game. |
| `/casino limits` | Shows current bet limits, daily loss cap, and win cooldown. |

---

## 8. Recommended Features

### Casino Stats Per User (Recommended)

**Logic:** Each user has a personal stats record that tracks their total EC wagered, total EC won, total EC lost, net result, and favorite game (most played). This gives users a fun overview of their history and helps the owner monitor for unusual behavior.

Accessible via `/casino stats` (user sees their own, owner/staff can specify `@user`).

---

### Daily Loss Limit Notification (Recommended)

**Logic:** When a user hits their daily loss limit, the bot sends them a DM rather than just a silent block:

> ⚠️ You've reached your daily casino loss limit of 50,000 EC. Casino games are locked for you until midnight. This limit is in place to keep things fair and fun for everyone.

This is more transparent than a generic error and helps frame the limit as a feature, not a punishment.

---

## 9. Nice-to-Add Features

### Blackjack Split (Nice to Add)

**Logic:** If the user's first two cards have the same value (e.g., two 8s), they can split them into two separate hands, each with its own bet equal to the original. They then play each hand independently.

This is a standard blackjack rule that adds strategic depth. It is optional and can be left out for simplicity.

| Button | When Available | What It Does |
|---|---|---|
| **Split** | First action, if both cards match | Splits into 2 hands, doubles the bet, plays each hand separately |

---

### Blackjack Insurance (Nice to Add)

**Logic:** If the dealer's visible card is an Ace, the user can place an "insurance" side bet of up to half their original bet. If the dealer's hidden card turns out to be a 10-value (completing a Blackjack), the insurance bet pays 2:1. If not, the insurance bet is lost and the round continues normally.

This is an optional advanced rule. It is commonly considered a trap for inexperienced players but is standard in real blackjack.

---

### Slots Symbol Customization (Nice to Add)

**Logic:** The owner can set custom symbols for the slots game to match the server's species theme (e.g., 🪶 feathers, 💫 halos, ✨ wings instead of generic fruit symbols).

| Command | Who | What It Does |
|---|---|---|
| `/slots setsymbols <common> <rare> <jackpot>` | Owner | Sets the emoji used for each symbol tier in slots. |

---

### Casino Leaderboard (Nice to Add)

**Logic:** Shows who has won the most EC from the casino overall. Resets seasonally alongside the EC leaderboard if seasons are enabled.

| Command | Who | What It Does |
|---|---|---|
| `/casino leaderboard` | User | Shows top casino earners by total EC won. |
