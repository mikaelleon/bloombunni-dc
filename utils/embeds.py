"""Consistent embed helpers."""

from __future__ import annotations

from typing import Any

import discord

PRIMARY = 0x669B9A
DARK = 0x135352
LIGHT = 0xF4ECED
DANGER = 0x2D2325
WARNING = 0xF4A261
SUCCESS = 0x2D6A4F  # same as success embed color


def success_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=SUCCESS)


def error_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=DANGER)


def info_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=PRIMARY)


def warning_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=WARNING)


def _status_badge(status: str) -> str:
    m = {
        "Queued": "🟡 Queued",
        "Awaiting Payment": "🟡 Awaiting Payment",
        "Noted": "🔵 Noted",
        "WIP": "🔵 WIP",
        "Processing": "🟣 Processing",
        "Done": "✅ Done",
        "Cancelled": "❌ Cancelled",
    }
    return m.get(status, status)


def queue_embed(orders: list[dict[str, Any]]) -> discord.Embed:
    embed = discord.Embed(
        title="📋 Commission Queue",
        description="Current active orders.",
        color=PRIMARY,
    )
    if not orders:
        embed.set_footer(text="No active orders.")
        return embed
    lines: list[str] = []
    for o in orders:
        oid = o.get("order_id", "?")
        name = o.get("client_name", "Unknown")
        ctype = o.get("commission_type", "")
        tier = o.get("tier", "")
        st = _status_badge(str(o.get("status", "")))
        lines.append(f"`[{oid}]` **@{name}** | {ctype} • {tier} | {st}")
    embed.description = "\n".join(lines)
    return embed
