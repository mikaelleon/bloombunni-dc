"""Interactive autoresponder builder (AR-XXX) with runtime trigger engine."""

from __future__ import annotations

import asyncio
import io
import json
import re
from datetime import datetime, timezone
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import guild_keys as gk
from utils.embeds import info_embed, success_embed, user_hint, user_warn

_TRIGGER_TYPES = ("message", "member_join", "member_leave", "role_assigned")
_MATCH_MODES = ("exact", "startswith", "endswith", "includes", "word_boundary")
_VAR_PATTERN = re.compile(r"\{[a-zA-Z0-9_:+#\.\-\[\]\| ]+\}")


def _utc_now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _autodismiss_response(interaction: discord.Interaction, seconds: int = 10) -> None:
    async def _cleanup() -> None:
        await asyncio.sleep(seconds)
        try:
            await interaction.delete_original_response()
        except (discord.HTTPException, discord.NotFound):
            pass

    asyncio.create_task(_cleanup())


def _normalize_trigger_lines(raw: str) -> list[str]:
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    out: list[str] = []
    seen: set[str] = set()
    for ln in lines:
        key = ln.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(ln)
    return out[:20]


def _match_message(content: str, trigger: str, mode: str) -> bool:
    c = content.lower()
    t = trigger.lower()
    if mode == "exact":
        return c == t
    if mode == "startswith":
        return c.startswith(t)
    if mode == "endswith":
        return c.endswith(t)
    if mode == "word_boundary":
        return re.search(rf"\b{re.escape(t)}\b", c) is not None
    return t in c  # includes


def _extract_args(content: str, trigger: str, mode: str) -> list[str]:
    text = content.strip()
    trg = trigger.strip()
    if mode == "startswith" and text.lower().startswith(trg.lower()):
        tail = text[len(trg) :].strip()
        return tail.split() if tail else []
    if mode == "exact":
        return []
    return text.split()


def _resolve_arg_tokens(text: str, args: list[str]) -> str:
    out = text
    for i in range(1, 21):
        token = f"[$%d]" % i
        val = args[i - 1] if i - 1 < len(args) else ""
        out = out.replace(token, val)
    for i in range(1, 21):
        token = f"[$%d+]" % i
        val = " ".join(args[i - 1 :]) if i - 1 < len(args) else ""
        out = out.replace(token, val)

    def repl_range(m: re.Match[str]) -> str:
        a = int(m.group(1))
        b = int(m.group(2))
        if a < 1 or b < a:
            return ""
        start = a - 1
        end = min(len(args), b)
        return " ".join(args[start:end])

    out = re.sub(r"\[\$(\d+)-(\d+)\]", repl_range, out)
    return out


def _resolve_basic_vars(
    text: str,
    *,
    guild: discord.Guild,
    member: discord.Member,
    channel: discord.abc.GuildChannel | discord.Thread | None,
    message: discord.Message | None,
) -> str:
    out = text
    now = datetime.now(timezone.utc)
    message_id = str(message.id) if message else ""
    message_content = message.content if message else ""
    message_link = message.jump_url if message else ""
    mapping = {
        "{user}": member.mention,
        "{user_mention}": member.mention,
        "{user_name}": member.display_name,
        "{user_tag}": str(member),
        "{user_id}": str(member.id),
        "{user_avatar}": member.display_avatar.url if member.display_avatar else "",
        "{server_name}": guild.name,
        "{server_id}": str(guild.id),
        "{server_membercount}": str(guild.member_count or 0),
        "{server_icon}": guild.icon.url if guild.icon else "",
        "{channel}": channel.mention if channel else "",
        "{channel_name}": channel.name if channel else "",
        "{message_id}": message_id,
        "{message_content}": message_content,
        "{message_link}": message_link,
        "{date}": now.strftime("%B %d, %Y %H:%M UTC"),
        "{newline}": "\n",
    }
    for k, v in mapping.items():
        out = out.replace(k, v)
    return out


def _parse_inline_functions(raw: str) -> tuple[str, dict[str, Any]]:
    text = raw
    flags: dict[str, Any] = {
        "dm": False,
        "delete_trigger": False,
        "delete_reply_after": None,
        "embed_color": None,
    }
    if "{dm}" in text:
        flags["dm"] = True
        text = text.replace("{dm}", "")
    if "{delete}" in text:
        flags["delete_trigger"] = True
        text = text.replace("{delete}", "")
    m = re.search(r"\{delete_reply:(\d+)\}", text, flags=re.IGNORECASE)
    if m:
        flags["delete_reply_after"] = max(1, min(3600, int(m.group(1))))
        text = text.replace(m.group(0), "")
    m2 = re.search(r"\{embed(?::(#[0-9a-fA-F]{6}))?\}", text)
    if m2:
        flags["embed_color"] = m2.group(1) or "#5865F2"
        text = text.replace(m2.group(0), "")
    return text.strip(), flags


def _ar_preview_embed(row: dict[str, Any]) -> discord.Embed:
    mode = str(row.get("match_mode") or "exact")
    trs = []
    for t in str(row.get("triggers_json") or "").split("\n"):
        s = t.strip()
        if s:
            trs.append(s)
    trigger_show = trs[0] if trs else "(not set)"
    extra = f" +{len(trs) - 1}" if len(trs) > 1 else ""
    desc = (
        f"**type:** {row.get('trigger_type') or 'message'}\n"
        f"**matchmode:** {mode}\n"
        f"**trigger:** `{trigger_show}`{extra}\n"
        f"**priority:** {int(row.get('priority') or 100)}\n"
        f"**status:** {row.get('status') or 'draft'}\n"
        f"**cooldown:** {int(row.get('cooldown_seconds') or 0)}s"
    )
    e = info_embed(f"Autoresponder Builder — {row['ar_id']}", desc)
    resp = str(row.get("response_text") or "_No response set yet._")
    e.add_field(name="Response", value=resp[:1024], inline=False)
    return e


class TriggerModal(discord.ui.Modal, title="Trigger + matchmode"):
    trigger_type = discord.ui.TextInput(
        label="Trigger type (message/join/leave/role)",
        max_length=24,
        required=True,
        default="message",
    )
    trigger_lines = discord.ui.TextInput(
        label="Triggers (one per line)",
        style=discord.TextStyle.paragraph,
        max_length=1500,
        required=True,
    )
    match_mode = discord.ui.TextInput(
        label="Match mode (exact/starts/ends/includes/word)",
        max_length=32,
        required=True,
        default="exact",
    )
    priority = discord.ui.TextInput(
        label="Priority (1 high, 100 default)",
        max_length=4,
        required=False,
        default="100",
    )
    trigger_role_id = discord.ui.TextInput(
        label="Role trigger role_id (optional)",
        max_length=30,
        required=False,
    )

    def __init__(self, row: dict[str, Any]) -> None:
        super().__init__(title=f"{row['ar_id']} · trigger"[:45])
        self.row = row
        self.trigger_type.default = str(row.get("trigger_type") or "message")
        self.trigger_lines.default = str(row.get("triggers_json") or "")
        self.match_mode.default = str(row.get("match_mode") or "exact")
        self.priority.default = str(int(row.get("priority") or 100))
        self.trigger_role_id.default = str(row.get("trigger_role_id") or "")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        trig_type_raw = str(self.trigger_type.value or "").strip().lower()
        trig_type = {
            "message": "message",
            "join": "member_join",
            "member_join": "member_join",
            "leave": "member_leave",
            "member_leave": "member_leave",
            "role": "role_assigned",
            "role_assigned": "role_assigned",
        }.get(trig_type_raw, "")
        if trig_type not in _TRIGGER_TYPES:
            await interaction.response.send_message(
                embed=user_hint("Invalid trigger type", "Use message / join / leave / role."),
                ephemeral=True,
            )
            return
        mode_raw = str(self.match_mode.value or "").strip().lower()
        mode = {
            "starts": "startswith",
            "startswith": "startswith",
            "ends": "endswith",
            "endswith": "endswith",
            "word": "word_boundary",
            "word_boundary": "word_boundary",
            "includes": "includes",
            "exact": "exact",
        }.get(mode_raw, "")
        if mode not in _MATCH_MODES:
            await interaction.response.send_message(
                embed=user_hint("Invalid matchmode", "Use exact/startswith/endswith/includes/word_boundary."),
                ephemeral=True,
            )
            return
        try:
            priority = int(str(self.priority.value or "100").strip() or "100")
        except ValueError:
            await interaction.response.send_message("Priority must be number.", ephemeral=True)
            return
        priority = max(1, min(999, priority))
        trs = _normalize_trigger_lines(str(self.trigger_lines.value or ""))
        if trig_type == "message" and not trs:
            await interaction.response.send_message("Add at least one trigger.", ephemeral=True)
            return
        role_id_val: int | None = None
        role_raw = str(self.trigger_role_id.value or "").strip()
        if trig_type == "role_assigned":
            if not role_raw.isdigit():
                await interaction.response.send_message("Role trigger requires numeric role_id.", ephemeral=True)
                return
            role_id_val = int(role_raw)
        await db.patch_autoresponder(
            int(self.row["guild_id"]),
            str(self.row["ar_id"]),
            {
                "trigger_type": trig_type,
                "match_mode": mode,
                "triggers_json": "\n".join(trs),
                "priority": priority,
                "trigger_role_id": role_id_val,
            },
        )
        row = await db.get_autoresponder(int(self.row["guild_id"]), str(self.row["ar_id"]))
        if not row:
            await interaction.response.send_message("AR missing.", ephemeral=True)
            return
        await _refresh_builder(interaction, row, interaction.user.id)


class ResponseModal(discord.ui.Modal, title="Response text"):
    response_text = discord.ui.TextInput(
        label="Response",
        style=discord.TextStyle.paragraph,
        max_length=4000,
        required=False,
    )

    def __init__(self, row: dict[str, Any]) -> None:
        super().__init__(title=f"{row['ar_id']} · response"[:45])
        self.row = row
        self.response_text.default = str(row.get("response_text") or "")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = str(self.response_text.value or "").strip()
        await db.patch_autoresponder(
            int(self.row["guild_id"]),
            str(self.row["ar_id"]),
            {"response_text": raw or None},
        )
        row = await db.get_autoresponder(int(self.row["guild_id"]), str(self.row["ar_id"]))
        if not row:
            await interaction.response.send_message("AR missing.", ephemeral=True)
            return
        await _refresh_builder(interaction, row, interaction.user.id)


class CooldownModal(discord.ui.Modal, title="Set cooldown"):
    cooldown = discord.ui.TextInput(label="Cooldown seconds (0-86400)", required=True, max_length=8, default="0")

    def __init__(
        self,
        row: dict[str, Any],
        *,
        builder_message: discord.Message,
        editor_id: int,
    ) -> None:
        super().__init__(title=f"{row['ar_id']} · cooldown"[:45])
        self.row = row
        self.builder_message = builder_message
        self.editor_id = editor_id
        self.cooldown.default = str(int(row.get("cooldown_seconds") or 0))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            cooldown = max(0, min(86400, int(str(self.cooldown.value or "0").strip() or "0")))
        except ValueError:
            await interaction.response.send_message("Cooldown must be number.", ephemeral=True)
            return
        await db.patch_autoresponder(
            int(self.row["guild_id"]),
            str(self.row["ar_id"]),
            {
                "cooldown_seconds": cooldown,
            },
        )
        row = await db.get_autoresponder(int(self.row["guild_id"]), str(self.row["ar_id"]))
        if not row:
            await interaction.response.send_message("AR missing.", ephemeral=True)
            return
        view = ARBuilderView(row, self.editor_id)
        try:
            await self.builder_message.edit(embed=_ar_preview_embed(row), view=view)
        except (discord.NotFound, discord.HTTPException):
            # Ephemeral source message can be non-editable by channel endpoint.
            pass
        await interaction.response.send_message(embed=success_embed("Cooldown set", f"{cooldown}s"), ephemeral=True)
        _autodismiss_response(interaction, 10)


class ConditionsEditorView(discord.ui.View):
    def __init__(self, row: dict[str, Any], *, builder_message: discord.Message | None, editor_id: int) -> None:
        super().__init__(timeout=300)
        self.row = row
        self.builder_message = builder_message
        self.editor_id = editor_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.editor_id:
            await interaction.response.send_message("Only builder owner can edit conditions.", ephemeral=True)
            return False
        return True

    async def _update_builder(self) -> dict[str, Any] | None:
        row = await db.get_autoresponder(int(self.row["guild_id"]), str(self.row["ar_id"]))
        if not row:
            return None
        self.row = row
        if self.builder_message is not None:
            view = ARBuilderView(row, self.editor_id)
            try:
                await self.builder_message.edit(embed=_ar_preview_embed(row), view=view)
            except (discord.NotFound, discord.HTTPException):
                # Do not fail component interaction when source message can't be edited.
                pass
        return row

    def _summary(self) -> str:
        return (
            f"Cooldown: `{int(self.row.get('cooldown_seconds') or 0)}s`\n"
            f"Required role: `{self.row.get('required_role_id') or 'none'}`\n"
            f"Denied role: `{self.row.get('denied_role_id') or 'none'}`\n"
            f"Required channel: `{self.row.get('required_channel_id') or 'none'}`\n"
            f"Denied channel: `{self.row.get('denied_channel_id') or 'none'}`"
        )

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Required role (optional)",
        min_values=0,
        max_values=1,
        row=0,
    )
    async def req_role_pick(self, interaction: discord.Interaction, sel: discord.ui.RoleSelect) -> None:
        rid = sel.values[0].id if sel.values else None
        await db.patch_autoresponder(int(self.row["guild_id"]), str(self.row["ar_id"]), {"required_role_id": rid})
        row = await self._update_builder()
        if not row:
            await interaction.response.send_message("AR missing.", ephemeral=True)
            return
        await interaction.response.send_message("Required role updated.", ephemeral=True)
        _autodismiss_response(interaction, 10)

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Denied role (optional)",
        min_values=0,
        max_values=1,
        row=1,
    )
    async def deny_role_pick(self, interaction: discord.Interaction, sel: discord.ui.RoleSelect) -> None:
        rid = sel.values[0].id if sel.values else None
        await db.patch_autoresponder(int(self.row["guild_id"]), str(self.row["ar_id"]), {"denied_role_id": rid})
        row = await self._update_builder()
        if not row:
            await interaction.response.send_message("AR missing.", ephemeral=True)
            return
        await interaction.response.send_message("Denied role updated.", ephemeral=True)
        _autodismiss_response(interaction, 10)

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Required channel (optional)",
        min_values=0,
        max_values=1,
        row=2,
    )
    async def req_ch_pick(self, interaction: discord.Interaction, sel: discord.ui.ChannelSelect) -> None:
        cid = sel.values[0].id if sel.values else None
        await db.patch_autoresponder(int(self.row["guild_id"]), str(self.row["ar_id"]), {"required_channel_id": cid})
        row = await self._update_builder()
        if not row:
            await interaction.response.send_message("AR missing.", ephemeral=True)
            return
        await interaction.response.send_message("Required channel updated.", ephemeral=True)
        _autodismiss_response(interaction, 10)

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Denied channel (optional)",
        min_values=0,
        max_values=1,
        row=3,
    )
    async def deny_ch_pick(self, interaction: discord.Interaction, sel: discord.ui.ChannelSelect) -> None:
        cid = sel.values[0].id if sel.values else None
        await db.patch_autoresponder(int(self.row["guild_id"]), str(self.row["ar_id"]), {"denied_channel_id": cid})
        row = await self._update_builder()
        if not row:
            await interaction.response.send_message("AR missing.", ephemeral=True)
            return
        await interaction.response.send_message("Denied channel updated.", ephemeral=True)
        _autodismiss_response(interaction, 10)

    @discord.ui.button(label="set cooldown", style=discord.ButtonStyle.secondary, row=4)
    async def cooldown_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = await db.get_autoresponder(int(self.row["guild_id"]), str(self.row["ar_id"]))
        if not row:
            await interaction.response.send_message("AR missing.", ephemeral=True)
            return
        await interaction.response.send_modal(
            CooldownModal(
                row,
                builder_message=self.builder_message,
                editor_id=self.editor_id,
            )
        )

    @discord.ui.button(label="clear all", style=discord.ButtonStyle.secondary, row=4)
    async def clear_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await db.patch_autoresponder(
            int(self.row["guild_id"]),
            str(self.row["ar_id"]),
            {
                "cooldown_seconds": 0,
                "required_role_id": None,
                "denied_role_id": None,
                "required_channel_id": None,
                "denied_channel_id": None,
            },
        )
        row = await self._update_builder()
        if not row:
            await interaction.response.send_message("AR missing.", ephemeral=True)
            return
        await interaction.response.send_message("Conditions cleared.", ephemeral=True)
        _autodismiss_response(interaction, 10)


class MetaModal(discord.ui.Modal, title="Internal label + note"):
    label = discord.ui.TextInput(label="Internal label", required=False, max_length=100)
    note = discord.ui.TextInput(label="Internal note", required=False, max_length=800, style=discord.TextStyle.paragraph)

    def __init__(self, row: dict[str, Any]) -> None:
        super().__init__(title=f"{row['ar_id']} · internal"[:45])
        self.row = row
        self.label.default = str(row.get("internal_label") or "")
        self.note.default = str(row.get("internal_note") or "")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await db.patch_autoresponder(
            int(self.row["guild_id"]),
            str(self.row["ar_id"]),
            {
                "internal_label": str(self.label.value or "").strip() or None,
                "internal_note": str(self.note.value or "").strip() or None,
            },
        )
        row = await db.get_autoresponder(int(self.row["guild_id"]), str(self.row["ar_id"]))
        if not row:
            await interaction.response.send_message("AR missing.", ephemeral=True)
            return
        await _refresh_builder(interaction, row, interaction.user.id)


class ARBuilderView(discord.ui.View):
    def __init__(self, row: dict[str, Any], editor_id: int) -> None:
        super().__init__(timeout=900)
        self.row = row
        self.editor_id = editor_id
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.editor_id:
            await interaction.response.send_message("Only builder owner can use this.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for c in self.children:
            if hasattr(c, "disabled"):
                c.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(label="trigger + matchmode", style=discord.ButtonStyle.secondary, row=0)
    async def trigger_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = await db.get_autoresponder(int(self.row["guild_id"]), str(self.row["ar_id"]))
        if not row:
            await interaction.response.send_message("AR missing.", ephemeral=True)
            return
        await interaction.response.send_modal(TriggerModal(row))

    @discord.ui.button(label="response", style=discord.ButtonStyle.secondary, row=0)
    async def response_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = await db.get_autoresponder(int(self.row["guild_id"]), str(self.row["ar_id"]))
        if not row:
            await interaction.response.send_message("AR missing.", ephemeral=True)
            return
        await interaction.response.send_modal(ResponseModal(row))

    @discord.ui.button(label="conditions", style=discord.ButtonStyle.secondary, row=0)
    async def cond_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = await db.get_autoresponder(int(self.row["guild_id"]), str(self.row["ar_id"]))
        if not row:
            await interaction.response.send_message("AR missing.", ephemeral=True)
            return
        if interaction.message is None:
            await interaction.response.send_message("Cannot find builder message.", ephemeral=True)
            return
        view = ConditionsEditorView(row, builder_message=interaction.message, editor_id=self.editor_id)
        summary = (
            f"Cooldown: `{int(row.get('cooldown_seconds') or 0)}s`\n"
            f"Required role: `{row.get('required_role_id') or 'none'}`\n"
            f"Denied role: `{row.get('denied_role_id') or 'none'}`\n"
            f"Required channel: `{row.get('required_channel_id') or 'none'}`\n"
            f"Denied channel: `{row.get('denied_channel_id') or 'none'}`"
        )
        await interaction.response.send_message(embed=info_embed("Conditions editor", summary), view=view, ephemeral=True)

    @discord.ui.button(label="internal label/note", style=discord.ButtonStyle.secondary, row=0)
    async def meta_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = await db.get_autoresponder(int(self.row["guild_id"]), str(self.row["ar_id"]))
        if not row:
            await interaction.response.send_message("AR missing.", ephemeral=True)
            return
        await interaction.response.send_modal(MetaModal(row))

    @discord.ui.button(label="variables reference", style=discord.ButtonStyle.secondary, row=1)
    async def vars_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        txt = (
            "`{user}` `{user_name}` `{user_tag}` `{user_id}` `{user_avatar}`\n"
            "`{server_name}` `{server_membercount}` `{channel}` `{channel_name}`\n"
            "`{message_content}` `{message_link}` `{date}` `{newline}`\n"
            "Args: `[$1]` `[$2]` `[$1+]` `[$2+]` `[$3-5]`\n"
            "Inline funcs: `{embed}` `{embed:#hex}` `{dm}` `{delete}` `{delete_reply:N}`"
        )
        await interaction.response.send_message(embed=info_embed("Variables", txt), ephemeral=True)

    @discord.ui.button(label="preview", style=discord.ButtonStyle.secondary, row=1)
    async def preview_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = await db.get_autoresponder(int(self.row["guild_id"]), str(self.row["ar_id"]))
        if not row:
            await interaction.response.send_message("AR missing.", ephemeral=True)
            return
        await interaction.response.send_message(embed=_ar_preview_embed(row), ephemeral=True)

    @discord.ui.button(label="done", style=discord.ButtonStyle.secondary, row=1)
    async def done_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await db.patch_autoresponder(int(self.row["guild_id"]), str(self.row["ar_id"]), {"status": "active"})
        await interaction.response.send_message(
            embed=success_embed("Saved", f"{self.row['ar_id']} is now active."),
            ephemeral=True,
        )
        _autodismiss_response(interaction, 10)
        self.stop()

    @discord.ui.button(label="discard", style=discord.ButtonStyle.secondary, row=1)
    async def discard_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        ok = await db.delete_autoresponder(int(self.row["guild_id"]), str(self.row["ar_id"]))
        if ok:
            await db.log_autoresponder_action(int(self.row["guild_id"]), interaction.user.id, "delete", str(self.row["ar_id"]))
        await interaction.response.send_message(embed=success_embed("Discarded", f"{self.row['ar_id']} deleted."), ephemeral=True)
        _autodismiss_response(interaction, 10)
        self.stop()


async def _refresh_builder(interaction: discord.Interaction, row: dict[str, Any], editor_id: int) -> None:
    view = ARBuilderView(row, editor_id)
    try:
        await interaction.response.edit_message(embed=_ar_preview_embed(row), view=view)
    except (discord.HTTPException, discord.NotFound):
        await interaction.response.send_message(embed=_ar_preview_embed(row), view=view, ephemeral=True)


class ARDeleteConfirmView(discord.ui.View):
    def __init__(self, row: dict[str, Any], user_id: int) -> None:
        super().__init__(timeout=120)
        self.row = row
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your delete prompt.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="yes, delete", style=discord.ButtonStyle.danger)
    async def yes_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        ok = await db.delete_autoresponder(int(self.row["guild_id"]), str(self.row["ar_id"]))
        if ok:
            await db.log_autoresponder_action(int(self.row["guild_id"]), interaction.user.id, "delete", str(self.row["ar_id"]))
        await interaction.response.send_message(embed=success_embed("Deleted", f"{self.row['ar_id']} removed."), ephemeral=True)
        _autodismiss_response(interaction, 10)

    @discord.ui.button(label="cancel", style=discord.ButtonStyle.secondary)
    async def no_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_message("Canceled.", ephemeral=True)
        _autodismiss_response(interaction, 10)


class AutoResponderCog(commands.Cog, name="AutoResponderCog"):
    ar = app_commands.Group(name="ar", description="Autoresponder builder")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _ar_id_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if not interaction.guild:
            return []
        rows = await db.list_autoresponders(interaction.guild.id)
        needle = current.lower().strip()
        out: list[app_commands.Choice[str]] = []
        for r in rows:
            arid = str(r.get("ar_id") or "")
            trig = (str(r.get("triggers_json") or "").splitlines() or [""])[0]
            label = f"{arid} · {trig[:60]}" if trig else arid
            if needle and needle not in arid.lower() and needle not in trig.lower():
                continue
            out.append(app_commands.Choice(name=label[:100], value=arid))
            if len(out) >= 25:
                break
        return out

    async def _can_use(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Use this in server.", ephemeral=True)
            return False
        if interaction.guild.owner_id == interaction.user.id or interaction.user.guild_permissions.administrator:
            return True
        rid = await db.get_guild_setting(interaction.guild.id, gk.STAFF_ROLE)
        if rid and any(r.id == rid for r in interaction.user.roles):
            return True
        await interaction.response.send_message("Staff/admin only.", ephemeral=True)
        return False

    async def _execute_ar(self, message: discord.Message, row: dict[str, Any], trigger_used: str) -> None:
        if not message.guild or not isinstance(message.author, discord.Member):
            return
        member = message.author
        guild = message.guild
        channel = message.channel

        req_role = row.get("required_role_id")
        if req_role and all(r.id != int(req_role) for r in member.roles):
            return
        deny_role = row.get("denied_role_id")
        if deny_role and any(r.id == int(deny_role) for r in member.roles):
            return
        req_ch = row.get("required_channel_id")
        if req_ch and int(req_ch) != channel.id:
            return
        deny_ch = row.get("denied_channel_id")
        if deny_ch and int(deny_ch) == channel.id:
            return

        cooldown = int(row.get("cooldown_seconds") or 0)
        if cooldown > 0:
            last_ts = await db.get_autoresponder_last_fire(guild.id, str(row["ar_id"]), member.id)
            now_ts = _utc_now_ts()
            if last_ts and now_ts - last_ts < cooldown:
                return

        raw = str(row.get("response_text") or "")
        if not raw.strip():
            return
        cleaned, flags = _parse_inline_functions(raw)
        args = _extract_args(message.content, trigger_used, str(row.get("match_mode") or "exact"))
        rendered = _resolve_arg_tokens(cleaned, args)
        rendered = _resolve_basic_vars(
            rendered,
            guild=guild,
            member=member,
            channel=channel if isinstance(channel, (discord.TextChannel, discord.Thread)) else None,
            message=message,
        )

        target_channel: discord.abc.Messageable = channel
        if flags.get("dm"):
            target_channel = member
        send_embed = None
        if flags.get("embed_color"):
            color = str(flags["embed_color"] or "#5865F2")
            try:
                send_embed = discord.Embed(description=rendered or None, color=discord.Color.from_str(color))
                rendered = ""
            except Exception:
                pass

        sent: discord.Message | None = None
        try:
            if send_embed:
                sent = await target_channel.send(embed=send_embed)
            else:
                sent = await target_channel.send(rendered[:2000] or " ")
        except discord.HTTPException:
            return

        if flags.get("delete_trigger"):
            try:
                await message.delete()
            except discord.HTTPException:
                pass
        if flags.get("delete_reply_after") and sent:
            async def _del_later(msg: discord.Message, sec: int) -> None:
                await asyncio.sleep(sec)
                try:
                    await msg.delete()
                except discord.HTTPException:
                    pass
            asyncio.create_task(_del_later(sent, int(flags["delete_reply_after"])))

        await db.bump_autoresponder_fire_count(guild.id, str(row["ar_id"]), member.id)
        await db.log_autoresponder_action(guild.id, member.id, "fire", str(row["ar_id"]), message.channel.id)

    async def _execute_ar_event(
        self,
        *,
        guild: discord.Guild,
        member: discord.Member,
        row: dict[str, Any],
        channel_id: int | None = None,
    ) -> None:
        req_role = row.get("required_role_id")
        if req_role and all(r.id != int(req_role) for r in member.roles):
            return
        deny_role = row.get("denied_role_id")
        if deny_role and any(r.id == int(deny_role) for r in member.roles):
            return
        if channel_id:
            req_ch = row.get("required_channel_id")
            if req_ch and int(req_ch) != int(channel_id):
                return
            deny_ch = row.get("denied_channel_id")
            if deny_ch and int(deny_ch) == int(channel_id):
                return

        cooldown = int(row.get("cooldown_seconds") or 0)
        if cooldown > 0:
            last_ts = await db.get_autoresponder_last_fire(guild.id, str(row["ar_id"]), member.id)
            now_ts = _utc_now_ts()
            if last_ts and now_ts - last_ts < cooldown:
                return

        raw = str(row.get("response_text") or "")
        if not raw.strip():
            return
        cleaned, flags = _parse_inline_functions(raw)
        rendered = _resolve_basic_vars(
            cleaned,
            guild=guild,
            member=member,
            channel=guild.get_channel(channel_id) if channel_id else None,  # type: ignore[arg-type]
            message=None,
        )
        target: discord.abc.Messageable | None = None
        if flags.get("dm"):
            target = member
        else:
            ch: discord.abc.GuildChannel | discord.Thread | None = None
            if channel_id:
                raw_ch = guild.get_channel(channel_id)
                if isinstance(raw_ch, (discord.TextChannel, discord.Thread)):
                    ch = raw_ch
            if ch is None and isinstance(guild.system_channel, discord.TextChannel):
                ch = guild.system_channel
            if ch is None:
                text_channels = [c for c in guild.text_channels if c.permissions_for(guild.me).send_messages] if guild.me else guild.text_channels
                ch = text_channels[0] if text_channels else None
            target = ch
        if target is None:
            return
        try:
            if flags.get("embed_color"):
                color = str(flags["embed_color"] or "#5865F2")
                emb = discord.Embed(description=rendered or None, color=discord.Color.from_str(color))
                await target.send(embed=emb)
            else:
                await target.send(rendered[:2000] or " ")
        except discord.HTTPException:
            return
        await db.bump_autoresponder_fire_count(guild.id, str(row["ar_id"]), member.id)
        ch_id = channel_id if channel_id else None
        await db.log_autoresponder_action(guild.id, member.id, "fire", str(row["ar_id"]), ch_id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild or not isinstance(message.channel, discord.TextChannel):
            return
        rows = await db.list_active_autoresponders(message.guild.id)
        if not rows:
            return
        matches: list[tuple[dict[str, Any], str]] = []
        content = message.content.strip()
        if not content:
            return
        for row in rows:
            if str(row.get("trigger_type") or "message") != "message":
                continue
            mode = str(row.get("match_mode") or "exact")
            trs = [x.strip() for x in str(row.get("triggers_json") or "").split("\n") if x.strip()]
            for t in trs:
                if _match_message(content, t, mode):
                    matches.append((row, t))
                    break
        if not matches:
            return
        matches.sort(key=lambda x: (int(x[0].get("priority") or 100), -len(x[1])))
        row, trig = matches[0]
        await self._execute_ar(message, row, trig)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        rows = await db.list_active_autoresponders(member.guild.id)
        targets = [r for r in rows if str(r.get("trigger_type") or "") == "member_join"]
        targets.sort(key=lambda r: int(r.get("priority") or 100))
        for row in targets[:5]:
            await self._execute_ar_event(guild=member.guild, member=member, row=row)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        rows = await db.list_active_autoresponders(member.guild.id)
        targets = [r for r in rows if str(r.get("trigger_type") or "") == "member_leave"]
        targets.sort(key=lambda r: int(r.get("priority") or 100))
        for row in targets[:5]:
            await self._execute_ar_event(guild=member.guild, member=member, row=row)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        before_ids = {r.id for r in before.roles}
        added = [r for r in after.roles if r.id not in before_ids]
        if not added:
            return
        rows = await db.list_active_autoresponders(after.guild.id)
        role_rows = [r for r in rows if str(r.get("trigger_type") or "") == "role_assigned" and r.get("trigger_role_id")]
        if not role_rows:
            return
        added_ids = {r.id for r in added}
        for row in sorted(role_rows, key=lambda r: int(r.get("priority") or 100)):
            target_role = int(row.get("trigger_role_id") or 0)
            if target_role in added_ids:
                await self._execute_ar_event(guild=after.guild, member=after, row=row)

    @ar.command(name="create", description="Create autoresponder draft (builder)")
    async def create_cmd(self, interaction: discord.Interaction) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        row = await db.create_autoresponder(interaction.guild.id, interaction.user.id)
        await db.log_autoresponder_action(interaction.guild.id, interaction.user.id, "create", str(row["ar_id"]))
        view = ARBuilderView(row, interaction.user.id)
        await interaction.response.send_message(embed=_ar_preview_embed(row), view=view, ephemeral=True)
        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            pass

    @ar.command(name="edit", description="Edit autoresponder by ID")
    @app_commands.describe(id="AR-001", field="Optional single field")
    @app_commands.choices(
        field=[
            app_commands.Choice(name="trigger", value="trigger"),
            app_commands.Choice(name="response", value="response"),
            app_commands.Choice(name="conditions", value="conditions"),
        ]
    )
    @app_commands.autocomplete(id=_ar_id_autocomplete)
    async def edit_cmd(self, interaction: discord.Interaction, id: str, field: str | None = None) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        row = await db.get_autoresponder(interaction.guild.id, id.upper())
        if not row:
            await interaction.response.send_message(embed=user_hint("Missing", f"No AR `{id.upper()}`."), ephemeral=True)
            return
        if field == "trigger":
            await interaction.response.send_modal(TriggerModal(row))
            return
        if field == "response":
            await interaction.response.send_modal(ResponseModal(row))
            return
        if field == "conditions":
            view = ConditionsEditorView(
                row,
                builder_message=None,
                editor_id=interaction.user.id,
            )
            await interaction.response.send_message(embed=info_embed("Conditions editor", view._summary()), view=view, ephemeral=True)
            return
        view = ARBuilderView(row, interaction.user.id)
        await interaction.response.send_message(embed=_ar_preview_embed(row), view=view, ephemeral=True)
        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            pass

    @ar.command(name="delete", description="Delete autoresponder")
    @app_commands.describe(id="AR-001")
    @app_commands.autocomplete(id=_ar_id_autocomplete)
    async def delete_cmd(self, interaction: discord.Interaction, id: str) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        row = await db.get_autoresponder(interaction.guild.id, id.upper())
        if not row:
            await interaction.response.send_message("Not found.", ephemeral=True)
            return
        txt = f"Delete **{row['ar_id']}**?\nTrigger: `{(str(row.get('triggers_json') or '').splitlines() or [''])[0]}`"
        await interaction.response.send_message(
            embed=user_warn("Confirm delete", txt),
            view=ARDeleteConfirmView(row, interaction.user.id),
            ephemeral=True,
        )

    @ar.command(name="list", description="List autoresponders")
    async def list_cmd(self, interaction: discord.Interaction) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        rows = await db.list_autoresponders(interaction.guild.id)
        if not rows:
            await interaction.response.send_message(embed=info_embed("Autoresponders", "None yet. Run `/ar create`."), ephemeral=True)
            return
        lines: list[str] = []
        for r in rows[:50]:
            tr = (str(r.get("triggers_json") or "").splitlines() or [""])[0]
            label = str(r.get("internal_label") or "")
            lbl = f"{label} · " if label else ""
            lines.append(f"`{r['ar_id']}` · {lbl}`{tr[:24]}` · {r.get('match_mode')} · {r.get('status')}")
        if len(rows) > 50:
            lines.append(f"... +{len(rows)-50} more")
        await interaction.response.send_message(embed=info_embed(f"AR list ({len(rows)})", "\n".join(lines)[:4000]), ephemeral=True)

    @ar.command(name="showlist", description="Extended list with details")
    async def showlist_cmd(self, interaction: discord.Interaction) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        rows = await db.list_autoresponders(interaction.guild.id)
        if not rows:
            await interaction.response.send_message("No autoresponders.", ephemeral=True)
            return
        lines: list[str] = []
        for r in rows[:30]:
            trigger_line = (str(r.get("triggers_json") or "").splitlines() or [""])[0][:32]
            lines.append(
                f"`{r['ar_id']}` {r.get('status')} · {r.get('trigger_type')}:{r.get('match_mode')} · "
                f"prio {int(r.get('priority') or 100)} · fired {int(r.get('fire_count') or 0)} · `{trigger_line}`"
            )
        if len(rows) > 30:
            lines.append(f"... +{len(rows)-30} more")
        await interaction.response.send_message(
            embed=info_embed(f"AR showlist ({len(rows)})", "\n".join(lines)[:4000]),
            ephemeral=True,
        )

    @ar.command(name="search", description="Search autoresponders")
    @app_commands.describe(query="Match ID/trigger/label", status="Filter status")
    @app_commands.choices(
        status=[
            app_commands.Choice(name="any", value="any"),
            app_commands.Choice(name="active", value="active"),
            app_commands.Choice(name="paused", value="paused"),
            app_commands.Choice(name="draft", value="draft"),
        ]
    )
    async def search_cmd(
        self,
        interaction: discord.Interaction,
        query: str | None = None,
        status: str = "any",
    ) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        status_filter = None if status == "any" else status
        rows = await db.search_autoresponders(interaction.guild.id, query=query, status=status_filter)
        if not rows:
            await interaction.response.send_message("No matches.", ephemeral=True)
            return
        lines = [f"`{r['ar_id']}` · {r.get('status')} · {r.get('trigger_type')} · `{(str(r.get('triggers_json') or '').splitlines() or [''])[0][:40]}`" for r in rows[:50]]
        if len(rows) > 50:
            lines.append(f"... +{len(rows)-50} more")
        await interaction.response.send_message(
            embed=info_embed(f"AR search ({len(rows)})", "\n".join(lines)[:4000]),
            ephemeral=True,
        )

    @ar.command(name="stats", description="Show autoresponder stats")
    @app_commands.describe(id="AR-001")
    @app_commands.autocomplete(id=_ar_id_autocomplete)
    async def stats_cmd(self, interaction: discord.Interaction, id: str) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        stats = await db.get_autoresponder_stats(interaction.guild.id, id.upper())
        if not stats:
            await interaction.response.send_message("Not found.", ephemeral=True)
            return
        body = (
            f"Status: `{stats['status']}`\n"
            f"Total fires: **{int(stats['fire_count'])}**\n"
            f"Unique users hit cooldown cache: **{int(stats['unique_users'])}**\n"
            f"Last fired at: `{stats['last_fired_at'] or 'never'}`\n"
            f"Last actor id: `{stats['last_actor_user_id'] or 'n/a'}`"
        )
        await interaction.response.send_message(embed=info_embed(f"Stats {id.upper()}", body), ephemeral=True)

    @ar.command(name="export", description="Export autoresponders as JSON")
    async def export_cmd(self, interaction: discord.Interaction) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        rows = await db.list_autoresponders(interaction.guild.id)
        payload = {
            "guild_id": interaction.guild.id,
            "count": len(rows),
            "entries": rows,
        }
        raw = json.dumps(payload, indent=2, ensure_ascii=False)
        fp = io.BytesIO(raw.encode("utf-8"))
        file = discord.File(fp=fp, filename=f"ar-export-{interaction.guild.id}.json")
        await interaction.response.send_message("AR export generated.", file=file, ephemeral=True)

    @ar.command(name="import", description="Import autoresponders from JSON export")
    @app_commands.describe(file="JSON file from /ar export", mode="merge keeps existing IDs")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="merge", value="merge"),
            app_commands.Choice(name="replace", value="replace"),
        ]
    )
    async def import_cmd(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        mode: str = "merge",
    ) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        if not file.filename.lower().endswith(".json"):
            await interaction.response.send_message("File must be .json", ephemeral=True)
            return
        blob = await file.read()
        try:
            payload = json.loads(blob.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            await interaction.response.send_message("Invalid JSON payload.", ephemeral=True)
            return
        entries = payload.get("entries")
        if not isinstance(entries, list):
            await interaction.response.send_message("Payload missing `entries` list.", ephemeral=True)
            return
        imported = 0
        skipped = 0
        for e in entries[:300]:
            if not isinstance(e, dict):
                skipped += 1
                continue
            ar_id = str(e.get("ar_id") or "").upper().strip()
            if not ar_id:
                skipped += 1
                continue
            current = await db.get_autoresponder(interaction.guild.id, ar_id)
            if current and mode == "merge":
                skipped += 1
                continue
            if current:
                target_id = ar_id
            else:
                created = await db.create_autoresponder(interaction.guild.id, interaction.user.id)
                target_id = str(created["ar_id"])
            await db.patch_autoresponder(
                interaction.guild.id,
                target_id,
                {
                    "status": str(e.get("status") or "draft"),
                    "trigger_type": str(e.get("trigger_type") or "message"),
                    "match_mode": str(e.get("match_mode") or "exact"),
                    "triggers_json": str(e.get("triggers_json") or ""),
                    "response_text": str(e.get("response_text") or ""),
                    "priority": int(e.get("priority") or 100),
                    "cooldown_seconds": int(e.get("cooldown_seconds") or 0),
                    "required_role_id": e.get("required_role_id"),
                    "denied_role_id": e.get("denied_role_id"),
                    "required_channel_id": e.get("required_channel_id"),
                    "denied_channel_id": e.get("denied_channel_id"),
                    "trigger_role_id": e.get("trigger_role_id"),
                    "trigger_channel_id": e.get("trigger_channel_id"),
                    "trigger_message_id": e.get("trigger_message_id"),
                    "trigger_emoji": e.get("trigger_emoji"),
                    "internal_label": e.get("internal_label"),
                    "internal_note": e.get("internal_note"),
                },
            )
            imported += 1
        await interaction.response.send_message(
            embed=success_embed("Import complete", f"Imported: **{imported}** · Skipped: **{skipped}**"),
            ephemeral=True,
        )

    @ar.command(name="pause", description="Pause autoresponder")
    @app_commands.describe(id="AR-001")
    @app_commands.autocomplete(id=_ar_id_autocomplete)
    async def pause_cmd(self, interaction: discord.Interaction, id: str) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        ok = await db.patch_autoresponder(interaction.guild.id, id.upper(), {"status": "paused"})
        if not ok:
            await interaction.response.send_message("Not found.", ephemeral=True)
            return
        await db.log_autoresponder_action(interaction.guild.id, interaction.user.id, "pause", id.upper())
        await interaction.response.send_message(embed=success_embed("Paused", f"{id.upper()} paused."), ephemeral=True)
        _autodismiss_response(interaction, 10)

    @ar.command(name="resume", description="Resume autoresponder")
    @app_commands.describe(id="AR-001")
    @app_commands.autocomplete(id=_ar_id_autocomplete)
    async def resume_cmd(self, interaction: discord.Interaction, id: str) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        ok = await db.patch_autoresponder(interaction.guild.id, id.upper(), {"status": "active"})
        if not ok:
            await interaction.response.send_message("Not found.", ephemeral=True)
            return
        await db.log_autoresponder_action(interaction.guild.id, interaction.user.id, "resume", id.upper())
        await interaction.response.send_message(embed=success_embed("Resumed", f"{id.upper()} active."), ephemeral=True)
        _autodismiss_response(interaction, 10)

    @ar.command(name="setembed", description="Set AR response to a builder embed")
    @app_commands.describe(id="AR-001", embed_id="EMB-001")
    @app_commands.autocomplete(id=_ar_id_autocomplete)
    async def setembed_cmd(self, interaction: discord.Interaction, id: str, embed_id: str) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        emb = await db.get_builder_embed(interaction.guild.id, embed_id.upper())
        if not emb:
            await interaction.response.send_message(embed=user_hint("Embed missing", f"No embed `{embed_id.upper()}`."), ephemeral=True)
            return
        ok = await db.patch_autoresponder(
            interaction.guild.id,
            id.upper(),
            {"response_text": f"{{embed:{embed_id.upper()}}}"},
        )
        if not ok:
            await interaction.response.send_message("AR not found.", ephemeral=True)
            return
        await db.log_autoresponder_action(interaction.guild.id, interaction.user.id, "set_embed", id.upper())
        await interaction.response.send_message(
            embed=success_embed("AR linked", f"{id.upper()} now sends `{embed_id.upper()}`."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoResponderCog(bot))
