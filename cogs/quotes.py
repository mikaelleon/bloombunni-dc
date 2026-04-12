"""Interactive commission quote calculator, pricelist, and staff price tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import guild_keys as gk
from utils.checks import is_staff
from utils.embeds import PRIMARY, info_embed, success_embed, user_hint, user_warn
from utils.forex import fetch_php_rates
from utils.logging_setup import get_logger

log = get_logger("quotes")

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


def _char_count(key: str) -> int:
    if key == "4+":
        return 4
    try:
        return max(1, int(key))
    except ValueError:
        return 1


def _fmt_php(n: float | int) -> str:
    v = float(n)
    if abs(v - round(v)) < 0.01:
        return f"₱{int(round(v)):,}"
    return f"₱{v:,.2f}"


def _currency_symbol(code: str) -> str:
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


@dataclass
class QuoteSession:
    step: int = 0
    commission_type: str | None = None
    tier: str | None = None
    char_key: str | None = None
    background: str | None = None
    target_member_id: int | None = None


class QuoteFlowView(discord.ui.View):
    """Multi-step quote; edits the same ephemeral message."""

    def __init__(self, cog: QuotesCog, target_member: discord.Member | None) -> None:
        super().__init__(timeout=420.0)
        self.cog = cog
        self.target_member = target_member
        self._add_commission_select()

    def _subject(self, interaction: discord.Interaction) -> discord.Member | None:
        if self.target_member:
            return self.target_member
        if isinstance(interaction.user, discord.Member):
            return interaction.user
        return None

    def _add_commission_select(self) -> None:
        sel = discord.ui.Select(
            custom_id="quote_ct",
            placeholder="Pick your commission type",
            options=[
                discord.SelectOption(label=t[:100], value=t[:100]) for t in COMMISSION_TYPES
            ],
        )

        async def cb(interaction: discord.Interaction) -> None:
            v = interaction.data.get("values", [""])[0] if interaction.data else ""
            subj = self._subject(interaction)
            if not subj or not interaction.guild:
                await interaction.response.send_message(
                    embed=user_hint("Unavailable", "Run this in a server."), ephemeral=True
                )
                return
            await interaction.response.edit_message(
                embed=info_embed("Quote — step 2/4", "Pick your **rendering tier**."),
                view=QuoteTierView(self.cog, subj, str(v)),
            )

        sel.callback = cb
        self.add_item(sel)


class QuoteTierView(discord.ui.View):
    def __init__(self, cog: QuotesCog, target: discord.Member, commission_type: str) -> None:
        super().__init__(timeout=420.0)
        self.cog = cog
        self.target = target
        self.commission_type = commission_type
        sel = discord.ui.Select(
            custom_id="quote_tier",
            placeholder="Pick rendering tier",
            options=[
                discord.SelectOption(label=t[:100], value=t[:100]) for t in RENDERING_TIERS
            ],
        )

        async def cb(interaction: discord.Interaction) -> None:
            v = interaction.data.get("values", [""])[0] if interaction.data else ""
            await interaction.response.edit_message(
                embed=info_embed("Quote — step 3/4", "How many **characters**?"),
                view=QuoteCharView(self.cog, target, self.commission_type, str(v)),
            )

        sel.callback = cb
        self.add_item(sel)


class QuoteCharView(discord.ui.View):
    def __init__(
        self,
        cog: QuotesCog,
        target: discord.Member,
        commission_type: str,
        tier: str,
    ) -> None:
        super().__init__(timeout=420.0)
        self.cog = cog
        self.target = target
        self.commission_type = commission_type
        self.tier = tier
        sel = discord.ui.Select(
            custom_id="quote_char",
            placeholder="Number of characters",
            options=[
                discord.SelectOption(label=c, value=c) for c in CHAR_OPTIONS
            ],
        )

        async def cb(interaction: discord.Interaction) -> None:
            v = interaction.data.get("values", [""])[0] if interaction.data else ""
            await interaction.response.edit_message(
                embed=info_embed("Quote — step 4/4", "**Background** level?"),
                view=QuoteBgView(self.cog, target, self.commission_type, self.tier, str(v)),
            )

        sel.callback = cb
        self.add_item(sel)


class QuoteBgView(discord.ui.View):
    def __init__(
        self,
        cog: QuotesCog,
        target: discord.Member,
        commission_type: str,
        tier: str,
        char_key: str,
    ) -> None:
        super().__init__(timeout=420.0)
        self.cog = cog
        self.target = target
        self.commission_type = commission_type
        self.tier = tier
        self.char_key = char_key
        sel = discord.ui.Select(
            custom_id="quote_bg",
            placeholder="Background",
            options=[
                discord.SelectOption(label=b, value=b) for b in BG_OPTIONS
            ],
        )

        async def cb(interaction: discord.Interaction) -> None:
            v = interaction.data.get("values", [""])[0] if interaction.data else ""
            if not interaction.guild:
                return
            emb = await self.cog.compute_quote_embed(
                interaction.guild,
                self.target,
                self.commission_type,
                self.tier,
                self.char_key,
                str(v),
            )
            await interaction.response.edit_message(embed=emb, view=None)

        sel.callback = cb
        self.add_item(sel)


class QuotesCog(commands.Cog, name="QuotesCog"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def compute_quote_embed(
        self,
        guild: discord.Guild,
        member: discord.Member,
        commission_type: str,
        tier: str,
        char_key: str,
        background: str,
    ) -> discord.Embed:
        gs = await db.get_quote_guild_settings(guild.id)
        brand = (gs or {}).get("brand_name") or "Mikaelleon"
        ex = int((gs or {}).get("extra_character_php") or 0)
        bg_s = int((gs or {}).get("bg_simple_php") or 0)
        bg_d = int((gs or {}).get("bg_detailed_php") or 0)

        rows = await db.list_quote_base_prices(guild.id)
        price_map = {(r["commission_type"], r["tier"]): int(r["price_php"]) for r in rows}
        base = int(price_map.get((commission_type, tier), 0))

        n_char = _char_count(char_key)
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

        subtotal = base + extra_line + bg_fee
        pct, disc_notes = await discount_percent_for_member(guild, member)
        discount_amt = subtotal * (pct / 100.0) if pct > 0 else 0.0
        total = max(0.0, float(subtotal) - discount_amt)

        lines: list[str] = [
            f"**Type:** {commission_type}",
            f"**Characters:** {char_key}",
            f"**Background:** {bg_label}",
            f"**Tier:** {tier}",
            "",
            "─────────────────────────────",
            f"{'Base Price':<20} {_fmt_php(base)}",
        ]
        if extra_line:
            lines.append(f"{'Extra character(s)':<20} {_fmt_php(extra_line)}")
        if bg_fee:
            lines.append(f"{'Background':<20} {_fmt_php(bg_fee)}")
        lines.append("─────────────────────────────")
        lines.append(f"{'Subtotal':<20} {_fmt_php(subtotal)}")
        if pct > 0:
            who = ", ".join(disc_notes) if disc_notes else "Role discount"
            lines.append(f"{'Discount':<20} -{_fmt_php(discount_amt)}  ({who})")
            lines.append("─────────────────────────────")
            lines.append(f"{'TOTAL':<20} {_fmt_php(total)}")
            lines.append("")
            lines.append(f"💰 You're saving {_fmt_php(discount_amt)} ({pct:g}%)!")
        else:
            lines.append("─────────────────────────────")
            lines.append(f"{'TOTAL':<20} {_fmt_php(subtotal)}")
            total = float(subtotal)

        await db.ensure_default_quote_currencies(guild.id)
        cur_rows = await db.list_quote_currencies(guild.id)
        enabled = [r["currency_code"] for r in cur_rows if r.get("enabled")]
        fx_lines: list[str] = []
        if enabled:
            rates = await fetch_php_rates(enabled)
            if rates:
                fx_lines.append("─────────────────────────────")
                fx_lines.append("🌍 **International Prices**")
                for code in sorted(enabled):
                    r = rates.get(code)
                    if r is None:
                        continue
                    sym = _currency_symbol(code)
                    amt = total * r
                    fx_lines.append(f"{code:<6} {sym}{amt:,.2f}")

        comp_lines: list[str] = ["─────────────────────────────", "📋 **Tier comparison**"]
        for t in RENDERING_TIERS:
            b = int(price_map.get((commission_type, t), 0))
            st = float(b + extra_line + bg_fee)
            pct_t, _ = await discount_percent_for_member(guild, member)
            tot_t = max(0.0, st - st * (pct_t / 100.0))
            if t == tier:
                comp_lines.append(f"**{t}**         {_fmt_php(tot_t)} ✅  ← your pick")
            else:
                diff = tot_t - total
                if diff > 0:
                    comp_lines.append(
                        f"**{t}**         {_fmt_php(tot_t)}   →  ₱{diff:,.0f} more than **{tier}**"
                    )
                elif diff < 0:
                    comp_lines.append(
                        f"**{t}**         {_fmt_php(tot_t)}   →  you'd save ₱{-diff:,.0f} vs **{tier}**"
                    )
                else:
                    comp_lines.append(f"**{t}**         {_fmt_php(tot_t)}")

        desc = "\n".join(lines)
        if fx_lines:
            desc += "\n" + "\n".join(fx_lines)
        desc += "\n" + "\n".join(comp_lines)
        desc += (
            "\n\n_Prices are subject to change. This quote is valid for today’s settings only._"
        )

        emb = discord.Embed(
            title=f"🎨 Commission Quote — {brand}",
            description=desc[:4096],
            color=PRIMARY,
        )
        emb.set_footer(
            text=member.display_name,
            icon_url=member.display_avatar.url if member.display_avatar else None,
        )
        return emb

    @app_commands.command(name="quote", description="Get an interactive commission price quote")
    @app_commands.describe(member="Staff only: quote for this member (roles/discounts use them)")
    async def quote_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                embed=user_hint("Server only", "Use this command in a server."), ephemeral=True
            )
            return

        target = member
        if member is not None:
            staff_role_id = await db.get_guild_setting(interaction.guild.id, gk.STAFF_ROLE)
            staff = (
                interaction.guild.get_role(int(staff_role_id))
                if staff_role_id
                else None
            )
            is_staff_u = (
                staff
                and isinstance(interaction.user, discord.Member)
                and staff in interaction.user.roles
            )
            if not is_staff_u:
                await interaction.response.send_message(
                    embed=user_warn("Staff only", "Only staff can generate a quote for another member."),
                    ephemeral=True,
                )
                return
            target = member
        else:
            if not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message(
                    embed=user_hint("Error", "Could not resolve member."), ephemeral=True
                )
                return
            target = interaction.user

        emb = info_embed(
            "Quote — step 1/4",
            "Pick your **commission type**.",
        )
        view = QuoteFlowView(self, target)
        await interaction.response.send_message(embed=emb, view=view, ephemeral=True)

    @app_commands.command(name="pricelist", description="Show commission base prices (PHP) from the database")
    async def pricelist_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        rows = await db.list_quote_base_prices(interaction.guild.id)
        gs = await db.get_quote_guild_settings(interaction.guild.id)
        extras = ""
        if gs:
            extras = (
                f"\n**Add-ons:** extra char ₱{gs.get('extra_character_php', 0):,} · "
                f"simple BG ₱{gs.get('bg_simple_php', 0):,} · "
                f"detailed BG ₱{gs.get('bg_detailed_php', 0):,}"
            )
        if not rows:
            await interaction.response.send_message(
                embed=info_embed(
                    "Pricelist",
                    "No prices in the database yet. Staff: use `/setprice` and `/quoteextras`." + extras,
                ),
                ephemeral=False,
            )
            return
        grid: dict[str, dict[str, int]] = {}
        for r in rows:
            ct = str(r["commission_type"])
            tier = str(r["tier"])
            if ct not in grid:
                grid[ct] = {}
            grid[ct][tier] = int(r["price_php"])
        header = " | ".join(["Type/Tier"] + [t[:12] for t in RENDERING_TIERS])
        lines = [header, "—" * min(80, len(header))]
        for ct in COMMISSION_TYPES:
            if ct not in grid:
                continue
            row_vals = [ct[:20]]
            for t in RENDERING_TIERS:
                p = grid[ct].get(t)
                row_vals.append(_fmt_php(p) if p is not None else "—")
            lines.append(" | ".join(row_vals))
        body = "\n".join(lines)[:3900] + extras
        await interaction.response.send_message(
            embed=info_embed("Commission base prices (PHP)", body),
            ephemeral=False,
        )

    @app_commands.command(name="setprice", description="Set base price (PHP) for a type + tier")
    @is_staff()
    @app_commands.describe(
        commission_type=f"One of: {', '.join(COMMISSION_TYPES)}",
        tier=f"One of: {', '.join(RENDERING_TIERS)}",
        price_php="Price in PHP (whole pesos)",
    )
    async def setprice_cmd(
        self,
        interaction: discord.Interaction,
        commission_type: str,
        tier: str,
        price_php: app_commands.Range[int, 0, 10_000_000],
    ) -> None:
        if not interaction.guild:
            return
        if commission_type not in COMMISSION_TYPES:
            await interaction.response.send_message(
                embed=user_hint("Invalid type", f"Use one of: {', '.join(COMMISSION_TYPES)}"),
                ephemeral=True,
            )
            return
        if tier not in RENDERING_TIERS:
            await interaction.response.send_message(
                embed=user_hint("Invalid tier", f"Use one of: {', '.join(RENDERING_TIERS)}"),
                ephemeral=True,
            )
            return
        await db.upsert_quote_base_price(
            interaction.guild.id, commission_type, tier, int(price_php)
        )
        await interaction.response.send_message(
            embed=success_embed(
                "Saved",
                f"**{commission_type}** / **{tier}** → {_fmt_php(price_php)}",
            ),
            ephemeral=True,
        )

    @app_commands.command(name="quoteextras", description="Set extra character & background add-ons (PHP)")
    @is_staff()
    @app_commands.describe(
        extra_per_character="Added per character after the first",
        bg_simple="Simple background",
        bg_detailed="Detailed background",
        brand_name="Shown in quote title",
    )
    async def quoteextras_cmd(
        self,
        interaction: discord.Interaction,
        extra_per_character: int | None = None,
        bg_simple: int | None = None,
        bg_detailed: int | None = None,
        brand_name: str | None = None,
    ) -> None:
        if not interaction.guild:
            return
        await db.upsert_quote_guild_settings(
            interaction.guild.id,
            extra_character_php=extra_per_character,
            bg_simple_php=bg_simple,
            bg_detailed_php=bg_detailed,
            brand_name=brand_name,
        )
        await interaction.response.send_message(
            embed=success_embed("Quote extras updated", "Values saved."),
            ephemeral=True,
        )

    @app_commands.command(name="setdiscount", description="Link Boostie or Reseller role and discount %")
    @is_staff()
    @app_commands.describe(
        which="boostie or reseller",
        role="Role that receives the discount",
        percent="Percent off subtotal (e.g. 10 for 10%)",
    )
    @app_commands.choices(
        which=[
            app_commands.Choice(name="Boostie", value="boostie"),
            app_commands.Choice(name="Reseller", value="reseller"),
        ]
    )
    async def setdiscount_cmd(
        self,
        interaction: discord.Interaction,
        which: str,
        role: discord.Role,
        percent: app_commands.Range[float, 0, 100],
    ) -> None:
        if not interaction.guild:
            return
        await db.upsert_quote_discount(
            interaction.guild.id,
            which,
            role_id=role.id,
            percent=float(percent),
        )
        await interaction.response.send_message(
            embed=success_embed(
                "Discount saved",
                f"**{which}** → {role.mention} at **{percent}%** off subtotal.",
            ),
            ephemeral=True,
        )

    @app_commands.command(name="setcurrency", description="Enable/disable a currency line on quotes")
    @is_staff()
    @app_commands.describe(
        code="ISO code, e.g. USD, EUR, SGD, MYR",
        enabled="Show in quote footer",
    )
    async def setcurrency_cmd(
        self,
        interaction: discord.Interaction,
        code: str,
        enabled: bool,
    ) -> None:
        if not interaction.guild:
            return
        c = code.strip().upper()[:8]
        if len(c) != 3:
            await interaction.response.send_message(
                embed=user_hint("Invalid", "Use a 3-letter ISO code (e.g. USD)."),
                ephemeral=True,
            )
            return
        await db.set_quote_currency_enabled(interaction.guild.id, c, enabled)
        await interaction.response.send_message(
            embed=success_embed("Currency toggle", f"**{c}** → {'on' if enabled else 'off'}"),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(QuotesCog(bot))
