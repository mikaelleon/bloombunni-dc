"""Async helpers to resolve per-guild channels/roles from the database."""

from __future__ import annotations

import discord

import database as db
import guild_keys as gk


async def get_setting_int(guild_id: int, key: str) -> int | None:
    return await db.get_guild_setting(guild_id, key)


async def get_text_channel(
    guild: discord.Guild, key: str
) -> discord.TextChannel | None:
    cid = await get_setting_int(guild.id, key)
    if not cid:
        return None
    ch = guild.get_channel(cid)
    if isinstance(ch, discord.TextChannel):
        return ch
    return None


async def get_category(
    guild: discord.Guild, key: str
) -> discord.CategoryChannel | None:
    cid = await get_setting_int(guild.id, key)
    if not cid:
        return None
    ch = guild.get_channel(cid)
    return ch if isinstance(ch, discord.CategoryChannel) else None


async def get_role(guild: discord.Guild, key: str) -> discord.Role | None:
    rid = await get_setting_int(guild.id, key)
    if not rid:
        return None
    return guild.get_role(rid)


async def ticket_category_ids(guild_id: int) -> set[int]:
    """Category IDs valid for /queue ticket channel picker."""
    out: set[int] = set()
    for k in (
        gk.TICKET_CATEGORY,
        gk.NOTED_CATEGORY,
        gk.PROCESSING_CATEGORY,
    ):
        v = await db.get_guild_setting(guild_id, k)
        if v:
            out.add(int(v))
    return out


async def is_payment_config_complete(guild_id: int) -> bool:
    """All payment panel strings set via `/config payment` subcommands."""
    for key in gk.PAYMENT_ALL_KEYS:
        v = await db.get_guild_string_setting(guild_id, key)
        if not v or not str(v).strip():
            return False
    return True
