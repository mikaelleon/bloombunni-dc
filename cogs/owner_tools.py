"""Server-owner utilities (e.g. purge bot-authored DMs to a member)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
import database as db
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
        self.db_backup_scheduler.start()

    def cog_unload(self) -> None:
        self.db_backup_scheduler.cancel()

    async def _send_backup_file(self, user: discord.abc.User, *, scheduled: bool = False) -> str | None:
        db_path = Path(config.DATABASE_PATH)
        if not db_path.exists():
            return f"Database file not found: {db_path}"
        max_bytes = 25 * 1024 * 1024
        size = db_path.stat().st_size
        if size > max_bytes:
            return f"Database too large ({size / (1024 * 1024):.2f}MB > 25MB Discord upload limit)."
        try:
            await user.send(
                content="Mika Shop scheduled database backup." if scheduled else "Mika Shop database backup.",
                file=discord.File(str(db_path), filename=db_path.name),
            )
            return None
        except discord.HTTPException:
            return "Could not DM backup file."

    @tasks.loop(minutes=1)
    async def db_backup_scheduler(self) -> None:
        now = datetime.now(timezone.utc)
        due = await db.list_due_db_backup_schedules(now.hour, now.minute)
        for row in due:
            uid = int(row["owner_user_id"])
            try:
                user = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
                if user is None:
                    continue
                err = await self._send_backup_file(user, scheduled=True)
                if err is None:
                    await db.mark_db_backup_schedule_sent(uid)
                else:
                    log.warning("scheduled_backup_failed owner_id=%s error=%s", uid, err)
            except Exception as e:
                log.warning("scheduled_backup_failed owner_id=%s error=%s", uid, e)

    @db_backup_scheduler.before_loop
    async def before_db_backup_scheduler(self) -> None:
        await self.bot.wait_until_ready()

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
    @app_commands.describe(
        schedule="Choose `daily` to schedule automatic daily DM backup",
        time_utc="For daily schedule, time in HH:MM (UTC), e.g. 01:30",
    )
    @app_commands.choices(
        schedule=[
            app_commands.Choice(name="once", value="once"),
            app_commands.Choice(name="daily", value="daily"),
            app_commands.Choice(name="off", value="off"),
        ]
    )
    @is_guild_owner()
    async def db_backup(
        self,
        interaction: discord.Interaction,
        schedule: str = "once",
        time_utc: str | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if schedule == "off":
            await db.disable_db_backup_schedule(interaction.user.id)
            await interaction.followup.send(
                embed=success_embed("Schedule disabled", "Daily `/db backup` schedule turned off."),
                ephemeral=True,
            )
            return

        if schedule == "daily":
            if not time_utc:
                await interaction.followup.send(
                    embed=user_hint("Missing time", "Provide `time_utc` like `01:30` when `schedule=daily`."),
                    ephemeral=True,
                )
                return
            try:
                hh, mm = time_utc.split(":", 1)
                hour = int(hh)
                minute = int(mm)
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError("range")
            except Exception:
                await interaction.followup.send(
                    embed=user_hint("Invalid time", "Use 24h UTC format `HH:MM` (example: `01:30`)."),
                    ephemeral=True,
                )
                return
            await db.upsert_db_backup_schedule(interaction.user.id, hour, minute, True)
            await interaction.followup.send(
                embed=success_embed(
                    "Daily schedule saved",
                    f"Daily DB backup scheduled at **{hour:02d}:{minute:02d} UTC**.\nRun `/db backup schedule:once` anytime for immediate backup.",
                ),
                ephemeral=True,
            )
            return

        err = await self._send_backup_file(interaction.user, scheduled=False)
        if err:
            await interaction.followup.send(
                embed=user_warn(
                    "Backup failed",
                    err + " Enable DMs and try again.",
                ),
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            embed=success_embed("Backup sent", "Check your DMs for the database file."),
            ephemeral=True,
        )

    @db_group.command(name="slowqueries", description="Show top recent slow DB queries")
    @is_guild_owner()
    async def db_slowqueries(self, interaction: discord.Interaction) -> None:
        rows = await db.list_recent_slow_queries(10)
        if not rows:
            await interaction.response.send_message(
                embed=user_hint("No slow queries", "No query exceeded threshold yet."),
                ephemeral=True,
            )
            return
        lines = [
            f"`{r['elapsed_ms']:.1f}ms` `{r['query_name']}` at `{r['created_at']}`"
            for r in rows
        ]
        await interaction.response.send_message(
            embed=success_embed("Slow queries (top 10)", "\n".join(lines)),
            ephemeral=True,
        )

    async def _db_health_snapshot(self) -> dict[str, int]:
        out = {"orphan_orders": 0, "stale_wizard_sessions": 0, "duplicate_panels": 0}
        async with aiosqlite.connect(config.DATABASE_PATH) as conn:
            cur = await conn.execute(
                """
                SELECT COUNT(*) FROM orders o
                WHERE o.ticket_channel_id IS NULL
                   OR NOT EXISTS (
                       SELECT 1 FROM tickets t
                       WHERE t.channel_id = o.ticket_channel_id
                         AND t.deleted_at IS NULL
                   )
                """
            )
            out["orphan_orders"] = int((await cur.fetchone() or [0])[0])
            cur = await conn.execute(
                "SELECT COUNT(*) FROM wizard_sessions WHERE updated_at < ?",
                ((datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),),
            )
            out["stale_wizard_sessions"] = int((await cur.fetchone() or [0])[0])
            cur = await conn.execute(
                "SELECT COUNT(*) FROM (SELECT panel, COUNT(*) c FROM persist_panels GROUP BY panel HAVING c > 1)"
            )
            out["duplicate_panels"] = int((await cur.fetchone() or [0])[0])
        return out

    @db_group.command(name="check", description="Run database health audit")
    @is_guild_owner()
    async def db_check(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        snap = await self._db_health_snapshot()
        broken_panel_refs = 0
        orphan_ticket_records = 0

        async with aiosqlite.connect(config.DATABASE_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT channel_id FROM tickets WHERE closed_at IS NULL AND deleted_at IS NULL")
            ticket_rows = await cur.fetchall()
            for r in ticket_rows:
                ch = self.bot.get_channel(int(r["channel_id"]))
                if ch is None:
                    orphan_ticket_records += 1
            cur = await conn.execute("SELECT channel_id, message_id FROM persist_panels")
            panel_rows = await cur.fetchall()
            for r in panel_rows:
                ch = self.bot.get_channel(int(r["channel_id"]))
                if not isinstance(ch, discord.TextChannel):
                    broken_panel_refs += 1
                    continue
                try:
                    await ch.fetch_message(int(r["message_id"]))
                except discord.HTTPException:
                    broken_panel_refs += 1

        text = (
            "Database Health Check\n\n"
            f"✅ Schema integrity: OK\n"
            f"{'✅' if orphan_ticket_records == 0 else '⚠️'} Orphaned ticket records: {orphan_ticket_records}\n"
            f"{'✅' if snap['orphan_orders'] == 0 else '⚠️'} Orphaned orders: {snap['orphan_orders']}\n"
            f"{'✅' if snap['duplicate_panels'] == 0 else '⚠️'} Duplicate panel records: {snap['duplicate_panels']}\n"
            f"{'✅' if snap['stale_wizard_sessions'] == 0 else '⚠️'} Stale wizard sessions: {snap['stale_wizard_sessions']}\n"
            f"{'✅' if broken_panel_refs == 0 else '⚠️'} Broken panel pointers: {broken_panel_refs}\n\n"
            "Run `/db clean` to remove safe flagged records."
        )
        await interaction.followup.send(embed=success_embed("DB health", text), ephemeral=True)

    @db_group.command(name="clean", description="Clean safe orphan/stale DB records")
    @is_guild_owner()
    async def db_clean(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        removed_orphan_orders = 0
        removed_stale_wizard = 0
        removed_broken_panels = 0

        async with aiosqlite.connect(config.DATABASE_PATH) as conn:
            cur = await conn.execute(
                """
                DELETE FROM orders
                WHERE ticket_channel_id IS NULL
                   OR NOT EXISTS (
                       SELECT 1 FROM tickets t
                       WHERE t.channel_id = orders.ticket_channel_id
                         AND t.deleted_at IS NULL
                   )
                """
            )
            removed_orphan_orders = int(cur.rowcount or 0)
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            cur = await conn.execute("DELETE FROM wizard_sessions WHERE updated_at < ?", (cutoff,))
            removed_stale_wizard = int(cur.rowcount or 0)

            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT rowid, channel_id, message_id FROM persist_panels")
            panel_rows = await cur.fetchall()
            for r in panel_rows:
                ch = self.bot.get_channel(int(r["channel_id"]))
                bad = False
                if not isinstance(ch, discord.TextChannel):
                    bad = True
                else:
                    try:
                        await ch.fetch_message(int(r["message_id"]))
                    except discord.HTTPException:
                        bad = True
                if bad:
                    await conn.execute("DELETE FROM persist_panels WHERE rowid = ?", (int(r["rowid"]),))
                    removed_broken_panels += 1
            await conn.commit()

        await interaction.followup.send(
            embed=success_embed(
                "DB clean done",
                (
                    f"Removed orphaned orders: **{removed_orphan_orders}**\n"
                    f"Removed stale wizard sessions: **{removed_stale_wizard}**\n"
                    f"Removed broken panel pointers: **{removed_broken_panels}**"
                ),
            ),
            ephemeral=True,
        )

    @app_commands.command(name="reload", description="Reload one cog module (server owner)")
    @app_commands.describe(cog="Cog short name, e.g. tickets, quotes, queue")
    @is_guild_owner()
    async def reload_cog(self, interaction: discord.Interaction, cog: str) -> None:
        await interaction.response.defer(ephemeral=True)
        short = cog.strip().lower().replace(".py", "")
        ext = short if short.startswith("cogs.") else f"cogs.{short}"
        try:
            if ext in self.bot.extensions:
                await self.bot.reload_extension(ext)
            else:
                await self.bot.load_extension(ext)
        except Exception as e:
            await interaction.followup.send(
                embed=user_warn("Reload failed", f"`{ext}` -> {type(e).__name__}: {e}"),
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            embed=success_embed("Reloaded", f"Extension `{ext}` reloaded."),
            ephemeral=True,
        )

    @app_commands.command(name="reloadall", description="Reload all loaded cogs (server owner)")
    @is_guild_owner()
    async def reload_all_cogs(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        failed: list[str] = []
        ok = 0
        for ext in list(self.bot.extensions.keys()):
            if not ext.startswith("cogs."):
                continue
            try:
                await self.bot.reload_extension(ext)
                ok += 1
            except Exception as e:
                failed.append(f"{ext}: {type(e).__name__}: {e}")
        msg = f"Reloaded {ok} extension(s)."
        if failed:
            msg += "\n\nFailed:\n" + "\n".join(f"- {x}" for x in failed[:10])
        await interaction.followup.send(
            embed=success_embed("Reload all", msg),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    cog = OwnerToolsCog(bot)
    await bot.add_cog(cog)
