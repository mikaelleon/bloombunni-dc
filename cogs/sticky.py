"""Sticky embeds that stay at the bottom of channels."""

from __future__ import annotations

import asyncio
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils.checks import is_staff
from utils.embeds import DEFAULT_EMBED_COLOR, PRIMARY, info_embed, user_hint, user_warn
from utils.logging_setup import get_logger

log = get_logger("sticky")

DEFAULT_STICKY_COLOR = DEFAULT_EMBED_COLOR


def _parse_hex_color(text: str | None) -> int:
    if not text or not str(text).strip():
        return DEFAULT_STICKY_COLOR
    s = str(text).strip()
    if s.startswith("#"):
        s = s[1:]
    return int(s, 16)


def _validate_http_url(url: str | None, label: str) -> str | None:
    if url is None or not str(url).strip():
        return None
    u = str(url).strip()
    if not u.startswith("http"):
        raise ValueError(f"{label} must start with http:// or https://")
    return u


def embed_from_sticky_row(row: dict) -> discord.Embed:
    color = DEFAULT_STICKY_COLOR
    try:
        color = _parse_hex_color(row.get("color"))
    except ValueError:
        color = DEFAULT_STICKY_COLOR
    e = discord.Embed(
        title=row.get("title") or "",
        description=row.get("description") or "",
        color=color,
    )
    foot = row.get("footer")
    if foot:
        e.set_footer(text=str(foot))
    img = row.get("image_url")
    if img:
        e.set_image(url=str(img))
    th = row.get("thumbnail_url")
    if th:
        e.set_thumbnail(url=str(th))
    return e


class StickiesPager(discord.ui.View):
    def __init__(self, user_id: int, pages: list[discord.Embed]) -> None:
        super().__init__(timeout=300.0)
        self.user_id = user_id
        self.pages = pages
        self.idx = 0

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your list.", ephemeral=True)
            return
        self.idx = max(0, self.idx - 1)
        await interaction.response.edit_message(embed=self.pages[self.idx], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your list.", ephemeral=True)
            return
        self.idx = min(len(self.pages) - 1, self.idx + 1)
        await interaction.response.edit_message(embed=self.pages[self.idx], view=self)


class StickyCog(commands.Cog, name="StickyCog"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.sticky_channels: set[int] = set()
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock_for(self, channel_id: int) -> asyncio.Lock:
        if channel_id not in self._locks:
            self._locks[channel_id] = asyncio.Lock()
        return self._locks[channel_id]

    async def refresh_sticky_cache(self) -> None:
        ids = await db.all_sticky_channel_ids()
        self.sticky_channels = set(ids)

    async def cog_load(self) -> None:
        await self.refresh_sticky_cache()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if not message.guild:
            return
        cid = message.channel.id
        if cid not in self.sticky_channels:
            return

        row = await db.get_sticky(cid)
        if not row:
            return

        lock = self._lock_for(cid)
        async with lock:
            await asyncio.sleep(1.5)
            row = await db.get_sticky(cid)
            if not row:
                return
            ch = message.channel
            if not isinstance(ch, discord.TextChannel):
                return

            mid = row.get("last_message_id")
            if mid:
                try:
                    old = await ch.fetch_message(int(mid))
                    await old.delete()
                except discord.NotFound:
                    pass
                except discord.Forbidden:
                    log.warning("Sticky: cannot delete message in channel %s", cid)
                    return

            emb = embed_from_sticky_row(row)
            try:
                new_msg = await ch.send(embed=emb)
            except discord.Forbidden:
                log.warning("Sticky: cannot send in channel %s", cid)
                return

            await db.set_sticky_last_message_id(cid, new_msg.id)

    @app_commands.command(name="sticky", description="Set a sticky embed at the bottom of a channel (staff)")
    @app_commands.describe(
        channel="Target channel",
        title="Embed title",
        description="Embed description",
        color="Hex color e.g. #242429",
        image_url="Main image URL",
        footer="Footer text",
        thumbnail_url="Thumbnail image URL",
    )
    @is_staff()
    async def sticky_cmd(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        description: str,
        color: str | None = None,
        image_url: str | None = None,
        footer: str | None = None,
        thumbnail_url: str | None = None,
    ) -> None:
        try:
            if color:
                _parse_hex_color(color)
            else:
                color = "#242429"
        except ValueError:
            await interaction.response.send_message(
                embed=user_hint(
                    "Invalid color",
                    "Use a hex color like **`#RRGGBB`** (example: `#242429`).",
                ),
                ephemeral=True,
            )
            return
        try:
            image_url = _validate_http_url(image_url, "Image URL")
            thumbnail_url = _validate_http_url(thumbnail_url, "Thumbnail URL")
        except ValueError as e:
            await interaction.response.send_message(
                embed=user_hint("Invalid URL", str(e)), ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        await db.upsert_sticky_full(
            channel.id,
            title,
            description,
            color or "#242429",
            image_url,
            footer,
            thumbnail_url,
            None,
            interaction.user.id,
        )
        row = await db.get_sticky(channel.id)
        emb = embed_from_sticky_row(row)
        try:
            msg = await channel.send(embed=emb)
        except discord.Forbidden:
            await interaction.followup.send(
                embed=user_warn(
                    "Missing permissions",
                    "The bot can’t send messages in that channel — adjust channel overrides or pick another channel.",
                ),
                ephemeral=True,
            )
            return
        await db.set_sticky_last_message_id(channel.id, msg.id)
        await self.refresh_sticky_cache()

        confirm = discord.Embed(
            title="Sticky saved",
            description=f"✅ Sticky set in {channel.mention}.",
            color=PRIMARY,
        )
        await interaction.followup.send(embeds=[confirm, emb], ephemeral=True)

    @app_commands.command(name="stickyupdate", description="Update fields on an existing sticky (staff)")
    @app_commands.describe(
        channel="Channel with sticky",
        title="Embed title",
        description="Embed description",
        color="Hex color",
        image_url="Main image URL",
        footer="Footer text",
        thumbnail_url="Thumbnail URL",
    )
    @is_staff()
    async def stickyupdate(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str | None = None,
        description: str | None = None,
        color: str | None = None,
        image_url: str | None = None,
        footer: str | None = None,
        thumbnail_url: str | None = None,
    ) -> None:
        before = await db.get_sticky(channel.id)
        if not before:
            await interaction.response.send_message(
                embed=user_hint(
                    "No sticky here yet",
                    "Create one with **`/sticky`** in that channel first.",
                ),
                ephemeral=True,
            )
            return

        provided = {o["name"] for o in (interaction.data or {}).get("options", [])}
        updatable = provided - {"channel"}
        if not updatable:
            await interaction.response.send_message(
                embed=user_hint(
                    "Nothing to change",
                    "Add at least one field to update (title, description, color, …).",
                ),
                ephemeral=True,
            )
            return

        if "color" in provided and color is not None:
            try:
                _parse_hex_color(color)
            except ValueError:
                await interaction.response.send_message(
                    embed=user_hint(
                        "Invalid color",
                        "Use a hex color like **`#RRGGBB`**.",
                    ),
                    ephemeral=True,
                )
                return
        try:
            if "image_url" in provided and image_url is not None:
                image_url = _validate_http_url(image_url, "Image URL")
            if "thumbnail_url" in provided and thumbnail_url is not None:
                thumbnail_url = _validate_http_url(thumbnail_url, "Thumbnail URL")
        except ValueError as e:
            await interaction.response.send_message(
                embed=user_hint("Invalid URL", str(e)), ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        kw: dict[str, Any] = {}
        if "title" in provided:
            kw["title"] = title
        if "description" in provided:
            kw["description"] = description
        if "color" in provided:
            kw["color"] = color
        if "image_url" in provided:
            kw["image_url"] = image_url
        if "footer" in provided:
            kw["footer"] = footer
        if "thumbnail_url" in provided:
            kw["thumbnail_url"] = thumbnail_url

        ok = await db.patch_sticky(channel.id, kw)
        if not ok:
            await interaction.followup.send(
                embed=user_warn("Couldn’t save changes", "The database update failed — try again or check bot/database access."), ephemeral=True
            )
            return

        row = await db.get_sticky(channel.id)
        assert row
        emb_before = embed_from_sticky_row(before)
        emb_after = embed_from_sticky_row(row)

        mid = row.get("last_message_id")
        if mid and isinstance(channel, discord.TextChannel):
            try:
                old = await channel.fetch_message(int(mid))
                await old.delete()
            except discord.NotFound:
                pass
            except discord.Forbidden:
                log.warning("Sticky update: cannot delete old message in %s", channel.id)

        try:
            new_msg = await channel.send(embed=emb_after)
        except discord.Forbidden:
            await interaction.followup.send(
                embed=user_warn("Missing permissions", "The bot can’t post in that channel after the update."),
                ephemeral=True,
            )
            return
        await db.set_sticky_last_message_id(channel.id, new_msg.id)
        await self.refresh_sticky_cache()

        header = discord.Embed(
            title="Sticky updated",
            description="Before → after preview:",
            color=PRIMARY,
        )
        await interaction.followup.send(
            embeds=[header, emb_before, emb_after],
            ephemeral=True,
        )

    @app_commands.command(name="unsticky", description="Remove sticky from a channel (staff)")
    @app_commands.describe(channel="Channel")
    @is_staff()
    async def unsticky_cmd(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        row = await db.get_sticky(channel.id)
        if not row:
            await interaction.response.send_message(
                embed=user_hint(
                    "No sticky here",
                    "There’s no sticky configured for that channel.",
                ),
                ephemeral=True,
            )
            return

        mid = row.get("last_message_id")
        if mid:
            try:
                m = await channel.fetch_message(int(mid))
                await m.delete()
            except discord.NotFound:
                pass
            except discord.Forbidden:
                log.warning("Unsticky: cannot delete message in %s", channel.id)

        await db.delete_sticky(channel.id)
        await self.refresh_sticky_cache()
        await interaction.response.send_message(
            f"✅ Sticky removed from {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(name="stickies", description="List all active stickies (staff)")
    @is_staff()
    async def stickies_list(self, interaction: discord.Interaction) -> None:
        rows = await db.list_all_stickies()
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("Stickies", "No active sticky messages."),
                ephemeral=True,
            )
            return

        chunk_size = 5
        pages: list[discord.Embed] = []
        for i in range(0, len(rows), chunk_size):
            part = rows[i : i + chunk_size]
            lines: list[str] = []
            for r in part:
                ch_mention = f"<#{r['channel_id']}>"
                t = r.get("title") or "(no title)"
                updated = r.get("updated_at") or "—"
                creator = r.get("created_by")
                who = f"<@{creator}>" if creator else "—"
                lines.append(f"{ch_mention}\n**{t}** · updated `{updated}` · by {who}")
            pages.append(
                discord.Embed(
                    title="Active stickies",
                    description="\n\n".join(lines),
                    color=PRIMARY,
                )
            )
        v = StickiesPager(interaction.user.id, pages)
        await interaction.response.send_message(embed=pages[0], view=v, ephemeral=True)

    @app_commands.command(name="stickypreview", description="Preview sticky config for a channel (staff)")
    @app_commands.describe(channel="Channel")
    @is_staff()
    async def stickypreview(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        row = await db.get_sticky(channel.id)
        if not row:
            await interaction.response.send_message(
                embed=user_hint(
                    "No sticky here",
                    "There’s no sticky configured for that channel.",
                ),
                ephemeral=True,
            )
            return
        emb = embed_from_sticky_row(row)
        prev = discord.Embed(
            title="Sticky preview",
            description=f"Configuration for {channel.mention}",
            color=PRIMARY,
        )
        await interaction.response.send_message(
            embeds=[prev, emb],
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StickyCog(bot))
