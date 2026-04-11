"""Warning system."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import guild_keys as gk
from guild_config import get_text_channel
from utils.checks import is_staff
from utils.embeds import DEFAULT_EMBED_COLOR, PRIMARY, error_embed, info_embed, success_embed, warning_embed

WARN_THRESHOLD = 3


def _norm_reason(reason: str | None) -> str:
    r = (reason or "").strip()
    return r if r else "no reason specified"


def _warn_notice_embed(*, shop_name: str, reason: str, total: int) -> discord.Embed:
    """DM notice styled like the reference (⚠️ WARNED NOTICE !)."""
    return discord.Embed(
        title="⚠️ WARNED NOTICE !",
        description=(
            f"hello ! you have been **warned** from **{shop_name}** for **{reason}**. "
            f"**take note** that once you received a total of **{WARN_THRESHOLD} warnings** from them you will be "
            f"**automatically banned** from their **server**. so, please **follow** their **rules. thank you !** "
            f"your **warning count : {total}** ⚠️"
        ),
        color=DEFAULT_EMBED_COLOR,
    )


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
    @app_commands.describe(user="User to warn", reason="Reason (optional)")
    @is_staff()
    async def warn_cmd(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str | None = None,
    ) -> None:
        if not interaction.guild or interaction.channel is None:
            await interaction.response.send_message(
                embed=error_embed("Error", "Use this command in a server."), ephemeral=True
            )
            return

        reason_s = _norm_reason(reason)
        await interaction.response.defer(ephemeral=True)

        wid = await db.add_warn(user.id, interaction.user.id, reason_s)
        total = await db.count_warns(user.id)
        shop_name = interaction.guild.name

        dm_emb = _warn_notice_embed(shop_name=shop_name, reason=reason_s, total=total)
        try:
            await user.send(embed=dm_emb)
        except discord.Forbidden:
            pass

        # Public channel confirmation (plain text, like reference)
        public = f"⚠️ {user.mention} now has {total} warning(s).\n\n**reason**: {reason_s}"
        public_ok = True
        try:
            await interaction.channel.send(
                content=public,
                allowed_mentions=discord.AllowedMentions(users=[user]),
            )
        except discord.Forbidden:
            public_ok = False

        log_ch = await get_text_channel(interaction.guild, gk.WARN_LOG_CHANNEL)
        if log_ch:
            await log_ch.send(
                embed=info_embed(
                    "Warn issued",
                    f"{user.mention} — `{reason_s}` (ID `{wid}`) by {interaction.user.mention}",
                )
            )

        staff_note = f"Warn ID `{wid}`. Total: {total}."
        if not public_ok:
            staff_note = (
                "Could not post the public confirmation here (missing **Send Messages**). "
                f"Warn was still logged.\n{staff_note}"
            )
        await interaction.followup.send(
            embed=success_embed("Warn logged", staff_note),
            ephemeral=True,
        )
        if total >= WARN_THRESHOLD:
            try:
                await user.ban(reason="3 warns reached", delete_message_days=0)
            except discord.Forbidden:
                await interaction.followup.send(
                    embed=error_embed("Ban failed", "Could not ban user."), ephemeral=True
                )
                return
            if log_ch:
                await log_ch.send(embed=warning_embed("Auto-ban", f"{user} banned — warn threshold."))

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
