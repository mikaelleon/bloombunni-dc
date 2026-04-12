"""Server-owner utilities (e.g. purge bot-authored DMs to a member)."""

from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import is_guild_owner
from utils.embeds import success_embed, user_hint, user_warn
from utils.logging_setup import get_logger

log = get_logger("owner_tools")

# Safety cap per invocation (Discord history + delete rate limits make huge purges slow).
_MAX_MESSAGES_SCAN = 15_000


class OwnerToolsCog(commands.Cog, name="OwnerToolsCog"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="purge_bot_dms",
        description="Delete DMs this bot sent to a member (server owner only)",
    )
    @app_commands.describe(
        user="Member who received the bot’s DMs (must be in this server)",
    )
    @is_guild_owner()
    async def purge_bot_dms(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if user.bot:
            await interaction.followup.send(
                embed=user_hint("Not applicable", "Pick a **user**, not a bot."),
                ephemeral=True,
            )
            return

        me = interaction.client.user
        assert me is not None

        try:
            dm = await user.create_dm()
        except discord.HTTPException as e:
            log.warning("purge_bot_dms: could not open DM with %s: %s", user.id, e)
            await interaction.followup.send(
                embed=user_warn(
                    "Couldn’t open DM",
                    "Discord wouldn’t open a DM channel with this user. They may have blocked the bot or disabled DMs.",
                ),
                ephemeral=True,
            )
            return

        deleted = 0
        failed = 0
        scanned = 0

        try:
            async for message in dm.history(limit=_MAX_MESSAGES_SCAN):
                scanned += 1
                if message.author.id != me.id:
                    continue
                try:
                    await message.delete()
                    deleted += 1
                    if deleted % 5 == 0:
                        await asyncio.sleep(0.35)
                except discord.NotFound:
                    pass
                except discord.Forbidden:
                    failed += 1
                    log.warning("purge_bot_dms: forbidden delete msg %s in DM %s", message.id, dm.id)
                except discord.HTTPException as e:
                    failed += 1
                    log.warning("purge_bot_dms: HTTP delete msg %s: %s", message.id, e)
        except discord.Forbidden:
            await interaction.followup.send(
                embed=user_warn(
                    "Couldn’t read DM history",
                    "The bot can’t read this DM channel — the user may need to allow DMs from server members or unblock the bot.",
                ),
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            log.exception("purge_bot_dms: history failed for DM %s", dm.id)
            await interaction.followup.send(
                embed=user_warn("Couldn’t scan messages", str(e)[:500]),
                ephemeral=True,
            )
            return

        note = (
            f"Scanned up to **{scanned}** message(s) in the DM (newest first). "
            f"**Deleted:** {deleted} bot message(s)."
        )
        if failed:
            note += f"\n**Skipped (could not delete):** {failed}"
        if scanned >= _MAX_MESSAGES_SCAN:
            note += (
                f"\n\nStopped at the safety limit ({_MAX_MESSAGES_SCAN} messages scanned). "
                "Run the command again to continue older messages."
            )

        await interaction.followup.send(embed=success_embed("DM purge finished", note), ephemeral=True)
        log.info(
            "purge_bot_dms guild_id=%s owner_id=%s target_id=%s deleted=%s failed=%s scanned=%s",
            interaction.guild.id if interaction.guild else None,
            interaction.user.id,
            user.id,
            deleted,
            failed,
            scanned,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OwnerToolsCog(bot))
