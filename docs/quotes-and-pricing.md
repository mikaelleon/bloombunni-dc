# Quotes and pricing (`cogs/quotes.py` + `utils/quote_compute.py`)

Staff configure **base PHP prices** and add-ons per guild. **`/quote`** builds an interactive **ephemeral** flow; the same math feeds **ticket creation** when a buyer submits a commission type through the ticket panel.

## Command group: `/quote`

### `/quote calculator`

- **Ephemeral** multi-step UI (timeout **420s**): commission **type** → **rendering tier** → **character count** (`1`–`4+`) → **background** → **rush** → **pay currency** → **payment method** (for USD).
- **Optional `member`:** staff may quote for another member (uses **their** roles for Boostie/Reseller discounts). Non-staff can only quote for themselves.
- Steps use **`info_embed("Quote — step N/7", …)`** titles.

**Output:** `build_quote_embed` → single embed (see [Embed shape](#quote-embed-shape)).

### `/quote recalculate`

- **Staff only**, run inside an **open ticket** channel with a **`quote_snapshot_json`** row.
- Merges optional overrides (tier, characters, background, rush, pay currency, payment method) into the snapshot, recomputes totals, **updates the DB** (`quote_total_php`, `quote_usd_approx`, snapshot, tier/bg/char/rush), and **posts a new quote embed** to the channel (not ephemeral).
- Ephemeral success: **`success_embed("Quote updated", "Posted a new quote embed in this channel.")`**

## Standalone pricing commands (staff where noted)

| Command | Purpose |
|---------|---------|
| **`/pricelist`** | Public grid of **base** PHP prices from `quote_base_price` + extras line from `quote_guild_settings`. If empty, hints **`/setprice`** / **`/quoteextras`**. |
| **`/setprice`** | `upsert_quote_base_price` for one `(commission_type, tier)` pair. Validates against `COMMISSION_TYPES` and `RENDERING_TIERS`. |
| **`/quoteextras`** | Updates `quote_guild_settings`: extra character PHP, simple/detailed BG PHP, optional **brand_name** (shown in quote title). |
| **`/setdiscount`** | `quote_role_discount` for **boostie** or **reseller** → role id + percent. |
| **`/setcurrency`** | Toggle optional **FX footer lines** in `quote_currency` (3-letter ISO). When enabled, `build_quote_embed` appends **International (approx.)** block using `fetch_php_rates`. |

## Data model (SQLite)

- **`quote_guild_settings`** — extras and `brand_name`.
- **`quote_base_price`** — `(guild_id, commission_type, tier) → price_php`.
- **`quote_role_discount`** — `(guild_id, discount_key) → role_id, percent`.
- **`quote_currency`** — optional enabled FX codes.

## Pricing logic (`compute_quote_totals`)

1. Load base price from the map; add **extra character** lines (count from `char_key`, `4+` → 4 chars).
2. Add **simple** or **detailed** background fee from guild settings.
3. Add **rush** fee **₱520** if enabled.
4. Apply **best** role discount % (Boostie vs Reseller) from `discount_percent_for_member`.
5. **USD estimate:** `fetch_php_rates(["USD"])` → PHP×rate; fallback **÷59** if no rate.

## Payment breakdown (`compute_payment_breakdown`)

- **PHP:** GCash path — **no** processor fee; **total to send** = artist PHP total.
- **USD:** PayPal or Ko‑fi — fee = **`artist_usd × 4.4% + $0.30`** (constants `PROCESSOR_FEE_RATE`, `PROCESSOR_FEE_FIXED_USD`). **Total to send** = artist USD + fee. Ko‑fi adds a note that the fee may vary.

**Down payment rules** (`payment_terms_from_total_send`) use **total to send** (after fees):

- PHP: full upfront if **≤ ₱500**; else **50% / 50%**.
- USD: full upfront if **≤ $25**; else **50% / 50%**.

Thresholds: `DOWNPAYMENT_THRESHOLD_PHP` / `DOWNPAYMENT_THRESHOLD_USD`.

## Quote embed shape

- **Title:** `🎨 Commission Quote — {brand}` (`brand` from settings or default **Mikaelleon**).
- **Description:** line items (type, characters, background, tier), dashed separators, base/extra/bg/subtotal/discount/**TOTAL** in PHP.
- If pay currency/method provided: **`format_settlement_lines`** block — paying currency, base, fee line, total to send, artist receives, then **payment terms** line.
- Optional **tier comparison** (calculator only): alternate tier totals with ✅ on current tier.
- Optional **International (approx.)** FX block from enabled currencies.
- **Footer text:** `_Prices reflect today's price matrix._` plus processor disclaimer when USD fees apply.
- **Embed footer:** member display name + avatar.

## Related

- Ticket flow posts the same embed after channel creation — see [tickets-and-panels.md](tickets-and-panels.md).
