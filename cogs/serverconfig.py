"""Per-guild channel, role, and payment mapping (no .env except BOT_TOKEN)."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import guild_keys as gk
from utils.checks import can_manage_server_config
from utils.embeds import error_embed, info_embed, success_embed


def _label_map(choices: list[tuple[str, str]]) -> dict[str, str]:
    return {v: n for n, v in choices}


_CHANNEL_LABELS = _label_map(gk.CHANNEL_SLOT_CHOICES)
_CATEGORY_LABELS = _label_map(gk.CATEGORY_SLOT_CHOICES)
_ROLE_LABELS = _label_map(gk.ROLE_SLOT_CHOICES)


def _is_http_url(s: str) -> bool:
    t = str(s).strip().lower()
    return t.startswith("http://") or t.startswith("https://")


class ServerConfigCog(commands.Cog, name="ServerConfigCog"):
    serverconfig = app_commands.Group(
        name="serverconfig",
        description="Configure this server (channels, roles, payment) — no IDs in .env",
    )

    serverconfig_payment = app_commands.Group(
        name="payment",
        description="GCash / PayPal / Ko-fi text and QR image URLs for the payment panel",
        parent=serverconfig,
    )

    @serverconfig.command(name="channel", description="Set a text channel for a feature")
    @app_commands.describe(
        slot="Which feature this channel is for",
        channel="Pick the channel (text or announcement)",
    )
    @app_commands.choices(
        slot=[
            app_commands.Choice(name=n, value=v)
            for n, v in gk.CHANNEL_SLOT_CHOICES
        ]
    )
    @can_manage_server_config()
    async def serverconfig_channel(
        self,
        interaction: discord.Interaction,
        slot: str,
        channel: discord.abc.GuildChannel,
    ) -> None:
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=info_embed(
                    "Invalid channel",
                    "Choose a **text** or **announcement** channel for this slot.",
                ),
                ephemeral=True,
            )
            return
        await db.set_guild_setting(interaction.guild.id, slot, channel.id)
        label = _CHANNEL_LABELS.get(slot, slot)
        await interaction.response.send_message(
            embed=success_embed(
                "Saved",
                f"**{label}** → {channel.mention}",
            ),
            ephemeral=True,
        )

    @serverconfig.command(name="category", description="Set a category for tickets / order stages")
    @app_commands.describe(
        slot="Which stage",
        category="Pick the category",
    )
    @app_commands.choices(
        slot=[
            app_commands.Choice(name=n, value=v)
            for n, v in gk.CATEGORY_SLOT_CHOICES
        ]
    )
    @can_manage_server_config()
    async def serverconfig_category(
        self,
        interaction: discord.Interaction,
        slot: str,
        category: discord.CategoryChannel,
    ) -> None:
        await db.set_guild_setting(interaction.guild.id, slot, category.id)
        label = _CATEGORY_LABELS.get(slot, slot)
        await interaction.response.send_message(
            embed=success_embed("Saved", f"**{label}** → `{category.name}`"),
            ephemeral=True,
        )

    @serverconfig.command(name="role", description="Set a role for staff / TOS / shop")
    @app_commands.describe(
        slot="Which role",
        role="Pick the role",
    )
    @app_commands.choices(
        slot=[
            app_commands.Choice(name=n, value=v)
            for n, v in gk.ROLE_SLOT_CHOICES
        ]
    )
    @can_manage_server_config()
    async def serverconfig_role(
        self,
        interaction: discord.Interaction,
        slot: str,
        role: discord.Role,
    ) -> None:
        await db.set_guild_setting(interaction.guild.id, slot, role.id)
        label = _ROLE_LABELS.get(slot, slot)
        await interaction.response.send_message(
            embed=success_embed("Saved", f"**{label}** → {role.mention}"),
            ephemeral=True,
        )

    @serverconfig.command(name="show", description="List current channel, role, and payment mappings")
    @can_manage_server_config()
    async def serverconfig_show(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        rows = await db.list_guild_settings(interaction.guild.id)
        lines: list[str] = []
        for label_map in (_CHANNEL_LABELS, _CATEGORY_LABELS, _ROLE_LABELS):
            for key, human in label_map.items():
                sid = rows.get(key)
                if not sid:
                    lines.append(f"**{human}** — _not set_")
                    continue
                ch = interaction.guild.get_channel(sid)
                rl = interaction.guild.get_role(sid)
                if ch:
                    if isinstance(ch, discord.CategoryChannel):
                        lines.append(f"**{human}** — `{ch.name}` (category)")
                    else:
                        lines.append(f"**{human}** — {ch.mention}")
                elif rl:
                    lines.append(f"**{human}** — {rl.mention}")
                else:
                    lines.append(f"**{human}** — ID `{sid}` (missing — re-pick)")

        lines.append("")
        lines.append("**Payment panel (text / URLs)**")
        str_rows = await db.list_guild_string_settings(interaction.guild.id)
        for key in gk.PAYMENT_ALL_KEYS:
            human = gk.PAYMENT_FIELD_LABELS.get(key, key)
            val = str_rows.get(key)
            if not val:
                lines.append(f"**{human}** — _not set_")
            else:
                preview = val.replace("\n", " ")[:120]
                if len(val) > 120:
                    preview += "…"
                lines.append(f"**{human}** — `{preview}`")

        body = "\n".join(lines)[:4000]
        await interaction.response.send_message(
            embed=info_embed("Server configuration", body),
            ephemeral=True,
        )

    # --- /serverconfig payment (nested) ---

    @serverconfig_payment.command(
        name="gcash_details",
        description="Body text for the GCash button (name, number, instructions)",
    )
    @app_commands.describe(text="Plain text shown in the GCash embed (max ~4000 characters)")
    @can_manage_server_config()
    async def payment_gcash_details(self, interaction: discord.Interaction, text: str) -> None:
        t = text.strip()
        if len(t) > 4000:
            await interaction.response.send_message(
                embed=error_embed("Too long", "Keep GCash text at or under 4000 characters."),
                ephemeral=True,
            )
            return
        await db.set_guild_string_setting(interaction.guild.id, gk.PAYMENT_GCASH_DETAILS, t)
        await interaction.response.send_message(
            embed=success_embed("Saved", "GCash embed body updated."),
            ephemeral=True,
        )

    @serverconfig_payment.command(name="paypal_link", description="PayPal payment link (https://…)")
    @app_commands.describe(url="Must start with http:// or https://")
    @can_manage_server_config()
    async def payment_paypal_link(self, interaction: discord.Interaction, url: str) -> None:
        if not _is_http_url(url):
            await interaction.response.send_message(
                embed=error_embed("Invalid URL", "Use a link starting with `http://` or `https://`."),
                ephemeral=True,
            )
            return
        await db.set_guild_string_setting(
            interaction.guild.id, gk.PAYMENT_PAYPAL_LINK, url.strip()
        )
        await interaction.response.send_message(
            embed=success_embed("Saved", "PayPal link updated."),
            ephemeral=True,
        )

    @serverconfig_payment.command(name="kofi_link", description="Ko-fi page link (https://…)")
    @app_commands.describe(url="Must start with http:// or https://")
    @can_manage_server_config()
    async def payment_kofi_link(self, interaction: discord.Interaction, url: str) -> None:
        if not _is_http_url(url):
            await interaction.response.send_message(
                embed=error_embed("Invalid URL", "Use a link starting with `http://` or `https://`."),
                ephemeral=True,
            )
            return
        await db.set_guild_string_setting(
            interaction.guild.id, gk.PAYMENT_KOFI_LINK, url.strip()
        )
        await interaction.response.send_message(
            embed=success_embed("Saved", "Ko-fi link updated."),
            ephemeral=True,
        )

    @serverconfig_payment.command(
        name="gcash_qr",
        description="Direct image URL for the GCash QR (png/jpg)",
    )
    @app_commands.describe(url="Must start with http:// or https://")
    @can_manage_server_config()
    async def payment_gcash_qr(self, interaction: discord.Interaction, url: str) -> None:
        if not _is_http_url(url):
            await interaction.response.send_message(
                embed=error_embed("Invalid URL", "Use a link starting with `http://` or `https://`."),
                ephemeral=True,
            )
            return
        await db.set_guild_string_setting(
            interaction.guild.id, gk.PAYMENT_GCASH_QR_URL, url.strip()
        )
        await interaction.response.send_message(
            embed=success_embed("Saved", "GCash QR image URL updated."),
            ephemeral=True,
        )

    @serverconfig_payment.command(
        name="paypal_qr",
        description="Direct image URL for the PayPal QR (png/jpg)",
    )
    @app_commands.describe(url="Must start with http:// or https://")
    @can_manage_server_config()
    async def payment_paypal_qr(self, interaction: discord.Interaction, url: str) -> None:
        if not _is_http_url(url):
            await interaction.response.send_message(
                embed=error_embed("Invalid URL", "Use a link starting with `http://` or `https://`."),
                ephemeral=True,
            )
            return
        await db.set_guild_string_setting(
            interaction.guild.id, gk.PAYMENT_PAYPAL_QR_URL, url.strip()
        )
        await interaction.response.send_message(
            embed=success_embed("Saved", "PayPal QR image URL updated."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerConfigCog(bot))
