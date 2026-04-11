"""Ticket channels, transcript, setup panel."""

from __future__ import annotations

import asyncio
import io
import re

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
from utils.checks import is_staff
from utils.embeds import PRIMARY, error_embed, info_embed, success_embed


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
            title="Commissions",
            description=(
                "Click **Open a Ticket** to get a private channel with staff.\n"
                f"You need the TOS role — agree in <#{config.TOS_CHANNEL_ID}> first.\n"
                "After staff gather your details, they will register your order with `/queue`."
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
        shop = self.bot.get_cog("ShopCog")
        if not shop or not hasattr(shop, "run_setup_tos"):
            await interaction.response.send_message(
                embed=error_embed("Error", "Shop cog unavailable."), ephemeral=True
            )
            return
        await shop.run_setup_tos(interaction)

    @setup_group.command(name="payment", description="Post the payment methods panel")
    @is_staff()
    async def setup_payment(self, interaction: discord.Interaction) -> None:
        pay = self.bot.get_cog("PaymentCog")
        if not pay or not hasattr(pay, "run_setup_payment"):
            await interaction.response.send_message(
                embed=error_embed("Error", "Payment cog unavailable."), ephemeral=True
            )
            return
        await pay.run_setup_payment(interaction)

    async def handle_open_ticket(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=error_embed("Error", "Use this in the server."), ephemeral=True
            )
            return
        tos_role = interaction.guild.get_role(config.TOS_AGREED_ROLE_ID)
        if tos_role is None or tos_role not in interaction.user.roles:
            await interaction.response.send_message(
                embed=error_embed(
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
            await interaction.response.send_message(
                f"You already have an open ticket at <#{existing['channel_id']}>.",
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
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True, manage_channels=True
            ),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True
            ),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_messages=True,
                manage_channels=True,
            )

        safe_name = re.sub(r"[^a-z0-9\-_]", "", interaction.user.name.lower())[:90] or "user"
        try:
            ticket_ch = await interaction.guild.create_text_channel(
                f"ticket-{safe_name}",
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

        await db.insert_ticket_open(ticket_ch.id, interaction.user.id)

        welcome = discord.Embed(
            title="Ticket opened",
            description=(
                "Describe your commission request here. A staff member will assist you "
                "and register the order with `/queue` when details are ready."
            ),
            color=PRIMARY,
        )
        await ticket_ch.send(embed=welcome, view=CloseTicketView())
        await interaction.followup.send(
            embed=success_embed("Ticket opened", f"Go to {ticket_ch.mention}"),
            ephemeral=True,
        )

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
        staff_role = interaction.guild.get_role(config.STAFF_ROLE_ID)
        is_staff_u = (
            staff_role
            and isinstance(interaction.user, discord.Member)
            and staff_role in interaction.user.roles
        )
        is_owner = interaction.user.id == int(ticket["client_id"])
        if not is_staff_u and not is_owner:
            await interaction.response.send_message(
                embed=error_embed("Error", "Only staff or the ticket owner can close."),
                ephemeral=True,
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

        if not dm_ok and isinstance(trans_ch, discord.TextChannel):
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
                embed=error_embed(
                    "DM failed",
                    "Transcript was posted to the transcript channel only.",
                ),
                ephemeral=True,
            )

        await db.close_ticket_record(interaction.channel.id, 1)

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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketsCog(bot))
