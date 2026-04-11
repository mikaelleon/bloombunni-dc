"""Consistent embed helpers."""

from __future__ import annotations

from typing import Any

import discord

PRIMARY = 0x669B9A
DARK = 0x135352
LIGHT = 0xF4ECED
DANGER = 0x2D2325
WARNING = 0xF4A261
SUCCESS = 0x2D6A4F


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
