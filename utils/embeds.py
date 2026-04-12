"""Consistent embed helpers — prefer user_hint / user_warn for member-facing messages."""

from __future__ import annotations

from typing import Any

import discord

# Default sidebar (#242429)
DEFAULT_EMBED_COLOR = 0x242429

PRIMARY = DEFAULT_EMBED_COLOR
DARK = DEFAULT_EMBED_COLOR
LIGHT = DEFAULT_EMBED_COLOR

# Queue / shop status panels (not ephemeral “errors”)
SUCCESS = 0x3BA55C
EMBED_ACCENT_RED = 0xC94C4C  # shop TOS banner, commissions closed — visible but not harsh
# Soft amber — limits, permissions, “can’t right now”
WARN_ORANGE = 0xE8A849
# Calm blue — invalid input, typos, “try this instead”
HINT_BLUE = 0x5B8FD8
# Back-compat for shop cog (status embeds)
DANGER = EMBED_ACCENT_RED
WARNING = WARN_ORANGE


def success_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=SUCCESS)


def user_hint(title: str, description: str) -> discord.Embed:
    """Suggestion-style reply: wrong input, missing config, or how to fix something."""
    return discord.Embed(title=title, description=description, color=HINT_BLUE)


def user_warn(title: str, description: str) -> discord.Embed:
    """Softer warning: permissions, shop closed, role missing — still friendly."""
    return discord.Embed(title=title, description=description, color=WARN_ORANGE)


def error_embed(title: str, description: str) -> discord.Embed:
    """Deprecated name: same as :func:`user_hint`. Prefer ``user_hint`` in new code."""
    return user_hint(title, description)


def info_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=PRIMARY)


def warning_embed(title: str, description: str) -> discord.Embed:
    """Neutral warning box (same palette as :func:`user_warn`)."""
    return user_warn(title, description)


def queue_embed(order: dict[str, Any], template_lines: str) -> discord.Embed:
    """Single queue entry embed: plain multi-line description from resolved templates."""
    return discord.Embed(description=template_lines, color=PRIMARY)
