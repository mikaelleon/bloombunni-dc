"""Shared commission quote math + payment terms (used by /quote and tickets)."""

from __future__ import annotations

from typing import Any

import discord

import database as db
from utils.forex import fetch_php_rates

# Re-export for single source of truth
COMMISSION_TYPES: tuple[str, ...] = (
    "Chibi",
    "Chibi Fullbody",
    "Bust",
    "Fullbody",
    "Other",
)
RENDERING_TIERS: tuple[str, ...] = (
    "Sketch",
    "Flat Color",
    "Shaded",
    "Fully Rendered",
)
CHAR_OPTIONS: tuple[str, ...] = ("1", "2", "3", "4+")
BG_OPTIONS: tuple[str, ...] = ("None", "Simple", "Detailed")

TIER_SLUG: dict[str, str] = {
    "Sketch": "sk",
    "Flat Color": "fc",
    "Shaded": "sr",
    "Fully Rendered": "fr",
}
TYPE_SLUG: dict[str, str] = {
    "Chibi": "ch",
    "Chibi Fullbody": "cfb",
    "Bust": "bu",
    "Fullbody": "fb",
    "Other": "ot",
}

# Payment thresholds (PHP / USD)
DOWNPAYMENT_THRESHOLD_PHP = 500.0
DOWNPAYMENT_THRESHOLD_USD = 25.0


def char_count(key: str) -> int:
    if key == "4+":
        return 4
    try:
        return max(1, int(key))
    except ValueError:
        return 1


def fmt_php(n: float | int) -> str:
    v = float(n)
    if abs(v - round(v)) < 0.01:
        return f"₱{int(round(v)):,}"
    return f"₱{v:,.2f}"


def currency_symbol(code: str) -> str:
    return {"USD": "$", "EUR": "€", "GBP": "£", "SGD": "S$", "MYR": "RM"}.get(code, "$")


async def discount_percent_for_member(
    guild: discord.Guild, member: discord.Member
) -> tuple[float, list[str]]:
    best = 0.0
    notes: list[str] = []
    for key, label in (("boostie", "Boostie"), ("reseller", "Reseller")):
        row = await db.get_quote_discount(guild.id, key)
        if not row:
            continue
        rid = row.get("role_id")
        pct = float(row.get("percent") or 0)
        if not rid or pct <= 0:
            continue
        role = guild.get_role(int(rid))
        if role and role in member.roles:
            notes.append(f"{label} ({pct:g}%)")
            if pct > best:
                best = pct
    return best, notes


async def compute_quote_totals(
    guild: discord.Guild,
    member: discord.Member,
    commission_type: str,
    tier: str,
    char_key: str,
    background: str,
    *,
    rush_addon: bool = False,
) -> dict[str, Any]:
    """Returns total_php, total_usd (approx), subtotal, discount, lines for embed."""
    gs = await db.get_quote_guild_settings(guild.id)
    ex = int((gs or {}).get("extra_character_php") or 0)
    bg_s = int((gs or {}).get("bg_simple_php") or 0)
    bg_d = int((gs or {}).get("bg_detailed_php") or 0)

    rows = await db.list_quote_base_prices(guild.id)
    price_map = {(r["commission_type"], r["tier"]): int(r["price_php"]) for r in rows}
    base = int(price_map.get((commission_type, tier), 0))

    n_char = char_count(char_key)
    extra_chars = max(0, n_char - 1)
    extra_line = extra_chars * ex

    if background == "None":
        bg_fee = 0
        bg_label = "None"
    elif background == "Simple":
        bg_fee = bg_s
        bg_label = "Simple"
    else:
        bg_fee = bg_d
        bg_label = "Detailed"

    rush_fee = 520 if rush_addon else 0  # ₱520 / user spec
    subtotal = base + extra_line + bg_fee + rush_fee
    pct, disc_notes = await discount_percent_for_member(guild, member)
    discount_amt = subtotal * (pct / 100.0) if pct > 0 else 0.0
    total_php = max(0.0, float(subtotal) - discount_amt)

    rates = await fetch_php_rates(["USD"])
    usd_rate = rates.get("USD") if rates else None
    total_usd = float(total_php * usd_rate) if usd_rate else (total_php / 59.0)

    return {
        "total_php": total_php,
        "total_usd_approx": total_usd,
        "subtotal": float(subtotal),
        "discount_amt": discount_amt,
        "discount_pct": pct,
        "disc_notes": disc_notes,
        "base": base,
        "extra_line": extra_line,
        "bg_fee": bg_fee,
        "bg_label": bg_label,
        "rush_fee": rush_fee,
        "price_map": price_map,
        "commission_type": commission_type,
        "tier": tier,
        "char_key": char_key,
        "background": background,
    }


def payment_terms_text(total_php: float, total_usd: float) -> str:
    """50% down vs full upfront + thresholds."""
    if total_php > DOWNPAYMENT_THRESHOLD_PHP or total_usd > DOWNPAYMENT_THRESHOLD_USD:
        half = total_php / 2.0
        return (
            f"**Payment terms:** **50% down payment** ({fmt_php(half)} approx.) required **before work begins**. "
            f"Remainder due before final delivery.\n"
            f"_Threshold: above {fmt_php(DOWNPAYMENT_THRESHOLD_PHP)} or ~${DOWNPAYMENT_THRESHOLD_USD:.0f} USD._"
        )
    return (
        "**Payment terms:** **Full payment required upfront** before work begins.\n"
        f"_At or below {fmt_php(DOWNPAYMENT_THRESHOLD_PHP)} / ~${DOWNPAYMENT_THRESHOLD_USD:.0f} USD._"
    )


def installment_eligibility_note(commission_type: str, tier: str) -> str | None:
    """Optional line for installment-eligible commission types."""
    ct = commission_type.lower()
    tier_l = tier.lower()
    if "ref" in ct or "sheet" in ct:
        return "📎 **Installment plan may be available** for this commission type — ask staff."
    if "fully rendered" in tier_l or tier == "Fully Rendered":
        return "📎 **Installment eligibility:** Fully Rendered commissions may qualify for a payment plan — confirm with staff."
    return None


def tat_estimate_text(tier: str, commission_type: str, rush: bool) -> str:
    if rush:
        return "**Turnaround:** **3 business days** (Rush Delivery add-on).\n_TAT may vary depending on queue position and character complexity._"
    tl = tier.lower()
    if "sketch" in tl or "flat" in tl:
        return "**Turnaround (estimate):** **1–5 days** for sketch / flat work.\n_TAT may vary depending on queue position and character complexity._"
    if "shaded" in tl or "semi" in commission_type.lower():
        return "**Turnaround (estimate):** **1–2 weeks** for semi-rendered work.\n_TAT may vary depending on queue position and character complexity._"
    if "fully" in tl or "rendered" in tl:
        return "**Turnaround (estimate):** **2–3 weeks** for fully rendered work.\n_TAT may vary depending on queue position and character complexity._"
    return "**Turnaround:** Depends on complexity and queue — staff will confirm.\n_TAT may vary depending on queue position and character complexity._"


def re_slug(s: str) -> str:
    import re

    x = re.sub(r"[^a-z0-9]+", "", s.lower().replace(" ", ""))
    return x[:40]


def ticket_channel_slug(tier: str, commission_type: str, username_slug: str) -> str:
    ts = TIER_SLUG.get(tier, re_slug(tier)[:2])
    cs = TYPE_SLUG.get(commission_type, re_slug(commission_type)[:4])
    u = re_slug(username_slug)[:24] or "user"
    raw = f"{ts}-{cs}-{u}"
    return raw[:100]


async def build_quote_embed(
    guild: discord.Guild,
    member: discord.Member,
    data: dict[str, Any],
    *,
    brand: str | None = None,
    include_tier_comparison: bool = True,
) -> discord.Embed:
    """Build the main quote embed from compute_quote_totals result."""
    from utils.embeds import PRIMARY

    gs = await db.get_quote_guild_settings(guild.id)
    br = brand or (gs or {}).get("brand_name") or "Mikaelleon"
    total_php = float(data["total_php"])
    total = total_php
    commission_type = data["commission_type"]
    tier = data["tier"]
    char_key = data["char_key"]
    bg_label = data["bg_label"]
    base = int(data["base"])
    extra_line = int(data["extra_line"])
    bg_fee = int(data["bg_fee"])
    subtotal = float(data["subtotal"])
    pct = float(data["discount_pct"])
    discount_amt = float(data["discount_amt"])
    disc_notes = data["disc_notes"]

    lines: list[str] = [
        f"**Type:** {commission_type}",
        f"**Characters:** {char_key}",
        f"**Background:** {bg_label}",
        f"**Tier:** {tier}",
        "",
        "─────────────────────────────",
        f"{'Base Price':<20} {fmt_php(base)}",
    ]
    if data.get("rush_fee"):
        lines.append(f"{'Rush delivery':<20} {fmt_php(data['rush_fee'])}")
    if extra_line:
        lines.append(f"{'Extra character(s)':<20} {fmt_php(extra_line)}")
    if bg_fee:
        lines.append(f"{'Background':<20} {fmt_php(bg_fee)}")
    lines.append("─────────────────────────────")
    lines.append(f"{'Subtotal':<20} {fmt_php(subtotal)}")
    if pct > 0:
        who = ", ".join(disc_notes) if disc_notes else "Role discount"
        lines.append(f"{'Discount':<20} -{fmt_php(discount_amt)}  ({who})")
        lines.append("─────────────────────────────")
        lines.append(f"{'TOTAL':<20} {fmt_php(total)}")
        lines.append("")
        lines.append(f"💰 You're saving {fmt_php(discount_amt)} ({pct:g}%)!")
    else:
        lines.append("─────────────────────────────")
        lines.append(f"{'TOTAL':<20} {fmt_php(subtotal)}")

    await db.ensure_default_quote_currencies(guild.id)
    cur_rows = await db.list_quote_currencies(guild.id)
    enabled = [r["currency_code"] for r in cur_rows if r.get("enabled")]
    fx_lines: list[str] = []
    if enabled:
        rates = await fetch_php_rates(enabled)
        if rates:
            fx_lines.append("─────────────────────────────")
            fx_lines.append("🌍 **International (approx.)**")
            for code in sorted(enabled):
                r = rates.get(code)
                if r is None:
                    continue
                sym = currency_symbol(code)
                amt = total * r
                fx_lines.append(f"{code:<6} {sym}{amt:,.2f}")

    desc = "\n".join(lines)
    if fx_lines:
        desc += "\n" + "\n".join(fx_lines)

    if include_tier_comparison:
        price_map = data.get("price_map") or {}
        extra_line = int(data["extra_line"])
        bg_fee = int(data["bg_fee"])
        pct_cmp, _ = await discount_percent_for_member(guild, member)
        rush_fee_cmp = int(data.get("rush_fee") or 0)
        comp_lines: list[str] = [
            "─────────────────────────────",
            "📋 **Tier comparison**",
        ]
        ref_total = float(total_php)
        for tname in RENDERING_TIERS:
            b = int(price_map.get((commission_type, tname), 0))
            st = float(b + extra_line + bg_fee + rush_fee_cmp)
            tot_t = max(0.0, st - st * (pct_cmp / 100.0))
            if tname == tier:
                comp_lines.append(f"**{tname}**         {fmt_php(tot_t)} ✅  ← your pick")
            else:
                diff = tot_t - ref_total
                if diff > 0:
                    comp_lines.append(
                        f"**{tname}**         {fmt_php(tot_t)}   →  ₱{diff:,.0f} more than **{tier}**"
                    )
                elif diff < 0:
                    comp_lines.append(
                        f"**{tname}**         {fmt_php(tot_t)}   →  you'd save ₱{-diff:,.0f} vs **{tier}**"
                    )
                else:
                    comp_lines.append(f"**{tname}**         {fmt_php(tot_t)}")
        desc += "\n" + "\n".join(comp_lines)

    desc += "\n\n_Prices reflect today’s price matrix._"

    emb = discord.Embed(
        title=f"🎨 Commission Quote — {br}",
        description=desc[:4096],
        color=PRIMARY,
    )
    emb.set_footer(
        text=member.display_name,
        icon_url=member.display_avatar.url if member.display_avatar else None,
    )
    return emb
