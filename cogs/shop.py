"""TOS gate, shop open/close, status embed."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
from guild_config import get_role, get_text_channel
import guild_keys as gk
from utils.checks import is_staff
from utils.embeds import DANGER, SUCCESS, error_embed, info_embed, success_embed


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
        role = await get_role(interaction.guild, gk.TOS_AGREED_ROLE)
        if role is None:
            await interaction.response.send_message(
                embed=error_embed("Error", "TOS role not configured."), ephemeral=True
            )
            return
        if role in interaction.user.roles:
            await interaction.response.send_message("You've already agreed.", ephemeral=True)
            return
        try:
            await interaction.user.add_roles(role, reason="TOS agreement")
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Error", "I cannot assign the role."), ephemeral=True
            )
            return
        await db.log_tos_agreement(interaction.user.id)
        await interaction.response.send_message(
            "✅ You've agreed! You can now open a commission ticket.", ephemeral=True
        )


class ShopCog(commands.Cog, name="ShopCog"):
    shop = app_commands.Group(name="shop", description="Shop status (staff)")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._status_message: discord.Message | None = None

    async def refresh_status_message(self) -> None:
        row = await db.get_persist_panel("shop_status")
        if not row:
            return
        ch = self.bot.get_channel(int(row["channel_id"]))
        if not isinstance(ch, discord.TextChannel):
            return
        try:
            self._status_message = await ch.fetch_message(int(row["message_id"]))
        except (discord.NotFound, discord.Forbidden):
            self._status_message = None

    async def run_setup_tos(self, interaction: discord.Interaction) -> None:
        """Called from `/setup tos`."""
        ch = await get_text_channel(interaction.guild, gk.TOS_CHANNEL)
        if not ch:
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

    def _embed(self, st: dict) -> discord.Embed:
        open_ = bool(st.get("is_open", 0))
        when = st.get("last_toggled") or "—"
        by = st.get("toggled_by")
        who = f"<@{by}>" if by else "—"
        if open_:
            return discord.Embed(
                title="✅ Commissions OPEN",
                description=f"Last toggled: {when}\nBy: {who}",
                color=SUCCESS,
            )
        return discord.Embed(
            title="🔴 Commissions CLOSED",
            description=f"Last toggled: {when}\nBy: {who}",
            color=DANGER,
        )

    async def _apply_status_embed(self, interaction: discord.Interaction, emb: discord.Embed) -> None:
        ch = await get_text_channel(interaction.guild, gk.SHOP_STATUS_CHANNEL)
        if not ch:
            return
        if self._status_message:
            try:
                await self._status_message.edit(embed=emb)
                return
            except (discord.NotFound, discord.Forbidden):
                self._status_message = None
        row = await db.get_persist_panel("shop_status")
        if row and row.get("message_id"):
            try:
                self._status_message = await ch.fetch_message(int(row["message_id"]))
                await self._status_message.edit(embed=emb)
                return
            except (discord.NotFound, discord.Forbidden):
                pass
        msg = await ch.send(embed=emb)
        self._status_message = msg
        await db.set_persist_panel("shop_status", ch.id, msg.id)

    @shop.command(name="open", description="Open commissions (staff)")
    @is_staff()
    async def shop_open(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer(ephemeral=True)
        await db.set_shop_state(True, interaction.user.id)
        st = await db.get_shop_state()
        emb = self._embed(st)
        await self._apply_status_embed(interaction, emb)

        start = await get_text_channel(interaction.guild, gk.START_HERE_CHANNEL)
        tos_role = await get_role(interaction.guild, gk.TOS_AGREED_ROLE)
        open_role = await get_role(interaction.guild, gk.COMMISSIONS_OPEN_ROLE)
        if start:
            await start.set_permissions(interaction.guild.default_role, view_channel=False)
            if tos_role:
                await start.set_permissions(tos_role, view_channel=True)
            if open_role:
                await start.set_permissions(open_role, view_channel=True)

        await interaction.followup.send(
            embed=success_embed("Shop", "Commissions are now **open**."), ephemeral=True
        )

    @shop.command(name="close", description="Close commissions (staff)")
    @is_staff()
    async def shop_close(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer(ephemeral=True)
        await db.set_shop_state(False, interaction.user.id)
        st = await db.get_shop_state()
        emb = self._embed(st)
        await self._apply_status_embed(interaction, emb)

        start = await get_text_channel(interaction.guild, gk.START_HERE_CHANNEL)
        tos_role = await get_role(interaction.guild, gk.TOS_AGREED_ROLE)
        open_role = await get_role(interaction.guild, gk.COMMISSIONS_OPEN_ROLE)
        if start:
            if tos_role:
                await start.set_permissions(tos_role, view_channel=False)
            if open_role:
                await start.set_permissions(open_role, view_channel=False)

        await interaction.followup.send(
            embed=success_embed("Shop", "Commissions are now **closed**."), ephemeral=True
        )

    @app_commands.command(name="shopstatus", description="Show whether commissions are open")
    async def shopstatus(self, interaction: discord.Interaction) -> None:
        st = await db.get_shop_state()
        open_ = bool(st.get("is_open", 0))
        await interaction.response.send_message(
            embed=info_embed(
                "Shop status",
                "✅ **Open**" if open_ else "🔴 **Closed**",
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ShopCog(bot))
