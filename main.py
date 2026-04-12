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

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

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
async def on_ready() -> None:
    log.info("Logged in as %s (%s)", bot.user, round(bot.latency * 1000))
    shop = bot.get_cog("ShopCog")
    if shop and hasattr(shop, "refresh_status_message"):
        await shop.refresh_status_message()
    sticky = bot.get_cog("StickyCog")
    if sticky and hasattr(sticky, "refresh_sticky_cache"):
        await sticky.refresh_sticky_cache()


@bot.tree.error
async def on_app_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    from utils.checks import check_failure_response
    from utils.embeds import error_embed

    orig = getattr(error, "original", error)
    if isinstance(error, app_commands.CommandInvokeError) and error.original:
        orig = error.original
    if isinstance(orig, app_commands.CheckFailure):
        await check_failure_response(interaction, orig)
        return
    if isinstance(error, CommandSignatureMismatch):
        log.warning("Command signature mismatch (Discord cache vs bot): %s", error)
        msg = (
            "Discord still has an **older** version of this slash command than your bot code "
            "(often after adding options like `channel`).\n\n"
            "**Fix:** Set **`SYNC_GUILD_ID`** in `.env` to this server’s ID (Developer Mode → "
            "right‑click server → Copy Server ID), **restart the bot**, then run the command again. "
            "That pushes commands to this guild **immediately**.\n\n"
            "Otherwise wait up to ~1 hour for global command updates, or re-invite the bot after "
            "changing commands."
        )
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    embed=error_embed("Slash command out of date", msg), ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    embed=error_embed("Slash command out of date", msg), ephemeral=True
                )
        except discord.HTTPException:
            pass
        return
    log.exception("App command error: %s", error)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                embed=error_embed("Error", "Something went wrong."), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=error_embed("Error", "Something went wrong."), ephemeral=True
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
