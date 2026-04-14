# 📋 Bot System — Master Index

This folder contains the full feature documentation for the Discord bot system.
Each file covers one feature group. Read them in order if setting up from scratch.

---

## 📁 Files

| # | File | What It Covers |
|---|---|---|
| 01 | `01_MYO_SYSTEM.md` | MYO coupons, species TOS, submission & approval workflow |
| 02 | `02_BATCH_SLOT_SYSTEM.md` | Batch opening, slot claiming, timers, channel locking |
| 03 | `03_CURRENCY_SYSTEM.md` | Earned currency, paid currency, top-up packages, conversion rates |
| 04 | `04_GACHA_SYSTEM.md` | Banners, draw mechanics, prize pools, pity system, rate rotation |
| 05 | `05_CASINO_MINIGAMES.md` | Coinflip, slots, number guess, high card, blackjack |
| 06 | `06_COLLECTIBLE_SYSTEM.md` | Collectible items, inventory, selling, trading, marketplace |

---

## 🔑 Role Permission Levels Used Throughout

| Role | Who They Are |
|---|---|
| **Owner** | The server owner. Has full access to all commands. |
| **Staff** | Trusted moderators assigned by the owner. Limited admin access. |
| **User** | Regular server members. Access to their own data and public commands only. |

---

## 💡 General Logic Notes

- **Earned Currency (EC)** is gained through activity — commands, events, giveaways, autoresponders.
- **Paid Currency (PC)** is gained only through real-money top-ups processed by the owner.
- **EC and PC are never interchangeable.** They exist in separate wallets.
- **MYO Coupons** are items that grant the right to design a species character. They come in tiers: Common, Rare, Legendary.
- All monetary values are anchored to **USD** as the source of truth. PHP amounts are approximate based on the current rate of **$1 USD ≈ ₱59 PHP**.
