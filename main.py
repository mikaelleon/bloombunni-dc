"""Discord bot entrypoint — Mika shop / commissions bot."""

from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.app_commands.errors import CommandSignatureMismatch
from discord.ext import commands

import config
import database as db
import guild_keys as gk
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
        self.startup_health: dict[str, object] = {
            "db_init_ok": False,
            "config_ok": False,
            "extensions_ok": [],
            "extensions_failed": [],
            "global_sync_ok": False,
            "global_sync_skipped": False,
            "guild_sync_ok": None,
            "views_ok": [],
            "views_failed": [],
        }
        self._error_alert_cache: dict[str, datetime] = {}
        self._startup_report_sent = False

    async def setup_hook(self) -> None:
        try:
            config.validate_config()
            self.startup_health["config_ok"] = True
        except Exception as e:
            self.startup_health["config_ok"] = False
            self.startup_health["extensions_failed"].append(f"config validation: {e}")
            raise

        try:
            await db.init_db()
            self.startup_health["db_init_ok"] = True
        except Exception as e:
            self.startup_health["db_init_ok"] = False
            self.startup_health["extensions_failed"].append(f"database init: {e}")
            raise

        exts = [
            "cogs.owner_tools",
            "cogs.embed_builder",
            "cogs.button_builder",
            "cogs.autoresponder_builder",
            "cogs.config_cmd",
            "cogs.setup_wizard",
            "cogs.quotes",
            "cogs.tickets",
            "cogs.queue",
            "cogs.shop",
            "cogs.vouch",
            "cogs.loyalty_cards",
            "cogs.warn",
            "cogs.sticky",
            "cogs.drop",
            "cogs.payment",
        ]
        for e in exts:
            try:
                await self.load_extension(e)
                self.startup_health["extensions_ok"].append(e)
            except Exception:
                log.exception("Failed to load %s", e)
                self.startup_health["extensions_failed"].append(e)

        # Register slash commands in ONE scope only. Order matters: push empty globals to Discord
        # *before* uploading guild commands, so the API never briefly has both (merged list = duplicates).
        if config.SYNC_GUILD_ID:
            self.startup_health["global_sync_skipped"] = True
            guild_obj = discord.Object(id=config.SYNC_GUILD_ID)
            try:
                self.tree.copy_global_to(guild=guild_obj)
                self.tree.clear_commands(guild=None)
                await self.tree.sync()
                await self.tree.sync(guild=guild_obj)
                self.startup_health["guild_sync_ok"] = True
                log.info(
                    "Guild-only slash sync (%s): globals cleared on API, then guild tree pushed. "
                    "Other servers have no slash commands until you unset SYNC_GUILD_ID and restart.",
                    config.SYNC_GUILD_ID,
                )
            except discord.HTTPException:
                self.startup_health["guild_sync_ok"] = False
                log.exception(
                    "Guild slash sync failed (is the bot in that server and is SYNC_GUILD_ID correct?)"
                )
            except Exception:
                self.startup_health["guild_sync_ok"] = False
                log.exception("Slash sync (guild + global clear) failed")
        else:
            try:
                # Stale guild-scoped commands (from old SYNC_GUILD_ID runs) + new globals both show
                # in the same server — PUT empty to this guild first removes the guild copy.
                if config.GUILD_SLASH_PURGE_ID:
                    purge = discord.Object(id=config.GUILD_SLASH_PURGE_ID)
                    await self.tree.sync(guild=purge)
                    log.info(
                        "GUILD_SLASH_PURGE_ID=%s: wiped guild-scoped slash commands on Discord.",
                        config.GUILD_SLASH_PURGE_ID,
                    )
                await self.tree.sync()
                self.startup_health["global_sync_ok"] = True
            except Exception:
                self.startup_health["global_sync_ok"] = False
                log.exception("Global slash sync failed")

        try:
            self.add_view(TOSAgreeView())
            self.startup_health["views_ok"].append("TOSAgreeView")
        except Exception:
            self.startup_health["views_failed"].append("TOSAgreeView")
            log.exception("Failed to register TOSAgreeView")
        try:
            self.add_view(PaymentView())
            self.startup_health["views_ok"].append("PaymentView")
        except Exception:
            self.startup_health["views_failed"].append("PaymentView")
            log.exception("Failed to register PaymentView")

        try:
            await register_ticket_persistent_views(self)
            self.startup_health["views_ok"].append("ticket persistent views")
        except Exception:
            self.startup_health["views_failed"].append("ticket persistent views")
            log.exception("Failed to register ticket persistent views")
        try:
            await register_order_status_views(self)
            self.startup_health["views_ok"].append("order status views")
        except Exception:
            self.startup_health["views_failed"].append("order status views")
            log.exception("Failed to register order status views")


bot = MikaBot()


async def _run_startup_task_with_retry(task_name: str, coro_factory) -> bool:
    waits = (0, 2, 5, 15)
    last_err: Exception | None = None
    for idx, w in enumerate(waits):
        if w:
            await asyncio.sleep(w)
        try:
            await coro_factory()
            if idx > 0:
                log.info("startup_task_recovered task=%s attempt=%s", task_name, idx + 1)
            return True
        except Exception as e:
            last_err = e
            log.warning("startup_task_failed task=%s attempt=%s err=%s", task_name, idx + 1, e)
    if last_err:
        log.error("startup_task_giveup task=%s err=%s", task_name, last_err)
    return False


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
        await _run_startup_task_with_retry(
            "refresh_status_message",
            shop.refresh_status_message,
        )
    sticky = bot.get_cog("StickyCog")
    if sticky and hasattr(sticky, "refresh_sticky_cache"):
        await _run_startup_task_with_retry(
            "refresh_sticky_cache",
            sticky.refresh_sticky_cache,
        )

    for g in bot.guilds:
        try:
            if await db.guild_has_any_config(g.id):
                continue
            if await db.get_setup_hint_sent(g.id):
                continue
            ch = g.system_channel
            if ch is None or not ch.permissions_for(g.me).send_messages:
                ch = g.rules_channel
            if ch is None or not ch.permissions_for(g.me).send_messages:
                for tc in g.text_channels:
                    if tc.permissions_for(g.me).send_messages:
                        ch = tc
                        break
            if ch and ch.permissions_for(g.me).send_messages:
                await ch.send(
                    "👋 Hi! I'm not fully configured for this server yet. "
                    "A manager should run **`/setup`** (wizard) or **`/config view`**."
                )
                await db.set_setup_hint_sent(g.id)
        except discord.HTTPException:
            log.warning("setup hint: could not message guild %s", g.id)
    await _send_startup_health_report_once()


async def _send_startup_health_report_once() -> None:
    if bot._startup_report_sent:
        return
    bot._startup_report_sent = True

    if config.BOT_OWNER_ID:
        owner = bot.get_user(config.BOT_OWNER_ID) or await bot.fetch_user(config.BOT_OWNER_ID)
    else:
        app_info = await bot.application_info()
        owner = app_info.owner

    if owner is None:
        return
    health = bot.startup_health
    failed = health.get("extensions_failed", []) or []
    views_failed = health.get("views_failed", []) or []
    ok_exts = health.get("extensions_ok", []) or []
    ok_views = health.get("views_ok", []) or []
    status = "✅ Startup healthy" if not failed and not views_failed else "⚠️ Startup has issues"
    emb = discord.Embed(title=status, color=0x57F287 if status.startswith("✅") else 0xFEE75C)
    emb.add_field(name="Database", value="✅" if health.get("db_init_ok") else "❌", inline=True)
    emb.add_field(name="Config validation", value="✅" if health.get("config_ok") else "❌", inline=True)
    if health.get("global_sync_skipped"):
        global_sync_val = "⏭️ skipped (guild-only)"
    elif health.get("global_sync_ok"):
        global_sync_val = "✅"
    else:
        global_sync_val = "❌"
    emb.add_field(name="Global sync", value=global_sync_val, inline=True)
    guild_sync = health.get("guild_sync_ok")
    emb.add_field(
        name="Guild sync",
        value="n/a" if guild_sync is None else ("✅" if guild_sync else "❌"),
        inline=True,
    )
    emb.add_field(name="Extensions loaded", value=str(len(ok_exts)), inline=True)
    emb.add_field(name="Views registered", value=str(len(ok_views)), inline=True)
    if failed:
        emb.add_field(name="Extension failures", value="\n".join(f"- {x}" for x in failed)[:1024], inline=False)
    if views_failed:
        emb.add_field(name="View failures", value="\n".join(f"- {x}" for x in views_failed)[:1024], inline=False)
    try:
        await owner.send(embed=emb)
    except discord.HTTPException:
        log.warning("Could not DM startup health report to owner id=%s", owner.id)
        # Fallback: try a channel named #bot-logs in connected guilds.
        for g in bot.guilds:
            ch = discord.utils.get(g.text_channels, name="bot-logs")
            if not isinstance(ch, discord.TextChannel):
                continue
            perms = ch.permissions_for(g.me)
            if not perms.send_messages:
                continue
            try:
                await ch.send(
                    content="Startup health report (owner DM failed):",
                    embed=emb,
                )
                break
            except discord.HTTPException:
                continue


async def _send_error_alert(interaction: discord.Interaction, error: Exception) -> None:
    # Global fallback channel from env if set.
    channel_id = config.ERROR_ALERT_CHANNEL_ID
    # Guild-specific override from /config error_channel.
    if interaction.guild:
        try:
            gid_channel = await db.get_guild_setting(interaction.guild.id, gk.ERROR_ALERT_CHANNEL)
            if gid_channel:
                channel_id = int(gid_channel)
        except Exception:
            pass
    if not channel_id:
        return

    key = f"{type(error).__name__}:{str(error)[:200]}"
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=5)
    last = bot._error_alert_cache.get(key)
    if last and last > cutoff:
        return
    bot._error_alert_cache[key] = now
    # prune old cache entries
    for k, v in list(bot._error_alert_cache.items()):
        if v <= cutoff:
            bot._error_alert_cache.pop(k, None)

    ch = bot.get_channel(channel_id)
    if not isinstance(ch, discord.TextChannel):
        return
    cmd = getattr(interaction.command, "qualified_name", "unknown")
    user = interaction.user.mention if interaction.user else "unknown"
    guild = f"{interaction.guild.name} ({interaction.guild.id})" if interaction.guild else "DM"
    channel = f"<#{interaction.channel.id}>" if interaction.channel else "unknown"
    tb = traceback.format_exception(type(error), error, error.__traceback__)
    tail = "".join(tb[-3:]).strip()[:1000] if tb else "no traceback"
    emb = discord.Embed(title="Bot runtime error", color=0xED4245)
    emb.add_field(name="Command", value=f"`{cmd}`", inline=False)
    emb.add_field(name="User", value=user, inline=True)
    emb.add_field(name="Guild", value=guild[:1024], inline=True)
    emb.add_field(name="Channel", value=channel, inline=True)
    emb.add_field(name="Error", value=f"`{type(error).__name__}: {str(error)[:300]}`", inline=False)
    emb.add_field(name="Traceback (tail)", value=f"```py\n{tail}\n```", inline=False)
    try:
        await ch.send(embed=emb)
    except discord.HTTPException:
        pass


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
    await _send_error_alert(interaction, orig if isinstance(orig, Exception) else error)
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
