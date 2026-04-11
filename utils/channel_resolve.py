"""Resolve Discord channels/categories from user input (mention, ID, or slash picker)."""

from __future__ import annotations

import re

import discord

# Matches <#123456789012345678> (channel mention from Discord)
_MENTION_CHANNEL = re.compile(r"^<#(\d+)>$")


def parse_snowflake(text: object) -> int | None:
    """Parse a channel mention, raw ID string, int, or object with ``.id`` (e.g. AppCommandChannel)."""
    if text is None:
        return None
    if isinstance(text, int):
        return text
    if not isinstance(text, str):
        sid = getattr(text, "id", None)
        if isinstance(sid, int):
            return sid
        return None
    raw = text.strip()
    if not raw:
        return None
    m = _MENTION_CHANNEL.match(raw)
    if m:
        return int(m.group(1))
    if raw.isdigit():
        return int(raw)
    return None


def resolve_text_channel(
    guild: discord.Guild, channel: object
) -> discord.TextChannel | None:
    """Resolve a text or announcement channel from string, picker object, or TextChannel."""
    if isinstance(channel, discord.TextChannel):
        if channel.guild is not None and channel.guild.id == guild.id:
            return channel
        return None
    sid = parse_snowflake(channel)
    if sid is None:
        return None
    ch = guild.get_channel(sid)
    return ch if isinstance(ch, discord.TextChannel) else None


def resolve_category(
    guild: discord.Guild, category: object
) -> discord.CategoryChannel | None:
    """Resolve a category from string ID, picker object, or CategoryChannel."""
    if isinstance(category, discord.CategoryChannel):
        if category.guild is not None and category.guild.id == guild.id:
            return category
        return None
    sid = parse_snowflake(category)
    if sid is None:
        return None
    ch = guild.get_channel(sid)
    return ch if isinstance(ch, discord.CategoryChannel) else None
