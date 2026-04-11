"""Vouch tracking and PlsVouch auto-remove."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import guild_keys as gk
from utils.checks import is_staff
from utils.embeds import PRIMARY, error_embed, info_embed, success_embed


class VouchPages(discord.ui.View):
    def __init__(self, user_id: int, pages: list[discord.Embed]) -> None:
        super().__init__(timeout=180.0)
        self.user_id = user_id
        self.pages = pages
        self.idx = 0

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your pager.", ephemeral=True)
            return
        self.idx = max(0, self.idx - 1)
        await interaction.response.edit_message(embed=self.pages[self.idx], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your pager.", ephemeral=True)
            return
        self.idx = min(len(self.pages) - 1, self.idx + 1)
        await interaction.response.edit_message(embed=self.pages[self.idx], view=self)


class VouchCog(commands.Cog, name="VouchCog"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        vcid = await db.get_guild_setting(message.guild.id, gk.VOUCHES_CHANNEL)
        if not vcid or message.channel.id != int(vcid):
            return
        pvr = await db.get_guild_setting(message.guild.id, gk.PLEASE_VOUCH_ROLE)
        role = message.guild.get_role(int(pvr)) if pvr else None
        if not role or not isinstance(message.author, discord.Member):
            return
        if role not in message.author.roles:
            return
        try:
            await message.author.remove_roles(role, reason="Vouched")
        except discord.Forbidden:
            return
        await db.insert_vouch(message.author.id, None, message.content[:2000])
        await message.reply(
            f"✅ Thanks for vouching, {message.author.mention}! Your PlsVouch role has been removed."
        )

    @app_commands.command(name="vouch", description="Manually log a vouch (staff)")
    @app_commands.describe(member="Client", order_id="Related order ID", message="Vouch text")
    @is_staff()
    async def vouch_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        order_id: str,
        message: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        await db.insert_vouch(member.id, order_id, message)
        pvr = await db.get_guild_setting(interaction.guild.id, gk.PLEASE_VOUCH_ROLE)
        role = interaction.guild.get_role(int(pvr)) if pvr else None
        if role and role in member.roles:
            try:
                await member.remove_roles(role)
            except discord.Forbidden:
                pass
        elif role:
            try:
                await member.add_roles(role)
                await member.remove_roles(role)
            except discord.Forbidden:
                pass
        vcid = await db.get_guild_setting(interaction.guild.id, gk.VOUCHES_CHANNEL)
        ch = interaction.guild.get_channel(int(vcid)) if vcid else None
        emb = discord.Embed(
            title="⭐ Vouch",
            description=f"**{member.display_name}**\n{message}\nOrder: `{order_id}`",
            color=PRIMARY,
        )
        if isinstance(ch, (discord.TextChannel, discord.NewsChannel)):
            await ch.send(embed=emb)
        await interaction.followup.send(
            embed=success_embed("Logged", "Vouch posted."), ephemeral=True
        )

    @app_commands.command(name="vouches", description="List vouches for a member")
    @app_commands.describe(member="Member")
    async def vouches_list(self, interaction: discord.Interaction, member: discord.Member) -> None:
        rows = await db.list_vouches_for_user(member.id)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("Vouches", "No vouches found."), ephemeral=True
            )
            return
        pages: list[discord.Embed] = []
        chunk = 5
        for i in range(0, len(rows), chunk):
            part = rows[i : i + chunk]
            lines = []
            for r in part:
                lines.append(
                    f"**#{r['vouch_id']}** — {r['created_at']}\n{r['message'][:500]}"
                )
            pages.append(
                discord.Embed(
                    title=f"Vouches for {member.display_name}",
                    description="\n\n".join(lines),
                    color=PRIMARY,
                )
            )
        v = VouchPages(interaction.user.id, pages)
        await interaction.response.send_message(embed=pages[0], view=v, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VouchCog(bot))
