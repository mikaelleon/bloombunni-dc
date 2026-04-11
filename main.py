"""Discord bot entrypoint — Mika shop / commissions bot."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
from cogs.payment import PaymentView
from cogs.tickets import CloseTicketView, TOSAgreeView, TicketOpenView
from keep_alive import keep_alive

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True
INTENTS.voice_states = True


class MikaBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=INTENTS, help_command=None)

    async def setup_hook(self) -> None:
        await db.init_db()
        config.validate_config()

        exts = [
            "cogs.tickets",
            "cogs.queue",
            "cogs.shop",
            "cogs.vouch",
            "cogs.warn",
            "cogs.sticky",
            "cogs.roblox",
            "cogs.drop",
            "cogs.calculator",
            "cogs.payment",
            "cogs.voice",
        ]
        for e in exts:
            try:
                await self.load_extension(e)
            except Exception:
                log.exception("Failed to load %s", e)
                raise

        guild = discord.Object(id=config.GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

        self.add_view(TicketOpenView())
        self.add_view(CloseTicketView())
        self.add_view(TOSAgreeView())
        self.add_view(PaymentView())


bot = MikaBot()


@bot.event
async def on_ready() -> None:
    log.info("Logged in as %s (%s)", bot.user, round(bot.latency * 1000))
    q = bot.get_cog("QueueCog")
    if q and hasattr(q, "load_queue_message"):
        await q.load_queue_message()
    if q and hasattr(q, "refresh_queue_board"):
        await q.refresh_queue_board()
    shop = bot.get_cog("ShopCog")
    if shop and hasattr(shop, "refresh_status_message"):
        await shop.refresh_status_message()
    vc = bot.get_cog("VoiceCog")
    if vc and hasattr(vc, "join_vc"):
        await vc.join_vc()


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
    main()
