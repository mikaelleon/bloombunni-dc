"""Interactive commission quote calculator, pricelist, and staff price tools."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import guild_keys as gk
from utils.checks import is_staff
from utils.embeds import PRIMARY, info_embed, success_embed, user_hint, user_warn
from utils.logging_setup import get_logger
from utils.quote_compute import (
    BG_OPTIONS,
    CHAR_OPTIONS,
    COMMISSION_TYPES,
    RENDERING_TIERS,
    build_quote_embed,
    compute_payment_breakdown,
    compute_quote_totals,
    fmt_php,
)

log = get_logger("quotes")


async def _safe_edit_component_message(
    interaction: discord.Interaction,
    *,
    embed: discord.Embed,
    view: discord.ui.View | None,
) -> bool:
    try:
        await interaction.response.edit_message(embed=embed, view=view)
        return True
    except discord.NotFound:
        log.info("quote component interaction expired before response")
        return False
    except discord.HTTPException as e:
        log.warning("quote component response failed: %s", e)
        return False


async def _safe_edit_original_component_message(
    interaction: discord.Interaction,
    *,
    embed: discord.Embed,
    view: discord.ui.View | None,
) -> bool:
    try:
        await interaction.edit_original_response(embed=embed, view=view)
        return True
    except discord.NotFound:
        log.info("quote component original message no longer available")
        return False
    except discord.HTTPException as e:
        log.warning("quote component original edit failed: %s", e)
        return False


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
            await _safe_edit_component_message(
                interaction,
                embed=info_embed("Quote — step 2/7", "Pick your **rendering tier**."),
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
            await interaction.response.send_modal(
                QuoteCharacterCountModal(self.cog, target, self.commission_type, str(v))
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
            await _safe_edit_component_message(
                interaction,
                embed=info_embed("Quote — step 4/7", "**Background** level?"),
                view=QuoteBgView(self.cog, target, self.commission_type, self.tier, str(v)),
            )

        sel.callback = cb
        self.add_item(sel)


class QuoteCharacterCountModal(discord.ui.Modal, title="Quote — step 3/7"):
    char_count = discord.ui.TextInput(
        label="How many characters?",
        placeholder="Enter integer (example: 2)",
        required=True,
        max_length=2,
    )

    def __init__(
        self,
        cog: "QuotesCog",
        target: discord.Member,
        commission_type: str,
        tier: str,
    ) -> None:
        super().__init__()
        self.cog = cog
        self.target = target
        self.commission_type = commission_type
        self.tier = tier

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = str(self.char_count.value or "").strip()
        if not raw.isdigit():
            await interaction.response.send_message(
                embed=user_hint("Invalid number", "Enter whole number like `1`, `2`, or `3`."),
                ephemeral=True,
            )
            return
        count = int(raw)
        if count < 1 or count > 20:
            await interaction.response.send_message(
                embed=user_hint("Out of range", "Character count must be between **1** and **20**."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=info_embed("Quote — step 4/7", "**Background** level?"),
            view=QuoteBgView(self.cog, self.target, self.commission_type, self.tier, str(count)),
            ephemeral=True,
        )


class SetPriceModal(discord.ui.Modal, title="Set base price (PHP)"):
    price_php = discord.ui.TextInput(
        label="Price (PHP)",
        placeholder="Example: 350",
        required=True,
        max_length=9,
    )

    def __init__(self, guild_id: int, commission_type: str, tier: str) -> None:
        super().__init__()
        self.guild_id = guild_id
        self.commission_type = commission_type
        self.tier = tier

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = str(self.price_php.value or "").strip().replace(",", "")
        if not raw.isdigit():
            await interaction.response.send_message(
                embed=user_hint("Invalid price", "Use whole number like `350`."),
                ephemeral=True,
            )
            return
        value = int(raw)
        if value < 0 or value > 10_000_000:
            await interaction.response.send_message(
                embed=user_hint("Price out of range", "Use value between `0` and `10,000,000`."),
                ephemeral=True,
            )
            return
        await db.upsert_quote_base_price(self.guild_id, self.commission_type, self.tier, value)
        await interaction.response.send_message(
            embed=success_embed(
                "Saved",
                f"**{self.commission_type}** / **{self.tier}** → {fmt_php(value)}",
            ),
            ephemeral=True,
        )


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
            await _safe_edit_component_message(
                interaction,
                embed=info_embed("Quote — step 5/7", "**Rush delivery** add-on?"),
                view=QuoteRushView(
                    self.cog, target, self.commission_type, self.tier, self.char_key, str(v)
                ),
            )

        sel.callback = cb
        self.add_item(sel)


class QuoteRushView(discord.ui.View):
    def __init__(
        self,
        cog: QuotesCog,
        target: discord.Member,
        commission_type: str,
        tier: str,
        char_key: str,
        background: str,
    ) -> None:
        super().__init__(timeout=420.0)
        self.cog = cog
        self.target = target
        self.commission_type = commission_type
        self.tier = tier
        self.char_key = char_key
        self.background = background
        sel = discord.ui.Select(
            custom_id="quote_rush",
            placeholder="Rush delivery",
            options=[
                discord.SelectOption(label="Standard (no rush)", value="0"),
                discord.SelectOption(
                    label="Rush (+₱520 / ~$30)", value="1"
                ),
            ],
        )

        async def cb(interaction: discord.Interaction) -> None:
            v = interaction.data.get("values", [""])[0] if interaction.data else "0"
            rush = v == "1"
            await _safe_edit_component_message(
                interaction,
                embed=info_embed(
                    "Quote — step 6/7",
                    "**Which currency will you be paying in?**",
                ),
                view=QuoteCurrencyView(
                    self.cog,
                    target,
                    commission_type,
                    tier,
                    char_key,
                    background,
                    rush,
                ),
            )

        sel.callback = cb
        self.add_item(sel)


class QuoteCurrencyView(discord.ui.View):
    def __init__(
        self,
        cog: QuotesCog,
        target: discord.Member,
        commission_type: str,
        tier: str,
        char_key: str,
        background: str,
        rush: bool,
    ) -> None:
        super().__init__(timeout=420.0)
        self.cog = cog
        self.target = target
        self.commission_type = commission_type
        self.tier = tier
        self.char_key = char_key
        self.background = background
        self.rush = rush
        sel = discord.ui.Select(
            custom_id="quote_cur",
            placeholder="Paying currency",
            options=[
                discord.SelectOption(label="PHP (GCash)", value="PHP"),
                discord.SelectOption(label="USD (PayPal / Ko-fi)", value="USD"),
            ],
        )

        async def cb(interaction: discord.Interaction) -> None:
            cur = interaction.data.get("values", [""])[0] if interaction.data else "PHP"
            if not interaction.guild:
                return
            try:
                await interaction.response.defer()
            except discord.NotFound:
                log.info("quote currency interaction expired before defer")
                return
            except discord.HTTPException as e:
                log.warning("quote currency defer failed: %s", e)
                return
            if cur == "PHP":
                data = await compute_quote_totals(
                    interaction.guild,
                    target,
                    commission_type,
                    tier,
                    char_key,
                    background,
                    rush_addon=rush,
                )
                emb = await build_quote_embed(
                    interaction.guild,
                    target,
                    data,
                    include_tier_comparison=True,
                    pay_currency="PHP",
                    payment_method="GCash",
                )
                await _safe_edit_original_component_message(interaction, embed=emb, view=None)
                return
            await _safe_edit_original_component_message(
                interaction,
                embed=info_embed(
                    "Quote — step 7/7",
                    "**Which payment method?** (USD)",
                ),
                view=QuoteUsdMethodView(
                    cog,
                    target,
                    commission_type,
                    tier,
                    char_key,
                    background,
                    rush,
                ),
            )

        sel.callback = cb
        self.add_item(sel)


class QuoteUsdMethodView(discord.ui.View):
    def __init__(
        self,
        cog: QuotesCog,
        target: discord.Member,
        commission_type: str,
        tier: str,
        char_key: str,
        background: str,
        rush: bool,
    ) -> None:
        super().__init__(timeout=420.0)
        self.cog = cog
        self.target = target
        self.commission_type = commission_type
        self.tier = tier
        self.char_key = char_key
        self.background = background
        self.rush = rush
        sel = discord.ui.Select(
            custom_id="quote_usd_m",
            placeholder="Payment method",
            options=[
                discord.SelectOption(label="PayPal", value="PayPal"),
                discord.SelectOption(label="Ko-fi", value="Ko-fi"),
            ],
        )

        async def cb(interaction: discord.Interaction) -> None:
            method = interaction.data.get("values", [""])[0] if interaction.data else "PayPal"
            if not interaction.guild:
                return
            try:
                await interaction.response.defer()
            except discord.NotFound:
                log.info("quote usd method interaction expired before defer")
                return
            except discord.HTTPException as e:
                log.warning("quote usd method defer failed: %s", e)
                return
            data = await compute_quote_totals(
                interaction.guild,
                target,
                commission_type,
                tier,
                char_key,
                background,
                rush_addon=rush,
            )
            emb = await build_quote_embed(
                interaction.guild,
                target,
                data,
                include_tier_comparison=True,
                pay_currency="USD",
                payment_method=str(method),
            )
            await _safe_edit_original_component_message(interaction, embed=emb, view=None)

        sel.callback = cb
        self.add_item(sel)


class QuotesCog(commands.Cog, name="QuotesCog"):
    quote = app_commands.Group(name="quote", description="Commission quote tools")

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
        *,
        rush_addon: bool = False,
        include_tier_comparison: bool = True,
        pay_currency: str | None = None,
        payment_method: str | None = None,
    ) -> discord.Embed:
        data = await compute_quote_totals(
            guild,
            member,
            commission_type,
            tier,
            char_key,
            background,
            rush_addon=rush_addon,
        )
        return await build_quote_embed(
            guild,
            member,
            data,
            include_tier_comparison=include_tier_comparison,
            pay_currency=pay_currency,
            payment_method=payment_method,
        )

    @quote.command(name="calculator", description="Interactive commission price quote (PHP + USD)")
    @app_commands.describe(member="Staff only: quote for this member (roles/discounts use them)")
    async def quote_calculator_cmd(
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
            "Quote — step 1/7",
            "Pick your **commission type**.",
        )
        view = QuoteFlowView(self, target)
        await interaction.response.send_message(embed=emb, view=view, ephemeral=True)

    @quote.command(
        name="recalculate",
        description="Refresh ticket quote from price matrix (ticket owner or staff; in ticket channel)",
    )
    @app_commands.describe(
        tier="Rendering tier (leave empty to keep current)",
        characters="Character count option (leave empty to keep current)",
        background="Background level (leave empty to keep current)",
        rush="Rush add-on (leave unset to keep current)",
        pay_currency="PHP or USD (leave empty to keep snapshot)",
        payment_method="GCash / PayPal / Ko-fi (leave empty to keep snapshot)",
    )
    @app_commands.choices(
        tier=[app_commands.Choice(name=t, value=t) for t in RENDERING_TIERS],
        characters=[app_commands.Choice(name=c, value=c) for c in CHAR_OPTIONS],
        background=[app_commands.Choice(name=b, value=b) for b in BG_OPTIONS],
        pay_currency=[
            app_commands.Choice(name="PHP", value="PHP"),
            app_commands.Choice(name="USD", value="USD"),
        ],
        payment_method=[
            app_commands.Choice(name="GCash", value="GCash"),
            app_commands.Choice(name="PayPal", value="PayPal"),
            app_commands.Choice(name="Ko-fi", value="Ko-fi"),
        ],
    )
    async def quote_recalculate_cmd(
        self,
        interaction: discord.Interaction,
        tier: str | None,
        characters: str | None,
        background: str | None,
        rush: bool | None,
        pay_currency: str | None,
        payment_method: str | None,
    ) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Use a ticket channel", "Run this inside an open commission ticket."), ephemeral=True
            )
            return
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket record for this channel."), ephemeral=True
            )
            return
        raw = ticket.get("quote_snapshot_json")
        if not raw:
            await interaction.response.send_message(
                embed=user_warn("No quote snapshot", "This ticket has no saved quote fields yet."), ephemeral=True
            )
            return
        try:
            snap = json.loads(raw)
        except json.JSONDecodeError:
            await interaction.response.send_message(
                embed=user_warn("Bad data", "Could not read quote snapshot."), ephemeral=True
            )
            return

        ct = str(snap.get("commission_type") or "")
        te = tier or str(snap.get("tier") or "")
        ck = characters or str(snap.get("char_key") or "1")
        bg = background or str(snap.get("background") or "None")
        rush_b = snap.get("rush_addon")
        if rush is not None:
            rush_b = rush
        elif isinstance(rush_b, bool):
            pass
        else:
            rush_b = bool(int(rush_b or 0))

        pc = (pay_currency or snap.get("pay_currency") or "PHP").strip().upper()
        pm_raw = payment_method or snap.get("payment_method")
        if pc == "PHP":
            pm = "GCash"
        else:
            pm = str(pm_raw or "PayPal")
            if pm not in ("PayPal", "Ko-fi"):
                pm = "PayPal"

        client = interaction.guild.get_member(int(ticket["client_id"]))
        if not client:
            await interaction.response.send_message(
                embed=user_hint("Member missing", "Buyer is not in the server."), ephemeral=True
            )
            return

        staff_role_id = await db.get_guild_setting(interaction.guild.id, gk.STAFF_ROLE)
        staff_role = (
            interaction.guild.get_role(int(staff_role_id))
            if staff_role_id
            else None
        )
        is_staff_u = (
            staff_role is not None
            and isinstance(interaction.user, discord.Member)
            and staff_role in interaction.user.roles
        )
        is_owner = interaction.user.id == int(ticket["client_id"])
        if not is_staff_u and not is_owner:
            await interaction.response.send_message(
                embed=user_warn(
                    "Not your ticket",
                    "Only the ticket owner or staff can refresh the quote here.",
                ),
                ephemeral=True,
            )
            return
        has_overrides = any(
            x is not None
            for x in (
                tier,
                characters,
                background,
                rush,
                pay_currency,
                payment_method,
            )
        )
        if has_overrides and not is_staff_u:
            await interaction.response.send_message(
                embed=user_hint(
                    "Staff only",
                    "Changing tier, characters, background, rush, or currency options requires staff. "
                    "Ask staff to run **`/quote recalculate`** with the new details.",
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        data = await compute_quote_totals(
            interaction.guild,
            client,
            ct,
            te,
            ck,
            bg,
            rush_addon=bool(rush_b),
        )
        emb = await build_quote_embed(
            interaction.guild,
            client,
            data,
            include_tier_comparison=False,
            pay_currency=pc,
            payment_method=pm,
        )
        bd = compute_payment_breakdown(
            artist_php=float(data["total_php"]),
            artist_usd=float(data["total_usd_approx"]),
            pay_currency=pc,
            payment_method=pm,
        )
        snap_out = {
            "commission_type": ct,
            "tier": te,
            "char_key": ck,
            "background": bg,
            "rush_addon": bool(rush_b),
            "pay_currency": pc,
            "payment_method": pm,
            "fee_usd": bd.get("fee_usd"),
            "total_send_php": bd.get("total_send_php"),
            "total_send_usd": bd.get("total_send_usd"),
        }
        await db.update_ticket_fields(
            interaction.channel.id,
            quote_total_php=float(data["total_php"]),
            quote_usd_approx=float(data["total_usd_approx"]),
            quote_snapshot_json=json.dumps(snap_out, ensure_ascii=False),
            rendering_tier=te,
            background=bg,
            char_count_key=ck,
            rush_addon=1 if rush_b else 0,
        )
        try:
            await interaction.channel.send(embed=emb)
        except discord.HTTPException:
            await interaction.followup.send(
                embed=user_warn("Send failed", "Could not post the embed."), ephemeral=True
            )
            return
        await interaction.followup.send(
            embed=success_embed("Quote updated", "Posted a new quote embed in this channel."), ephemeral=True
        )

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
                row_vals.append(fmt_php(p) if p is not None else "—")
            lines.append(" | ".join(row_vals))
        body = "\n".join(lines)[:3900] + extras
        await interaction.response.send_message(
            embed=info_embed("Commission base prices (PHP)", body),
            ephemeral=False,
        )

    @app_commands.command(name="setprice", description="Set base price (PHP) for a type + tier")
    @is_staff()
    @app_commands.describe(
        commission_type="Commission type",
        tier="Rendering tier",
    )
    @app_commands.choices(
        commission_type=[app_commands.Choice(name=t, value=t) for t in COMMISSION_TYPES],
        tier=[app_commands.Choice(name=t, value=t) for t in RENDERING_TIERS],
    )
    async def setprice_cmd(
        self,
        interaction: discord.Interaction,
        commission_type: str,
        tier: str,
    ) -> None:
        if not interaction.guild:
            return
        await interaction.response.send_modal(
            SetPriceModal(interaction.guild.id, commission_type, tier)
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
