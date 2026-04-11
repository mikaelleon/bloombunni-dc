"""Sticky messages per channel."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils.checks import is_staff
from utils.embeds import error_embed, info_embed, success_embed


class StickyCog(commands.Cog, name="StickyCog"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._debounce: dict[int, asyncio.Task[None]] = {}

    def _schedule_repost(self, channel_id: int, coro: Coroutine[None, None, None]) -> None:
        old = self._debounce.pop(channel_id, None)
        if old:
            old.cancel()

        async def _run() -> None:
            await asyncio.sleep(1.5)
            self._debounce.pop(channel_id, None)
            await coro

        self._debounce[channel_id] = asyncio.create_task(_run())

    async def _repost_sticky(self, channel: discord.TextChannel) -> None:
        row = await db.get_sticky(channel.id)
        if not row:
            return
        mid = row.get("last_message_id")
        if mid:
            try:
                m = await channel.fetch_message(int(mid))
                await m.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
        content = row["message_content"] or ""
        msg = await channel.send(content)
        await db.update_sticky_message_id(channel.id, msg.id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        row = await db.get_sticky(message.channel.id)
        if not row:
            return
        if message.id == row.get("last_message_id"):
            return

        ch = message.channel
        if not isinstance(ch, discord.TextChannel):
            return

        self._schedule_repost(ch.id, self._repost_sticky(ch))

    @app_commands.command(name="sticky", description="Set a sticky message in a channel (staff)")
    @app_commands.describe(channel="Channel", message="Sticky text")
    @is_staff()
    async def sticky_cmd(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str,
    ) -> None:
        await db.upsert_sticky(channel.id, message, None, None)
        msg = await channel.send(message)
        await db.update_sticky_message_id(channel.id, msg.id)
        await interaction.response.send_message(
            embed=success_embed("Sticky set", f"{channel.mention}"), ephemeral=True
        )

    @app_commands.command(name="unsticky", description="Remove sticky from a channel (staff)")
    @app_commands.describe(channel="Channel")
    @is_staff()
    async def unsticky_cmd(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        row = await db.get_sticky(channel.id)
        if row and row.get("last_message_id"):
            try:
                m = await channel.fetch_message(int(row["last_message_id"]))
                await m.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
        await db.delete_sticky(channel.id)
        await interaction.response.send_message(
            embed=success_embed("Removed", f"{channel.mention}"), ephemeral=True
        )

    @app_commands.command(name="stickies", description="List active sticky channels (staff)")
    @is_staff()
    async def stickies_list(self, interaction: discord.Interaction) -> None:
        rows = await db.list_all_stickies()
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("Stickies", "None."), ephemeral=True
            )
            return
        lines = [f"<#{r['channel_id']}>" for r in rows]
        await interaction.response.send_message(
            embed=info_embed("Active stickies", "\n".join(lines)), ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StickyCog(bot))
