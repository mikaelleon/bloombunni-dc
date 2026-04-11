"""Vouch tracking and PlsVouch auto-remove."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
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
        if message.channel.id != config.VOUCHES_CHANNEL_ID:
            return
        role = message.guild.get_role(config.PLEASE_VOUCH_ROLE_ID)
        if not role or not isinstance(message.author, discord.Member):
            return
        if role not in message.author.roles:
            return
        try:
            await message.author.remove_roles(role, reason="Vouched")
        except discord.Forbidden:
            return
        await db.insert_vouch(message.author.id, None, 0, message.content[:2000])
        await message.reply(
            f"✅ Thanks for vouching, {message.author.mention}! Your PlsVouch role has been removed."
        )

    @app_commands.command(name="vouch", description="Manually log a vouch (staff)")
    @app_commands.describe(
        member="Client",
        order_id="Related order ID",
        rating="1-5 stars",
        message="Vouch text",
    )
    @is_staff()
    async def vouch_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        order_id: str,
        rating: app_commands.Range[int, 1, 5],
        message: str,
    ) -> None:
        await db.insert_vouch(member.id, order_id, int(rating), message)
        role = interaction.guild.get_role(config.PLEASE_VOUCH_ROLE_ID)
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
        await interaction.response.defer(ephemeral=True)
        ch = interaction.guild.get_channel(config.VOUCHES_CHANNEL_ID)
        emb = discord.Embed(
            title="⭐ Vouch",
            description=f"**{member.display_name}** — {rating}/5\n{message}\nOrder: `{order_id}`",
            color=PRIMARY,
        )
        if isinstance(ch, discord.TextChannel):
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
                    f"**#{r['vouch_id']}** — {r['rating']}/5 — {r['created_at']}\n{r['message'][:500]}"
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
