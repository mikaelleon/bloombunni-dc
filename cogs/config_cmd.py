"""Read-only and reset helpers — replaces removed `/serverconfig` slash tree."""

from __future__ import annotations

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
    ) -> None:
        super().__init__(timeout=120.0)
        self.guild_id = guild_id
        self.group = group
        self.int_keys = int_keys
        self.str_keys = str_keys
        self.pricing = pricing

    @discord.ui.button(label="Confirm reset", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if self.pricing:
            await db.clear_quote_data_for_guild(self.guild_id)
            await interaction.response.edit_message(
                embed=success_embed("Reset", "Quote prices and related rows cleared for this server."),
                view=None,
            )
            return
        await db.delete_guild_settings_keys(self.guild_id, self.int_keys)
        await db.delete_guild_string_settings_keys(self.guild_id, self.str_keys)
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
        await db.set_guild_string_setting(interaction.guild.id, gk.PAYMENT_GCASH_DETAILS, t)
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
        await db.set_guild_string_setting(
            interaction.guild.id, gk.PAYMENT_PAYPAL_LINK, url.strip()
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
        await db.set_guild_string_setting(
            interaction.guild.id, gk.PAYMENT_KOFI_LINK, url.strip()
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
        await db.set_guild_string_setting(
            interaction.guild.id, gk.PAYMENT_GCASH_QR_URL, url.strip()
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
        await db.set_guild_string_setting(
            interaction.guild.id, gk.PAYMENT_PAYPAL_QR_URL, url.strip()
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
        await db.set_guild_setting(interaction.guild.id, gk.ERROR_ALERT_CHANNEL, channel.id)
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
                interaction.guild.id, group, [], [], pricing=True
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
            interaction.guild.id, group, int_keys, str_keys, pricing=False
        )
        await interaction.response.send_message(
            embed=user_warn(
                "Confirm reset",
                f"This removes saved **{group}** keys from the database. Continue?",
            ),
            view=view,
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ConfigCog(bot))
