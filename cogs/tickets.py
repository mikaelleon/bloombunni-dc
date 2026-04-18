"""Configurable ticket panel, modal forms, and ticket channels."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import guild_keys as gk
from cogs.queue import QueueCog, build_queue_entry_text, register_order_in_ticket_channel
from discord.utils import format_dt

from guild_config import get_category, get_role, get_text_channel, is_payment_config_complete
from utils.channel_resolve import resolve_category, resolve_text_channel
from utils.checks import is_staff
from utils.embeds import PRIMARY, info_embed, success_embed, user_hint, user_warn
from utils.quote_compute import (
    BG_OPTIONS,
    CHAR_OPTIONS,
    RENDERING_TIERS,
    build_quote_embed,
    compute_payment_breakdown,
    compute_quote_totals,
    fmt_php,
    fmt_usd,
    payment_terms_from_total_send,
    ticket_channel_slug,
)

_SETUP_CH_ERR = (
    "Could not find that **text channel**. Use a channel mention (`<#id>`) or paste the "
    "**numeric channel ID** (Developer Mode → Copy Channel ID)."
)

log = logging.getLogger("bot.tickets")

# Modal-only fields (tier / characters / BG / rush are chosen in quote steps first).
DEFAULT_MODAL_FIELDS: list[dict[str, Any]] = [
    {
        "label": "Mode of Payment",
        "placeholder": "e.g. GCash, PayPal",
        "required": True,
        "long": False,
    },
    {
        "label": "Reference Links",
        "placeholder": "Paste image links here",
        "required": False,
        "long": True,
    },
    {
        "label": "Additional Notes",
        "placeholder": "Any extra requests?",
        "required": False,
        "long": True,
    },
]

DEFAULT_SELECT_OPTIONS: list[str] = [
    "Icon",
    "Bust Up",
    "Half Body",
    "Full Body",
    "Doodle Small (2-3 poses)",
    "Doodle Large (4-5 poses)",
    "Other",
]

# Welcome embed field order (quote details are added separately).
WELCOME_FIELD_ORDER: tuple[str, ...] = (
    "Commission Type",
    "Mode of Payment",
    "Reference Links",
    "Additional Notes",
)

# WIP stage labels (staff panel dropdown + legacy quote flows).
WIP_STAGES: tuple[str, ...] = (
    "Sketch",
    "Sketch Approved",
    "Base Colors",
    "Final Rendering",
    "Watermarked Preview Sent",
    "Final Balance Pending",
    "Delivered",
)

BUTTON_STYLE_MAP: dict[str, discord.ButtonStyle] = {
    "blurple": discord.ButtonStyle.primary,
    "green": discord.ButtonStyle.success,
    "red": discord.ButtonStyle.danger,
    "grey": discord.ButtonStyle.secondary,
}

REMIND_COOLDOWN = timedelta(hours=24)

_PAYMENT_STATUS_LABEL: dict[str, str] = {
    "awaiting_payment": "Pending — awaiting payment",
    "awaiting_payment_review": "Pending — proof submitted",
    "paid": "Confirmed",
    "payment_declined": "Declined",
}


def _payment_status_line(raw: str | None) -> str:
    key = str(raw or "awaiting_payment").strip()
    return _PAYMENT_STATUS_LABEL.get(key, key.replace("_", " ").title())


async def _deploy_prereq_failures(guild: discord.Guild) -> list[str]:
    """Human-readable missing slots for `/deploy all`."""
    out: list[str] = []
    cat = await get_category(guild, gk.TICKET_CATEGORY)
    if not cat:
        out.append("Ticket category (`/config` → new tickets)")
    sr = await get_role(guild, gk.STAFF_ROLE)
    if sr is None:
        out.append("Staff role")
    tos_ch = await get_text_channel(guild, gk.TOS_CHANNEL)
    if not isinstance(tos_ch, discord.TextChannel):
        out.append("TOS text channel")
    pay_ch = await get_text_channel(guild, gk.PAYMENT_CHANNEL)
    if not isinstance(pay_ch, discord.TextChannel):
        out.append("Payment panel channel")
    rows = await db.list_ticket_buttons(guild.id)
    if not rows:
        out.append("At least one ticket button (`/ticketbutton add`)")
    if not await is_payment_config_complete(guild.id):
        out.append("Payment details (`/config payment` — GCash / PayPal / Ko-fi)")
    return out


def _hex_to_color(s: str) -> int:
    t = (s or "").strip()
    if t.startswith("#"):
        t = t[1:]
    try:
        return int(t, 16)
    except ValueError:
        return 0x669B9A


def _slug_button_id(label: str, guild_id: int) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")[:40] or "btn"
    bid = f"btn_{base}"
    return bid  # uniqueness checked in add loop with suffix


async def _ensure_unique_button_id(guild_id: int, base_id: str) -> str:
    bid = base_id
    n = 2
    while await db.get_ticket_button_by_id(bid):
        bid = f"{base_id}_{n}"
        n += 1
    return bid


def _parse_form_fields_json(raw: str | None) -> list[dict[str, Any]]:
    if not raw or not str(raw).strip():
        return [dict(f) for f in DEFAULT_MODAL_FIELDS]
    try:
        data = json.loads(raw)
        if not isinstance(data, list) or len(data) < 1:
            raise ValueError("invalid list")
        return data
    except (json.JSONDecodeError, ValueError):
        return [dict(f) for f in DEFAULT_MODAL_FIELDS]


def _parse_select_options_from_row(row: dict[str, Any]) -> list[str]:
    raw = row.get("select_options")
    if not raw or not str(raw).strip():
        return list(DEFAULT_SELECT_OPTIONS)
    try:
        data = json.loads(raw)
        if isinstance(data, list) and len(data) >= 1:
            out = [str(x).strip()[:100] for x in data if str(x).strip()]
            return out[:25]
    except json.JSONDecodeError:
        pass
    return list(DEFAULT_SELECT_OPTIONS)


def _validate_form_fields(data: Any) -> tuple[list[dict[str, Any]] | None, str | None]:
    if not isinstance(data, list):
        return None, "JSON must be an array of field objects."
    if len(data) < 1:
        return None, "Provide at least one field."
    if len(data) > 4:
        return None, "Maximum 4 modal fields (commission type uses the select menu first)."
    out: list[dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            return None, f"Item {i} must be an object."
        lab = item.get("label")
        if not lab or not str(lab).strip():
            return None, f"Item {i} needs a non-empty `label`."
        out.append(
            {
                "label": str(lab)[:45],
                "placeholder": str(item.get("placeholder", ""))[:100],
                "required": bool(item.get("required", True)),
                "long": bool(item.get("long", False)),
            }
        )
    return out, None


def _parse_comma_select_options(text: str) -> tuple[list[str] | None, str | None]:
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) < 1:
        return None, "Provide at least one option."
    if len(parts) > 25:
        return None, "Maximum 25 options (Discord select limit)."
    for i, p in enumerate(parts):
        if len(p) > 100:
            return None, f"Option {i + 1} is longer than 100 characters."
    return parts, None


class CloseTicketView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Archive Ticket", style=discord.ButtonStyle.danger, custom_id="ticket_close"
    )
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        cog = interaction.client.get_cog("TicketsCog")
        if not isinstance(cog, TicketsCog):
            await interaction.response.send_message(
                embed=user_warn("Tickets unavailable", "Try again in a moment."), ephemeral=True
            )
            return
        await cog.handle_close_button(interaction)


class TicketOpsView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @staticmethod
    async def _is_staff_or_admin(interaction: discord.Interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return False
        if interaction.user.guild_permissions.administrator:
            return True
        staff_role = await get_role(interaction.guild, gk.STAFF_ROLE)
        return bool(staff_role and staff_role in interaction.user.roles)

    @discord.ui.button(
        label="Claim Ticket",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_ops_claim",
    )
    async def claim_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self._is_staff_or_admin(interaction):
            await interaction.response.send_message(
                embed=user_warn("Staff only", "Only staff/admin can claim tickets."),
                ephemeral=True,
            )
            return
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Ticket only", "Use this inside ticket channel."),
                ephemeral=True,
            )
            return
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket record for this channel."),
                ephemeral=True,
            )
            return
        proc_cat = await get_category(interaction.guild, gk.PROCESSING_CATEGORY)
        try:
            if isinstance(proc_cat, discord.CategoryChannel):
                await interaction.channel.edit(category=proc_cat)
        except (discord.Forbidden, discord.HTTPException):
            pass
        await db.update_ticket_fields(
            interaction.channel.id,
            ticket_status="processing",
            assigned_staff_id=interaction.user.id,
        )
        opener = interaction.guild.get_member(int(ticket["client_id"]))
        opener_mention = opener.mention if opener else f"<@{int(ticket['client_id'])}>"
        await interaction.response.send_message(
            embed=success_embed(
                "Ticket claimed",
                f"{opener_mention} your ticket is now claimed by {interaction.user.mention}.\n"
                "Moved to processing category when available.",
            ),
            ephemeral=False,
        )

    @discord.ui.button(
        label="Noted",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_ops_noted",
    )
    async def noted_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        cog = interaction.client.get_cog("TicketsCog")
        if not isinstance(cog, TicketsCog):
            await interaction.response.send_message(
                embed=user_warn("Tickets unavailable", "Try again in a moment."),
                ephemeral=True,
            )
            return
        await cog.handle_noted_button(interaction)

    @discord.ui.button(
        label="Mark Complete",
        style=discord.ButtonStyle.success,
        custom_id="ticket_ops_done",
    )
    async def done_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()
        if not await self._is_staff_or_admin(interaction):
            await interaction.followup.send(
                embed=user_warn("Staff only", "Only staff/admin can mark done."),
                ephemeral=True,
            )
            return
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.followup.send(
                embed=user_hint("Ticket only", "Use this inside ticket channel."),
                ephemeral=True,
            )
            return
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.followup.send(
                embed=user_hint("Not a ticket", "No open ticket record for this channel."),
                ephemeral=True,
            )
            return
        done_cat = await get_category(interaction.guild, gk.DONE_CATEGORY)
        try:
            if isinstance(done_cat, discord.CategoryChannel):
                await interaction.channel.edit(category=done_cat)
        except (discord.Forbidden, discord.HTTPException):
            pass
        await db.update_ticket_fields(
            interaction.channel.id,
            ticket_status="done_hold",
            assigned_staff_id=interaction.user.id,
        )
        opener = interaction.guild.get_member(int(ticket["client_id"]))
        issued = False
        try:
            from cogs.loyalty_cards import issue_loyalty_card_for_ticket_closure

            issued = await issue_loyalty_card_for_ticket_closure(
                interaction.guild, ticket, opener
            )
        except Exception:
            log.exception(
                "done_btn loyalty issue failed guild_id=%s ticket_channel_id=%s",
                interaction.guild.id,
                interaction.channel.id,
            )
        opener_mention = opener.mention if opener else f"<@{int(ticket['client_id'])}>"
        hours = await db.get_guild_setting(interaction.guild.id, gk.DONE_TICKET_AUTO_DELETE_HOURS)
        done_lines = [
            f"{opener_mention} work marked complete by {interaction.user.mention}.",
            "Moved to done category when available.",
        ]
        if hours and int(hours) > 0:
            done_lines.append(
                f"This ticket will be **archived** (channel deleted) in **{int(hours)}** hour(s) unless staff archive sooner."
            )
        if issued:
            done_lines.append("Loyalty stamp card posted (if configured).")
        await interaction.followup.send(
            embed=success_embed("Mark complete", "\n".join(done_lines)),
            ephemeral=False,
        )
        if issued:
            lch = await get_text_channel(interaction.guild, gk.LOYALTY_CARD_CHANNEL)
            lmention = lch.mention if lch else "#loyalty-cards"
            try:
                await interaction.channel.send(
                    embed=info_embed(
                        "Loyalty card",
                        f"Your stamp card was posted in {lmention} — **vouch** after delivery to earn your next stamp.",
                    )
                )
            except discord.HTTPException:
                pass
        if hours and int(hours) > 0:
            wait_s = int(hours) * 3600
            channel_id = interaction.channel.id
            guild_id = interaction.guild.id

            async def _auto_delete_when_due() -> None:
                await asyncio.sleep(wait_s)
                g = interaction.client.get_guild(guild_id)
                if not g:
                    return
                ch = g.get_channel(channel_id)
                if not isinstance(ch, discord.TextChannel):
                    return
                row = await db.get_ticket_by_channel(channel_id)
                if not row:
                    return
                if str(row.get("ticket_status") or "") != "done_hold":
                    return
                await db.delete_ticket_by_channel(channel_id)
                try:
                    await ch.delete(reason="Done ticket auto-delete timer")
                except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                    pass

            asyncio.create_task(_auto_delete_when_due())

    @discord.ui.button(
        label="Remind Client",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_ops_remind",
    )
    async def remind_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self._is_staff_or_admin(interaction):
            await interaction.response.send_message(
                embed=user_warn("Staff only", "Only staff/admin can remind clients."),
                ephemeral=True,
            )
            return
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Ticket only", "Use this inside ticket channel."),
                ephemeral=True,
            )
            return
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket record for this channel."),
                ephemeral=True,
            )
            return
        raw_last = ticket.get("last_client_remind_at")
        last_dt: datetime | None = None
        if raw_last:
            try:
                last_dt = datetime.fromisoformat(str(raw_last))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                last_dt = None
        if last_dt is not None:
            now = datetime.now(timezone.utc)
            elapsed = now - last_dt
            if elapsed < REMIND_COOLDOWN:
                left = REMIND_COOLDOWN - elapsed
                hrs = int(left.total_seconds() // 3600)
                mins = int((left.total_seconds() % 3600) // 60)
                await interaction.response.send_message(
                    embed=user_warn(
                        "Reminder cooldown",
                        f"Last reminded {format_dt(last_dt, 'R')}. Cooldown active — try again in **~{hrs}h {mins}m**.",
                    ),
                    ephemeral=True,
                )
                return
        client = interaction.guild.get_member(int(ticket["client_id"]))
        if not client:
            await interaction.response.send_message(
                embed=user_warn("User missing", "Client is no longer in server."),
                ephemeral=True,
            )
            return
        jump = interaction.channel.jump_url
        try:
            await client.send(
                embed=info_embed(
                    "Ticket reminder",
                    f"Staff sent reminder for your ticket.\nPlease check: {jump}",
                )
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=user_warn("DM failed", f"Could not DM {client.mention}."),
                ephemeral=True,
            )
            return
        await db.update_ticket_fields(
            interaction.channel.id,
            last_client_remind_at=datetime.now(timezone.utc).isoformat(),
        )
        extra = ""
        if last_dt:
            extra = f" (previous: {format_dt(last_dt, 'R')})"
        await interaction.response.send_message(
            embed=success_embed(
                "Reminder sent",
                f"DM reminder sent to {client.mention}.{extra}",
            ),
            ephemeral=False,
        )

    @discord.ui.select(
        placeholder="Set WIP stage (staff)",
        custom_id="ticket_ops_stage_select",
        row=1,
        options=[discord.SelectOption(label=s[:100], value=s) for s in WIP_STAGES],
    )
    async def stage_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ) -> None:
        if not await self._is_staff_or_admin(interaction):
            await interaction.response.send_message(
                embed=user_warn("Staff only", "Only staff/admin can set WIP stage."),
                ephemeral=True,
            )
            return
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Ticket only", "Use this inside ticket channel."),
                ephemeral=True,
            )
            return
        t = await db.get_ticket_by_channel(interaction.channel.id)
        if not t:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket here."),
                ephemeral=True,
            )
            return
        stage = str(select.values[0])[:200]
        await db.update_ticket_fields(interaction.channel.id, wip_stage=stage)
        cog = interaction.client.get_cog("TicketsCog")
        if isinstance(cog, TicketsCog):
            await cog._refresh_queue_card_from_ticket(interaction.guild, t, stage=stage)
        emb = discord.Embed(
            title="📍 Stage update",
            description=f"**{stage}**",
            color=PRIMARY,
        )
        await interaction.response.send_message(embed=emb)

    @discord.ui.button(
        label="Archive Ticket",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_ops_close",
    )
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        cog = interaction.client.get_cog("TicketsCog")
        if not isinstance(cog, TicketsCog):
            await interaction.response.send_message(
                embed=user_warn("Tickets unavailable", "Try again in a moment."),
                ephemeral=True,
            )
            return
        await cog.handle_close_button(interaction)


class QuoteApprovalView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Approve Quote",
        style=discord.ButtonStyle.success,
        custom_id="ticket_quote_approve",
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Ticket only", "Use this in your ticket channel."),
                ephemeral=True,
            )
            return
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket here."),
                ephemeral=True,
            )
            return
        if interaction.user.id != int(ticket["client_id"]):
            await interaction.response.send_message(
                embed=user_warn("Client only", "Only ticket owner can approve quote."),
                ephemeral=True,
            )
            return
        await db.update_ticket_fields(
            interaction.channel.id,
            quote_approved=1,
            ticket_status="quote_approved",
        )
        await interaction.response.send_message(
            embed=success_embed("Quote approved", "Staff can now proceed with payment processing."),
            ephemeral=False,
        )

    @discord.ui.button(
        label="Request Quote Changes",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_quote_changes",
    )
    async def request_changes(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Ticket only", "Use this in your ticket channel."),
                ephemeral=True,
            )
            return
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket here."),
                ephemeral=True,
            )
            return
        if interaction.user.id != int(ticket["client_id"]):
            await interaction.response.send_message(
                embed=user_warn("Client only", "Only ticket owner can request quote changes."),
                ephemeral=True,
            )
            return
        await db.update_ticket_fields(
            interaction.channel.id,
            quote_approved=0,
            ticket_status="quote_revision_requested",
        )
        await interaction.response.send_message(
            embed=info_embed(
                "Quote changes requested",
                "Staff will review your requested changes. Use `/quote recalculate` after updates.",
            ),
            ephemeral=False,
        )


class CommissionTypeSelectView(discord.ui.View):
    """Ephemeral-only: commission type select → modal. Not registered with add_view."""

    def __init__(
        self,
        cog: TicketsCog,
        guild_id: int,
        button_id: str,
        button_label: str,
        row: dict[str, Any],
    ) -> None:
        super().__init__(timeout=60.0)
        self.cog = cog
        self.guild_id = guild_id
        self.button_id = button_id
        self.button_label = button_label
        self._row = row
        self.message: discord.Message | None = None

        opts = _parse_select_options_from_row(row)[:25]
        select = discord.ui.Select(
            placeholder="Choose a commission type…",
            custom_id="ticket_commission_type",
            options=[
                discord.SelectOption(label=t[:100], value=t[:100]) for t in opts
            ],
        )

        async def _select_cb(interaction: discord.Interaction) -> None:
            # CHANGED: cursor-prompt.md §2 — open flow = commission type → one modal (no quote wizard).
            if not interaction.data or "values" not in interaction.data:
                return
            commission_type = str(interaction.data["values"][0])[:100]
            tier = RENDERING_TIERS[0]
            char_key = CHAR_OPTIONS[0]
            background = BG_OPTIONS[0]
            rush = False
            fields = _parse_form_fields_json(self._row.get("form_fields"))
            modal = CommissionModal(
                self.cog,
                self.guild_id,
                self.button_id,
                self.button_label,
                commission_type,
                tier,
                char_key,
                background,
                rush,
                "PHP",
                "GCash",
                fields,
            )
            await interaction.response.send_modal(modal)

        select.callback = _select_cb
        self.add_item(select)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(
                    embed=info_embed(
                        "Timed out",
                        "Timed out. Click the button again to restart.",
                    ),
                    view=self,
                )
            except discord.HTTPException:
                pass


class TicketQuoteTierView(discord.ui.View):
    def __init__(
        self,
        cog: TicketsCog,
        guild_id: int,
        button_id: str,
        button_label: str,
        row: dict[str, Any],
        commission_type: str,
    ) -> None:
        super().__init__(timeout=420.0)
        self.cog = cog
        self.guild_id = guild_id
        self.button_id = button_id
        self.button_label = button_label
        self._row = row
        self.commission_type = commission_type
        sel = discord.ui.Select(
            custom_id="tqtier",
            placeholder="Rendering tier",
            options=[
                discord.SelectOption(label=t[:100], value=t[:100]) for t in RENDERING_TIERS
            ],
        )

        async def cb(interaction: discord.Interaction) -> None:
            v = interaction.data.get("values", [""])[0] if interaction.data else ""
            await interaction.response.edit_message(
                embed=info_embed("Characters", "How many **characters**? (step 3/7)"),
                view=TicketQuoteCharView(
                    cog,
                    guild_id,
                    button_id,
                    button_label,
                    row,
                    commission_type,
                    str(v),
                ),
            )

        sel.callback = cb
        self.add_item(sel)


class TicketQuoteCharView(discord.ui.View):
    def __init__(
        self,
        cog: TicketsCog,
        guild_id: int,
        button_id: str,
        button_label: str,
        row: dict[str, Any],
        commission_type: str,
        tier: str,
    ) -> None:
        super().__init__(timeout=420.0)
        self.cog = cog
        self.guild_id = guild_id
        self.button_id = button_id
        self.button_label = button_label
        self._row = row
        self.commission_type = commission_type
        self.tier = tier
        sel = discord.ui.Select(
            custom_id="tqchar",
            placeholder="Number of characters",
            options=[discord.SelectOption(label=c, value=c) for c in CHAR_OPTIONS],
        )

        async def cb(interaction: discord.Interaction) -> None:
            v = interaction.data.get("values", [""])[0] if interaction.data else ""
            await interaction.response.edit_message(
                embed=info_embed("Background", "**Background** level (step 4/7)"),
                view=TicketQuoteBgView(
                    cog,
                    guild_id,
                    button_id,
                    button_label,
                    row,
                    commission_type,
                    tier,
                    str(v),
                ),
            )

        sel.callback = cb
        self.add_item(sel)


class TicketQuoteBgView(discord.ui.View):
    def __init__(
        self,
        cog: TicketsCog,
        guild_id: int,
        button_id: str,
        button_label: str,
        row: dict[str, Any],
        commission_type: str,
        tier: str,
        char_key: str,
    ) -> None:
        super().__init__(timeout=420.0)
        self.cog = cog
        self.guild_id = guild_id
        self.button_id = button_id
        self.button_label = button_label
        self._row = row
        self.commission_type = commission_type
        self.tier = tier
        self.char_key = char_key
        sel = discord.ui.Select(
            custom_id="tqbg",
            placeholder="Background",
            options=[discord.SelectOption(label=b, value=b) for b in BG_OPTIONS],
        )

        async def cb(interaction: discord.Interaction) -> None:
            v = interaction.data.get("values", [""])[0] if interaction.data else ""
            await interaction.response.edit_message(
                embed=info_embed("Rush delivery", "**Rush** add-on? (step 5/7)"),
                view=TicketQuoteRushView(
                    cog,
                    guild_id,
                    button_id,
                    button_label,
                    row,
                    commission_type,
                    tier,
                    char_key,
                    str(v),
                ),
            )

        sel.callback = cb
        self.add_item(sel)


class TicketQuoteRushView(discord.ui.View):
    def __init__(
        self,
        cog: TicketsCog,
        guild_id: int,
        button_id: str,
        button_label: str,
        row: dict[str, Any],
        commission_type: str,
        tier: str,
        char_key: str,
        background: str,
    ) -> None:
        super().__init__(timeout=420.0)
        self.cog = cog
        self.guild_id = guild_id
        self.button_id = button_id
        self.button_label = button_label
        self._row = row
        self.commission_type = commission_type
        self.tier = tier
        self.char_key = char_key
        self.background = background
        sel = discord.ui.Select(
            custom_id="tqrush",
            placeholder="Rush delivery",
            options=[
                discord.SelectOption(label="Standard (no rush)", value="0"),
                discord.SelectOption(label="Rush (+₱520 / ~$30)", value="1"),
            ],
        )

        async def cb(interaction: discord.Interaction) -> None:
            v = interaction.data.get("values", [""])[0] if interaction.data else "0"
            rush = v == "1"
            await interaction.response.edit_message(
                embed=info_embed(
                    "Paying currency",
                    "**Which currency will you be paying in?** (step 6/7)",
                ),
                view=TicketQuoteCurrencyView(
                    cog,
                    guild_id,
                    button_id,
                    button_label,
                    row,
                    commission_type,
                    tier,
                    char_key,
                    background,
                    rush,
                ),
            )

        sel.callback = cb
        self.add_item(sel)


class TicketQuoteCurrencyView(discord.ui.View):
    def __init__(
        self,
        cog: TicketsCog,
        guild_id: int,
        button_id: str,
        button_label: str,
        row: dict[str, Any],
        commission_type: str,
        tier: str,
        char_key: str,
        background: str,
        rush: bool,
    ) -> None:
        super().__init__(timeout=420.0)
        self.cog = cog
        self.guild_id = guild_id
        self.button_id = button_id
        self.button_label = button_label
        self._row = row
        self.commission_type = commission_type
        self.tier = tier
        self.char_key = char_key
        self.background = background
        self.rush = rush
        sel = discord.ui.Select(
            custom_id="tqcur",
            placeholder="Paying currency",
            options=[
                discord.SelectOption(label="PHP (GCash)", value="PHP"),
                discord.SelectOption(label="USD (PayPal / Ko-fi)", value="USD"),
            ],
        )

        async def cb(interaction: discord.Interaction) -> None:
            cur = interaction.data.get("values", [""])[0] if interaction.data else "PHP"
            fields = _parse_form_fields_json(self._row.get("form_fields"))
            if cur == "PHP":
                modal = CommissionModal(
                    cog,
                    guild_id,
                    button_id,
                    button_label,
                    commission_type,
                    tier,
                    char_key,
                    background,
                    rush,
                    "PHP",
                    "GCash",
                    fields,
                )
                await interaction.response.send_modal(modal)
                return
            await interaction.response.edit_message(
                embed=info_embed(
                    "Payment method",
                    "**Which payment method?** (USD) — step 7/7",
                ),
                view=TicketQuoteUsdMethodView(
                    cog,
                    guild_id,
                    button_id,
                    button_label,
                    row,
                    commission_type,
                    tier,
                    char_key,
                    background,
                    rush,
                ),
            )

        sel.callback = cb
        self.add_item(sel)


class TicketQuoteUsdMethodView(discord.ui.View):
    def __init__(
        self,
        cog: TicketsCog,
        guild_id: int,
        button_id: str,
        button_label: str,
        row: dict[str, Any],
        commission_type: str,
        tier: str,
        char_key: str,
        background: str,
        rush: bool,
    ) -> None:
        super().__init__(timeout=420.0)
        self.cog = cog
        self.guild_id = guild_id
        self.button_id = button_id
        self.button_label = button_label
        self._row = row
        self.commission_type = commission_type
        self.tier = tier
        self.char_key = char_key
        self.background = background
        self.rush = rush
        sel = discord.ui.Select(
            custom_id="tq_usd_m",
            placeholder="Payment method",
            options=[
                discord.SelectOption(label="PayPal", value="PayPal"),
                discord.SelectOption(label="Ko-fi", value="Ko-fi"),
            ],
        )

        async def cb(interaction: discord.Interaction) -> None:
            method = interaction.data.get("values", [""])[0] if interaction.data else "PayPal"
            fields = _parse_form_fields_json(self._row.get("form_fields"))
            modal = CommissionModal(
                cog,
                guild_id,
                button_id,
                button_label,
                commission_type,
                tier,
                char_key,
                background,
                rush,
                "USD",
                str(method),
                fields,
            )
            await interaction.response.send_modal(modal)

        sel.callback = cb
        self.add_item(sel)


class CommissionModal(discord.ui.Modal):
    def __init__(
        self,
        cog: TicketsCog,
        guild_id: int,
        button_id: str,
        button_label: str,
        commission_type: str,
        rendering_tier: str,
        char_key: str,
        background: str,
        rush_addon: bool,
        pay_currency: str,
        payment_method: str,
        fields: list[dict[str, Any]],
    ) -> None:
        super().__init__(title="Payment & references")
        self.cog = cog
        self.guild_id = guild_id
        self.button_id = button_id
        self.button_label = button_label
        self.commission_type = commission_type
        self.rendering_tier = rendering_tier
        self.char_key = char_key
        self.background = background
        self.rush_addon = rush_addon
        self.pay_currency = pay_currency
        self.payment_method = payment_method
        self._field_labels: list[str] = []
        for i, f in enumerate(fields[:4]):
            lab = str(f.get("label", "Field"))[:45]
            self._field_labels.append(lab)
            ph = str(f.get("placeholder", ""))[:100]
            req = bool(f.get("required", True))
            long = bool(f.get("long", False))
            style = discord.TextStyle.paragraph if long else discord.TextStyle.short
            mx = 4000 if long else 400
            ti = discord.ui.TextInput(
                label=lab,
                style=style,
                placeholder=ph or None,
                required=req,
                max_length=mx,
                custom_id=f"tf_{i}",
            )
            self.add_item(ti)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        values: list[str] = []
        for child in self.children:
            if isinstance(child, discord.ui.TextInput):
                values.append((child.value or "").strip())
        answers = dict(zip(self._field_labels, values))
        await self.cog.handle_modal_submit(
            interaction,
            self.guild_id,
            self.button_id,
            self.button_label,
            self.commission_type,
            answers,
            rendering_tier=self.rendering_tier,
            char_key=self.char_key,
            background=self.background,
            rush_addon=self.rush_addon,
            pay_currency=self.pay_currency,
            payment_method=self.payment_method,
        )


class TicketsCog(commands.Cog, name="TicketsCog"):
    deploy_group = app_commands.Group(
        name="deploy",
        description="Post TOS / payment panels (use `/setup` for the full wizard)",
    )
    ticketbutton = app_commands.Group(name="ticketbutton", description="Ticket panel buttons (staff)")
    ticketform = app_commands.Group(name="ticketform", description="Ticket form fields (staff)")
    payment = app_commands.Group(name="payment", description="Ticket payment workflow")
    revision = app_commands.Group(name="revision", description="Ticket revision tracking")
    references = app_commands.Group(name="references", description="Ticket reference links")
    note = app_commands.Group(name="note", description="Internal staff notes")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @staticmethod
    def _ticket_answers(ticket: dict[str, Any]) -> dict[str, str]:
        raw = ticket.get("answers")
        if not raw:
            return {}
        if isinstance(raw, dict):
            return {str(k): str(v) for k, v in raw.items()}
        try:
            data = json.loads(str(raw))
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items()}

    @staticmethod
    def _is_owner_or_admin(interaction: discord.Interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return False
        if interaction.user.id == interaction.guild.owner_id:
            return True
        return bool(interaction.user.guild_permissions.administrator)

    async def _post_noted_queue_summary(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel,
        ticket: dict[str, Any],
        staff: discord.Member,
    ) -> None:
        qch = await get_text_channel(guild, gk.QUEUE_CHANNEL)
        if not qch:
            return
        ans = self._ticket_answers(ticket)
        buyer = guild.get_member(int(ticket["client_id"]))
        buyer_name = (buyer.display_name if buyer else "client").replace("`", "")
        line1 = f"{ans.get('Characters', '?')}  ・  {ans.get('Rendering Tier', '?')}  ・  {ans.get('Commission Type', '?')}"
        line2 = ans.get("Paying in", "price  ・  payment method")
        opened_ts = int(datetime.fromisoformat(str(ticket.get("opened_at"))).timestamp()) if ticket.get("opened_at") else int(datetime.now(timezone.utc).timestamp())
        summary = (
            "_ _\n"
            "_ _\n"
            f"‎ ‎ ‎ ‎ ‎ ╭‎ ‎ ‎ ‎ ‎ 🌸  **__ {buyer_name}'s order line-up__ !**\n"
            f"-# ‎  ‎ ‎ ‎ ‎ ‎‎﹒ assisted by : {staff.display_name}\n"
            f"‎ ‎ ‎ ‎ ‎ ﹒ ‎‎` OOO `‎‎ ‎ ‎ ‎ ‎ ‎‎➖‎ ‎ ‎ ‎ ‎ {line1}\n"
            f"‎ ‎ ‎ ‎ ‎ ‎‎﹒ ` OO1 `‎‎ ‎ ‎ ‎ ‎ ‎‎➖‎ ‎ ‎ ‎ ‎ {line2}\n"
            f"‎ ‎ ‎ ‎ ‎ ‎‎﹒ ` OO2 `‎‎ ‎ ‎ ‎ ‎ ‎‎➖‎ ‎ ‎ ‎ ‎ <t:{opened_ts}:R>\n"
            "-# ‎  ‎ ‎ ‎ ‎ ‎‎﹒ check order status here : **__ noted__**  🐇\n"
            f"‎ ‎ ‎ ‎ ‎ ╰ ‎ ‎ ‎ ‎ ticket  ・  {channel.mention}\n"
            "_ _\n"
            "_ _"
        )
        try:
            await qch.send(content=summary)
        except discord.HTTPException:
            pass

    async def _apply_noted_workflow(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel,
        ticket: dict[str, Any],
        staff: discord.Member,
    ) -> str | None:
        """Move ticket to Noted category and post queue summary. Returns error string or None."""
        noted_cat = await get_category(guild, gk.NOTED_CATEGORY)
        try:
            if isinstance(noted_cat, discord.CategoryChannel):
                await channel.edit(category=noted_cat)
        except (discord.Forbidden, discord.HTTPException):
            pass
        await db.update_ticket_fields(
            channel.id,
            ticket_status="noted",
            assigned_staff_id=staff.id,
        )
        fresh = await db.get_ticket_by_channel(channel.id)
        await self._post_noted_queue_summary(guild, channel, fresh or ticket, staff)
        return None

    async def handle_noted_button(self, interaction: discord.Interaction) -> None:
        if not await TicketOpsView._is_staff_or_admin(interaction):
            await interaction.response.send_message(
                embed=user_warn("Staff only", "Only staff/admin can move to Noted."),
                ephemeral=True,
            )
            return
        if (
            not interaction.guild
            or not isinstance(interaction.channel, discord.TextChannel)
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                embed=user_hint("Ticket only", "Use this inside ticket channel."),
                ephemeral=True,
            )
            return
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket record for this channel."),
                ephemeral=True,
            )
            return
        err = await self._apply_noted_workflow(
            interaction.guild, interaction.channel, ticket, interaction.user
        )
        if err:
            await interaction.response.send_message(
                embed=user_warn("Noted failed", err), ephemeral=True
            )
            return
        opener = interaction.guild.get_member(int(ticket["client_id"]))
        opener_mention = opener.mention if opener else f"<@{int(ticket['client_id'])}>"
        await interaction.response.send_message(
            embed=success_embed(
                "Moved to noted",
                f"{opener_mention} ticket moved to noted by {interaction.user.mention}. Queue summary posted.",
            ),
            ephemeral=False,
        )

    @staticmethod
    def _strike_lines(text: str) -> str:
        out: list[str] = []
        for ln in str(text).splitlines():
            if ln.strip():
                out.append(f"~~{ln}~~")
            else:
                out.append(ln)
        return "\n".join(out)

    async def _refresh_queue_card_from_ticket(
        self,
        guild: discord.Guild,
        ticket: dict[str, Any],
        *,
        stage: str | None = None,
        force_done_strikethrough: bool = False,
    ) -> None:
        order_id = str(ticket.get("order_id") or "").strip()
        if not order_id:
            return
        order = await db.get_order(order_id)
        if not order:
            return
        qcid = await db.get_guild_setting(guild.id, gk.QUEUE_CHANNEL)
        vcid = await db.get_guild_setting(guild.id, gk.VOUCHES_CHANNEL)
        if not qcid or not vcid:
            return
        qmid = int(order.get("queue_message_id") or 0)
        if qmid <= 0:
            return
        qch = guild.get_channel(int(qcid))
        if not isinstance(qch, discord.TextChannel):
            return
        status = "Done" if force_done_strikethrough else str(order.get("status") or "Noted")
        buyer = guild.get_member(int(order["client_id"]))
        buyer_name = buyer.display_name if buyer else str(order.get("client_name") or "buyer")
        order_number = int(ticket.get("order_number") or 1)
        body = await build_queue_entry_text(
            order,
            guild,
            qmid,
            status,
            order_number=order_number,
            buyer_display_name=buyer_name,
            queue_channel_id=int(qcid),
            vouches_channel_id=int(vcid),
        )
        if stage:
            body = f"{body}\n\n003 - stage: {stage}"
        if force_done_strikethrough:
            body = self._strike_lines(body)
        emb = queue_embed(order, body)
        try:
            msg = await qch.fetch_message(qmid)
            await msg.edit(embed=emb)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

    # --- /ticketpanel ---

    @app_commands.command(name="ticketpanel", description="Post or update the configurable ticket panel")
    @app_commands.describe(
        channel="Channel for the panel",
        title="Embed title",
        description="Embed description/body",
        color="Embed color hex (e.g. #669b9a)",
        footer="Optional footer text",
    )
    @is_staff()
    async def ticketpanel_cmd(
        self,
        interaction: discord.Interaction,
        channel: str,
        title: str,
        description: str,
        color: str | None = None,
        footer: str | None = None,
    ) -> None:
        if not interaction.guild:
            return
        cat = await get_category(interaction.guild, gk.TICKET_CATEGORY)
        staff_role = await get_role(interaction.guild, gk.STAFF_ROLE)
        if not cat or not staff_role:
            await interaction.response.send_message(
                embed=user_hint(
                    "Configuration required",
                    "Please run **`/setup`** or **`/config view`** first to set your **ticket category** "
                    "and **staff role**.",
                ),
                ephemeral=True,
            )
            return

        ch = resolve_text_channel(interaction.guild, channel)
        if not ch:
            await interaction.response.send_message(
                embed=user_hint("Invalid channel", _SETUP_CH_ERR), ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        col = (color or "#669b9a").strip()
        emb = discord.Embed(
            title=title[:256],
            description=description[:4096],
            color=_hex_to_color(col),
        )
        if footer:
            emb.set_footer(text=footer[:2048])

        rows = await db.list_ticket_buttons(interaction.guild.id)
        view = self._build_panel_view(interaction.guild.id, rows)
        old = await db.get_ticket_panel(interaction.guild.id)
        if old and old.get("channel_id") and old.get("message_id"):
            old_ch = interaction.guild.get_channel(int(old["channel_id"]))
            if isinstance(old_ch, discord.TextChannel):
                try:
                    om = await old_ch.fetch_message(int(old["message_id"]))
                    await om.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass

        if not rows:
            emb.description = (emb.description or "") + (
                "\n\n_No ticket types configured yet. Use `/ticketbutton add` to add buttons._"
            )

        kwargs: dict[str, Any] = {"embed": emb}
        if view is not None:
            kwargs["view"] = view
        msg = await ch.send(**kwargs)

        await db.upsert_ticket_panel(
            interaction.guild.id,
            ch.id,
            msg.id,
            title[:256],
            description[:4096],
            col,
            footer[:2048] if footer else None,
        )
        if view is not None:
            try:
                self.bot.add_view(view, message_id=msg.id)
            except ValueError:
                pass

        await interaction.followup.send(
            embed=success_embed("Ticket panel", f"✅ Ticket panel posted in {ch.mention}."),
            ephemeral=True,
        )

    # --- /ticketbutton ---

    @ticketbutton.command(name="add", description="Add a ticket type button to the panel")
    @app_commands.describe(
        label="Button label (e.g. order, report)",
        emoji="Optional emoji for the button",
        color="Button color",
        category="Category where tickets open (optional; defaults to server ticket category)",
    )
    @app_commands.choices(
        color=[
            app_commands.Choice(name="blurple", value="blurple"),
            app_commands.Choice(name="green", value="green"),
            app_commands.Choice(name="red", value="red"),
            app_commands.Choice(name="grey", value="grey"),
        ]
    )
    @is_staff()
    async def ticketbutton_add(
        self,
        interaction: discord.Interaction,
        label: str,
        emoji: str | None = None,
        color: str | None = None,
        category: str | None = None,
    ) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer(ephemeral=True)
        if await db.count_ticket_buttons(interaction.guild.id) >= 5:
            await interaction.followup.send(
                embed=user_hint("Limit", "Maximum 5 ticket buttons per server."),
                ephemeral=True,
            )
            return
        if await db.find_ticket_button_by_label(interaction.guild.id, label):
            await interaction.followup.send(
                embed=user_hint(
                    "Duplicate",
                    "A button with that label already exists. Use `/ticketbutton remove` first.",
                ),
                ephemeral=True,
            )
            return

        base = _slug_button_id(label, interaction.guild.id)
        bid = await _ensure_unique_button_id(interaction.guild.id, base)

        col = (color or "blurple").lower()
        if col not in BUTTON_STYLE_MAP:
            col = "blurple"
        cat_id: int | None = None
        if category and str(category).strip():
            cat_ch = resolve_category(interaction.guild, category)
            if not cat_ch:
                await interaction.followup.send(
                    embed=user_hint("Invalid category", "Could not resolve that category."),
                    ephemeral=True,
                )
                return
            cat_id = cat_ch.id
        else:
            gc = await get_category(interaction.guild, gk.TICKET_CATEGORY)
            if gc:
                cat_id = gc.id

        emoji_val = emoji.strip() if emoji and emoji.strip() else None

        await db.insert_ticket_button(
            bid,
            interaction.guild.id,
            label.strip()[:80],
            emoji_val,
            col,
            cat_id,
            None,
        )
        err = await self._refresh_panel_message(interaction.guild)
        if err:
            await interaction.followup.send(embed=user_hint("Panel", err), ephemeral=True)
            return
        rows = await db.list_ticket_buttons(interaction.guild.id)
        preview = ", ".join(f"**{r['label']}**" for r in rows) or "—"
        await interaction.followup.send(
            embed=success_embed("Button added", f"Updated panel. Buttons: {preview}"),
            ephemeral=True,
        )

    @ticketbutton.command(name="remove", description="Remove a ticket button by label")
    @app_commands.describe(label="The button label to remove")
    @is_staff()
    async def ticketbutton_remove(
        self, interaction: discord.Interaction, label: str
    ) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer(ephemeral=True)
        ok = await db.delete_ticket_button_by_label(interaction.guild.id, label)
        if not ok:
            await interaction.followup.send(
                embed=user_hint("Not found", "No button with that label."),
                ephemeral=True,
            )
            return
        err = await self._refresh_panel_message(interaction.guild)
        if err:
            await interaction.followup.send(embed=user_hint("Panel", err), ephemeral=True)
            return
        await interaction.followup.send(
            embed=success_embed("Removed", f"Removed **{label}** and refreshed the panel."),
            ephemeral=True,
        )

    @ticketbutton.command(name="list", description="List configured ticket buttons")
    @is_staff()
    async def ticketbutton_list(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        rows = await db.list_ticket_buttons(interaction.guild.id)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("Ticket buttons", "No buttons configured."),
                ephemeral=True,
            )
            return
        lines = []
        for r in rows:
            cat = (
                interaction.guild.get_channel(int(r["category_id"]))
                if r.get("category_id")
                else None
            )
            cname = cat.name if isinstance(cat, discord.CategoryChannel) else "default"
            ff = "custom" if r.get("form_fields") else "default"
            em = r.get("emoji") or "—"
            ag = "🔞 age gate" if int(r.get("require_age_verified") or 0) else ""
            lines.append(
                f"**{r['label']}** — emoji: {em} — color: `{r['color']}` — category: {cname} — form: {ff} {ag}".strip()
            )
        await interaction.response.send_message(
            embed=info_embed("Ticket buttons", "\n".join(lines)[:4000]),
            ephemeral=True,
        )

    # --- /ticketform ---

    @ticketform.command(name="set", description="Set modal form fields (JSON) for a button")
    @app_commands.describe(button="Button label", fields="JSON array of field objects")
    @is_staff()
    async def ticketform_set(
        self, interaction: discord.Interaction, button: str, fields: str
    ) -> None:
        if not interaction.guild:
            return
        row = await db.find_ticket_button_by_label(interaction.guild.id, button)
        if not row:
            await interaction.response.send_message(
                embed=user_hint("Not found", "No button with that label."),
                ephemeral=True,
            )
            return
        try:
            parsed = json.loads(fields)
        except json.JSONDecodeError:
            await interaction.response.send_message(
                embed=user_hint("JSON", "Invalid JSON."),
                ephemeral=True,
            )
            return
        valid, err = _validate_form_fields(parsed)
        if valid is None:
            await interaction.response.send_message(
                embed=user_hint("Validation", err or "Invalid fields."),
                ephemeral=True,
            )
            return
        await db.update_ticket_button_form_fields(
            row["button_id"], json.dumps(valid, ensure_ascii=False)
        )
        lines = [f"• **{f['label']}** ({'paragraph' if f['long'] else 'short'})" for f in valid]
        await interaction.response.send_message(
            embed=success_embed("Form saved", "\n".join(lines)[:4000]),
            ephemeral=True,
        )

    @ticketform.command(name="reset", description="Reset form fields to defaults for a button")
    @app_commands.describe(button="Button label")
    @is_staff()
    async def ticketform_reset(self, interaction: discord.Interaction, button: str) -> None:
        if not interaction.guild:
            return
        row = await db.find_ticket_button_by_label(interaction.guild.id, button)
        if not row:
            await interaction.response.send_message(
                embed=user_hint("Not found", "No button with that label."),
                ephemeral=True,
            )
            return
        await db.update_ticket_button_form_fields(row["button_id"], None)
        await interaction.response.send_message(
            embed=success_embed("Reset", f"Form for **{row['label']}** reset to defaults."),
            ephemeral=True,
        )

    @ticketform.command(name="preview", description="Preview form fields for a button")
    @app_commands.describe(button="Button label")
    @is_staff()
    async def ticketform_preview(self, interaction: discord.Interaction, button: str) -> None:
        if not interaction.guild:
            return
        row = await db.find_ticket_button_by_label(interaction.guild.id, button)
        if not row:
            await interaction.response.send_message(
                embed=user_hint("Not found", "No button with that label."),
                ephemeral=True,
            )
            return
        fields = _parse_form_fields_json(row.get("form_fields"))
        lines = [
            f"• **{f['label']}** — placeholder: {f.get('placeholder','')} — required: {f.get('required', True)} — long: {f.get('long', False)}"
            for f in fields
        ]
        await interaction.response.send_message(
            embed=info_embed(f"Form: {row['label']}", "\n".join(lines)[:4000]),
            ephemeral=True,
        )

    @ticketform.command(
        name="setoptions",
        description="Set commission type options for the select menu (comma-separated)",
    )
    @app_commands.describe(
        button="Button label",
        options="Comma-separated, e.g. Icon, Bust Up, Full Body",
    )
    @is_staff()
    async def ticketform_setoptions(
        self, interaction: discord.Interaction, button: str, options: str
    ) -> None:
        if not interaction.guild:
            return
        row = await db.find_ticket_button_by_label(interaction.guild.id, button)
        if not row:
            await interaction.response.send_message(
                embed=user_hint("Not found", "No button with that label."),
                ephemeral=True,
            )
            return
        parsed, err = _parse_comma_select_options(options)
        if parsed is None:
            await interaction.response.send_message(
                embed=user_hint("Options", err or "Invalid options."),
                ephemeral=True,
            )
            return
        await db.update_ticket_button_select_options(
            row["button_id"], json.dumps(parsed, ensure_ascii=False)
        )
        listed = "\n".join(f"• {o}" for o in parsed)
        await interaction.response.send_message(
            embed=success_embed("Select options saved", listed[:4000]),
            ephemeral=True,
        )

    @ticketform.command(
        name="resetoptions",
        description="Reset commission type select options to the default list",
    )
    @app_commands.describe(button="Button label")
    @is_staff()
    async def ticketform_resetoptions(
        self, interaction: discord.Interaction, button: str
    ) -> None:
        if not interaction.guild:
            return
        row = await db.find_ticket_button_by_label(interaction.guild.id, button)
        if not row:
            await interaction.response.send_message(
                embed=user_hint("Not found", "No button with that label."),
                ephemeral=True,
            )
            return
        await db.update_ticket_button_select_options(row["button_id"], None)
        listed = "\n".join(f"• {o}" for o in DEFAULT_SELECT_OPTIONS)
        await interaction.response.send_message(
            embed=success_embed("Options reset", f"Restored defaults:\n{listed}"),
            ephemeral=True,
        )

    # --- /deploy tos, payment (panels) ---

    @deploy_group.command(
        name="tos",
        description="Post the TOS agreement panel in the channel you specify (mention or ID)",
    )
    @app_commands.describe(
        channel="Where to post the panel — mention, ID, or pick a channel",
    )
    @is_staff()
    async def setup_tos(self, interaction: discord.Interaction, channel: str) -> None:
        ch = resolve_text_channel(interaction.guild, channel)
        if not ch:
            await interaction.response.send_message(
                embed=user_hint("Invalid channel", _SETUP_CH_ERR), ephemeral=True
            )
            return
        await db.set_guild_setting(interaction.guild.id, gk.TOS_CHANNEL, ch.id)
        shop = self.bot.get_cog("ShopCog")
        if not shop or not hasattr(shop, "run_setup_tos"):
            await interaction.response.send_message(
                embed=user_hint("Shop module unavailable", "Try again later or contact the bot owner."), ephemeral=True
            )
            return
        await shop.run_setup_tos(interaction, ch)

    @deploy_group.command(
        name="payment",
        description="Post the payment methods panel in the channel you specify (mention or ID)",
    )
    @app_commands.describe(
        channel="Where to post the panel — mention, ID, or pick a channel",
    )
    @is_staff()
    async def setup_payment(self, interaction: discord.Interaction, channel: str) -> None:
        ch = resolve_text_channel(interaction.guild, channel)
        if not ch:
            await interaction.response.send_message(
                embed=user_hint("Invalid channel", _SETUP_CH_ERR), ephemeral=True
            )
            return
        await db.set_guild_setting(interaction.guild.id, gk.PAYMENT_CHANNEL, ch.id)
        pay = self.bot.get_cog("PaymentCog")
        if not pay or not hasattr(pay, "run_setup_payment"):
            await interaction.response.send_message(
                embed=user_hint("Payment module unavailable", "Try again later or contact the bot owner."), ephemeral=True
            )
            return
        await pay.run_setup_payment(interaction, ch)

    @deploy_group.command(
        name="all",
        description="Deploy TOS panel, payment panel, and refresh ticket panel (staff)",
    )
    @is_staff()
    async def deploy_all_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        missing = await _deploy_prereq_failures(interaction.guild)
        if missing:
            bullet = "\n".join(f"• {m}" for m in missing[:20])
            await interaction.response.send_message(
                embed=user_warn(
                    "Setup incomplete",
                    f"Fix these, then run **`/deploy all`** again:\n{bullet}",
                ),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        lines: list[str] = []
        shop = interaction.client.get_cog("ShopCog")
        pay = interaction.client.get_cog("PaymentCog")
        tos_ch = await get_text_channel(interaction.guild, gk.TOS_CHANNEL)
        pay_ch = await get_text_channel(interaction.guild, gk.PAYMENT_CHANNEL)
        if shop is not None and callable(getattr(shop, "deploy_tos_panel", None)) and tos_ch:
            try:
                await shop.deploy_tos_panel(tos_ch)  # type: ignore[union-attr]
                lines.append("TOS panel posted.")
            except Exception as e:
                lines.append(f"TOS deploy failed: {e!s}")
        else:
            lines.append("TOS skipped (missing ShopCog or TOS channel).")
        if pay is not None and callable(getattr(pay, "deploy_payment_panel", None)) and pay_ch:
            try:
                await pay.deploy_payment_panel(pay_ch)  # type: ignore[union-attr]
                lines.append("Payment panel posted.")
            except Exception as e:
                lines.append(f"Payment deploy failed: {e!s}")
        else:
            lines.append("Payment skipped (missing PaymentCog or payment channel).")
        panel_err = await self._refresh_panel_message(interaction.guild)
        if panel_err:
            lines.append(f"Ticket panel: {panel_err}")
        else:
            lines.append("Ticket panel refreshed.")
        await interaction.followup.send(
            embed=info_embed("Deploy all", "\n".join(lines)[:3900]),
            ephemeral=True,
        )

    def _build_panel_view(
        self, guild_id: int, rows: list[dict[str, Any]]
    ) -> discord.ui.View | None:
        if not rows:
            return None
        view = discord.ui.View(timeout=None)
        for row in rows[:5]:
            style = BUTTON_STYLE_MAP.get(
                str(row.get("color") or "blurple").lower(), discord.ButtonStyle.primary
            )
            cid = f"bbtp:{guild_id}:{row['button_id']}"
            emoji = row.get("emoji") or None

            btn = discord.ui.Button(
                label=str(row["label"])[:80],
                style=style,
                custom_id=cid,
                emoji=emoji,
            )
            bid = str(row["button_id"])

            def _handler(button_id: str):
                async def _inner(interaction: discord.Interaction) -> None:
                    await self.handle_panel_button(interaction, button_id)

                return _inner

            btn.callback = _handler(bid)
            view.add_item(btn)
        return view

    async def _refresh_panel_message(self, guild: discord.Guild) -> str | None:
        """Rebuild ticket panel message; returns error string or None."""
        panel = await db.get_ticket_panel(guild.id)
        if not panel:
            return "No ticket panel yet. Run `/ticketpanel` first."
        ch = guild.get_channel(int(panel["channel_id"]))
        if not isinstance(ch, discord.TextChannel):
            return "Ticket panel channel is missing."
        rows = await db.list_ticket_buttons(guild.id)
        emb = discord.Embed(
            title=panel["embed_title"][:256],
            description=panel["embed_description"][:4096],
            color=_hex_to_color(panel.get("embed_color") or "#669b9a"),
        )
        if panel.get("embed_footer"):
            emb.set_footer(text=str(panel["embed_footer"])[:2048])
        if not rows:
            emb.description = (emb.description or "") + (
                "\n\n_No ticket types configured yet. Use `/ticketbutton add` to add buttons._"
            )
        view = self._build_panel_view(guild.id, rows)
        try:
            old = await ch.fetch_message(int(panel["message_id"]))
            await old.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass
        kwargs: dict[str, Any] = {"embed": emb}
        if view is not None:
            kwargs["view"] = view
        try:
            msg = await ch.send(**kwargs)
        except discord.HTTPException:
            return "Could not post the panel message."
        await db.upsert_ticket_panel(
            guild.id,
            ch.id,
            msg.id,
            panel["embed_title"],
            panel["embed_description"],
            panel.get("embed_color") or "#669b9a",
            panel.get("embed_footer"),
        )
        if view is not None:
            try:
                # Global registration handles stale/older panel messages too.
                self.bot.add_view(view)
            except ValueError:
                pass
            try:
                self.bot.add_view(view, message_id=msg.id)
            except ValueError:
                pass
        return None

    @staticmethod
    def _next_ticket_suffix(guild: discord.Guild, base_slug: str) -> int:
        max_n = 0
        pat = re.compile(rf"^{re.escape(base_slug)}-(\d{{3}})$")
        for ch in guild.text_channels:
            m = pat.match(ch.name)
            if not m:
                continue
            try:
                n = int(m.group(1))
            except ValueError:
                continue
            if n > max_n:
                max_n = n
        return max_n + 1

    async def handle_panel_button(self, interaction: discord.Interaction, button_id: str) -> None:
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.HTTPException:
            return
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.followup.send(
                embed=user_hint("Use this in a server", "Open this from inside the Discord server."), ephemeral=True
            )
            return

        row = await db.get_ticket_button_by_id(button_id)
        if not row or int(row["guild_id"]) != interaction.guild.id:
            await interaction.followup.send(
                embed=user_hint(
                    "Button needs a refresh",
                    "Ask staff to run **`/ticketpanel`** again so buttons stay in sync.",
                ),
                ephemeral=True,
            )
            return

        tos_role = await get_role(interaction.guild, gk.TOS_AGREED_ROLE)
        if tos_role is None or tos_role not in interaction.user.roles:
            tos_cid = await db.get_guild_setting(interaction.guild.id, gk.TOS_CHANNEL)
            if tos_cid:
                hint = (
                    f"You need to agree to our Terms of Service first — open <#{tos_cid}> and click **I Have Read & Agree**."
                )
            else:
                hint = "You need to agree to our Terms of Service first — ask staff to set the TOS channel (`/config`)."
            await interaction.followup.send(embed=user_warn("Terms required", hint), ephemeral=True)
            return
        if not await db.has_current_tos_agreement(interaction.user.id):
            cur_ver = await db.get_current_tos_version()
            tos_cid = await db.get_guild_setting(interaction.guild.id, gk.TOS_CHANNEL)
            hint = (
                f"TOS updated to version **v{cur_ver}**. Please re-agree in <#{tos_cid}> first."
                if tos_cid
                else f"TOS updated to version **v{cur_ver}**. Please re-agree first."
            )
            await interaction.followup.send(
                embed=user_warn("TOS updated", hint),
                ephemeral=True,
            )
            return

        if int(row.get("require_age_verified") or 0):
            age_role = await get_role(interaction.guild, gk.AGE_VERIFIED_ROLE)
            if not age_role or age_role not in interaction.user.roles:
                ver_cid = await db.get_guild_setting(
                    interaction.guild.id, gk.VERIFICATION_CHANNEL
                )
                hint = (
                    f"This ticket type needs **age 18+** verification (proves you may view NSFW content). "
                    f"Complete steps in <#{ver_cid}> to get the **Age verified** role, then open a ticket again."
                    if ver_cid
                    else "This ticket type needs **age 18+** verification. Ask staff to map **Age verified** role + verification channel in **`/config`**, then verify."
                )
                await interaction.followup.send(
                    embed=user_warn("Age verification required", hint), ephemeral=True
                )
                return

        if not await db.shop_is_open_db():
            await interaction.followup.send(
                embed=user_warn("Shop is closed", "Commissions are closed right now — check back when staff reopen."),
                ephemeral=True,
            )
            return

        existing = await db.get_open_ticket_by_user(interaction.user.id, interaction.guild.id)
        if existing:
            existing_channel_id = int(existing["channel_id"])
            ch = interaction.guild.get_channel(existing_channel_id)
            if ch is None:
                # Stale DB row (channel deleted manually) — clear and allow a new ticket.
                await db.delete_ticket_by_channel(existing_channel_id)
            else:
                ch_name = ch.name if isinstance(ch, discord.TextChannel) else str(existing_channel_id)
                await interaction.followup.send(
                    embed=user_warn(
                        "Open ticket already exists",
                        f"You already have an open ticket: **#{ch_name}** — continue there: <#{existing_channel_id}>",
                    ),
                    ephemeral=True,
                )
                return

        emb = info_embed(
            "Commission type",
            "What type of commission are you ordering?",
        )
        view = CommissionTypeSelectView(
            self,
            interaction.guild.id,
            button_id,
            str(row["label"]),
            row,
        )
        try:
            msg = await interaction.followup.send(embed=emb, view=view, ephemeral=True, wait=True)
            view.message = msg
        except discord.HTTPException:
            pass

    async def handle_modal_submit(
        self,
        interaction: discord.Interaction,
        guild_id: int,
        button_id: str,
        button_label: str,
        commission_type: str,
        answers: dict[str, str],
        *,
        rendering_tier: str,
        char_key: str,
        background: str,
        rush_addon: bool,
        pay_currency: str,
        payment_method: str,
    ) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer(ephemeral=True)

        row = await db.get_ticket_button_by_id(button_id)
        if not row:
            await interaction.followup.send(
                embed=user_hint("Configuration missing", "That ticket type isn’t set up anymore. Ask staff to check `/ticketbutton`."), ephemeral=True
            )
            return

        category = None
        if row.get("category_id"):
            c = interaction.guild.get_channel(int(row["category_id"]))
            if isinstance(c, discord.CategoryChannel):
                category = c
        if category is None:
            category = await get_category(interaction.guild, gk.TICKET_CATEGORY)
        if not category:
            await interaction.followup.send(
                embed=user_hint("Config", "Ticket category missing. Use **`/setup`** (Tickets group) or map categories manually."),
                ephemeral=True,
            )
            return

        staff_role = await get_role(interaction.guild, gk.STAFF_ROLE)
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.followup.send(
                embed=user_hint("Couldn’t verify member", "Try the command again from the server."), ephemeral=True
            )
            return

        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True, manage_channels=True, send_messages=True
            ),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                manage_channels=True,
                attach_files=True,
                embed_links=True,
            )

        raw_name = re.sub(r"[^a-z0-9\s]", "", member.name.lower())
        raw_name = re.sub(r"\s+", "_", raw_name).strip("_")[:80] or "user"
        base_slug = ticket_channel_slug(rendering_tier, commission_type, raw_name)[:96]
        ticket_no = self._next_ticket_suffix(interaction.guild, base_slug)
        ch_slug = f"{base_slug}-{ticket_no:03d}"[:100]

        try:
            ticket_ch = await interaction.guild.create_text_channel(
                ch_slug,
                category=category,
                overwrites=overwrites,
                reason=f"Ticket ({button_label}) for {member}",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=user_warn(
                    "Missing permissions",
                    "The bot needs permission to **manage channels** in that category. Ask an admin to adjust role/channel settings.",
                ),
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            await interaction.followup.send(
                embed=user_warn("Couldn’t create channel", "Discord blocked channel creation — try again or ask an admin to check limits and permissions."),
                ephemeral=True,
            )
            return

        data = await compute_quote_totals(
            interaction.guild,
            member,
            commission_type,
            rendering_tier,
            char_key,
            background,
            rush_addon=rush_addon,
        )
        total_php = float(data["total_php"])
        total_usd = float(data["total_usd_approx"])
        pc = pay_currency.strip().upper()
        pm = payment_method.strip()
        if pc == "PHP":
            pm = "GCash"
        bd = compute_payment_breakdown(
            artist_php=total_php,
            artist_usd=total_usd,
            pay_currency=pc,
            payment_method=pm,
        )
        snap = {
            "commission_type": commission_type,
            "tier": rendering_tier,
            "char_key": char_key,
            "background": background,
            "rush_addon": rush_addon,
            "total_php": total_php,
            "pay_currency": pc,
            "payment_method": pm,
            "fee_usd": bd.get("fee_usd"),
            "total_send_php": bd.get("total_send_php"),
            "total_send_usd": bd.get("total_send_usd"),
        }
        quote_expiry_hours = 72
        expires_at = datetime.now(timezone.utc) + timedelta(hours=quote_expiry_hours)
        snap["quote_expires_at"] = expires_at.isoformat()

        full_answers: dict[str, str] = {
            "Commission Type": commission_type,
            "Rendering Tier": rendering_tier,
            "Characters": char_key,
            "Background": background,
            "Rush": "Yes (+₱520)" if rush_addon else "No",
            "Paying in": f"{pc} — {pm}",
        }
        full_answers.update(answers)

        try:
            await db.insert_ticket_open(
                ticket_ch.id,
                interaction.guild.id,
                member.id,
                button_id=button_id,
                answers=full_answers,
                quote_total_php=total_php,
                quote_usd_approx=total_usd,
                quote_snapshot_json=json.dumps(snap, ensure_ascii=False),
                rendering_tier=rendering_tier,
                background=background,
                char_count_key=char_key,
                rush_addon=1 if rush_addon else 0,
                ticket_status="awaiting_payment",
                quote_expires_at=expires_at.isoformat(),
                quote_approved=1,
                payment_status="awaiting_payment",
                close_approved_by_client=0,
            )
        except Exception:
            log.exception(
                "Ticket create DB save failed guild_id=%s user_id=%s channel_name=%s",
                interaction.guild.id,
                member.id,
                ch_slug,
            )
            try:
                await ticket_ch.delete(reason="Ticket DB create failed")
            except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                pass
            await interaction.followup.send(
                embed=user_warn(
                    "Ticket create failed",
                    "Could not save ticket record. Please try again.",
                ),
                ephemeral=True,
            )
            return

        try:
            await ticket_ch.send(member.mention)
        except discord.HTTPException:
            pass

        q_emb = await build_quote_embed(
            interaction.guild,
            member,
            data,
            include_tier_comparison=False,
            pay_currency=pc,
            payment_method=pm,
        )
        try:
            await ticket_ch.send(embed=q_emb)
        except discord.HTTPException:
            pass
        try:
            await ticket_ch.send(
                embed=info_embed(
                    "Quote estimate",
                    f"Staff may adjust pricing. Quote window **{quote_expiry_hours}h** — use `/quote recalculate` if details change.",
                ),
            )
        except discord.HTTPException:
            pass

        welcome = discord.Embed(
            title="Ticket Opened",
            description=f"{member.mention} has created a new **{button_label}** ticket.",
            color=PRIMARY,
        )
        for key in WELCOME_FIELD_ORDER:
            if key in full_answers:
                label = str(key).strip().lower()
                welcome.add_field(
                    name=label,
                    value=str(full_answers[key])[:1024] or "-",
                    inline=False,
                )
        for k, v in full_answers.items():
            if k not in WELCOME_FIELD_ORDER and not k.startswith("_"):
                label = str(k).strip().lower()
                welcome.add_field(name=label[:256], value=str(v)[:1024] or "-", inline=False)
        welcome.add_field(
            name="payment",
            value=_payment_status_line("awaiting_payment"),
            inline=False,
        )
        welcome.set_footer(text=f"Ticket ID: {ch_slug} • staff action panel below")
        panel_msg = await ticket_ch.send(embed=welcome, view=TicketOpsView())
        try:
            await panel_msg.pin(reason="Staff action panel")
        except (discord.Forbidden, discord.HTTPException):
            pass

        # Downpayment / full payment due (amounts use **total to send** including processor fee)
        if pc == "PHP":
            ts = float(bd["total_send_php"] or 0)
            if ts <= 500:
                due_l = f"**Full payment due upfront:** {fmt_php(ts)}."
            else:
                half = ts / 2.0
                due_l = (
                    f"**50% down payment due now:** {fmt_php(half)}. "
                    f"**Remaining balance:** {fmt_php(half)}."
                )
            settle_line = f"**Total to send (incl. fees):** {fmt_php(ts)}"
        else:
            ts = float(bd["total_send_usd"] or 0)
            if ts <= 25:
                due_l = f"**Full payment due upfront:** {fmt_usd(ts)}."
            else:
                half = ts / 2.0
                due_l = (
                    f"**50% down payment due now:** {fmt_usd(half)}. "
                    f"**Remaining balance:** {fmt_usd(half)}."
                )
            settle_line = f"**Total to send (incl. fees):** {fmt_usd(ts)}"

        gcash = await db.get_guild_string_setting(interaction.guild.id, gk.PAYMENT_GCASH_DETAILS)
        pp = await db.get_guild_string_setting(interaction.guild.id, gk.PAYMENT_PAYPAL_LINK)
        kf = await db.get_guild_string_setting(interaction.guild.id, gk.PAYMENT_KOFI_LINK)
        pay_bits = []
        if gcash:
            pay_bits.append("**GCash** — see payment panel / staff.")
        if pp:
            pay_bits.append(f"**PayPal:** {pp[:200]}")
        if kf:
            pay_bits.append(f"**Ko-fi:** {kf[:200]}")
        pay_body = "\n".join(pay_bits) if pay_bits else "_Configure payment text with `/config payment`._"
        dp = discord.Embed(
            title="💳 Awaiting payment",
            description=f"{due_l}\n\n{settle_line}\n**Artist commission (no fee to you):** {fmt_php(total_php)} (~${total_usd:,.2f} USD est.)\n\n{pay_body}",
            color=PRIMARY,
        )
        try:
            await ticket_ch.send(embed=dp)
        except discord.HTTPException:
            pass

        info_e = discord.Embed(
            title="Staff shortcuts",
            description=(
                "**Panel:** Claim → **Noted** → Mark Complete → Archive · **Remind** (24h cooldown) · WIP stage dropdown\n"
                "**`/quote recalculate`** — refresh quote from matrix (ticket owner can refresh; staff changes options)\n"
                "**`/payment confirm`** — payment received → queue + in progress\n"
                "**`/revision log`** — log a revision\n"
                "**`/references add`** — save reference links"
            ),
            color=PRIMARY,
        )
        try:
            await ticket_ch.send(embed=info_e)
        except discord.HTTPException:
            pass

        await interaction.followup.send(
            embed=success_embed(
                "Ticket opened",
                f"Channel **#{ticket_ch.name}** — {ticket_ch.jump_url}",
            ),
            ephemeral=True,
        )
        try:
            await member.send(
                embed=info_embed(
                    "Ticket created",
                    f"Your ticket: **#{ticket_ch.name}**\n{ticket_ch.jump_url}",
                )
            )
        except discord.Forbidden:
            pass

    @payment.command(
        name="proof",
        description="Client submits payment proof URL in-ticket",
    )
    @app_commands.describe(url="Screenshot URL or payment receipt link")
    async def payment_proof_cmd(
        self,
        interaction: discord.Interaction,
        url: str,
    ) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Ticket only", "Use this inside your ticket."),
                ephemeral=True,
            )
            return
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket record for this channel."),
                ephemeral=True,
            )
            return
        if interaction.user.id != int(ticket["client_id"]):
            await interaction.response.send_message(
                embed=user_warn("Client only", "Only ticket owner can submit payment proof."),
                ephemeral=True,
            )
            return
        u = url.strip()
        if not (u.startswith("http://") or u.startswith("https://")):
            await interaction.response.send_message(
                embed=user_hint("Invalid URL", "Provide full URL starting with `http://` or `https://`."),
                ephemeral=True,
            )
            return
        await db.update_ticket_fields(
            interaction.channel.id,
            payment_proof_url=u,
            payment_status="awaiting_payment_review",
            ticket_status="awaiting_payment_review",
        )
        await interaction.response.send_message(
            embed=success_embed("Proof submitted", "Staff has been notified to review payment proof."),
            ephemeral=False,
        )

    @payment.command(
        name="status",
        description="Set ticket payment status (staff)",
    )
    @app_commands.describe(state="New payment state")
    @app_commands.choices(
        state=[
            app_commands.Choice(name="Awaiting payment", value="awaiting_payment"),
            app_commands.Choice(name="Awaiting payment review", value="awaiting_payment_review"),
            app_commands.Choice(name="Paid", value="paid"),
            app_commands.Choice(name="Declined", value="payment_declined"),
        ]
    )
    @is_staff()
    async def payment_status_cmd(
        self,
        interaction: discord.Interaction,
        state: str,
    ) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Ticket only", "Use this inside buyer ticket."),
                ephemeral=True,
            )
            return
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket record for this channel."),
                ephemeral=True,
            )
            return
        await db.update_ticket_fields(
            interaction.channel.id,
            payment_status=state,
            ticket_status=state,
        )
        await interaction.response.send_message(
            embed=success_embed("Payment status updated", f"Set to **{state}**."),
            ephemeral=False,
        )

    @payment.command(
        name="confirm",
        description="Confirm payment received — register queue order and mark ticket in progress (staff)",
    )
    @is_staff()
    async def payment_confirm_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Ticket only", "Use this inside the buyer’s ticket channel."), ephemeral=True
            )
            return
        if not isinstance(interaction.user, discord.Member):
            return
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket record for this channel."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)

        # First-time order registration: simplified open flow auto-approves quote; do not block staff.
        registering_first = not ticket.get("order_id")
        if not registering_first:
            expires_raw = ticket.get("quote_expires_at")
            if expires_raw:
                try:
                    exp_dt = datetime.fromisoformat(str(expires_raw))
                    if datetime.now(timezone.utc) > exp_dt:
                        await interaction.followup.send(
                            embed=user_warn(
                                "Quote expired",
                                "Quote already expired. Recalculate quote first (`/quote recalculate`).",
                            ),
                            ephemeral=True,
                        )
                        return
                except ValueError:
                    pass
            if not bool(int(ticket.get("quote_approved") or 0)):
                await interaction.followup.send(
                    embed=user_warn(
                        "Quote not approved",
                        "Client must approve quote first (use quote approval buttons in ticket).",
                    ),
                    ephemeral=True,
                )
                return

        raw_ans = ticket.get("answers")
        try:
            answers: dict[str, Any] = (
                json.loads(raw_ans) if isinstance(raw_ans, str) else (raw_ans or {})
            )
        except json.JSONDecodeError:
            answers = {}

        client = interaction.guild.get_member(int(ticket["client_id"]))
        if not client:
            await interaction.followup.send(
                embed=user_hint("Buyer missing", "The client is not in this server."), ephemeral=True
            )
            return

        snap_raw = ticket.get("quote_snapshot_json")
        try:
            snap = json.loads(snap_raw) if snap_raw else {}
        except json.JSONDecodeError:
            snap = {}
        total_php = float(ticket.get("quote_total_php") or 0)
        item = f"{snap.get('commission_type', 'Commission')} / {snap.get('tier', '')}".strip(
            " /"
        )
        amount = str(snap.get("char_key", "1"))
        mop = str(answers.get("Mode of Payment", "—"))
        price = fmt_php(total_php) if total_php else "—"

        if ticket.get("order_id"):
            await db.update_ticket_fields(
                interaction.channel.id,
                ticket_status="in_progress",
                downpayment_confirmed=1,
                payment_status="paid",
            )
            try:
                await interaction.channel.send(
                    content=client.mention,
                    embed=success_embed(
                        "Payment confirmed",
                        "Payment confirmed — your order is on record. Work can proceed; staff will pick up this ticket when ready.",
                    ),
                )
            except discord.HTTPException:
                pass
            await interaction.followup.send(
                embed=success_embed("Updated", "Ticket marked **in progress**."), ephemeral=True
            )
            return

        qc = interaction.client.get_cog("QueueCog")
        if not isinstance(qc, QueueCog):
            await interaction.followup.send(
                embed=user_warn("Queue unavailable", "Queue module not loaded."), ephemeral=True
            )
            return
        oid, err = await register_order_in_ticket_channel(
            qc,
            interaction.guild,
            interaction.channel,
            interaction.user,
            client,
            amount,
            item,
            mop,
            price,
        )
        if err:
            await interaction.followup.send(
                embed=user_warn("Queue", err), ephemeral=True
            )
            return

        await db.update_ticket_fields(
            interaction.channel.id,
            ticket_status="in_progress",
            downpayment_confirmed=1,
            payment_status="paid",
        )
        try:
            await interaction.channel.send(
                content=client.mention,
                embed=success_embed(
                    "Payment confirmed",
                    f"Payment confirmed — order **`{oid}`** is registered on the queue. We'll claim your ticket soon.",
                ),
            )
        except discord.HTTPException:
            pass
        await interaction.followup.send(
            embed=success_embed("Done", f"Registered **`{oid}`** and posted queue card."), ephemeral=True
        )

    @revision.command(name="log", description="Log a revision (2 free, then +₱200 each)")
    @is_staff()
    @app_commands.describe(note="Optional note")
    async def revision_log_cmd(
        self, interaction: discord.Interaction, note: str | None = None
    ) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Ticket only", "Use this in a ticket channel."), ephemeral=True
            )
            return
        trow = await db.get_ticket_by_channel(interaction.channel.id)
        if not trow:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket here."), ephemeral=True
            )
            return
        n, fee_this, extra = await db.log_ticket_revision(interaction.channel.id)
        client = interaction.guild.get_member(int(trow["client_id"]))
        lines = [f"**Revision #{n}** logged."]
        if fee_this > 0:
            lines.append(
                f"**Extra revision fee (this ticket):** {fmt_php(fee_this)} (running extra total: {fmt_php(extra)})."
            )
        if note:
            lines.append(f"Note: {note}")
        emb = discord.Embed(
            title="Revision",
            description="\n".join(lines),
            color=PRIMARY,
        )
        await interaction.response.send_message(
            content=client.mention if client else None,
            embed=emb,
        )

    @references.command(name="add", description="Append a reference URL to this ticket (staff)")
    @is_staff()
    @app_commands.describe(url="Image or moodboard link")
    async def references_add_cmd(self, interaction: discord.Interaction, url: str) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Ticket only", "Use this in a ticket channel."), ephemeral=True
            )
            return
        t = await db.get_ticket_by_channel(interaction.channel.id)
        if not t:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket here."), ephemeral=True
            )
            return
        await db.append_ticket_reference(interaction.channel.id, url.strip())
        await interaction.response.send_message(
            embed=success_embed("Saved", url[:500]), ephemeral=True
        )

    @references.command(name="view", description="Show all saved reference links for this ticket")
    @is_staff()
    async def references_view_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Ticket only", "Use this in a ticket channel."), ephemeral=True
            )
            return
        t = await db.get_ticket_by_channel(interaction.channel.id)
        if not t:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket here."), ephemeral=True
            )
            return
        raw = t.get("references_json")
        try:
            links = json.loads(raw) if raw else []
            if not isinstance(links, list):
                links = []
        except json.JSONDecodeError:
            links = []
        if not links:
            await interaction.response.send_message(
                embed=info_embed("References", "No links saved yet."), ephemeral=True
            )
            return
        body = "\n".join(f"{i + 1}. {u}" for i, u in enumerate(links))[:3900]
        await interaction.response.send_message(
            embed=info_embed("Reference links", body), ephemeral=True
        )

    @note.command(name="add", description="Add internal staff note for this ticket")
    @app_commands.describe(message="Private staff handoff/context note")
    @is_staff()
    async def note_add_cmd(self, interaction: discord.Interaction, message: str) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Ticket only", "Use this inside ticket channel."),
                ephemeral=True,
            )
            return
        t = await db.get_ticket_by_channel(interaction.channel.id)
        if not t:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket here."),
                ephemeral=True,
            )
            return
        text = message.strip()[:1800]
        nid = await db.add_ticket_note(interaction.channel.id, interaction.guild.id, interaction.user.id, text)
        emb = discord.Embed(
            title="🔒 Staff note",
            description=text,
            color=PRIMARY,
        )
        emb.set_footer(text=f"Note #{nid} • internal")
        await interaction.response.send_message(embed=emb)

    @note.command(name="list", description="List internal notes for this ticket")
    @is_staff()
    async def note_list_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Ticket only", "Use this inside ticket channel."),
                ephemeral=True,
            )
            return
        t = await db.get_ticket_by_channel(interaction.channel.id)
        if not t:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket here."),
                ephemeral=True,
            )
            return
        rows = await db.list_ticket_notes(interaction.channel.id)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("Ticket notes", "No staff notes yet."),
                ephemeral=True,
            )
            return
        lines = [
            f"**#{r['note_id']}** `{r['created_at']}` by <@{r['author_id']}>\n{str(r['note'])[:220]}"
            for r in rows[-15:]
        ]
        await interaction.response.send_message(
            embed=info_embed("Ticket notes", "\n\n".join(lines)[:3900]),
            ephemeral=True,
        )

    @app_commands.command(name="assign", description="Assign or unassign ticket handler (staff)")
    @app_commands.describe(member="Staff member to assign (leave empty to unassign)")
    @is_staff()
    async def assign_cmd(self, interaction: discord.Interaction, member: discord.Member | None = None) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Ticket only", "Use this in ticket channel."),
                ephemeral=True,
            )
            return
        t = await db.get_ticket_by_channel(interaction.channel.id)
        if not t:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket here."),
                ephemeral=True,
            )
            return
        rid = await db.get_guild_setting(interaction.guild.id, gk.STAFF_ROLE)
        staff_role = interaction.guild.get_role(int(rid)) if rid else None
        if member is not None and staff_role and staff_role not in member.roles:
            await interaction.response.send_message(
                embed=user_hint("Invalid assignee", "Target member is not in configured staff role."),
                ephemeral=True,
            )
            return
        await db.update_ticket_fields(
            interaction.channel.id,
            assigned_staff_id=member.id if member else None,
        )
        if member:
            try:
                await member.send(
                    embed=info_embed(
                        "Ticket assigned",
                        f"You were assigned to `{interaction.channel.name}` in **{interaction.guild.name}**.",
                    )
                )
            except discord.Forbidden:
                pass
        await interaction.response.send_message(
            embed=success_embed(
                "Assignment updated",
                f"Assigned to {member.mention}." if member else "Ticket unassigned.",
            ),
            ephemeral=False,
        )

    @app_commands.command(name="mytickets", description="List tickets assigned to you (staff)")
    @is_staff()
    async def mytickets_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        rows = await db.list_open_tickets_for_staff(interaction.guild.id, interaction.user.id)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("Assigned tickets", "No assigned open tickets."),
                ephemeral=True,
            )
            return
        lines = [f"<#{r['channel_id']}> — client <@{r['client_id']}>" for r in rows[:30]]
        await interaction.response.send_message(
            embed=info_embed("Assigned tickets", "\n".join(lines)),
            ephemeral=True,
        )

    @app_commands.command(name="ticketsearch", description="Search open tickets by channel/member term (staff)")
    @app_commands.describe(query="Member ID, mention, name fragment, or channel fragment")
    @is_staff()
    async def ticketsearch_cmd(self, interaction: discord.Interaction, query: str) -> None:
        if not interaction.guild:
            return
        q = query.strip().lower()
        rows = await db.list_open_tickets_for_staff(interaction.guild.id, None)
        hits: list[str] = []
        for r in rows:
            cid = int(r["client_id"])
            chid = int(r["channel_id"])
            ch = interaction.guild.get_channel(chid)
            m = interaction.guild.get_member(cid)
            c_name = (m.display_name if m else str(cid)).lower()
            ch_name = (ch.name if isinstance(ch, discord.TextChannel) else str(chid)).lower()
            if q in c_name or q in ch_name or q in str(cid) or q in str(chid):
                assignee = f"<@{r['assigned_staff_id']}>" if r.get("assigned_staff_id") else "_unassigned_"
                hits.append(f"<#{chid}> — client <@{cid}> — assignee {assignee}")
        if not hits:
            await interaction.response.send_message(
                embed=info_embed("Ticket search", "No open tickets matched query."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=info_embed("Ticket search results", "\n".join(hits[:40])),
            ephemeral=True,
        )

    @app_commands.command(name="noted", description="Move current ticket to noted orders and post queue summary")
    @is_staff()
    async def noted_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel) or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=user_hint("Ticket only", "Use this inside ticket channel."),
                ephemeral=True,
            )
            return
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket record for this channel."),
                ephemeral=True,
            )
            return
        err = await self._apply_noted_workflow(
            interaction.guild, interaction.channel, ticket, interaction.user
        )
        if err:
            await interaction.response.send_message(
                embed=user_warn("Noted failed", err), ephemeral=True
            )
            return
        opener = interaction.guild.get_member(int(ticket["client_id"]))
        opener_mention = opener.mention if opener else f"<@{int(ticket['client_id'])}>"
        await interaction.response.send_message(
            embed=success_embed(
                "Moved to noted",
                f"{opener_mention} ticket moved to noted by {interaction.user.mention}. Queue summary posted.",
            ),
            ephemeral=False,
        )

    @app_commands.command(name="deleteticket", description="Owner/admin delete current ticket channel")
    async def deleteticket_cmd(self, interaction: discord.Interaction) -> None:
        if not self._is_owner_or_admin(interaction):
            await interaction.response.send_message(
                embed=user_warn("Owner/admin only", "Only server owner/admin can delete ticket channel directly."),
                ephemeral=True,
            )
            return
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Ticket only", "Use this inside ticket channel."),
                ephemeral=True,
            )
            return
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket record for this channel."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=info_embed("Deleting", "Ticket channel will be deleted now."),
            ephemeral=True,
        )
        await db.delete_ticket_by_channel(interaction.channel.id)
        try:
            await interaction.channel.delete(reason=f"Ticket deleted by owner/admin {interaction.user.id}")
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

    @app_commands.command(name="setdoneautodelete", description="Owner/admin set auto-delete hours for done tickets (0 off)")
    @app_commands.describe(hours="Hours after Done button before auto-delete. 0 disables.")
    async def setdoneautodelete_cmd(
        self, interaction: discord.Interaction, hours: app_commands.Range[int, 0, 720]
    ) -> None:
        if not self._is_owner_or_admin(interaction):
            await interaction.response.send_message(
                embed=user_warn("Owner/admin only", "Only server owner/admin can set done auto-delete."),
                ephemeral=True,
            )
            return
        if not interaction.guild:
            return
        await db.set_guild_setting(interaction.guild.id, gk.DONE_TICKET_AUTO_DELETE_HOURS, int(hours))
        await interaction.response.send_message(
            embed=success_embed("Saved", f"Done auto-delete set to **{hours}** hour(s)."),
            ephemeral=True,
        )

    @ticketbutton.command(
        name="agegate",
        description="Require age-verified role to open this ticket type (NSFW)",
    )
    @app_commands.describe(
        button="Button label",
        require_age_verified="If true, user must have Age verified role",
    )
    @is_staff()
    async def ticketbutton_agegate(
        self,
        interaction: discord.Interaction,
        button: str,
        require_age_verified: bool,
    ) -> None:
        if not interaction.guild:
            return
        row = await db.find_ticket_button_by_label(interaction.guild.id, button)
        if not row:
            await interaction.response.send_message(
                embed=user_hint("Not found", "No button with that label."), ephemeral=True
            )
            return
        await db.set_ticket_button_require_age(
            row["button_id"], 1 if require_age_verified else 0
        )
        await interaction.response.send_message(
            embed=success_embed(
                "Age gate",
                f"**{button}** → age verification **{'required' if require_age_verified else 'off'}**.",
            ),
            ephemeral=True,
        )

    async def handle_close_button(self, interaction: discord.Interaction) -> None:
        await self._run_close(interaction)

    async def _run_close(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Wrong channel", "Use this inside an open ticket channel."), ephemeral=True
            )
            return
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "This channel isn’t linked to an open ticket."), ephemeral=True
            )
            return
        staff_role = await get_role(interaction.guild, gk.STAFF_ROLE)
        is_staff_u = (
            staff_role
            and isinstance(interaction.user, discord.Member)
            and staff_role in interaction.user.roles
        )
        is_owner = interaction.user.id == int(ticket["client_id"])
        if not is_staff_u and not is_owner:
            await interaction.response.send_message(
                embed=user_warn("Can’t close this", "Only **staff** or the **ticket owner** can close it."),
                ephemeral=True,
            )
            return
        if is_staff_u and not is_owner and not bool(int(ticket.get("close_approved_by_client") or 0)):
            await interaction.response.send_message(
                embed=user_warn(
                    "Client approval required",
                    "Client must approve closure first. Ask them to run **`/closeapprove`** in this ticket.",
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        from utils.transcript import generate_transcript

        meta_lines: list[str] = []
        if ticket.get("revision_count") is not None:
            meta_lines.append(
                f"Revisions logged: {int(ticket.get('revision_count') or 0)}"
            )
        if ticket.get("revision_extra_fee_php") is not None:
            meta_lines.append(
                f"Extra revision fees (PHP): {float(ticket.get('revision_extra_fee_php') or 0):,.2f}"
            )
        if ticket.get("quote_total_php") is not None:
            meta_lines.append(
                f"Quoted total (PHP): {float(ticket.get('quote_total_php') or 0):,.2f}"
            )

        try:
            file = await generate_transcript(
                interaction.channel,
                extra_meta=meta_lines if meta_lines else None,
            )
        except Exception:
            await interaction.followup.send(
                embed=user_warn("Transcript issue", "Couldn’t build the transcript file. Ask an admin to check bot permissions in this channel."),
            )
            return

        raw = file.fp.read()
        filename = file.filename or "transcript.html"
        dm_file = discord.File(io.BytesIO(raw), filename=filename)
        trans_file = discord.File(io.BytesIO(raw), filename=filename)

        client = interaction.guild.get_member(int(ticket["client_id"]))
        dm_ok = True
        if client:
            try:
                await client.send(
                    embed=info_embed("Ticket closed", "Transcript attached."),
                    file=dm_file,
                )
            except discord.Forbidden:
                dm_ok = False

        trans_ch = await get_text_channel(interaction.guild, gk.TRANSCRIPT_CHANNEL)
        if trans_ch:
            try:
                await trans_ch.send(
                    embed=info_embed("Transcript", f"Ticket {interaction.channel.name}"),
                    file=trans_file,
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        if not dm_ok and trans_ch:
            try:
                await trans_ch.send(
                    content=f"⚠️ Could not DM transcript to <@{ticket['client_id']}>.",
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        if dm_ok:
            await interaction.followup.send(
                embed=success_embed("Closing", "Transcript sent. Channel deletes in 15 seconds."),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                embed=user_hint(
                    "DM failed",
                    "Transcript was posted to the transcript channel only.",
                ),
                ephemeral=True,
            )

        await db.close_ticket_record(interaction.channel.id, 1)
        if ticket.get("order_id"):
            await db.update_order_status(str(ticket["order_id"]), "Done")
            await self._refresh_queue_card_from_ticket(
                interaction.guild,
                ticket,
                stage=str(ticket.get("wip_stage") or ""),
                force_done_strikethrough=True,
            )

        ch = interaction.channel
        for i in range(15, 0, -1):
            try:
                await ch.send(f"Channel closing in **{i}** seconds...")
            except discord.HTTPException:
                break
            await asyncio.sleep(1)
        try:
            await ch.delete(reason="Ticket closed")
        except (discord.Forbidden, discord.NotFound):
            pass

    @app_commands.command(name="close", description="Close this ticket with transcript")
    async def close_cmd(self, interaction: discord.Interaction) -> None:
        await self._run_close(interaction)

    @app_commands.command(
        name="closeapprove",
        description="Client approval for staff to close this ticket",
    )
    async def closeapprove_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Ticket only", "Use this inside your ticket."),
                ephemeral=True,
            )
            return
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "No open ticket here."),
                ephemeral=True,
            )
            return
        if interaction.user.id != int(ticket["client_id"]):
            await interaction.response.send_message(
                embed=user_warn("Client only", "Only ticket owner can approve closure."),
                ephemeral=True,
            )
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.update_ticket_fields(
            interaction.channel.id,
            close_approved_by_client=1,
            close_approved_at=now_iso,
        )
        # Hard guarantee for legacy DBs where update helper may skip absent columns.
        await db.force_mark_ticket_close_approved(interaction.channel.id, now_iso)
        await interaction.response.send_message(
            embed=success_embed("Closure approved", "Staff may now close this ticket."),
            ephemeral=False,
        )


async def register_ticket_persistent_views(bot: commands.Bot) -> None:
    try:
        bot.add_view(CloseTicketView())
    except ValueError:
        pass
    try:
        bot.add_view(TicketOpsView())
    except ValueError:
        pass
    try:
        bot.add_view(QuoteApprovalView())
    except ValueError:
        pass
    panels = await db.all_ticket_panels()
    cog = bot.get_cog("TicketsCog")
    if not isinstance(cog, TicketsCog):
        return
    for panel in panels:
        gid = int(panel["guild_id"])
        mid = int(panel["message_id"])
        rows = await db.list_ticket_buttons(gid)
        if not rows:
            continue
        view = cog._build_panel_view(gid, rows)
        if view:
            try:
                # Register globally so old panel messages still get handled.
                bot.add_view(view)
            except ValueError:
                pass
            try:
                bot.add_view(view, message_id=mid)
            except ValueError:
                pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketsCog(bot))
