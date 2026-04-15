"""Embed builder commands: create, edit, list, showlist."""

from __future__ import annotations

import re
from difflib import get_close_matches
from datetime import datetime, timezone
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils.embeds import info_embed, success_embed, user_hint, user_warn

_VAR_PATTERN = re.compile(r"\{[a-z_]+\}")
_IMAGE_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
_IMAGE_EXT_RE = re.compile(r"\.(png|jpg|jpeg|gif|webp)(\?.*)?$", re.IGNORECASE)

KNOWN_VARS: dict[str, str] = {
    "{user_name}": "Triggering user display name",
    "{user_tag}": "Triggering user tag",
    "{user_avatar}": "Triggering user avatar URL",
    "{user_id}": "Triggering user ID",
    "{user_mention}": "Triggering user mention",
    "{server_name}": "Server name",
    "{server_icon}": "Server icon URL",
    "{server_membercount}": "Server member count",
    "{server_boostcount}": "Server boost count",
    "{server_boosttier}": "Server boost tier",
    "{date}": "Current UTC date",
    "{time}": "Current UTC time",
    "{newline}": "Line break",
}


def _is_valid_hex(v: str) -> bool:
    t = v.strip().lstrip("#")
    return len(t) == 6 and all(c in "0123456789abcdefABCDEF" for c in t)


def _format_hex(v: str) -> str:
    return f"#{v.strip().lstrip('#').upper()}"


def _valid_image_url(v: str) -> bool:
    t = (v or "").strip()
    if not t:
        return True
    if t in ("{user_avatar}", "{server_icon}"):
        return True
    if not _IMAGE_URL_RE.match(t):
        return False
    return bool(_IMAGE_EXT_RE.search(t) or "cdn.discordapp.com" in t or "i.imgur.com" in t)


def _resolve_vars(text: str | None, guild: discord.Guild, user: discord.abc.User | None) -> str | None:
    if text is None:
        return None
    out = str(text)
    now = datetime.now(timezone.utc)
    mapping = {
        "{server_name}": guild.name,
        "{server_icon}": guild.icon.url if guild.icon else "",
        "{server_membercount}": str(guild.member_count or 0),
        "{server_boostcount}": str(guild.premium_subscription_count or 0),
        "{server_boosttier}": str(guild.premium_tier),
        "{date}": f"{now.strftime('%B')} {now.day}, {now.year}",
        "{time}": now.strftime("%H:%M UTC"),
        "{newline}": "\n",
        "{user_name}": getattr(user, "display_name", "") if user else "",
        "{user_tag}": str(user) if user else "",
        "{user_avatar}": (user.display_avatar.url if user and getattr(user, "display_avatar", None) else ""),
        "{user_id}": str(user.id) if user else "",
        "{user_mention}": user.mention if user else "",
    }
    for k, v in mapping.items():
        out = out.replace(k, v)
    return out


def _builder_preview(row: dict[str, Any]) -> discord.Embed:
    desc_raw = row.get("description") or "_This embed is empty. Use edit buttons._"
    # In builder preview, render only newline token so text layout previews correctly.
    desc = str(desc_raw).replace("{newline}", "\n")
    e = discord.Embed(
        title=row.get("title") or None,
        description=desc,
        color=discord.Color.from_str(row.get("color") or "#5865F2"),
    )
    if row.get("author_text"):
        e.set_author(name=str(row["author_text"])[:256], icon_url=(row.get("author_icon") or None))
    if row.get("thumbnail_url"):
        e.set_thumbnail(url=str(row["thumbnail_url"]))
    if row.get("image_url"):
        e.set_image(url=str(row["image_url"]))
    if row.get("footer_text"):
        e.set_footer(text=str(row["footer_text"])[:2048], icon_url=(row.get("footer_icon") or None))
    if int(row.get("ts_enabled") or 0):
        e.timestamp = datetime.now(timezone.utc)
    return e


def _resolved_send_embed(row: dict[str, Any], guild: discord.Guild, user: discord.abc.User | None) -> discord.Embed:
    color = row.get("color") or "#5865F2"
    e = discord.Embed(
        title=_resolve_vars(row.get("title"), guild, user) or None,
        description=_resolve_vars(row.get("description"), guild, user) or None,
        color=discord.Color.from_str(color),
    )
    author_text = _resolve_vars(row.get("author_text"), guild, user)
    author_icon = _resolve_vars(row.get("author_icon"), guild, user)
    if author_text:
        e.set_author(name=author_text[:256], icon_url=(author_icon or None))
    thumb = _resolve_vars(row.get("thumbnail_url"), guild, user)
    if thumb and _valid_image_url(thumb):
        e.set_thumbnail(url=thumb)
    img = _resolve_vars(row.get("image_url"), guild, user)
    if img and _valid_image_url(img):
        e.set_image(url=img)
    footer_text = _resolve_vars(row.get("footer_text"), guild, user)
    footer_icon = _resolve_vars(row.get("footer_icon"), guild, user)
    if footer_text:
        e.set_footer(text=footer_text[:2048], icon_url=(footer_icon or None))
    if int(row.get("ts_enabled") or 0):
        e.timestamp = datetime.now(timezone.utc)
    return e


def _unknown_vars_in_text(text: str | None) -> list[str]:
    if not text:
        return []
    found = set(_VAR_PATTERN.findall(text))
    return sorted(v for v in found if v not in KNOWN_VARS)


def _var_warning_lines(values: list[str]) -> list[str]:
    out: list[str] = []
    for token in values:
        close = get_close_matches(token, list(KNOWN_VARS.keys()), n=1, cutoff=0.65)
        if close:
            out.append(f"⚠️ Unknown variable `{token}`. Did you mean `{close[0]}`?")
        else:
            out.append(f"⚠️ Unknown variable `{token}`. It will remain raw text.")
    return out


def _builder_header_embed(embed_id: str) -> discord.Embed:
    return info_embed(
        f"✨ editing: {embed_id}",
        "please select from the buttons below for what you'd like to edit.\nvariables resolve when posted/triggers run.",
    )


async def _refresh_builder_message(
    interaction: discord.Interaction,
    row: dict[str, Any],
    *,
    warning_lines: list[str] | None = None,
) -> None:
    view = BuilderView(interaction.client.get_cog("EmbedBuilderCog"), row, interaction.user.id)  # type: ignore[arg-type]
    header = _builder_header_embed(str(row["embed_id"]))
    if warning_lines:
        header.description = (header.description or "") + "\n\n" + "\n".join(warning_lines[:5])
    try:
        await interaction.response.edit_message(
            embeds=[header, _builder_preview(row)],
            view=view,
        )
    except (discord.HTTPException, discord.NotFound):
        await interaction.response.send_message(
            embeds=[header, _builder_preview(row)],
            view=view,
            ephemeral=True,
        )


class FieldModal(discord.ui.Modal):
    value = discord.ui.TextInput(label="Value", required=False, max_length=4000, style=discord.TextStyle.short)

    def __init__(self, cog: "EmbedBuilderCog", row: dict[str, Any], field: str) -> None:
        self.cog = cog
        self.row = row
        self.field = field
        title = f"{row['embed_id']} · Edit {field}"
        super().__init__(title=title[:45])
        cfg = {
            "author": ("Author + icon URL (line2)", 900, discord.TextStyle.paragraph),
            "title": ("Title", 256, discord.TextStyle.short),
            "description": ("Description", 4000, discord.TextStyle.paragraph),
            "footer": ("Footer + icon URL (line2)", 2600, discord.TextStyle.paragraph),
            "thumbnail": ("Thumbnail URL", 512, discord.TextStyle.short),
            "image": ("Image URL", 512, discord.TextStyle.short),
            "color": ("Color hex (#RRGGBB)", 7, discord.TextStyle.short),
        }[field]
        self.value = discord.ui.TextInput(
            label=cfg[0],
            required=False,
            max_length=cfg[1],
            style=cfg[2],
            default=self._default_value(),
            placeholder=self._placeholder(field),
        )
        self.add_item(self.value)

    def _default_value(self) -> str:
        r = self.row
        if self.field == "author":
            return "\n".join([str(r.get("author_text") or ""), str(r.get("author_icon") or "")]).strip()
        if self.field == "footer":
            return "\n".join([str(r.get("footer_text") or ""), str(r.get("footer_icon") or "")]).strip()
        if self.field == "thumbnail":
            return str(r.get("thumbnail_url") or "")
        if self.field == "image":
            return str(r.get("image_url") or "")
        if self.field == "color":
            return str(r.get("color") or "#5865F2")
        return str(r.get(self.field) or "")

    def _placeholder(self, field: str) -> str:
        return {
            "author": "Line 1: author text\nLine 2: icon URL (optional)",
            "title": "Welcome to server",
            "description": "Write embed content here...",
            "footer": "Line 1: footer text\nLine 2: icon URL (optional)",
            "thumbnail": "https://... or {user_avatar}",
            "image": "https://... or {server_icon}",
            "color": "#5865F2",
        }[field]

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = str(self.value.value or "")
        updates: dict[str, Any] = {}
        warn_lines: list[str] = []
        field_name = self.field
        if field_name == "author":
            lines = raw.splitlines()
            updates["author_text"] = (lines[0].strip() if lines else "") or None
            updates["author_icon"] = (lines[1].strip() if len(lines) > 1 else "") or None
            if updates["author_icon"] and not _valid_image_url(str(updates["author_icon"])):
                await interaction.response.send_message(embed=user_hint("Invalid URL", "Author icon URL is invalid."), ephemeral=True)
                return
            warn_lines.extend(_var_warning_lines(_unknown_vars_in_text(updates["author_text"])))
            warn_lines.extend(_var_warning_lines(_unknown_vars_in_text(updates["author_icon"])))
        elif field_name == "footer":
            lines = raw.splitlines()
            updates["footer_text"] = (lines[0].strip() if lines else "") or None
            updates["footer_icon"] = (lines[1].strip() if len(lines) > 1 else "") or None
            if updates["footer_icon"] and not _valid_image_url(str(updates["footer_icon"])):
                await interaction.response.send_message(embed=user_hint("Invalid URL", "Footer icon URL is invalid."), ephemeral=True)
                return
            warn_lines.extend(_var_warning_lines(_unknown_vars_in_text(updates["footer_text"])))
            warn_lines.extend(_var_warning_lines(_unknown_vars_in_text(updates["footer_icon"])))
        elif field_name == "thumbnail":
            v = raw.strip()
            if v and not _valid_image_url(v):
                await interaction.response.send_message(embed=user_hint("Invalid URL", "Thumbnail must be direct image URL."), ephemeral=True)
                return
            updates["thumbnail_url"] = v or None
            warn_lines.extend(_var_warning_lines(_unknown_vars_in_text(v)))
        elif field_name == "image":
            v = raw.strip()
            if v and not _valid_image_url(v):
                await interaction.response.send_message(embed=user_hint("Invalid URL", "Image must be direct image URL."), ephemeral=True)
                return
            updates["image_url"] = v or None
            warn_lines.extend(_var_warning_lines(_unknown_vars_in_text(v)))
        elif field_name == "color":
            v = raw.strip()
            if not v:
                updates["color"] = "#5865F2"
            elif not _is_valid_hex(v):
                await interaction.response.send_message(embed=user_hint("Invalid color", "Use hex like `#5865F2`."), ephemeral=True)
                return
            else:
                updates["color"] = _format_hex(v)
        else:
            updates[field_name] = raw or None
            warn_lines.extend(_var_warning_lines(_unknown_vars_in_text(raw)))

        await db.patch_builder_embed(int(self.row["guild_id"]), str(self.row["embed_id"]), updates)
        row = await db.get_builder_embed(int(self.row["guild_id"]), str(self.row["embed_id"]))
        if not row:
            await interaction.response.send_message(embed=user_warn("Missing", "Embed record missing now."), ephemeral=True)
            return
        await _refresh_builder_message(interaction, row, warning_lines=warn_lines)


class BasicInfoModal(discord.ui.Modal):
    title_input = discord.ui.TextInput(label="Title", required=False, max_length=256)
    desc_input = discord.ui.TextInput(
        label="Description",
        required=False,
        max_length=4000,
        style=discord.TextStyle.paragraph,
    )
    color_input = discord.ui.TextInput(
        label="Hex Color",
        required=False,
        max_length=7,
        placeholder="#5865F2",
    )

    def __init__(self, row: dict[str, Any]) -> None:
        super().__init__(title=f"Editing: {row['embed_id']}"[:45])
        self.row = row
        self.title_input.default = str(row.get("title") or "")
        self.desc_input.default = str(row.get("description") or "")
        self.color_input.default = str(row.get("color") or "#5865F2")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        title = str(self.title_input.value or "").strip() or None
        desc = str(self.desc_input.value or "").strip() or None
        color_raw = str(self.color_input.value or "").strip()
        if color_raw and not _is_valid_hex(color_raw):
            await interaction.response.send_message(
                embed=user_hint("Invalid color", "Use hex like `#5865F2`."),
                ephemeral=True,
            )
            return
        color = _format_hex(color_raw) if color_raw else "#5865F2"
        warns = _var_warning_lines(_unknown_vars_in_text(title)) + _var_warning_lines(
            _unknown_vars_in_text(desc)
        )
        await db.patch_builder_embed(
            int(self.row["guild_id"]),
            str(self.row["embed_id"]),
            {"title": title, "description": desc, "color": color},
        )
        row = await db.get_builder_embed(int(self.row["guild_id"]), str(self.row["embed_id"]))
        if not row:
            await interaction.response.send_message("Embed no longer exists.", ephemeral=True)
            return
        await _refresh_builder_message(interaction, row, warning_lines=warns)


class ImagesModal(discord.ui.Modal):
    image_input = discord.ui.TextInput(
        label="Main Image",
        required=False,
        max_length=512,
        placeholder="https://cdn.mimu.bot/img.png",
    )
    thumb_input = discord.ui.TextInput(
        label="Thumbnail",
        required=False,
        max_length=512,
        placeholder="https://cdn.mimu.bot/img.png",
    )

    def __init__(self, row: dict[str, Any]) -> None:
        super().__init__(title=f"Editing: {row['embed_id']} (images)"[:45])
        self.row = row
        self.image_input.default = str(row.get("image_url") or "")
        self.thumb_input.default = str(row.get("thumbnail_url") or "")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        thumb = str(self.thumb_input.value or "").strip()
        img = str(self.image_input.value or "").strip()
        if thumb and not _valid_image_url(thumb):
            await interaction.response.send_message(
                embed=user_hint("Invalid URL", "Thumbnail must be direct image URL."),
                ephemeral=True,
            )
            return
        if img and not _valid_image_url(img):
            await interaction.response.send_message(
                embed=user_hint("Invalid URL", "Image must be direct image URL."),
                ephemeral=True,
            )
            return
        await db.patch_builder_embed(
            int(self.row["guild_id"]),
            str(self.row["embed_id"]),
            {"thumbnail_url": thumb or None, "image_url": img or None},
        )
        row = await db.get_builder_embed(int(self.row["guild_id"]), str(self.row["embed_id"]))
        if not row:
            await interaction.response.send_message("Embed no longer exists.", ephemeral=True)
            return
        warns = _var_warning_lines(_unknown_vars_in_text(thumb)) + _var_warning_lines(
            _unknown_vars_in_text(img)
        )
        await _refresh_builder_message(interaction, row, warning_lines=warns)


class AuthorModal(discord.ui.Modal):
    author_text = discord.ui.TextInput(label="Author Text", required=False, max_length=256)
    author_image = discord.ui.TextInput(
        label="Author Image (optional)",
        required=False,
        max_length=512,
        placeholder="https://cdn.mimu.bot/img.png",
    )

    def __init__(self, row: dict[str, Any]) -> None:
        super().__init__(title=f"Editing: {row['embed_id']}"[:45])
        self.row = row
        self.author_text.default = str(row.get("author_text") or "")
        self.author_image.default = str(row.get("author_icon") or "")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        text = str(self.author_text.value or "").strip()
        icon = str(self.author_image.value or "").strip()
        if icon and not _valid_image_url(icon):
            await interaction.response.send_message(
                embed=user_hint("Invalid URL", "Author image URL is invalid."),
                ephemeral=True,
            )
            return
        await db.patch_builder_embed(
            int(self.row["guild_id"]),
            str(self.row["embed_id"]),
            {"author_text": text or None, "author_icon": icon or None},
        )
        row = await db.get_builder_embed(int(self.row["guild_id"]), str(self.row["embed_id"]))
        if not row:
            await interaction.response.send_message("Embed no longer exists.", ephemeral=True)
            return
        warns = _var_warning_lines(_unknown_vars_in_text(text)) + _var_warning_lines(
            _unknown_vars_in_text(icon)
        )
        await _refresh_builder_message(interaction, row, warning_lines=warns)


class FooterModal(discord.ui.Modal):
    footer_text = discord.ui.TextInput(label="Footer Text", required=False, max_length=2048)
    footer_image = discord.ui.TextInput(
        label="Footer Image (optional)",
        required=False,
        max_length=512,
        placeholder="https://cdn.mimu.bot/img.png",
    )
    timestamp = discord.ui.TextInput(
        label="Timestamp? (yes/no)",
        required=False,
        max_length=3,
        placeholder="no",
    )

    def __init__(self, row: dict[str, Any]) -> None:
        super().__init__(title=f"Editing: {row['embed_id']}"[:45])
        self.row = row
        self.footer_text.default = str(row.get("footer_text") or "")
        self.footer_image.default = str(row.get("footer_icon") or "")
        self.timestamp.default = "yes" if int(row.get("ts_enabled") or 0) else "no"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        text = str(self.footer_text.value or "").strip()
        icon = str(self.footer_image.value or "").strip()
        ts_raw = str(self.timestamp.value or "").strip().lower()
        if icon and not _valid_image_url(icon):
            await interaction.response.send_message(
                embed=user_hint("Invalid URL", "Footer image URL is invalid."),
                ephemeral=True,
            )
            return
        if ts_raw not in ("", "yes", "no", "y", "n", "true", "false", "1", "0"):
            await interaction.response.send_message(
                embed=user_hint("Invalid timestamp", "Use `yes` or `no`."),
                ephemeral=True,
            )
            return
        ts_enabled = 1 if ts_raw in ("yes", "y", "true", "1") else 0
        await db.patch_builder_embed(
            int(self.row["guild_id"]),
            str(self.row["embed_id"]),
            {"footer_text": text or None, "footer_icon": icon or None, "ts_enabled": ts_enabled},
        )
        row = await db.get_builder_embed(int(self.row["guild_id"]), str(self.row["embed_id"]))
        if not row:
            await interaction.response.send_message("Embed no longer exists.", ephemeral=True)
            return
        warns = _var_warning_lines(_unknown_vars_in_text(text)) + _var_warning_lines(
            _unknown_vars_in_text(icon)
        )
        await _refresh_builder_message(interaction, row, warning_lines=warns)


class BuilderView(discord.ui.View):
    def __init__(self, cog: "EmbedBuilderCog", row: dict[str, Any], editor_id: int) -> None:
        super().__init__(timeout=900)
        self.cog = cog
        self.row = row
        self.editor_id = editor_id
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True
        if self.message:
            try:
                await self.message.edit(
                    embeds=[
                        info_embed(
                            f"{self.row['embed_id']} builder expired",
                            "Session expired. Use `/embed edit` to continue.",
                        ),
                        _builder_preview(self.row),
                    ],
                    view=self,
                )
            except discord.HTTPException:
                pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.editor_id:
            await interaction.response.send_message("Only builder owner can use this panel.", ephemeral=True)
            return False
        return True

    async def _open_field(self, interaction: discord.Interaction, field: str) -> None:
        row = await db.get_builder_embed(int(self.row["guild_id"]), str(self.row["embed_id"]))
        if not row:
            await interaction.response.send_message("Embed no longer exists.", ephemeral=True)
            return
        await interaction.response.send_modal(FieldModal(self.cog, row, field))

    @discord.ui.button(
        label="edit basic information (color / title / description)",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def basic_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = await db.get_builder_embed(int(self.row["guild_id"]), str(self.row["embed_id"]))
        if not row:
            await interaction.response.send_message("Embed no longer exists.", ephemeral=True)
            return
        await interaction.response.send_modal(BasicInfoModal(row))

    @discord.ui.button(label="edit author", style=discord.ButtonStyle.secondary, row=0)
    async def author_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = await db.get_builder_embed(int(self.row["guild_id"]), str(self.row["embed_id"]))
        if not row:
            await interaction.response.send_message("Embed no longer exists.", ephemeral=True)
            return
        await interaction.response.send_modal(AuthorModal(row))

    @discord.ui.button(label="edit footer", style=discord.ButtonStyle.secondary, row=0)
    async def footer_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = await db.get_builder_embed(int(self.row["guild_id"]), str(self.row["embed_id"]))
        if not row:
            await interaction.response.send_message("Embed no longer exists.", ephemeral=True)
            return
        await interaction.response.send_modal(FooterModal(row))

    @discord.ui.button(label="edit images", style=discord.ButtonStyle.secondary, row=0)
    async def images_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = await db.get_builder_embed(int(self.row["guild_id"]), str(self.row["embed_id"]))
        if not row:
            await interaction.response.send_message("Embed no longer exists.", ephemeral=True)
            return
        await interaction.response.send_modal(ImagesModal(row))

    @discord.ui.button(label="variables", style=discord.ButtonStyle.secondary, row=1)
    async def vars_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        lines = ["Available variables:"]
        for k, v in KNOWN_VARS.items():
            lines.append(f"`{k}` → {v}")
        lines.append("")
        lines.append("Tip: Description modal supports real line breaks with Enter.")
        await interaction.response.send_message(embed=info_embed("Variables", "\n".join(lines)[:4000]), ephemeral=True)

    @discord.ui.button(label="preview", style=discord.ButtonStyle.secondary, row=1)
    async def preview_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = await db.get_builder_embed(int(self.row["guild_id"]), str(self.row["embed_id"]))
        if not row:
            await interaction.response.send_message("Embed no longer exists.", ephemeral=True)
            return
        await interaction.response.send_message(
            embeds=[info_embed(row["embed_id"], "_Variables shown raw in preview._"), _builder_preview(row)],
            ephemeral=True,
        )

    @discord.ui.button(label="done", style=discord.ButtonStyle.secondary, row=1)
    async def done_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await db.patch_builder_embed(int(self.row["guild_id"]), str(self.row["embed_id"]), {"status": "active"})
        await interaction.response.send_message(
            embed=success_embed("Builder closed", f"{self.row['embed_id']} saved and ready."),
            ephemeral=True,
        )
        self.stop()

    @discord.ui.button(label="discard", style=discord.ButtonStyle.secondary, row=1)
    async def discard_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        ok = await db.delete_builder_embed(int(self.row["guild_id"]), str(self.row["embed_id"]))
        if ok:
            await db.log_embed_builder_action(int(self.row["guild_id"]), self.editor_id, "delete", str(self.row["embed_id"]))
        await interaction.response.send_message(
            embed=success_embed("Discarded", f"{self.row['embed_id']} removed."),
            ephemeral=True,
        )
        self.stop()

class ShowListView(discord.ui.View):
    def __init__(self, cog: "EmbedBuilderCog", rows: list[dict[str, Any]], user_id: int) -> None:
        super().__init__(timeout=600)
        self.cog = cog
        self.rows = rows
        self.user_id = user_id
        self.idx = 0
        self.message: discord.Message | None = None
        self._refresh_state()

    async def on_timeout(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True
        if self.message:
            try:
                meta, prev = self._page_embed()
                meta.description = (meta.description or "") + "\n\n_Session expired. Run `/embed showlist` again._"
                await self.message.edit(embeds=[meta, prev], view=self)
            except discord.HTTPException:
                pass

    def _refresh_state(self) -> None:
        self.first_btn.disabled = self.idx <= 0
        self.prev_btn.disabled = self.idx <= 0
        self.next_btn.disabled = self.idx >= len(self.rows) - 1
        self.last_btn.disabled = self.idx >= len(self.rows) - 1
        cur = self.rows[self.idx]["embed_id"] if self.rows else "EMB-000"
        self.center_btn.label = f"{cur} / {len(self.rows)}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your browser session.", ephemeral=True)
            return False
        return True

    def _page_embed(self) -> tuple[discord.Embed, discord.Embed]:
        row = self.rows[self.idx]
        meta = info_embed(
            "Embed Browser",
            f"{row['embed_id']} · created by <@{row['created_by']}> · created `{row['created_at']}` · edited `{row['last_edited_at']}`\n_Variables shown raw in preview._",
        )
        return meta, _builder_preview(row)

    async def _render(self, interaction: discord.Interaction) -> None:
        self._refresh_state()
        meta, prev = self._page_embed()
        await interaction.response.edit_message(embeds=[meta, prev], view=self)

    @discord.ui.button(label="⏮ First", style=discord.ButtonStyle.secondary)
    async def first_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.idx = 0
        await self._render(interaction)

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.idx = max(0, self.idx - 1)
        await self._render(interaction)

    @discord.ui.button(label="EMB / N", style=discord.ButtonStyle.secondary, disabled=True)
    async def center_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.defer()

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.idx = min(len(self.rows) - 1, self.idx + 1)
        await self._render(interaction)

    @discord.ui.button(label="Last ⏭", style=discord.ButtonStyle.secondary)
    async def last_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.idx = len(self.rows) - 1
        await self._render(interaction)

    @discord.ui.button(label="✏️ Edit", style=discord.ButtonStyle.primary, row=1)
    async def edit_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = self.rows[self.idx]
        await interaction.response.send_message(
            embed=info_embed(f"{row['embed_id']}", "Use builder buttons below."),
            view=BuilderView(self.cog, row, interaction.user.id),
            ephemeral=True,
        )

    @discord.ui.button(label="📤 Post", style=discord.ButtonStyle.success, row=1)
    async def post_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = self.rows[self.idx]
        await interaction.response.send_message(
            "Pick target channel for posting.",
            view=PostChannelPickView(self.cog, row),
            ephemeral=True,
        )

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=1)
    async def del_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = self.rows[self.idx]
        await interaction.response.send_message(
            embed=user_warn("Delete confirmation", f"Delete **{row['embed_id']}** permanently?"),
            view=DeleteConfirmView(self, row),
            ephemeral=True,
        )

    @discord.ui.button(label="🔍 Go to ID", style=discord.ButtonStyle.secondary, row=1)
    async def goto_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(GoToIdModal(self))


class GoToIdModal(discord.ui.Modal, title="Go to embed ID"):
    embed_id = discord.ui.TextInput(label="Embed ID", placeholder="EMB-007", required=True, max_length=16)

    def __init__(self, browser: ShowListView) -> None:
        super().__init__()
        self.browser = browser

    async def on_submit(self, interaction: discord.Interaction) -> None:
        v = str(self.embed_id.value or "").strip().upper()
        idx = next((i for i, r in enumerate(self.browser.rows) if str(r["embed_id"]).upper() == v), -1)
        if idx < 0:
            await interaction.response.send_message(
                embed=user_hint("Not found", f"No embed found with ID {v} on this server."),
                ephemeral=True,
            )
            return
        self.browser.idx = idx
        self.browser._refresh_state()
        meta, prev = self.browser._page_embed()
        if self.browser.message:
            try:
                await self.browser.message.edit(embeds=[meta, prev], view=self.browser)
            except discord.HTTPException:
                pass
        await interaction.response.send_message(
            embed=success_embed("Jumped", f"Now viewing **{v}**."),
            ephemeral=True,
        )


class DeleteConfirmView(discord.ui.View):
    def __init__(self, browser: ShowListView, row: dict[str, Any]) -> None:
        super().__init__(timeout=120)
        self.browser = browser
        self.row = row

    @discord.ui.button(label="Yes, Delete", style=discord.ButtonStyle.danger)
    async def yes_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        ok = await db.delete_builder_embed(int(self.row["guild_id"]), str(self.row["embed_id"]))
        if not ok:
            await interaction.response.send_message("Delete failed.", ephemeral=True)
            return
        await db.log_embed_builder_action(int(self.row["guild_id"]), interaction.user.id, "delete", str(self.row["embed_id"]))
        self.browser.rows = await db.list_builder_embeds(int(self.row["guild_id"]))
        if not self.browser.rows:
            await interaction.response.send_message(
                embed=info_embed("No embeds", "This server has no embeds now. Run `/embed create`."),
                ephemeral=True,
            )
            return
        self.browser.idx = min(self.browser.idx, len(self.browser.rows) - 1)
        self.browser._refresh_state()
        meta, prev = self.browser._page_embed()
        if self.browser.message:
            try:
                await self.browser.message.edit(embeds=[meta, prev], view=self.browser)
            except discord.HTTPException:
                pass
        await interaction.response.send_message(
            embed=success_embed("Deleted", f"{self.row['embed_id']} removed."),
            ephemeral=True,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_message("Delete canceled.", ephemeral=True)


class PostChannelPickView(discord.ui.View):
    def __init__(self, cog: "EmbedBuilderCog", row: dict[str, Any]) -> None:
        super().__init__(timeout=120)
        self.cog = cog
        self.row = row

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Select channel")
    async def pick(self, interaction: discord.Interaction, sel: discord.ui.ChannelSelect) -> None:
        ch = sel.values[0]
        if not isinstance(ch, discord.TextChannel) or not interaction.guild:
            await interaction.response.send_message("Invalid channel.", ephemeral=True)
            return
        emb = _resolved_send_embed(self.row, interaction.guild, interaction.user)
        try:
            await ch.send(embed=emb)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Post failed: {e}", ephemeral=True)
            return
        await db.log_embed_builder_action(int(self.row["guild_id"]), interaction.user.id, "post", str(self.row["embed_id"]), ch.id)
        await interaction.response.send_message(
            embed=success_embed("Posted", f"{self.row['embed_id']} posted to {ch.mention}."),
            ephemeral=True,
        )


class EmbedBuilderCog(commands.Cog, name="EmbedBuilderCog"):
    embed = app_commands.Group(name="embed", description="Embed builder tools")
    config = app_commands.Group(name="config", description="Embed config", parent=embed)

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _embed_id_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if not interaction.guild:
            return []
        rows = await db.list_builder_embeds(interaction.guild.id)
        needle = current.lower().strip()
        out: list[app_commands.Choice[str]] = []
        for r in rows:
            eid = str(r.get("embed_id") or "")
            title = str(r.get("title") or "")
            label = f"{eid} · {title[:60]}" if title else eid
            if needle and needle not in eid.lower() and needle not in title.lower():
                continue
            out.append(app_commands.Choice(name=label[:100], value=eid))
            if len(out) >= 25:
                break
        return out

    async def _can_use(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return False
        if interaction.guild.owner_id == interaction.user.id:
            return True
        if interaction.user.guild_permissions.administrator:
            return True
        roles = await db.list_embed_staff_roles(interaction.guild.id)
        if roles:
            if any((r.id in roles) for r in interaction.user.roles):
                return True
        await interaction.response.send_message(
            "You don't have permission to use embed commands. This feature is limited to staff and above.",
            ephemeral=True,
        )
        return False

    @config.command(name="staffrole", description="Manage embed staff role allow-list")
    @app_commands.describe(action="add/remove/list", role="Role for add/remove")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="add", value="add"),
            app_commands.Choice(name="remove", value="remove"),
            app_commands.Choice(name="list", value="list"),
        ]
    )
    async def config_staffrole(
        self,
        interaction: discord.Interaction,
        action: str,
        role: discord.Role | None = None,
    ) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        if not (interaction.guild.owner_id == interaction.user.id or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message("Only server owner/admin can manage embed staff roles.", ephemeral=True)
            return
        if action == "list":
            ids = await db.list_embed_staff_roles(interaction.guild.id)
            txt = "\n".join(f"- <@&{rid}>" for rid in ids) if ids else "No embed staff roles set."
            await interaction.response.send_message(embed=info_embed("Embed staff roles", txt), ephemeral=True)
            return
        if role is None:
            await interaction.response.send_message("Provide role for add/remove.", ephemeral=True)
            return
        if action == "add":
            await db.add_embed_staff_role(interaction.guild.id, role.id)
            await interaction.response.send_message(embed=success_embed("Added", f"{role.mention} can use embed commands."), ephemeral=True)
            return
        await db.remove_embed_staff_role(interaction.guild.id, role.id)
        await interaction.response.send_message(embed=success_embed("Removed", f"{role.mention} removed from embed access."), ephemeral=True)

    @embed.command(name="create", description="Create new embed draft and open builder")
    async def create_cmd(self, interaction: discord.Interaction) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        row = await db.create_builder_embed(interaction.guild.id, interaction.user.id)
        await db.log_embed_builder_action(interaction.guild.id, interaction.user.id, "create", str(row["embed_id"]))
        view = BuilderView(self, row, interaction.user.id)
        guide = info_embed(
            "✨ successfully created an embed",
            (
                f"created an embed called **{row['embed_id']}**.\n"
                "please select from the buttons below for what you'd like to edit!\n"
                "alternatively, you can edit these individually in slash commands with `/embed edit`."
            ),
        )
        await interaction.response.send_message(
            embeds=[guide, _builder_preview(row)],
            view=view,
            ephemeral=True,
        )
        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            pass

    @embed.command(name="edit", description="Edit embed by ID")
    @app_commands.describe(id="Embed ID like EMB-001", field="Optional field shortcut")
    @app_commands.choices(
        field=[
            app_commands.Choice(name="author", value="author"),
            app_commands.Choice(name="title", value="title"),
            app_commands.Choice(name="description", value="description"),
            app_commands.Choice(name="footer", value="footer"),
            app_commands.Choice(name="thumbnail", value="thumbnail"),
            app_commands.Choice(name="image", value="image"),
            app_commands.Choice(name="color", value="color"),
            app_commands.Choice(name="timestamp", value="timestamp"),
        ]
    )
    @app_commands.autocomplete(id=_embed_id_autocomplete)
    async def edit_cmd(self, interaction: discord.Interaction, id: str, field: str | None = None) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        row = await db.get_builder_embed(interaction.guild.id, id.upper())
        if not row:
            await interaction.response.send_message(embed=user_hint("Missing", f"No embed found with ID {id.upper()} on this server."), ephemeral=True)
            return
        if field == "timestamp":
            new_v = 0 if int(row.get("ts_enabled") or 0) else 1
            await db.patch_builder_embed(interaction.guild.id, row["embed_id"], {"ts_enabled": new_v})
            await interaction.response.send_message(embed=success_embed("Timestamp updated", f"{row['embed_id']} timestamp {'enabled' if new_v else 'disabled'}."), ephemeral=True)
            return
        if field:
            await interaction.response.send_modal(FieldModal(self, row, field))
            return
        view = BuilderView(self, row, interaction.user.id)
        await interaction.response.send_message(
            embeds=[
                info_embed(
                    f"Editing: {row['embed_id']}",
                    "Please select from buttons below for what you'd like to edit.",
                ),
                _builder_preview(row),
            ],
            view=view,
            ephemeral=True,
        )
        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            pass

    @embed.command(name="show", description="Post embed by ID to channel")
    @app_commands.describe(id="Embed ID like EMB-001", channel="Target channel")
    @app_commands.autocomplete(id=_embed_id_autocomplete)
    async def show_cmd(self, interaction: discord.Interaction, id: str, channel: discord.TextChannel) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        row = await db.get_builder_embed(interaction.guild.id, id.upper())
        if not row:
            await interaction.response.send_message(embed=user_hint("Missing", f"No embed found with ID {id.upper()} on this server."), ephemeral=True)
            return
        emb = _resolved_send_embed(row, interaction.guild, interaction.user)
        try:
            await channel.send(embed=emb)
        except discord.HTTPException as e:
            await interaction.response.send_message(embed=user_warn("Post failed", str(e)[:400]), ephemeral=True)
            return
        await db.log_embed_builder_action(interaction.guild.id, interaction.user.id, "post", row["embed_id"], channel.id)
        await interaction.response.send_message(embed=success_embed("Posted", f"{row['embed_id']} posted to {channel.mention}."), ephemeral=True)

    @embed.command(name="list", description="List embeds on this server")
    async def list_cmd(self, interaction: discord.Interaction) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        rows = await db.list_builder_embeds(interaction.guild.id)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("📋 Server Embeds — 0 total", "No embeds have been created yet.\nRun `/embed create` to get started."),
                ephemeral=True,
            )
            return
        lines = [f"{r['embed_id']} · Created by <@{r['created_by']}> · {str(r['created_at'])[:10]}" for r in rows[:50]]
        text = "\n".join(lines)
        if len(rows) > 50:
            text += f"\n\nShowing 50 of {len(rows)}."
        text += "\n\nTo edit: `/embed edit id:EMB-XXX`\nTo browse previews: `/embed showlist`"
        await interaction.response.send_message(
            embed=info_embed(f"📋 Server Embeds — {len(rows)} total", text[:4000]),
            ephemeral=True,
        )

    @embed.command(name="showlist", description="Browse embeds with previews")
    async def showlist_cmd(self, interaction: discord.Interaction) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        rows = await db.list_builder_embeds(interaction.guild.id)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("📋 No Embeds Yet", "This server doesn't have any embeds.\nRun `/embed create` to make your first one."),
                ephemeral=True,
            )
            return
        view = ShowListView(self, rows, interaction.user.id)
        meta, prev = view._page_embed()
        await interaction.response.send_message(embeds=[meta, prev], view=view, ephemeral=True)
        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EmbedBuilderCog(bot))
