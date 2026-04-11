"""Warning system."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
from utils.checks import is_staff
from utils.embeds import PRIMARY, error_embed, info_embed, success_embed, warning_embed

WARN_THRESHOLD = 3


class WarnPages(discord.ui.View):
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


class WarnCog(commands.Cog, name="WarnCog"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="warn", description="Warn a member (staff)")
    @app_commands.describe(member="Member to warn", reason="Reason")
    @is_staff()
    async def warn_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        wid = await db.add_warn(member.id, interaction.user.id, reason)
        total = await db.count_warns(member.id)
        emb = warning_embed(
            "Warning",
            f"**Reason:** {reason}\n**Your warns:** {total}/{WARN_THRESHOLD}\n"
            "Reaching 3 warns may result in a ban.",
        )
        try:
            await member.send(embed=emb)
        except discord.Forbidden:
            pass
        log_ch = interaction.guild.get_channel(config.WARN_LOG_CHANNEL_ID)
        if isinstance(log_ch, discord.TextChannel):
            await log_ch.send(
                embed=info_embed(
                    "Warn issued",
                    f"{member.mention} — `{reason}` (ID `{wid}`) by {interaction.user.mention}",
                )
            )
        await interaction.followup.send(
            embed=success_embed("Warn logged", f"Warn ID `{wid}`. Total: {total}."),
            ephemeral=True,
        )
        if total >= WARN_THRESHOLD:
            try:
                await member.ban(reason="3 warns reached", delete_message_days=0)
            except discord.Forbidden:
                await interaction.followup.send(
                    embed=error_embed("Ban failed", "Could not ban user."), ephemeral=True
                )
                return
            if isinstance(log_ch, discord.TextChannel):
                await log_ch.send(embed=warning_embed("Auto-ban", f"{member} banned — warn threshold."))

    @app_commands.command(name="warns", description="List warns for a member (staff)")
    @app_commands.describe(member="Member")
    @is_staff()
    async def warns_list(self, interaction: discord.Interaction, member: discord.Member) -> None:
        rows = await db.list_warns(member.id)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("Warns", "No warns."), ephemeral=True
            )
            return
        pages: list[discord.Embed] = []
        for r in rows:
            mod = self.bot.get_user(int(r["moderator_id"]))
            mod_s = mod.mention if mod else str(r["moderator_id"])
            pages.append(
                discord.Embed(
                    title=f"Warn #{r['warn_id']}",
                    description=f"**Reason:** {r['reason']}\n**Mod:** {mod_s}\n**When:** {r['created_at']}",
                    color=PRIMARY,
                )
            )
        if len(pages) == 1:
            await interaction.response.send_message(embed=pages[0], ephemeral=True)
            return
        v = WarnPages(interaction.user.id, pages)
        await interaction.response.send_message(embed=pages[0], view=v, ephemeral=True)

    @app_commands.command(name="clearwarn", description="Delete a warn by ID (staff)")
    @app_commands.describe(warn_id="Warn ID")
    @is_staff()
    async def clearwarn(self, interaction: discord.Interaction, warn_id: int) -> None:
        ok = await db.delete_warn(warn_id)
        if not ok:
            await interaction.response.send_message(
                embed=error_embed("Error", "Warn not found."), ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=success_embed("Cleared", f"Warn `{warn_id}` removed."), ephemeral=True
        )

    @app_commands.command(name="clearallwarns", description="Clear all warns for a member (staff)")
    @app_commands.describe(member="Member")
    @is_staff()
    async def clearallwarns(self, interaction: discord.Interaction, member: discord.Member) -> None:
        n = await db.clear_warns_user(member.id)
        await interaction.response.send_message(
            embed=success_embed("Cleared", f"Removed {n} warn(s)."), ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WarnCog(bot))
