"""Server-owner utilities (e.g. purge bot-authored DMs to a member)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.checks import is_guild_owner
from utils.embeds import success_embed, user_hint, user_warn
from utils.logging_setup import get_logger

log = get_logger("owner_tools")

# Safety cap per invocation (Discord history + delete rate limits make huge purges slow).
_MAX_MESSAGES_SCAN = 15_000


class OwnerToolsCog(commands.Cog, name="OwnerToolsCog"):
    db_group = app_commands.Group(name="db", description="Owner database tools")

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

    @db_group.command(name="backup", description="DM yourself a SQLite backup file")
    @is_guild_owner()
    async def db_backup(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        db_path = Path(config.DATABASE_PATH)
        if not db_path.exists():
            await interaction.followup.send(
                embed=user_warn("Backup failed", f"Database file not found: `{db_path}`"),
                ephemeral=True,
            )
            return
        max_bytes = 25 * 1024 * 1024
        size = db_path.stat().st_size
        if size > max_bytes:
            await interaction.followup.send(
                embed=user_warn(
                    "Backup too large",
                    f"Database is {size / (1024 * 1024):.2f}MB (>25MB Discord upload limit). Use host filesystem backup.",
                ),
                ephemeral=True,
            )
            return
        try:
            dm = await interaction.user.create_dm()
            await dm.send(
                content="Mika Shop database backup.",
                file=discord.File(str(db_path), filename=db_path.name),
            )
        except discord.HTTPException:
            await interaction.followup.send(
                embed=user_warn(
                    "DM blocked",
                    "Could not DM backup file. Enable DMs and try again.",
                ),
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            embed=success_embed("Backup sent", "Check your DMs for the database file."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    cog = OwnerToolsCog(bot)
    await bot.add_cog(cog)
