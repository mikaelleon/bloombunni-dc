"""Read-only and reset helpers — replaces removed `/serverconfig` slash tree."""

from __future__ import annotations

import json
import io

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import guild_keys as gk
from utils.checks import can_manage_server_config
from utils.embeds import info_embed, success_embed, user_hint, user_warn
from utils.guild_config_display import chunk_lines, status_lines_for_guild
from utils.paged_embeds import PagedEmbedView

RESET_GROUP_KEYS: dict[str, tuple[list[str], list[str]]] = {
    "tickets": (
        [
            gk.TICKET_CATEGORY,
            gk.NOTED_CATEGORY,
            gk.PROCESSING_CATEGORY,
            gk.DONE_CATEGORY,
            gk.TRANSCRIPT_CHANNEL,
            gk.START_HERE_CHANNEL,
            gk.VERIFICATION_CHANNEL,
            gk.AGE_VERIFIED_ROLE,
        ],
        [],
    ),
    "queue": (
        [gk.QUEUE_CHANNEL, gk.ORDER_NOTIFS_CHANNEL],
        [gk.ORDER_ID_PREFIX],
    ),
    "shop": (
        [gk.TOS_CHANNEL, gk.SHOP_STATUS_CHANNEL, gk.TOS_AGREED_ROLE, gk.COMMISSIONS_OPEN_ROLE],
        [],
    ),
    "payment": (
        [gk.PAYMENT_CHANNEL],
        list(gk.PAYMENT_ALL_KEYS),
    ),
    "channels_roles": (
        [
            gk.STAFF_ROLE,
            gk.BOOSTIE_ROLE,
            gk.RESELLER_ROLE,
            gk.PLEASE_VOUCH_ROLE,
            gk.VOUCHES_CHANNEL,
            gk.WARN_LOG_CHANNEL,
        ],
        [gk.WARN_REASON_TEMPLATES_JSON],
    ),
}


def _is_http_url(s: str) -> bool:
    t = str(s).strip().lower()
    return t.startswith("http://") or t.startswith("https://")


class ConfirmResetView(discord.ui.View):
    def __init__(
        self,
        guild_id: int,
        group: str,
        int_keys: list[str],
        str_keys: list[str],
        pricing: bool,
        changed_by: int,
    ) -> None:
        super().__init__(timeout=120.0)
        self.guild_id = guild_id
        self.group = group
        self.int_keys = int_keys
        self.str_keys = str_keys
        self.pricing = pricing
        self.changed_by = changed_by

    @discord.ui.button(label="Confirm reset", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if self.pricing:
            await db.create_config_snapshot(self.guild_id, self.changed_by)
            await db.clear_quote_data_for_guild(self.guild_id)
            await db.log_config_change(
                self.guild_id,
                self.changed_by,
                "config.reset.pricing",
                "quote data present",
                "cleared",
            )
            await interaction.response.edit_message(
                embed=success_embed("Reset", "Quote prices and related rows cleared for this server."),
                view=None,
            )
            return
        await db.create_config_snapshot(self.guild_id, self.changed_by)
        await db.delete_guild_settings_keys(self.guild_id, self.int_keys)
        await db.delete_guild_string_settings_keys(self.guild_id, self.str_keys)
        await db.log_config_change(
            self.guild_id,
            self.changed_by,
            f"config.reset.{self.group}",
            f"int_keys={len(self.int_keys)},str_keys={len(self.str_keys)}",
            "cleared",
        )
        await interaction.response.edit_message(
            embed=success_embed(
                "Reset",
                f"Group **{self.group}** keys removed from the database. Run `/config view` to verify.",
            ),
            view=None,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=info_embed("Cancelled", "No changes."), view=None
        )


class ConfigCog(commands.Cog, name="ConfigCog"):
    config = app_commands.Group(
        name="config",
        description="View, reset, and payment text (replaces old /serverconfig)",
    )

    config_payment = app_commands.Group(
        name="payment",
        description="GCash / PayPal / Ko-fi text and QR URLs",
        parent=config,
    )

    async def _record_string_change(
        self,
        guild_id: int,
        changed_by: int,
        key: str,
        new_value: str,
    ) -> None:
        old = await db.get_guild_string_setting(guild_id, key)
        await db.set_guild_string_setting(guild_id, key, new_value)
        await db.log_config_change(guild_id, changed_by, key, old, new_value)

    async def _record_int_change(
        self,
        guild_id: int,
        changed_by: int,
        key: str,
        new_value: int,
    ) -> None:
        old = await db.get_guild_setting(guild_id, key)
        await db.set_guild_setting(guild_id, key, new_value)
        await db.log_config_change(
            guild_id,
            changed_by,
            key,
            str(old) if old is not None else None,
            str(new_value),
        )

    @config_payment.command(
        name="gcash_details",
        description="Body text for the GCash button (name, number, instructions)",
    )
    @app_commands.describe(text="Plain text shown in the GCash embed (max ~4000 characters)")
    @can_manage_server_config()
    async def cfg_pay_gcash(self, interaction: discord.Interaction, text: str) -> None:
        t = text.strip()
        if len(t) > 4000:
            await interaction.response.send_message(
                embed=user_hint("Too long", "Keep GCash text at or under 4000 characters."),
                ephemeral=True,
            )
            return
        if not interaction.guild:
            return
        await self._record_string_change(interaction.guild.id, interaction.user.id, gk.PAYMENT_GCASH_DETAILS, t)
        await interaction.response.send_message(
            embed=success_embed("Saved", "GCash embed body updated."),
            ephemeral=True,
        )

    @config_payment.command(name="paypal_link", description="PayPal payment link (https://…)")
    @app_commands.describe(url="Must start with http:// or https://")
    @can_manage_server_config()
    async def cfg_pay_paypal(self, interaction: discord.Interaction, url: str) -> None:
        if not _is_http_url(url):
            await interaction.response.send_message(
                embed=user_hint("Invalid URL", "Use a link starting with `http://` or `https://`."),
                ephemeral=True,
            )
            return
        if not interaction.guild:
            return
        await self._record_string_change(
            interaction.guild.id,
            interaction.user.id,
            gk.PAYMENT_PAYPAL_LINK,
            url.strip(),
        )
        await interaction.response.send_message(
            embed=success_embed("Saved", "PayPal link updated."),
            ephemeral=True,
        )

    @config_payment.command(name="kofi_link", description="Ko-fi page link (https://…)")
    @app_commands.describe(url="Must start with http:// or https://")
    @can_manage_server_config()
    async def cfg_pay_kofi(self, interaction: discord.Interaction, url: str) -> None:
        if not _is_http_url(url):
            await interaction.response.send_message(
                embed=user_hint("Invalid URL", "Use a link starting with `http://` or `https://`."),
                ephemeral=True,
            )
            return
        if not interaction.guild:
            return
        await self._record_string_change(
            interaction.guild.id,
            interaction.user.id,
            gk.PAYMENT_KOFI_LINK,
            url.strip(),
        )
        await interaction.response.send_message(
            embed=success_embed("Saved", "Ko-fi link updated."),
            ephemeral=True,
        )

    @config_payment.command(
        name="gcash_qr",
        description="Direct image URL for the GCash QR (png/jpg)",
    )
    @app_commands.describe(url="Must start with http:// or https://")
    @can_manage_server_config()
    async def cfg_pay_gcash_qr(self, interaction: discord.Interaction, url: str) -> None:
        if not _is_http_url(url):
            await interaction.response.send_message(
                embed=user_hint("Invalid URL", "Use a link starting with `http://` or `https://`."),
                ephemeral=True,
            )
            return
        if not interaction.guild:
            return
        await self._record_string_change(
            interaction.guild.id,
            interaction.user.id,
            gk.PAYMENT_GCASH_QR_URL,
            url.strip(),
        )
        await interaction.response.send_message(
            embed=success_embed("Saved", "GCash QR image URL updated."),
            ephemeral=True,
        )

    @config_payment.command(
        name="paypal_qr",
        description="Direct image URL for the PayPal QR (png/jpg)",
    )
    @app_commands.describe(url="Must start with http:// or https://")
    @can_manage_server_config()
    async def cfg_pay_paypal_qr(self, interaction: discord.Interaction, url: str) -> None:
        if not _is_http_url(url):
            await interaction.response.send_message(
                embed=user_hint("Invalid URL", "Use a link starting with `http://` or `https://`."),
                ephemeral=True,
            )
            return
        if not interaction.guild:
            return
        await self._record_string_change(
            interaction.guild.id,
            interaction.user.id,
            gk.PAYMENT_PAYPAL_QR_URL,
            url.strip(),
        )
        await interaction.response.send_message(
            embed=success_embed("Saved", "PayPal QR image URL updated."),
            ephemeral=True,
        )

    @config.command(name="view", description="Show all channel, role, and payment mappings")
    @can_manage_server_config()
    async def config_view(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        rows = await db.list_guild_settings(interaction.guild.id)
        str_rows = await db.list_guild_string_settings(interaction.guild.id)
        lines = status_lines_for_guild(interaction.guild, rows, str_rows)
        qrows = await db.list_quote_base_prices(interaction.guild.id)
        if qrows:
            lines.append("")
            lines.append(f"**Quote base price rows:** {len(qrows)}")
        chunks = chunk_lines(lines)
        pages = [
            info_embed(f"Server configuration ({i + 1}/{len(chunks)})", c[:4000])
            for i, c in enumerate(chunks)
        ]
        if len(pages) == 1:
            await interaction.response.send_message(embed=pages[0], ephemeral=True)
            return
        view = PagedEmbedView(pages, interaction.user.id)
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)

    @config.command(
        name="error_channel",
        description="Set where unhandled runtime errors are posted",
    )
    @app_commands.describe(
        channel="Private staff text channel for bot error alerts",
    )
    @can_manage_server_config()
    async def config_error_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        if not interaction.guild:
            return
        await self._record_int_change(
            interaction.guild.id,
            interaction.user.id,
            gk.ERROR_ALERT_CHANNEL,
            channel.id,
        )
        await interaction.response.send_message(
            embed=success_embed(
                "Saved",
                f"Runtime errors will alert in {channel.mention}.",
            ),
            ephemeral=True,
        )

    @config.command(
        name="check",
        description="Validate setup health and catch broken config before users hit errors",
    )
    @can_manage_server_config()
    async def config_check(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return

        guild = interaction.guild
        rows = await db.list_guild_settings(guild.id)
        str_rows = await db.list_guild_string_settings(guild.id)
        ok: list[str] = []
        warn: list[str] = []
        err: list[str] = []

        def _role_exists(key: str) -> bool:
            rid = rows.get(key)
            return bool(rid and guild.get_role(int(rid)))

        def _channel_exists(key: str) -> bool:
            cid = rows.get(key)
            return bool(cid and guild.get_channel(int(cid)))

        payment_values = [str_rows.get(k, "").strip() for k in gk.PAYMENT_ALL_KEYS]
        if _channel_exists(gk.PAYMENT_CHANNEL):
            if any(payment_values):
                ok.append("Payment channel has at least one payment field configured.")
            else:
                err.append("Payment channel is set but all payment methods are empty.")
        else:
            warn.append("Payment channel is not set.")

        if await db.shop_is_open_db():
            if _role_exists(gk.TOS_AGREED_ROLE):
                ok.append("Shop is open and TOS role exists.")
            else:
                err.append("Shop is open but TOS agreed role is missing.")
        else:
            ok.append("Shop is currently closed.")

        btns = await db.list_ticket_buttons(guild.id)
        if btns:
            if _channel_exists(gk.TICKET_CATEGORY):
                ok.append("Ticket buttons exist and ticket category is configured.")
            else:
                err.append("Ticket buttons exist but New tickets category is missing.")
        else:
            warn.append("No ticket buttons configured yet.")

        wt = rows.get(gk.WARN_THRESHOLD_KEY)
        if wt is not None:
            if _channel_exists(gk.WARN_LOG_CHANNEL):
                ok.append("Warn threshold and warn log channel are configured.")
            else:
                err.append("Warn threshold is set but warn log channel is missing.")
        else:
            warn.append("Warn threshold uses default (3).")

        if _channel_exists(gk.TOS_CHANNEL):
            panel = await db.get_persist_panel("tos")
            if panel:
                ok.append("TOS channel is set and TOS panel was deployed.")
            else:
                warn.append("TOS channel is set but TOS panel is not deployed yet (`/deploy tos`).")
        else:
            warn.append("TOS channel is not set.")

        total_checks = len(ok) + len(warn) + len(err)
        lines = []
        lines.extend([f"✅ {x}" for x in ok])
        lines.extend([f"⚠️ {x}" for x in warn])
        lines.extend([f"❌ {x}" for x in err])
        summary = f"Checks: **{total_checks}** | ✅ {len(ok)} | ⚠️ {len(warn)} | ❌ {len(err)}"
        emb = info_embed("Configuration health check", "\n".join(lines)[:3900] or "No checks run.")
        emb.add_field(name="Summary", value=summary, inline=False)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @config.command(
        name="progress",
        description="Show setup completion progress checklist",
    )
    @can_manage_server_config()
    async def config_progress(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        guild = interaction.guild
        rows = await db.list_guild_settings(guild.id)
        str_rows = await db.list_guild_string_settings(guild.id)

        required_checks: list[tuple[bool, str]] = []
        optional_checks: list[tuple[bool, str]] = []

        def _role_ok(key: str) -> bool:
            rid = rows.get(key)
            return bool(rid and guild.get_role(int(rid)))

        def _chan_ok(key: str) -> bool:
            cid = rows.get(key)
            return bool(cid and guild.get_channel(int(cid)))

        required_checks.append((True, "Bot token and environment"))
        required_checks.append((_role_ok(gk.STAFF_ROLE), "Staff role configured"))
        required_checks.append((_chan_ok(gk.TICKET_CATEGORY), "Ticket category set"))
        required_checks.append((_role_ok(gk.TOS_AGREED_ROLE), "TOS role set"))
        required_checks.append((bool(await db.get_persist_panel("tos")), "TOS panel deployed"))
        required_checks.append((_chan_ok(gk.QUEUE_CHANNEL), "Queue channel set"))

        payment_ready = any(str_rows.get(k, "").strip() for k in gk.PAYMENT_ALL_KEYS)
        required_checks.append((payment_ready, "At least one payment method configured"))

        optional_checks.append((_chan_ok(gk.TRANSCRIPT_CHANNEL), "Transcript channel set"))
        optional_checks.append((_chan_ok(gk.WARN_LOG_CHANNEL), "Warn log channel set"))
        optional_checks.append((_chan_ok(gk.ORDER_NOTIFS_CHANNEL), "Order notifications channel set"))

        lines: list[str] = []
        done_required = 0
        for ok, label in required_checks:
            if ok:
                done_required += 1
                lines.append(f"✅ {label}")
            else:
                lines.append(f"❌ {label}")
        lines.append("")
        for ok, label in optional_checks:
            lines.append(f"✅ {label}" if ok else f"⚠️ {label}")

        total_required = len(required_checks)
        progress_line = f"Progress: **{done_required} / {total_required}** required steps complete."
        emb = info_embed("Setup progress — Mika Shop", "\n".join(lines)[:3900])
        emb.add_field(name="Summary", value=progress_line + "\nRun `/setup` to continue.", inline=False)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @config.command(name="reset", description="Clear one configuration group (requires confirmation)")
    @app_commands.describe(group="Which group to clear")
    @app_commands.choices(
        group=[
            app_commands.Choice(name="Tickets & panels", value="tickets"),
            app_commands.Choice(name="Queue & orders", value="queue"),
            app_commands.Choice(name="Shop & TOS", value="shop"),
            app_commands.Choice(name="Payment", value="payment"),
            app_commands.Choice(name="Channels & roles", value="channels_roles"),
            app_commands.Choice(name="Pricing (quotes only)", value="pricing"),
        ]
    )
    @can_manage_server_config()
    async def config_reset(
        self, interaction: discord.Interaction, group: str
    ) -> None:
        if not interaction.guild:
            return
        if group == "pricing":
            view = ConfirmResetView(
                interaction.guild.id, group, [], [], pricing=True, changed_by=interaction.user.id
            )
            await interaction.response.send_message(
                embed=user_warn(
                    "Confirm reset",
                    "This deletes **all quote prices, discounts, and currency toggles** for this server.",
                ),
                view=view,
                ephemeral=True,
            )
            return

        int_keys, str_keys = RESET_GROUP_KEYS[group]
        view = ConfirmResetView(
            interaction.guild.id, group, int_keys, str_keys, pricing=False, changed_by=interaction.user.id
        )
        await interaction.response.send_message(
            embed=user_warn(
                "Confirm reset",
                f"This removes saved **{group}** keys from the database. Continue?",
            ),
            view=view,
            ephemeral=True,
        )

    @config.command(name="log", description="Show recent config change log")
    @can_manage_server_config()
    async def config_log(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        rows = await db.list_config_audit_log(interaction.guild.id, 20)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("Config log", "No config changes logged yet."),
                ephemeral=True,
            )
            return
        lines = []
        for r in rows:
            lines.append(
                f"`{r['changed_at']}` key=`{r['key']}` by <@{r['changed_by']}>\n"
                f"old: `{(r.get('old_value') or 'None')[:80]}` -> new: `{(r.get('new_value') or 'None')[:80]}`"
            )
        chunks = chunk_lines(lines, max_chars=3500)
        pages = [
            info_embed(f"Config change log ({i + 1}/{len(chunks)})", c[:4000])
            for i, c in enumerate(chunks)
        ]
        if len(pages) == 1:
            await interaction.response.send_message(embed=pages[0], ephemeral=True)
            return
        view = PagedEmbedView(pages, interaction.user.id)
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)

    @config.command(name="export", description="Export current guild config JSON")
    @can_manage_server_config()
    async def config_export(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        payload = {
            "guild_id": interaction.guild.id,
            "settings": await db.list_guild_settings(interaction.guild.id),
            "string_settings": await db.list_guild_string_settings(interaction.guild.id),
        }
        raw = json.dumps(payload, ensure_ascii=False, indent=2)
        await interaction.response.send_message(
            embed=success_embed("Config export", "Attached JSON export file."),
            file=discord.File(fp=io.BytesIO(raw.encode("utf-8")), filename="config-export.json"),
            ephemeral=True,
        )

    @config.command(name="import", description="Import config JSON and apply after confirmation snapshot")
    @app_commands.describe(file="JSON file exported from /config export")
    @can_manage_server_config()
    async def config_import(self, interaction: discord.Interaction, file: discord.Attachment) -> None:
        if not interaction.guild:
            return
        if not file.filename.lower().endswith(".json"):
            await interaction.response.send_message(
                embed=user_hint("Invalid file", "Attach `.json` config export file."),
                ephemeral=True,
            )
            return
        raw = (await file.read()).decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            await interaction.response.send_message(
                embed=user_hint("Invalid JSON", "Could not parse file."),
                ephemeral=True,
            )
            return
        settings = payload.get("settings", {}) or {}
        str_settings = payload.get("string_settings", {}) or {}
        await db.create_config_snapshot(interaction.guild.id, interaction.user.id)
        cur_int = list((await db.list_guild_settings(interaction.guild.id)).keys())
        cur_str = list((await db.list_guild_string_settings(interaction.guild.id)).keys())
        await db.delete_guild_settings_keys(interaction.guild.id, cur_int)
        await db.delete_guild_string_settings_keys(interaction.guild.id, cur_str)
        for k, v in settings.items():
            await db.set_guild_setting(interaction.guild.id, str(k), int(v))
            await db.log_config_change(interaction.guild.id, interaction.user.id, str(k), None, str(v))
        for k, v in str_settings.items():
            await db.set_guild_string_setting(interaction.guild.id, str(k), str(v))
            await db.log_config_change(interaction.guild.id, interaction.user.id, str(k), None, str(v))
        await interaction.response.send_message(
            embed=success_embed("Config import complete", "Imported values applied."),
            ephemeral=True,
        )

    @config.command(name="restore", description="Restore config from recent snapshot id")
    @app_commands.describe(snapshot_id="Snapshot id from `/config snapshots`")
    @can_manage_server_config()
    async def config_restore(self, interaction: discord.Interaction, snapshot_id: int) -> None:
        if not interaction.guild:
            return
        await db.create_config_snapshot(interaction.guild.id, interaction.user.id)
        ok = await db.apply_config_snapshot(interaction.guild.id, snapshot_id)
        if not ok:
            await interaction.response.send_message(
                embed=user_hint("Restore failed", "Snapshot id not found for this guild."),
                ephemeral=True,
            )
            return
        await db.log_config_change(
            interaction.guild.id,
            interaction.user.id,
            "config.restore",
            None,
            f"snapshot:{snapshot_id}",
        )
        await interaction.response.send_message(
            embed=success_embed("Config restored", f"Applied snapshot **#{snapshot_id}**."),
            ephemeral=True,
        )

    @config.command(name="snapshots", description="List recent config snapshots")
    @can_manage_server_config()
    async def config_snapshots(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        rows = await db.list_config_snapshots(interaction.guild.id, 5)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("Config snapshots", "No snapshots yet."),
                ephemeral=True,
            )
            return
        lines = [
            f"**#{r['id']}** — `{r['created_at']}` by <@{r['created_by']}>"
            for r in rows
        ]
        await interaction.response.send_message(
            embed=info_embed("Recent config snapshots", "\n".join(lines)),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ConfigCog(bot))
