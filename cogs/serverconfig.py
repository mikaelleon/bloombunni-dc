"""Per-guild channel and role mapping (replaces .env IDs)."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import guild_keys as gk
from utils.checks import can_manage_server_config
from utils.embeds import info_embed, success_embed


def _label_map(choices: list[tuple[str, str]]) -> dict[str, str]:
    return {v: n for n, v in choices}


_CHANNEL_LABELS = _label_map(gk.CHANNEL_SLOT_CHOICES)
_CATEGORY_LABELS = _label_map(gk.CATEGORY_SLOT_CHOICES)
_ROLE_LABELS = _label_map(gk.ROLE_SLOT_CHOICES)


class ServerConfigCog(commands.Cog, name="ServerConfigCog"):
    serverconfig = app_commands.Group(
        name="serverconfig",
        description="Choose channels and roles for this server (no IDs in .env)",
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
        if not isinstance(channel, (discord.TextChannel, discord.NewsChannel)):
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

    @serverconfig.command(name="show", description="List current channel and role mappings")
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
        if not lines:
            lines = ["Nothing configured yet. Use `/serverconfig channel`, `category`, and `role`."]
        await interaction.response.send_message(
            embed=info_embed("Server configuration", "\n".join(lines)[:4000]),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerConfigCog(bot))
