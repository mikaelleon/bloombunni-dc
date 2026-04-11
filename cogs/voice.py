"""Bot stays in a voice channel (24/7 style)."""

from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.checks import is_staff
from utils.embeds import error_embed, success_embed


class VoiceCog(commands.Cog, name="VoiceCog"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._reconnect_task: asyncio.Task[None] | None = None

    async def join_vc(self) -> None:
        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild:
            return
        ch = guild.get_channel(config.VC_CHANNEL_ID)
        if not isinstance(ch, discord.VoiceChannel):
            return
        try:
            await guild.change_voice_state(channel=ch, self_deaf=True)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.id != self.bot.user.id:
            return
        if after.channel is not None:
            return
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()

        async def _later() -> None:
            await asyncio.sleep(30)
            await self.join_vc()

        self._reconnect_task = asyncio.create_task(_later())

    @app_commands.command(name="vcjoin", description="Join the configured VC (staff)")
    @is_staff()
    async def vcjoin(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await self.join_vc()
        await interaction.followup.send(
            embed=success_embed("VC", "Joined voice channel."), ephemeral=True
        )

    @app_commands.command(name="vcleave", description="Leave voice (staff)")
    @is_staff()
    async def vcleave(self, interaction: discord.Interaction) -> None:
        g = self.bot.get_guild(config.GUILD_ID)
        if g:
            try:
                await g.change_voice_state(channel=None)
            except discord.HTTPException:
                pass
        await interaction.response.send_message(
            embed=success_embed("VC", "Disconnected."), ephemeral=True
        )

    @app_commands.command(name="vcdeafen", description="Toggle self-deafen (staff)")
    @is_staff()
    async def vcdeafen(self, interaction: discord.Interaction) -> None:
        g = self.bot.get_guild(config.GUILD_ID)
        vc = g.voice_client if g else None
        if not vc:
            await interaction.response.send_message(
                embed=error_embed("VC", "Not connected."), ephemeral=True
            )
            return
        deaf = not vc.self_deaf
        try:
            await interaction.guild.change_voice_state(channel=vc.channel, self_deaf=deaf)
        except discord.HTTPException as e:
            await interaction.response.send_message(
                embed=error_embed("Error", str(e)), ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=success_embed("VC", f"Self-deafen: **{deaf}**"), ephemeral=True
        )

    @app_commands.command(name="vcmute", description="Toggle self-mute (staff)")
    @is_staff()
    async def vcmute(self, interaction: discord.Interaction) -> None:
        g = self.bot.get_guild(config.GUILD_ID)
        vc = g.voice_client if g else None
        if not vc:
            await interaction.response.send_message(
                embed=error_embed("VC", "Not connected."), ephemeral=True
            )
            return
        mute = not vc.self_mute
        try:
            await interaction.guild.change_voice_state(channel=vc.channel, self_mute=mute)
        except discord.HTTPException as e:
            await interaction.response.send_message(
                embed=error_embed("Error", str(e)), ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=success_embed("VC", f"Self-mute: **{mute}**"), ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoiceCog(bot))
