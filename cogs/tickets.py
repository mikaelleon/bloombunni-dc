"""Ticket intake, TOS panel, order confirmation, and close."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
import io
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
from utils.checks import is_staff
from utils.embeds import (
    DANGER,
    PRIMARY,
    error_embed,
    info_embed,
    success_embed,
    warning_embed,
)

# --- Pricing (editable) ---
BASE_PRICES: dict[tuple[str, str], int] = {
    ("Chibi", "Sketch"): 80,
    ("Chibi", "Flat Color"): 150,
    ("Chibi", "Shaded"): 220,
    ("Chibi", "Fully Rendered"): 300,
    ("Normal", "Sketch"): 120,
    ("Normal", "Flat Color"): 200,
    ("Normal", "Shaded"): 300,
    ("Normal", "Fully Rendered"): 450,
    ("Chibi Scene", "Sketch"): 100,
    ("Chibi Scene", "Flat Color"): 180,
    ("Chibi Scene", "Shaded"): 260,
    ("Chibi Scene", "Fully Rendered"): 350,
}

EXTRA_CHARACTER_FEE = 80
BACKGROUND_FEES = {"None": 0, "Simple": 50, "Detailed": 120}
BOOSTIE_DISCOUNT = 0.10
RESELLER_DISCOUNT = 0.15


def _normalize_commission_type(label: str) -> str:
    if "Normal" in label and "Semi" in label:
        return "Normal"
    if "Chibi Scene" in label:
        return "Chibi Scene"
    return "Chibi"


def _char_count(label: str) -> int:
    if label == "4+":
        return 4
    return int(label)


def compute_price(
    commission_label: str,
    tier: str,
    chars_label: str,
    background: str,
    boostie: bool,
    reseller: bool,
) -> tuple[float, float, int, int]:
    ctype = _normalize_commission_type(commission_label)
    key = (ctype, tier)
    base = float(BASE_PRICES.get(key, 0))
    n = _char_count(chars_label)
    extra = max(0, n - 1) * EXTRA_CHARACTER_FEE
    bg = float(BACKGROUND_FEES.get(background, 0))
    subtotal = base + extra + bg
    b_flag = 1 if boostie else 0
    r_flag = 1 if reseller else 0
    discount = 0.0
    if boostie:
        discount = BOOSTIE_DISCOUNT
    elif reseller:
        discount = RESELLER_DISCOUNT
    final = subtotal * (1.0 - discount)
    return subtotal, final, b_flag, r_flag


async def _next_order_id() -> str:
    now = datetime.now(timezone.utc)
    mm = now.month
    yy = now.year % 100
    count = await db.count_orders_in_month(now.year, now.month) + 1
    return f"MIKA-{mm:02d}{yy:02d}-{count:04d}"


class TicketOpenView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="Open a Ticket", style=discord.ButtonStyle.primary, custom_id="ticket_open")
    async def open_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        cog = interaction.client.get_cog("TicketsCog")
        if not isinstance(cog, TicketsCog):
            await interaction.response.send_message(
                embed=error_embed("Error", "Tickets unavailable."), ephemeral=True
            )
            return
        await cog.handle_open_ticket(interaction)


class CloseTicketView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        cog = interaction.client.get_cog("TicketsCog")
        if not isinstance(cog, TicketsCog):
            await interaction.response.send_message(
                embed=error_embed("Error", "Tickets unavailable."), ephemeral=True
            )
            return
        await cog.handle_close_button(interaction)


class ConfirmOrderView(discord.ui.View):
    def __init__(self, order_id: str) -> None:
        super().__init__(timeout=3600.0)
        self.order_id = order_id

    @discord.ui.button(label="Confirm Order", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        cog = interaction.client.get_cog("TicketsCog")
        if not isinstance(cog, TicketsCog):
            return
        await cog.handle_confirm_order(interaction, self.order_id)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        cog = interaction.client.get_cog("TicketsCog")
        if not isinstance(cog, TicketsCog):
            return
        await cog.handle_cancel_order(interaction, self.order_id)


class IntakeModal(discord.ui.Modal, title="References & Notes"):
    refs = discord.ui.TextInput(
        label="Reference links (required)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000,
    )
    notes = discord.ui.TextInput(
        label="Additional notes (optional)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=2000,
    )

    def __init__(self, session: dict[str, Any]) -> None:
        super().__init__()
        self.session = session

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cog = interaction.client.get_cog("TicketsCog")
        if not isinstance(cog, TicketsCog):
            return
        self.session["refs"] = str(self.refs.value)
        self.session["notes"] = str(self.notes.value) if self.notes.value else ""
        await cog.finish_intake(interaction, self.session)


class IntakeStepView(discord.ui.View):
    def __init__(self, session: dict[str, Any]) -> None:
        super().__init__(timeout=600.0)
        self.session = session
        sel = discord.ui.Select(
            custom_id="intake_commission",
            placeholder="Step 1: Commission type",
            options=[
                discord.SelectOption(label="Chibi", value="Chibi"),
                discord.SelectOption(label="Normal / Semi-Realistic", value="Normal / Semi-Realistic"),
                discord.SelectOption(label="Chibi Scene", value="Chibi Scene"),
            ],
        )
        sel.callback = self._step1
        self.add_item(sel)

    async def _step1(self, interaction: discord.Interaction) -> None:
        self.session["commission_type"] = interaction.data["values"][0]
        self.clear_items()
        sel = discord.ui.Select(
            custom_id="intake_tier",
            placeholder="Step 2: Rendering tier",
            options=[
                discord.SelectOption(label="Sketch", value="Sketch"),
                discord.SelectOption(label="Flat Color", value="Flat Color"),
                discord.SelectOption(label="Shaded", value="Shaded"),
                discord.SelectOption(label="Fully Rendered", value="Fully Rendered"),
            ],
        )
        sel.callback = self._step2
        self.add_item(sel)
        await interaction.response.edit_message(embed=self._embed_step(2), view=self)

    async def _step2(self, interaction: discord.Interaction) -> None:
        self.session["tier"] = interaction.data["values"][0]
        self.clear_items()
        sel = discord.ui.Select(
            custom_id="intake_chars",
            placeholder="Step 3: Number of characters",
            options=[
                discord.SelectOption(label="1", value="1"),
                discord.SelectOption(label="2", value="2"),
                discord.SelectOption(label="3", value="3"),
                discord.SelectOption(label="4+", value="4+"),
            ],
        )
        sel.callback = self._step3
        self.add_item(sel)
        await interaction.response.edit_message(embed=self._embed_step(3), view=self)

    async def _step3(self, interaction: discord.Interaction) -> None:
        self.session["characters"] = interaction.data["values"][0]
        self.clear_items()
        sel = discord.ui.Select(
            custom_id="intake_bg",
            placeholder="Step 4: Background",
            options=[
                discord.SelectOption(label="None", value="None"),
                discord.SelectOption(label="Simple", value="Simple"),
                discord.SelectOption(label="Detailed", value="Detailed"),
            ],
        )
        sel.callback = self._step4
        self.add_item(sel)
        await interaction.response.edit_message(embed=self._embed_step(4), view=self)

    async def _step4(self, interaction: discord.Interaction) -> None:
        self.session["background"] = interaction.data["values"][0]
        await interaction.response.send_modal(IntakeModal(self.session))

    def _embed_step(self, step: int) -> discord.Embed:
        return info_embed(
            "Commission intake",
            f"Step {step} of 5 — follow the selects, then fill the form.\n"
            f"**Type:** {self.session.get('commission_type', '—')}\n"
            f"**Tier:** {self.session.get('tier', '—')}\n"
            f"**Characters:** {self.session.get('characters', '—')}\n"
            f"**Background:** {self.session.get('background', '—')}",
        )


class TOSAgreeView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="I Have Read & Agree to the TOS",
        style=discord.ButtonStyle.success,
        custom_id="tos_agree",
    )
    async def agree(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=error_embed("Error", "Use this in the server."), ephemeral=True
            )
            return
        role = interaction.guild.get_role(config.TOS_AGREED_ROLE_ID)
        if role is None:
            await interaction.response.send_message(
                embed=error_embed("Error", "TOS role not configured."), ephemeral=True
            )
            return
        if role in interaction.user.roles:
            await interaction.response.send_message(
                "You've already agreed.", ephemeral=True
            )
            return
        try:
            await interaction.user.add_roles(role, reason="TOS agreement")
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Error", "I cannot assign the role. Check bot permissions."),
                ephemeral=True,
            )
            return
        await db.log_tos_agreement(interaction.user.id)
        await interaction.response.send_message(
            "✅ You've agreed! You can now open a commission ticket.", ephemeral=True
        )


class TicketsCog(commands.Cog, name="TicketsCog"):
    setup_group = app_commands.Group(name="setup", description="Staff setup commands")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @setup_group.command(name="tickets", description="Post the ticket panel in Start Here")
    @is_staff()
    async def setup_tickets(self, interaction: discord.Interaction) -> None:
        ch = interaction.guild.get_channel(config.START_HERE_CHANNEL_ID)
        if not isinstance(ch, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("Config", "Start Here channel invalid."), ephemeral=True
            )
            return
        emb = discord.Embed(
            title="Open a commission ticket",
            description=(
                "Click **Open a Ticket** to create a private channel and complete the intake.\n"
                f"You need the TOS role to use this channel — agree in <#{config.TOS_CHANNEL_ID}> first.\n"
                "Staff will review after you confirm your order."
            ),
            color=PRIMARY,
        )
        await interaction.response.send_message(
            embed=success_embed("Posted", "Ticket panel deployed."), ephemeral=True
        )
        msg = await ch.send(embed=emb, view=TicketOpenView())
        await db.set_persist_panel("tickets", ch.id, msg.id)

    @setup_group.command(name="tos", description="Post the TOS agreement panel")
    @is_staff()
    async def setup_tos(self, interaction: discord.Interaction) -> None:
        ch = interaction.guild.get_channel(config.TOS_CHANNEL_ID)
        if not isinstance(ch, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("Config", "TOS channel invalid."), ephemeral=True
            )
            return
        text = (
            config.TOS_FILE.read_text(encoding="utf-8")
            if config.TOS_FILE.exists()
            else "TOS text missing."
        )
        emb = discord.Embed(title="Terms of Service", description=text[:4000], color=DANGER)
        await interaction.response.send_message(
            embed=success_embed("Posted", "TOS panel deployed."), ephemeral=True
        )
        msg = await ch.send(embed=emb, view=TOSAgreeView())
        await db.set_persist_panel("tos", ch.id, msg.id)

    @setup_group.command(name="queue", description="Post the queue board in the queue channel")
    @is_staff()
    async def setup_queue(self, interaction: discord.Interaction) -> None:
        q = self.bot.get_cog("QueueCog")
        if not q or not hasattr(q, "run_setup_queue"):
            await interaction.response.send_message(
                embed=error_embed("Error", "Queue module unavailable."), ephemeral=True
            )
            return
        await q.run_setup_queue(interaction)

    @setup_group.command(name="payment", description="Post the payment methods panel")
    @is_staff()
    async def setup_payment(self, interaction: discord.Interaction) -> None:
        p = self.bot.get_cog("PaymentCog")
        if not p or not hasattr(p, "run_setup_payment"):
            await interaction.response.send_message(
                embed=error_embed("Error", "Payment module unavailable."), ephemeral=True
            )
            return
        await p.run_setup_payment(interaction)

    async def handle_open_ticket(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=error_embed("Error", "Use this in the server."), ephemeral=True
            )
            return
        tos_role = interaction.guild.get_role(config.TOS_AGREED_ROLE_ID)
        if tos_role is None or tos_role not in interaction.user.roles:
            await interaction.response.send_message(
                embed=warning_embed(
                    "Terms required",
                    f"Please read and agree in <#{config.TOS_CHANNEL_ID}> first.",
                ),
                ephemeral=True,
            )
            return
        if not await db.shop_is_open_db():
            await interaction.response.send_message(
                embed=error_embed("Shop closed", "Commissions are closed right now."),
                ephemeral=True,
            )
            return
        existing = await db.get_open_ticket_by_user(interaction.user.id)
        if existing:
            ch_id = int(existing["channel_id"])
            await interaction.response.send_message(
                f"You already have an open ticket at <#{ch_id}>.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        category = interaction.guild.get_channel(config.TICKET_CATEGORY_ID)
        if not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send(
                embed=error_embed("Config", "Ticket category missing."), ephemeral=True
            )
            return

        staff_role = interaction.guild.get_role(config.STAFF_ROLE_ID)
        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_messages=True
            )

        safe_name = re.sub(r"[^a-z0-9\-_]", "", interaction.user.name.lower())[:90] or "user"
        channel_name = f"ticket-{safe_name}"
        try:
            ticket_ch = await interaction.guild.create_text_channel(
                channel_name,
                category=category,
                overwrites=overwrites,
                reason=f"Ticket for {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=error_embed("Error", "Missing permission to create channels."),
                ephemeral=True,
            )
            return

        await db.insert_ticket(None, ticket_ch.id, None, interaction.user.id)

        emb = info_embed(
            "Welcome to your ticket",
            "Use the menu below to complete your commission intake (5 steps).\n"
            "Staff will assist you after you confirm your order.",
        )
        v = IntakeStepView(
            {
                "client_id": interaction.user.id,
                "client_name": interaction.user.display_name,
                "channel_id": ticket_ch.id,
            }
        )
        close_v = CloseTicketView()
        await ticket_ch.send(embed=emb, view=v)
        await ticket_ch.send(embed=info_embed("Manage", "Close this ticket when finished."), view=close_v)
        await interaction.followup.send(
            embed=success_embed("Ticket opened", f"Go to {ticket_ch.mention}"),
            ephemeral=True,
        )

    async def finish_intake(self, interaction: discord.Interaction, session: dict[str, Any]) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=error_embed("Error", "Invalid context."), ephemeral=True
            )
            return
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("Error", "Wrong channel."), ephemeral=True
            )
            return

        boostie = interaction.guild.get_role(config.BOOSTIE_ROLE_ID)
        reseller = interaction.guild.get_role(config.RESELLER_ROLE_ID)
        b = boostie is not None and boostie in interaction.user.roles
        r = reseller is not None and reseller in interaction.user.roles and not b

        base_p, final_p, bf, rf = compute_price(
            session["commission_type"],
            session["tier"],
            session["characters"],
            session["background"],
            b,
            r,
        )
        if base_p <= 0:
            await interaction.response.send_message(
                embed=error_embed("Pricing", "Could not calculate price. Contact staff."),
                ephemeral=True,
            )
            return

        order_id = await _next_order_id()
        notes_combined = f"Refs: {session['refs']}\nNotes: {session.get('notes', '')}"
        char_int = _char_count(session["characters"])

        await db.insert_order(
            order_id,
            session["client_id"],
            session["client_name"],
            session["commission_type"],
            session["tier"],
            char_int,
            session["background"],
            notes_combined,
            "Queued",
            bf,
            rf,
            base_p,
            final_p,
        )
        await db.update_ticket_order_id(channel.id, order_id)

        summary = (
            f"**Order ID:** `{order_id}`\n"
            f"**Type:** {session['commission_type']}\n"
            f"**Tier:** {session['tier']}\n"
            f"**Characters:** {session['characters']}\n"
            f"**Background:** {session['background']}\n"
            f"**Base price:** ${base_p:.2f}\n"
        )
        if final_p < base_p:
            summary += f"**Discount applied** → **Final:** ${final_p:.2f}\n"
        else:
            summary += f"**Final price:** ${final_p:.2f}\n"
        summary += "\nConfirm to proceed to payment."

        emb = discord.Embed(title="Order summary", description=summary, color=PRIMARY)
        await interaction.response.send_message(embed=emb, view=ConfirmOrderView(order_id))

    async def handle_confirm_order(self, interaction: discord.Interaction, order_id: str) -> None:
        order = await db.get_order(order_id)
        if not order:
            await interaction.response.send_message(
                embed=error_embed("Error", "Order not found."), ephemeral=True
            )
            return
        if interaction.user.id != int(order["client_id"]):
            await interaction.response.send_message(
                embed=error_embed("Error", "Only the client can confirm."), ephemeral=True
            )
            return

        await db.update_order_status(order_id, "Awaiting Payment")
        await interaction.response.send_message(
            embed=success_embed("Confirmed", "Staff have been notified. Complete payment as instructed."),
            ephemeral=True,
        )

        notif_ch = interaction.guild.get_channel(config.ORDER_NOTIFS_CHANNEL_ID) if interaction.guild else None
        staff_role = interaction.guild.get_role(config.STAFF_ROLE_ID) if interaction.guild else None
        if isinstance(notif_ch, discord.TextChannel):
            ping = staff_role.mention if staff_role else "@staff"
            e = info_embed(
                f"Order {order_id} awaiting payment",
                f"{ping}\nClient <@{order['client_id']}>\n```{order_id}```",
            )
            try:
                await notif_ch.send(content=ping if staff_role else None, embed=e)
            except discord.Forbidden:
                pass

        q = self.bot.get_cog("QueueCog")
        if q and hasattr(q, "refresh_queue_board"):
            await q.refresh_queue_board()

    async def handle_cancel_order(self, interaction: discord.Interaction, order_id: str) -> None:
        order = await db.get_order(order_id)
        if not order:
            await interaction.response.send_message(
                embed=error_embed("Error", "Order not found."), ephemeral=True
            )
            return
        if interaction.user.id != int(order["client_id"]):
            await interaction.response.send_message(
                embed=error_embed("Error", "Only the client can cancel."), ephemeral=True
            )
            return

        await interaction.response.send_message(
            embed=warning_embed("Cancelled", "This ticket will close in 10 seconds."),
            ephemeral=True,
        )
        await db.delete_order(order_id)
        ch = interaction.channel
        if isinstance(ch, discord.TextChannel):
            await db.delete_ticket_by_channel(ch.id)
            for i in range(10, 0, -1):
                try:
                    await ch.send(f"Closing in **{i}**...")
                except discord.HTTPException:
                    break
                await asyncio.sleep(1)
            try:
                await ch.delete(reason="Order cancelled")
            except discord.Forbidden:
                pass
            except discord.NotFound:
                pass

        q = self.bot.get_cog("QueueCog")
        if q and hasattr(q, "refresh_queue_board"):
            await q.refresh_queue_board()

    async def handle_close_button(self, interaction: discord.Interaction) -> None:
        await self._run_close(interaction)

    async def _run_close(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("Error", "Use this inside a ticket channel."), ephemeral=True
            )
            return
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message(
                embed=error_embed("Error", "Not a ticket channel."), ephemeral=True
            )
            return
        is_staff = False
        staff_role = interaction.guild.get_role(config.STAFF_ROLE_ID)
        if staff_role and isinstance(interaction.user, discord.Member):
            is_staff = staff_role in interaction.user.roles
        is_owner = interaction.user.id == int(ticket["client_id"])
        if not is_staff and not is_owner:
            await interaction.response.send_message(
                embed=error_embed("Error", "Only staff or the ticket owner can close."), ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        from utils.transcript import generate_transcript

        try:
            file = await generate_transcript(interaction.channel)
        except Exception:
            await interaction.followup.send(
                embed=error_embed("Error", "Could not build transcript."), ephemeral=True
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

        trans_ch = interaction.guild.get_channel(config.TRANSCRIPT_CHANNEL_ID)
        if isinstance(trans_ch, discord.TextChannel):
            try:
                await trans_ch.send(
                    embed=info_embed("Transcript", f"Ticket {interaction.channel.name}"),
                    file=trans_file,
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        if not dm_ok:
            await interaction.followup.send(
                embed=warning_embed(
                    "DM failed",
                    "Could not DM the client the transcript. Send it manually.",
                ),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                embed=success_embed("Closing", "Transcript sent. Channel deletes in 15 seconds."),
                ephemeral=True,
            )

        await db.close_ticket_record(interaction.channel.id, 1)

        ch = interaction.channel
        for i in range(15, 0, -1):
            try:
                await ch.send(f"Closing in **{i}** seconds...")
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketsCog(bot))
