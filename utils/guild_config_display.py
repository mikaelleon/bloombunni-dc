"""Build human-readable guild config lines for /config view (shared)."""

from __future__ import annotations

from typing import Any

import discord

import guild_keys as gk

_CHANNEL_LABELS = {v: n for n, v in gk.CHANNEL_SLOT_CHOICES}
_CATEGORY_LABELS = {v: n for n, v in gk.CATEGORY_SLOT_CHOICES}
_ROLE_LABELS = {v: n for n, v in gk.ROLE_SLOT_CHOICES}


def status_lines_for_guild(
    guild: discord.Guild, rows: dict[str, int], str_rows: dict[str, str]
) -> list[str]:
    lines: list[str] = []
    for label_map in (_CHANNEL_LABELS, _CATEGORY_LABELS, _ROLE_LABELS):
        for key, human in label_map.items():
            sid = rows.get(key)
            if not sid:
                lines.append(f"**{human}** — _not set_")
                continue
            ch = guild.get_channel(sid)
            rl = guild.get_role(sid)
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
    prefix = str_rows.get(gk.ORDER_ID_PREFIX)
    lines.append("")
    lines.append(f"**Order ID prefix** — `{prefix}`" if prefix else "**Order ID prefix** — _not set_ (defaults to MIKA)_")
    wt = rows.get(gk.WARN_THRESHOLD_KEY)
    lines.append(
        f"**Warn threshold** — {wt}"
        if wt is not None
        else "**Warn threshold** — _default 3_"
    )
    return lines


def chunk_lines(lines: list[str], max_chars: int = 3500) -> list[str]:
    text = "\n".join(lines)
    if not text:
        return [""]
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    rest = text
    while rest:
        if len(rest) <= max_chars:
            chunks.append(rest)
            break
        cut = rest.rfind("\n", 0, max_chars)
        if cut <= 0:
            cut = max_chars
        chunks.append(rest[:cut])
        rest = rest[cut:].lstrip("\n")
    return chunks
