"""HTML transcript generation."""

from __future__ import annotations

import html
import io
from datetime import datetime, timezone

import discord


async def generate_transcript(
    channel: discord.TextChannel | discord.Thread,
) -> discord.File:
    """Fetch up to 500 messages (oldest first) and return HTML as discord.File."""
    messages: list[discord.Message] = []
    async for msg in channel.history(limit=500, oldest_first=True):
        messages.append(msg)

    guild_name = html.escape(channel.guild.name if channel.guild else "DM")
    ch_name = html.escape(channel.name)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    gen_time = datetime.now(timezone.utc).isoformat()

    parts: list[str] = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Transcript</title>",
        "<style>body{font-family:Segoe UI,sans-serif;background:#1e1e2e;color:#cdd6f4;padding:24px;}",
        ".meta{color:#94e2d5;margin-bottom:16px;} .msg{border-left:3px solid #669b9a;padding:8px 12px;margin:8px 0;background:#181825;}",
        ".author{font-weight:bold;color:#89dceb;} .time{color:#6c7086;font-size:0.85em;} blockquote{border-left:2px solid #669b9a;margin:4px 0;padding-left:8px;color:#bac2de;}",
        "a{color:#89b4fa;}</style></head><body>",
        f"<div class='meta'><strong>Server:</strong> {guild_name}<br>",
        f"<strong>Channel:</strong> #{ch_name}<br>",
        f"<strong>Generated:</strong> {html.escape(gen_time)}</div>",
        "<hr>",
    ]

    for msg in messages:
        author = html.escape(str(msg.author))
        avatar = msg.author.display_avatar.url if msg.author.display_avatar else ""
        mtime = msg.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        content = html.escape(msg.content or "").replace("\n", "<br>\n")

        parts.append("<div class='msg'>")
        if avatar:
            parts.append(
                f"<img src='{html.escape(avatar)}' width='32' height='32' style='vertical-align:middle;border-radius:50%;margin-right:8px;'>"
            )
        parts.append(
            f"<span class='author'>{author}</span> <span class='time'>{html.escape(mtime)}</span><br>"
        )
        if content:
            parts.append(f"<div>{content}</div>")

        for emb in msg.embeds:
            parts.append("<blockquote>")
            if emb.title:
                parts.append(f"<strong>{html.escape(emb.title)}</strong><br>")
            if emb.description:
                parts.append(html.escape(emb.description).replace("\n", "<br>\n"))
            parts.append("</blockquote>")

        for att in msg.attachments:
            parts.append(
                f"<div>📎 Attachment: <a href='{html.escape(att.url)}'>{html.escape(att.filename)}</a></div>"
            )

        parts.append("</div>")

    parts.append("</body></html>")
    html_out = "".join(parts)
    filename = f"transcript-{channel.name}-{ts}.html"
    data = html_out.encode("utf-8")
    return discord.File(io.BytesIO(data), filename=filename)
