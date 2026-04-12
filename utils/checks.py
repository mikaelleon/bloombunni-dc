"""Reusable app_commands checks."""

from __future__ import annotations

import discord
from discord import app_commands

import database as db
import guild_keys as gk
from utils.embeds import user_warn


def is_staff():
    async def predicate(interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            raise app_commands.CheckFailure("This command can only be used in a server.")
        rid = await db.get_guild_setting(interaction.guild.id, gk.STAFF_ROLE)
        if not rid:
            raise app_commands.CheckFailure(
                "Staff role is not configured. Ask a server manager to run `/serverconfig`."
            )
        role = interaction.guild.get_role(int(rid))
        if role is None or role not in interaction.user.roles:
            raise app_commands.CheckFailure("You need the staff role to use this command.")
        return True

    return app_commands.check(predicate)


def has_tos():
    async def predicate(interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            raise app_commands.CheckFailure("This command can only be used in a server.")
        rid = await db.get_guild_setting(interaction.guild.id, gk.TOS_AGREED_ROLE)
        if not rid:
            raise app_commands.CheckFailure(
                "TOS role is not configured. Ask a server manager to run `/serverconfig`."
            )
        role = interaction.guild.get_role(int(rid))
        if role is None or role not in interaction.user.roles:
            raise app_commands.CheckFailure(
                "You must agree to the Terms of Service first. See the TOS channel."
            )
        return True

    return app_commands.check(predicate)


def shop_is_open():
    async def predicate(interaction) -> bool:
        if not await db.shop_is_open_db():
            raise app_commands.CheckFailure("The shop is currently closed. Please check back later.")
        return True

    return app_commands.check(predicate)


def can_manage_server_config():
    """Administrator, Manage Server, or configured staff role."""

    async def predicate(interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            raise app_commands.CheckFailure("This command can only be used in a server.")
        perms = interaction.user.guild_permissions
        if perms.administrator or perms.manage_guild:
            return True
        rid = await db.get_guild_setting(interaction.guild.id, gk.STAFF_ROLE)
        if rid:
            role = interaction.guild.get_role(int(rid))
            if role and role in interaction.user.roles:
                return True
        raise app_commands.CheckFailure(
            "You need **Manage Server**, **Administrator**, or the configured staff role."
        )

    return app_commands.check(predicate)


async def check_failure_response(interaction, error: Exception) -> None:
    """Send ephemeral embed for CheckFailure (friendly warning tone)."""
    if isinstance(error, app_commands.CheckFailure):
        msg = str(error) or "You cannot use this command right now."
        emb = user_warn("Heads up", msg)
        if interaction.response.is_done():
            await interaction.followup.send(embed=emb, ephemeral=True)
        else:
            await interaction.response.send_message(embed=emb, ephemeral=True)
