"""TOS gate, shop open/close, status embed."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
from guild_config import get_role, get_text_channel
import guild_keys as gk
from utils.checks import is_staff
from utils.embeds import DANGER, SUCCESS, info_embed, success_embed, user_hint, user_warn
from utils.logging_setup import get_logger

log = get_logger("shop")


class TOSAgreeView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="I Have Read & Agree to the TOS",
        style=discord.ButtonStyle.success,
        custom_id="tos_agree",
    )
    async def agree(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.HTTPException:
            return
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.followup.send(
                embed=user_hint("Use this in a server", "Open the TOS panel from inside your Discord server."), ephemeral=True
            )
            return
        role = await get_role(interaction.guild, gk.TOS_AGREED_ROLE)
        if role is None:
            await interaction.followup.send(
                embed=user_hint("TOS role not set", "Ask an admin to map **TOS agreed role** in **`/setup`** or staff tools."), ephemeral=True
            )
            return
        if role in interaction.user.roles:
            await interaction.followup.send("You've already agreed.", ephemeral=True)
            return
        try:
            await interaction.user.add_roles(role, reason="TOS agreement")
        except discord.Forbidden:
            await interaction.followup.send(
                embed=user_warn("Can’t assign role", "The bot needs **Manage Roles** above the TOS role, or the role is managed elsewhere."), ephemeral=True
            )
            return
        await db.log_tos_agreement(interaction.user.id)
        await interaction.followup.send(
            "✅ You've agreed! You can now open a commission ticket.", ephemeral=True
        )


class ShopCog(commands.Cog, name="ShopCog"):
    shop = app_commands.Group(name="shop", description="Shop status (staff)")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._status_message: discord.Message | None = None

    async def refresh_status_message(self) -> None:
        row = await db.get_persist_panel("shop_status")
        if not row:
            return
        ch = self.bot.get_channel(int(row["channel_id"]))
        if not isinstance(ch, discord.TextChannel):
            return
        try:
            self._status_message = await ch.fetch_message(int(row["message_id"]))
        except (discord.NotFound, discord.Forbidden):
            self._status_message = None

    async def deploy_tos_panel(self, ch: discord.TextChannel) -> discord.Message:
        """Post TOS embed + agree button; persist panel row."""
        text = (
            config.TOS_FILE.read_text(encoding="utf-8")
            if config.TOS_FILE.exists()
            else "TOS text missing."
        )
        emb = discord.Embed(title="Terms of Service", description=text[:4000], color=DANGER)
        msg = await ch.send(embed=emb, view=TOSAgreeView())
        await db.set_persist_panel("tos", ch.id, msg.id)
        return msg

    async def run_setup_tos(
        self, interaction: discord.Interaction, ch: discord.TextChannel
    ) -> None:
        """Called from `/deploy tos` with a resolved TOS text channel."""
        await self.deploy_tos_panel(ch)
        await interaction.response.send_message(
            embed=success_embed("Posted", "TOS panel deployed."), ephemeral=True
        )

    def _embed(self, st: dict) -> discord.Embed:
        open_ = bool(st.get("is_open", 0))
        when = st.get("last_toggled") or "—"
        by = st.get("toggled_by")
        who = f"<@{by}>" if by else "—"
        reason = (st.get("close_reason") or "").strip()
        if open_:
            return discord.Embed(
                title="✅ Commissions OPEN",
                description=f"Last toggled: {when}\nBy: {who}",
                color=SUCCESS,
            )
        desc = f"Last toggled: {when}\nBy: {who}"
        if reason:
            desc += f"\nReason: {reason[:500]}"
        return discord.Embed(
            title="🔴 Commissions CLOSED",
            description=desc,
            color=DANGER,
        )

    async def _apply_status_embed(self, interaction: discord.Interaction, emb: discord.Embed) -> None:
        ch = await get_text_channel(interaction.guild, gk.SHOP_STATUS_CHANNEL)
        if not ch:
            return
        if self._status_message:
            try:
                await self._status_message.edit(embed=emb)
                return
            except (discord.NotFound, discord.Forbidden):
                self._status_message = None
        row = await db.get_persist_panel("shop_status")
        if row and row.get("message_id"):
            try:
                self._status_message = await ch.fetch_message(int(row["message_id"]))
                await self._status_message.edit(embed=emb)
                return
            except (discord.NotFound, discord.Forbidden):
                pass
        msg = await ch.send(embed=emb)
        self._status_message = msg
        await db.set_persist_panel("shop_status", ch.id, msg.id)

    @shop.command(name="open", description="Open commissions (staff)")
    @is_staff()
    async def shop_open(self, interaction: discord.Interaction) -> None:
        # Acknowledge within 3s — never return before responding (causes "application did not respond").
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            await interaction.followup.send(
                embed=user_hint("Use this in a server", "Run shop commands from inside your Discord server."),
                ephemeral=True,
            )
            return
        try:
            await db.set_shop_state(True, interaction.user.id)
            st = await db.get_shop_state()
            emb = self._embed(st)
            await self._apply_status_embed(interaction, emb)

            start = await get_text_channel(interaction.guild, gk.START_HERE_CHANNEL)
            tos_role = await get_role(interaction.guild, gk.TOS_AGREED_ROLE)
            open_role = await get_role(interaction.guild, gk.COMMISSIONS_OPEN_ROLE)
            if start:
                await start.set_permissions(interaction.guild.default_role, view_channel=False)
                if tos_role:
                    await start.set_permissions(tos_role, view_channel=True)
                if open_role:
                    await start.set_permissions(open_role, view_channel=True)

            await interaction.followup.send(
                embed=success_embed("Shop", "Commissions are now **open**."), ephemeral=True
            )
        except discord.HTTPException as e:
            detail = (getattr(e, "text", None) or str(e))[:200]
            await interaction.followup.send(
                embed=user_warn("Couldn’t update status", f"Discord returned: {detail}\nCheck bot permissions and try again."),
                ephemeral=True,
            )
        except Exception:
            log.exception("shop_open failed")
            await interaction.followup.send(
                embed=user_warn(
                    "Couldn’t open shop",
                    "Something went wrong — check bot permissions and **`/config view`** mappings.",
                ),
                ephemeral=True,
            )

    @shop.command(name="close", description="Close commissions (staff)")
    @app_commands.describe(reason="Optional public reason shown in shop status")
    @is_staff()
    async def shop_close(self, interaction: discord.Interaction, reason: str | None = None) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            await interaction.followup.send(
                embed=user_hint("Use this in a server", "Run shop commands from inside your Discord server."),
                ephemeral=True,
            )
            return
        try:
            await db.set_shop_state(False, interaction.user.id, reason)
            st = await db.get_shop_state()
            emb = self._embed(st)
            await self._apply_status_embed(interaction, emb)

            start = await get_text_channel(interaction.guild, gk.START_HERE_CHANNEL)
            tos_role = await get_role(interaction.guild, gk.TOS_AGREED_ROLE)
            open_role = await get_role(interaction.guild, gk.COMMISSIONS_OPEN_ROLE)
            if start:
                if tos_role:
                    await start.set_permissions(tos_role, view_channel=False)
                if open_role:
                    await start.set_permissions(open_role, view_channel=False)

            await interaction.followup.send(
                embed=success_embed("Shop", "Commissions are now **closed**."), ephemeral=True
            )
        except discord.HTTPException as e:
            detail = (getattr(e, "text", None) or str(e))[:200]
            await interaction.followup.send(
                embed=user_warn("Couldn’t update status", f"Discord returned: {detail}\nCheck bot permissions and try again."),
                ephemeral=True,
            )
        except Exception:
            log.exception("shop_close failed")
            await interaction.followup.send(
                embed=user_warn(
                    "Couldn’t close shop",
                    "Something went wrong — check bot permissions and **`/config view`** mappings.",
                ),
                ephemeral=True,
            )

    @app_commands.command(name="shopstatus", description="Show whether commissions are open")
    async def shopstatus(self, interaction: discord.Interaction) -> None:
        st = await db.get_shop_state()
        open_ = bool(st.get("is_open", 0))
        await interaction.response.send_message(
            embed=self._embed(st),
            ephemeral=True,
        )

    @app_commands.command(name="tosstats", description="Show TOS agreement stats (staff)")
    @is_staff()
    async def tosstats_cmd(self, interaction: discord.Interaction) -> None:
        stats = await db.tos_stats()
        emb = info_embed(
            "TOS agreement stats",
            (
                f"Current version: **v{stats['version']}**\n"
                f"Total agreements: **{stats['total']}**\n"
                f"Current version users: **{stats['current']}**\n"
                f"Outdated users: **{stats['outdated']}**\n"
                f"Agreements in last 7d: **{stats['week']}**"
            ),
        )
        if stats.get("last_user"):
            emb.add_field(
                name="Last agreement",
                value=f"<@{stats['last_user']}> at `{stats.get('last_at') or '—'}`",
                inline=False,
            )
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @app_commands.command(
        name="tosversion",
        description="View or set current TOS version (staff)",
    )
    @app_commands.describe(new_version="Optional: set a new TOS version number")
    @is_staff()
    async def tosversion_cmd(
        self,
        interaction: discord.Interaction,
        new_version: int | None = None,
    ) -> None:
        if new_version is None:
            cur = await db.get_current_tos_version()
            await interaction.response.send_message(
                embed=info_embed("TOS version", f"Current version: **v{cur}**"),
                ephemeral=True,
            )
            return
        if new_version < 1:
            await interaction.response.send_message(
                embed=user_hint("Invalid version", "Version must be 1 or greater."),
                ephemeral=True,
            )
            return
        await db.set_current_tos_version(new_version)
        await interaction.response.send_message(
            embed=success_embed(
                "TOS version updated",
                f"Set current TOS version to **v{new_version}**. Users on older agreements must re-agree.",
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ShopCog(bot))
