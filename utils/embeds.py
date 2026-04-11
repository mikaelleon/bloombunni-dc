"""Consistent embed helpers."""

from __future__ import annotations

from typing import Any

import discord

# Default sidebar color for all bot embeds (#242429)
DEFAULT_EMBED_COLOR = 0x242429

PRIMARY = DEFAULT_EMBED_COLOR
DARK = DEFAULT_EMBED_COLOR
LIGHT = DEFAULT_EMBED_COLOR
DANGER = DEFAULT_EMBED_COLOR
WARNING = DEFAULT_EMBED_COLOR
SUCCESS = DEFAULT_EMBED_COLOR


def success_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=SUCCESS)


def error_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=DANGER)


def info_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=PRIMARY)


def warning_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=WARNING)


def queue_embed(order: dict[str, Any], template_lines: str) -> discord.Embed:
    """Single queue entry embed: plain multi-line description from resolved templates."""
    return discord.Embed(description=template_lines, color=PRIMARY)
