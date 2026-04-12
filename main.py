"""Discord bot entrypoint — Mika shop / commissions bot."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.app_commands.errors import CommandSignatureMismatch
from discord.ext import commands

import config
import database as db
from cogs.payment import PaymentView
from cogs.queue import register_order_status_views
from cogs.shop import TOSAgreeView
from cogs.tickets import register_ticket_persistent_views
from keep_alive import keep_alive
from utils.logging_setup import get_logger, setup_logging

setup_logging(logging.INFO)
log = get_logger("core")

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True


class MikaBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=INTENTS, help_command=None)

    async def setup_hook(self) -> None:
        await db.init_db()
        config.validate_config()

        exts = [
            "cogs.owner_tools",
            "cogs.serverconfig",
            "cogs.tickets",
            "cogs.queue",
            "cogs.shop",
            "cogs.vouch",
            "cogs.warn",
            "cogs.sticky",
            "cogs.drop",
            "cogs.payment",
        ]
        for e in exts:
            try:
                await self.load_extension(e)
            except Exception:
                log.exception("Failed to load %s", e)
                raise

        await self.tree.sync()

        # Guild-scoped sync updates slash commands in that server immediately (global sync can lag hours).
        if config.SYNC_GUILD_ID:
            guild_obj = discord.Object(id=config.SYNC_GUILD_ID)
            try:
                self.tree.copy_global_to(guild=guild_obj)
                await self.tree.sync(guild=guild_obj)
                log.info(
                    "Slash commands synced to guild %s — use this server for up-to-date commands.",
                    config.SYNC_GUILD_ID,
                )
            except discord.HTTPException:
                log.exception(
                    "Guild slash sync failed (is the bot in that server and is SYNC_GUILD_ID correct?)"
                )

        self.add_view(TOSAgreeView())
        self.add_view(PaymentView())

        await register_ticket_persistent_views(self)
        await register_order_status_views(self)


bot = MikaBot()


@bot.event
async def on_interaction(interaction: discord.Interaction) -> None:
    """Log slash / component usage for support and auditing (INFO)."""
    if interaction.type != discord.InteractionType.application_command:
        return
    if not interaction.command:
        return
    gid = interaction.guild.id if interaction.guild else None
    cid = interaction.channel.id if interaction.channel else None
    uid = interaction.user.id if interaction.user else None
    log.info(
        "cmd=%s guild_id=%s channel_id=%s user_id=%s",
        interaction.command.qualified_name,
        gid,
        cid,
        uid,
    )


@bot.event
async def on_ready() -> None:
    log.info("ready user=%s id=%s latency_ms=%s", bot.user, bot.user.id if bot.user else None, round(bot.latency * 1000))
    shop = bot.get_cog("ShopCog")
    if shop and hasattr(shop, "refresh_status_message"):
        await shop.refresh_status_message()
    sticky = bot.get_cog("StickyCog")
    if sticky and hasattr(sticky, "refresh_sticky_cache"):
        await sticky.refresh_sticky_cache()


@bot.tree.error
async def on_app_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    from utils.checks import check_failure_response
    from utils.embeds import user_hint, user_warn

    orig = getattr(error, "original", error)
    if isinstance(error, app_commands.CommandInvokeError) and error.original:
        orig = error.original
    if isinstance(orig, app_commands.CheckFailure):
        await check_failure_response(interaction, orig)
        return
    if isinstance(error, CommandSignatureMismatch):
        log.warning(
            "command_signature_mismatch cmd=%s guild_id=%s: %s",
            getattr(interaction.command, "qualified_name", None),
            interaction.guild.id if interaction.guild else None,
            error,
        )
        msg = (
            "Discord still has an **older** version of this slash command than your bot code "
            "(often after adding options like `channel`).\n\n"
            "**Suggestion:** Set **`SYNC_GUILD_ID`** in `.env` to this server’s ID (Developer Mode → "
            "right‑click server → Copy Server ID), **restart the bot**, then run the command again. "
            "That pushes commands to this guild **immediately**.\n\n"
            "Otherwise wait up to ~1 hour for global command updates, or re-invite the bot after "
            "changing commands."
        )
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    embed=user_hint("Slash commands still updating", msg), ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    embed=user_hint("Slash commands still updating", msg), ephemeral=True
                )
        except discord.HTTPException:
            pass
        return
    log.exception(
        "app_command_failed cmd=%s guild_id=%s user_id=%s",
        getattr(interaction.command, "qualified_name", None),
        interaction.guild.id if interaction.guild else None,
        interaction.user.id if interaction.user else None,
    )
    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                embed=user_warn(
                    "That didn’t work",
                    "Something went wrong on our side. Try again in a moment. "
                    "If it keeps happening, tell a moderator and include what command you ran.",
                ),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=user_warn(
                    "That didn’t work",
                    "Something went wrong on our side. Try again in a moment. "
                    "If it keeps happening, tell a moderator and include what command you ran.",
                ),
                ephemeral=True,
            )
    except discord.HTTPException:
        pass


def main() -> None:
    keep_alive()
    bot.run(config.BOT_TOKEN)


if __name__ == "__main__":
    import sys
    import traceback

    try:
        main()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(1)
