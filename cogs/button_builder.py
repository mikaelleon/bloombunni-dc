"""Interactive button builder (BTN-XXX) — role actions + ephemeral responses."""

from __future__ import annotations

import json
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils.embeds import info_embed, success_embed, user_hint, user_warn

CUSTOM_PREFIX = "bb:"
STYLE_KEYS = ("primary", "secondary", "success", "danger")


def _style_from_key(key: str) -> discord.ButtonStyle:
    return {
        "primary": discord.ButtonStyle.primary,
        "secondary": discord.ButtonStyle.secondary,
        "success": discord.ButtonStyle.success,
        "danger": discord.ButtonStyle.danger,
    }.get(key or "secondary", discord.ButtonStyle.secondary)


def _parse_custom_id(custom_id: str) -> tuple[int, str] | None:
    if not custom_id.startswith(CUSTOM_PREFIX):
        return None
    rest = custom_id[len(CUSTOM_PREFIX) :]
    idx = rest.rfind(":")
    if idx <= 0:
        return None
    guild_s, bid = rest[:idx], rest[idx + 1 :]
    if not guild_s.isdigit() or not bid:
        return None
    return int(guild_s), bid.upper()


def _emoji_from_row(row: dict[str, Any]) -> discord.PartialEmoji | str | None:
    raw = row.get("emoji_str")
    if not raw or not str(raw).strip():
        return None
    t = str(raw).strip()
    try:
        return discord.PartialEmoji.from_str(t)
    except Exception:
        return t if len(t) <= 32 else None


def _preview_button_from_row(row: dict[str, Any], *, row_idx: int = 0) -> discord.ui.Button:
    label = str(row.get("label") or "Button")[:80]
    emoji = _emoji_from_row(row)
    style = _style_from_key(str(row.get("style") or "secondary"))
    btn = discord.ui.Button(
        label=label,
        style=style,
        disabled=True,
        emoji=emoji,
        row=row_idx,
    )
    return btn


def _live_button_from_row(guild_id: int, row: dict[str, Any]) -> discord.ui.Button:
    bid = str(row["button_id"])
    label = str(row.get("label") or "Button")[:80]
    emoji = _emoji_from_row(row)
    style = _style_from_key(str(row.get("style") or "secondary"))

    class _LiveBtn(discord.ui.Button):
        def __init__(self) -> None:
            super().__init__(
                label=label,
                style=style,
                custom_id=f"{CUSTOM_PREFIX}{guild_id}:{bid}",
                emoji=emoji,
                row=0,
            )

        async def callback(self, interaction: discord.Interaction) -> None:
            cog = interaction.client.get_cog("ButtonBuilderCog")
            if isinstance(cog, ButtonBuilderCog):
                await cog.handle_public_click(interaction)

    return _LiveBtn()


def _default_responses() -> dict[str, str]:
    return {
        "on_success": "✅ Done!",
        "on_already_has": "You already have this role.",
        "on_not_have": "You don't have this role.",
        "on_toggle_add": "✅ Role added.",
        "on_toggle_remove": "❌ Role removed.",
    }


def _merged_responses(row: dict[str, Any]) -> dict[str, str]:
    out = _default_responses()
    raw = row.get("responses_json")
    if raw:
        try:
            data = json.loads(str(raw))
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, str) and k in out:
                        out[k] = v
        except json.JSONDecodeError:
            pass
    return out


def _resolve_response(
    text: str,
    *,
    member: discord.Member,
    guild: discord.Guild,
    role: discord.Role | None,
) -> str:
    out = text
    role_name = role.name if role else "role"
    mapping = {
        "{user_name}": member.display_name,
        "{user_tag}": str(member),
        "{user_mention}": member.mention,
        "{server_name}": guild.name,
        "{role_name}": role_name,
    }
    for k, v in mapping.items():
        out = out.replace(k, v)
    return out[:2000]


def _action_summary(row: dict[str, Any]) -> str:
    at = str(row.get("action_type") or "toggle_role")
    rid = row.get("role_id")
    if not rid:
        return f"{at} — **no role set** (configure Action)"
    return f"{at} — role id `{rid}`"


def _builder_header_embed(button_id: str, row: dict[str, Any]) -> discord.Embed:
    lines = [
        f"**Action:** {_action_summary(row)}",
    ]
    if row.get("internal_label"):
        lines.append(f"**Staff label:** {row['internal_label']}")
    return info_embed(f"🔘 Button builder — {button_id}", "\n".join(lines))


async def _refresh_builder_message(
    interaction: discord.Interaction,
    row: dict[str, Any],
    editor_id: int,
    cog: "ButtonBuilderCog",
) -> None:
    view = ButtonBuilderView(cog, row, editor_id)
    header = _builder_header_embed(str(row["button_id"]), row)
    try:
        await interaction.response.edit_message(
            embeds=[header],
            view=view,
        )
    except (discord.HTTPException, discord.NotFound):
        await interaction.response.send_message(
            embeds=[header],
            view=view,
            ephemeral=True,
        )


class LabelModal(discord.ui.Modal, title="Button label"):
    val = discord.ui.TextInput(label="Label (max 80)", required=True, max_length=80)

    def __init__(self, row: dict[str, Any]) -> None:
        super().__init__(title=f"{row['button_id']} · label"[:45])
        self.row = row
        self.val.default = str(row.get("label") or "Button")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        label = str(self.val.value or "").strip() or "Button"
        await db.patch_builder_button(int(self.row["guild_id"]), str(self.row["button_id"]), {"label": label})
        row = await db.get_builder_button(int(self.row["guild_id"]), str(self.row["button_id"]))
        if not row:
            await interaction.response.send_message("Button missing.", ephemeral=True)
            return
        await _refresh_builder_message(interaction, row, interaction.user.id, interaction.client.get_cog("ButtonBuilderCog"))  # type: ignore[arg-type]


class EmojiModal(discord.ui.Modal, title="Button emoji"):
    val = discord.ui.TextInput(
        label="Emoji (optional)",
        required=False,
        max_length=32,
        placeholder="Unicode or <:name:id>",
    )

    def __init__(self, row: dict[str, Any]) -> None:
        super().__init__(title=f"{row['button_id']} · emoji"[:45])
        self.row = row
        self.val.default = str(row.get("emoji_str") or "")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = str(self.val.value or "").strip()
        if raw:
            try:
                discord.PartialEmoji.from_str(raw)
            except Exception:
                await interaction.response.send_message(
                    embed=user_hint("Invalid emoji", "Use Unicode or custom `<:name:id>`."),
                    ephemeral=True,
                )
                return
        await db.patch_builder_button(
            int(self.row["guild_id"]),
            str(self.row["button_id"]),
            {"emoji_str": raw or None},
        )
        row = await db.get_builder_button(int(self.row["guild_id"]), str(self.row["button_id"]))
        if not row:
            await interaction.response.send_message("Button missing.", ephemeral=True)
            return
        await _refresh_builder_message(interaction, row, interaction.user.id, interaction.client.get_cog("ButtonBuilderCog"))  # type: ignore[arg-type]


class StaffNoteModal(discord.ui.Modal, title="Staff-only note"):
    lab = discord.ui.TextInput(label="Internal label", required=False, max_length=100)
    note = discord.ui.TextInput(
        label="Internal note",
        required=False,
        max_length=500,
        style=discord.TextStyle.paragraph,
    )

    def __init__(self, row: dict[str, Any]) -> None:
        super().__init__(title=f"{row['button_id']} · staff"[:45])
        self.row = row
        self.lab.default = str(row.get("internal_label") or "")
        self.note.default = str(row.get("internal_note") or "")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await db.patch_builder_button(
            int(self.row["guild_id"]),
            str(self.row["button_id"]),
            {
                "internal_label": str(self.lab.value or "").strip() or None,
                "internal_note": str(self.note.value or "").strip() or None,
            },
        )
        row = await db.get_builder_button(int(self.row["guild_id"]), str(self.row["button_id"]))
        if not row:
            await interaction.response.send_message("Button missing.", ephemeral=True)
            return
        await _refresh_builder_message(interaction, row, interaction.user.id, interaction.client.get_cog("ButtonBuilderCog"))  # type: ignore[arg-type]


class ResponsesModal(discord.ui.Modal, title="Ephemeral responses"):
    on_success = discord.ui.TextInput(label="On success (assign)", required=False, max_length=500)
    on_already = discord.ui.TextInput(label="Already has role", required=False, max_length=500)
    on_not_have = discord.ui.TextInput(label="Doesn't have role (remove)", required=False, max_length=500)
    on_add = discord.ui.TextInput(label="Toggle: added", required=False, max_length=500)
    on_rem = discord.ui.TextInput(label="Toggle: removed", required=False, max_length=500)

    def __init__(self, row: dict[str, Any]) -> None:
        super().__init__(title=f"{row['button_id']} · responses"[:45])
        self.row = row
        m = _merged_responses(row)
        self.on_success.default = m.get("on_success", "")
        self.on_already.default = m.get("on_already_has", "")
        self.on_not_have.default = m.get("on_not_have", "")
        self.on_add.default = m.get("on_toggle_add", "")
        self.on_rem.default = m.get("on_toggle_remove", "")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        data = {
            "on_success": str(self.on_success.value or "").strip(),
            "on_already_has": str(self.on_already.value or "").strip(),
            "on_not_have": str(self.on_not_have.value or "").strip(),
            "on_toggle_add": str(self.on_add.value or "").strip(),
            "on_toggle_remove": str(self.on_rem.value or "").strip(),
        }
        payload = {k: v for k, v in data.items() if v}
        await db.patch_builder_button(
            int(self.row["guild_id"]),
            str(self.row["button_id"]),
            {"responses_json": json.dumps(payload) if payload else None},
        )
        row = await db.get_builder_button(int(self.row["guild_id"]), str(self.row["button_id"]))
        if not row:
            await interaction.response.send_message("Button missing.", ephemeral=True)
            return
        await _refresh_builder_message(interaction, row, interaction.user.id, interaction.client.get_cog("ButtonBuilderCog"))  # type: ignore[arg-type]


class StylePickView(discord.ui.View):
    def __init__(
        self,
        cog: "ButtonBuilderCog",
        row: dict[str, Any],
        builder_message: discord.Message,
        editor_id: int,
    ) -> None:
        super().__init__(timeout=120)
        self.cog = cog
        self.row = row
        self.builder_message = builder_message
        self.editor_id = editor_id

    @discord.ui.select(
        placeholder="Button color",
        options=[
            discord.SelectOption(label="Blurple (primary)", value="primary"),
            discord.SelectOption(label="Grey (secondary)", value="secondary"),
            discord.SelectOption(label="Green (success)", value="success"),
            discord.SelectOption(label="Red (danger)", value="danger"),
        ],
    )
    async def pick(self, interaction: discord.Interaction, sel: discord.ui.Select) -> None:
        v = sel.values[0]
        if v not in STYLE_KEYS:
            await interaction.response.send_message("Invalid.", ephemeral=True)
            return
        await db.patch_builder_button(int(self.row["guild_id"]), str(self.row["button_id"]), {"style": v})
        row = await db.get_builder_button(int(self.row["guild_id"]), str(self.row["button_id"]))
        if not row:
            await interaction.response.send_message("Button missing.", ephemeral=True)
            return
        view = ButtonBuilderView(self.cog, row, self.editor_id)
        await self.builder_message.edit(
            embeds=[_builder_header_embed(str(row["button_id"]), row)],
            view=view,
        )
        await interaction.response.send_message(embed=success_embed("Style updated", v), ephemeral=True)
        self.stop()


class ActionConfigView(discord.ui.View):
    def __init__(
        self,
        cog: "ButtonBuilderCog",
        row: dict[str, Any],
        builder_message: discord.Message,
        editor_id: int,
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.row = row
        self.builder_message = builder_message
        self.editor_id = editor_id
        self._action_type = str(row.get("action_type") or "toggle_role")

    @discord.ui.select(
        placeholder="Action type",
        options=[
            discord.SelectOption(label="Assign role", value="assign_role"),
            discord.SelectOption(label="Remove role", value="remove_role"),
            discord.SelectOption(label="Toggle role", value="toggle_role"),
        ],
    )
    async def act_pick(self, interaction: discord.Interaction, sel: discord.ui.Select) -> None:
        self._action_type = sel.values[0]
        await interaction.response.send_message(
            f"Action: **{self._action_type}**. Now pick the role below.",
            ephemeral=True,
        )

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Target role", min_values=1, max_values=1)
    async def role_pick(self, interaction: discord.Interaction, sel: discord.ui.RoleSelect) -> None:
        role = sel.values[0]
        at = self._action_type
        await db.patch_builder_button(
            int(self.row["guild_id"]),
            str(self.row["button_id"]),
            {"action_type": at, "role_id": role.id},
        )
        row = await db.get_builder_button(int(self.row["guild_id"]), str(self.row["button_id"]))
        if not row:
            await interaction.response.send_message("Button missing.", ephemeral=True)
            return
        view = ButtonBuilderView(self.cog, row, self.editor_id)
        await self.builder_message.edit(
            embeds=[_builder_header_embed(str(row["button_id"]), row)],
            view=view,
        )
        await interaction.response.send_message(
            embed=success_embed("Action saved", f"{at} → {role.mention}"),
            ephemeral=True,
        )
        self.stop()


class ButtonBuilderView(discord.ui.View):
    def __init__(self, cog: "ButtonBuilderCog", row: dict[str, Any], editor_id: int) -> None:
        super().__init__(timeout=900)
        self.cog = cog
        self.row = row
        self.editor_id = editor_id
        self.message: discord.Message | None = None
        self.add_item(_preview_button_from_row(row, row_idx=2))

    async def on_timeout(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True
        if self.message:
            try:
                await self.message.edit(
                    embeds=[
                        info_embed(
                            f"{self.row['button_id']} — session ended",
                            "Use `/button edit` to reopen.",
                        ),
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

    @discord.ui.button(label="label", style=discord.ButtonStyle.secondary, row=0)
    async def b_label(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = await db.get_builder_button(int(self.row["guild_id"]), str(self.row["button_id"]))
        if not row:
            await interaction.response.send_message("Button missing.", ephemeral=True)
            return
        await interaction.response.send_modal(LabelModal(row))

    @discord.ui.button(label="emoji", style=discord.ButtonStyle.secondary, row=0)
    async def b_emoji(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = await db.get_builder_button(int(self.row["guild_id"]), str(self.row["button_id"]))
        if not row:
            await interaction.response.send_message("Button missing.", ephemeral=True)
            return
        await interaction.response.send_modal(EmojiModal(row))

    @discord.ui.button(label="style", style=discord.ButtonStyle.secondary, row=0)
    async def b_style(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = await db.get_builder_button(int(self.row["guild_id"]), str(self.row["button_id"]))
        if not row:
            await interaction.response.send_message("Button missing.", ephemeral=True)
            return
        msg = interaction.message
        if msg is None:
            await interaction.response.send_message("Cannot find builder message to refresh.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=info_embed("Pick style", "Choose button color."),
            view=StylePickView(self.cog, row, msg, self.editor_id),
            ephemeral=True,
        )

    @discord.ui.button(label="action + role", style=discord.ButtonStyle.secondary, row=0)
    async def b_action(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = await db.get_builder_button(int(self.row["guild_id"]), str(self.row["button_id"]))
        if not row:
            await interaction.response.send_message("Button missing.", ephemeral=True)
            return
        msg = interaction.message
        if msg is None:
            await interaction.response.send_message("Cannot find builder message to refresh.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=info_embed("Action", "Pick action type, then role."),
            view=ActionConfigView(self.cog, row, msg, self.editor_id),
            ephemeral=True,
        )

    @discord.ui.button(label="staff note", style=discord.ButtonStyle.secondary, row=0)
    async def b_staff(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = await db.get_builder_button(int(self.row["guild_id"]), str(self.row["button_id"]))
        if not row:
            await interaction.response.send_message("Button missing.", ephemeral=True)
            return
        await interaction.response.send_modal(StaffNoteModal(row))

    @discord.ui.button(label="responses", style=discord.ButtonStyle.secondary, row=1)
    async def b_resp(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = await db.get_builder_button(int(self.row["guild_id"]), str(self.row["button_id"]))
        if not row:
            await interaction.response.send_message("Button missing.", ephemeral=True)
            return
        await interaction.response.send_modal(ResponsesModal(row))

    @discord.ui.button(label="variables", style=discord.ButtonStyle.secondary, row=1)
    async def b_vars(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        txt = (
            "In responses: `{user_name}` `{user_mention}` `{user_tag}` "
            "`{server_name}` `{role_name}`"
        )
        await interaction.response.send_message(embed=info_embed("Variables", txt), ephemeral=True)

    @discord.ui.button(label="preview", style=discord.ButtonStyle.secondary, row=1)
    async def b_preview(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        row = await db.get_builder_button(int(self.row["guild_id"]), str(self.row["button_id"]))
        if not row:
            await interaction.response.send_message("Button missing.", ephemeral=True)
            return
        pv = discord.ui.View(timeout=60)
        pv.add_item(_preview_button_from_row(row))
        await interaction.response.send_message(
            embed=info_embed("Preview", _action_summary(row)),
            view=pv,
            ephemeral=True,
        )

    @discord.ui.button(label="done", style=discord.ButtonStyle.secondary, row=1)
    async def b_done(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await db.patch_builder_button(int(self.row["guild_id"]), str(self.row["button_id"]), {"status": "active"})
        await interaction.response.send_message(
            embed=success_embed("Saved", f"{self.row['button_id']} ready. Use `/button post` to place it."),
            ephemeral=True,
        )
        self.stop()

    @discord.ui.button(label="discard", style=discord.ButtonStyle.secondary, row=1)
    async def b_disc(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        ok = await db.delete_builder_button(int(self.row["guild_id"]), str(self.row["button_id"]))
        if ok:
            await db.log_button_builder_action(int(self.row["guild_id"]), self.editor_id, "delete", str(self.row["button_id"]))
        await interaction.response.send_message(
            embed=success_embed("Discarded", f"{self.row['button_id']} removed."),
            ephemeral=True,
        )
        self.stop()


class ButtonBuilderCog(commands.Cog, name="ButtonBuilderCog"):
    button = app_commands.Group(name="button", description="Button builder (role actions)")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _can_use(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return False
        if interaction.guild.owner_id == interaction.user.id:
            return True
        if interaction.user.guild_permissions.administrator:
            return True
        roles = await db.list_embed_staff_roles(interaction.guild.id)
        if roles and any(r.id in roles for r in interaction.user.roles):
            return True
        await interaction.response.send_message(
            "No permission. Admins, owner, or `/embed config staffrole` roles only.",
            ephemeral=True,
        )
        return False

    async def handle_public_click(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Use in server.", ephemeral=True)
            return
        cid = interaction.data.get("custom_id") if interaction.data else None
        if not cid or not isinstance(cid, str):
            await interaction.response.send_message("Invalid interaction.", ephemeral=True)
            return
        parsed = _parse_custom_id(cid)
        if not parsed:
            await interaction.response.send_message("Invalid button.", ephemeral=True)
            return
        guild_id, bid = parsed
        if guild_id != interaction.guild.id:
            await interaction.response.send_message("Wrong server.", ephemeral=True)
            return
        row = await db.get_builder_button(guild_id, bid)
        if not row or str(row.get("status") or "") != "active":
            await interaction.response.send_message(
                embed=user_warn("Inactive", "This button is not available."),
                ephemeral=True,
            )
            return
        rid = row.get("role_id")
        if not rid:
            await interaction.response.send_message(
                embed=user_warn("Misconfigured", "Button has no role."),
                ephemeral=True,
            )
            return
        role = interaction.guild.get_role(int(rid))
        if not role:
            await interaction.response.send_message(
                embed=user_warn("Missing role", "Target role was deleted."),
                ephemeral=True,
            )
            return
        me = interaction.guild.me
        if me and role >= me.top_role:
            await interaction.response.send_message(
                embed=user_warn("Hierarchy", "Bot cannot manage this role."),
                ephemeral=True,
            )
            return
        resp = _merged_responses(row)
        at = str(row.get("action_type") or "toggle_role")
        member = interaction.user

        if at == "assign_role":
            if role in member.roles:
                raw = resp.get("on_already_has") or _default_responses()["on_already_has"]
                text = _resolve_response(raw, member=member, guild=interaction.guild, role=role)
                await interaction.response.send_message(text[:2000], ephemeral=True)
                return
            try:
                await member.add_roles(role, reason=f"Button {bid}")
            except discord.HTTPException as e:
                await interaction.response.send_message(
                    embed=user_warn("Failed", str(e)[:500]),
                    ephemeral=True,
                )
                return
            raw = resp.get("on_success") or _default_responses()["on_success"]
            text = _resolve_response(raw, member=member, guild=interaction.guild, role=role)
            await interaction.response.send_message(text[:2000], ephemeral=True)
            return

        if at == "remove_role":
            if role not in member.roles:
                raw = resp.get("on_not_have") or _default_responses()["on_not_have"]
                text = _resolve_response(raw, member=member, guild=interaction.guild, role=role)
                await interaction.response.send_message(text[:2000], ephemeral=True)
                return
            try:
                await member.remove_roles(role, reason=f"Button {bid}")
            except discord.HTTPException as e:
                await interaction.response.send_message(
                    embed=user_warn("Failed", str(e)[:500]),
                    ephemeral=True,
                )
                return
            raw = resp.get("on_success") or _default_responses()["on_success"]
            text = _resolve_response(raw, member=member, guild=interaction.guild, role=role)
            await interaction.response.send_message(text[:2000], ephemeral=True)
            return

        # toggle
        if role in member.roles:
            try:
                await member.remove_roles(role, reason=f"Button {bid}")
            except discord.HTTPException as e:
                await interaction.response.send_message(
                    embed=user_warn("Failed", str(e)[:500]),
                    ephemeral=True,
                )
                return
            raw = resp.get("on_toggle_remove") or _default_responses()["on_toggle_remove"]
            text = _resolve_response(raw, member=member, guild=interaction.guild, role=role)
            await interaction.response.send_message(text[:2000], ephemeral=True)
            return
        try:
            await member.add_roles(role, reason=f"Button {bid}")
        except discord.HTTPException as e:
            await interaction.response.send_message(
                embed=user_warn("Failed", str(e)[:500]),
                ephemeral=True,
            )
            return
        raw = resp.get("on_toggle_add") or _default_responses()["on_toggle_add"]
        text = _resolve_response(raw, member=member, guild=interaction.guild, role=role)
        await interaction.response.send_message(text[:2000], ephemeral=True)

    @button.command(name="create", description="New button draft (interactive builder)")
    async def create_cmd(self, interaction: discord.Interaction) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        row = await db.create_builder_button(interaction.guild.id, interaction.user.id)
        await db.log_button_builder_action(interaction.guild.id, interaction.user.id, "create", str(row["button_id"]))
        view = ButtonBuilderView(self, row, interaction.user.id)
        await interaction.response.send_message(
            embeds=[_builder_header_embed(str(row["button_id"]), row)],
            view=view,
            ephemeral=True,
        )
        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            pass

    @button.command(name="edit", description="Edit existing button")
    @app_commands.describe(id="BTN-001", field="Optional shortcut")
    @app_commands.choices(
        field=[
            app_commands.Choice(name="label", value="label"),
            app_commands.Choice(name="emoji", value="emoji"),
            app_commands.Choice(name="responses", value="responses"),
        ]
    )
    async def edit_cmd(self, interaction: discord.Interaction, id: str, field: str | None = None) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        row = await db.get_builder_button(interaction.guild.id, id.upper())
        if not row:
            await interaction.response.send_message(
                embed=user_hint("Not found", f"No `{id.upper()}` here."),
                ephemeral=True,
            )
            return
        if field == "label":
            await interaction.response.send_modal(LabelModal(row))
            return
        if field == "emoji":
            await interaction.response.send_modal(EmojiModal(row))
            return
        if field == "responses":
            await interaction.response.send_modal(ResponsesModal(row))
            return
        view = ButtonBuilderView(self, row, interaction.user.id)
        await interaction.response.send_message(
            embeds=[_builder_header_embed(str(row["button_id"]), row)],
            view=view,
            ephemeral=True,
        )
        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            pass

    @button.command(name="clone", description="Duplicate button to new BTN-XXX")
    @app_commands.describe(id="Source BTN-001")
    async def clone_cmd(self, interaction: discord.Interaction, id: str) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        new_row = await db.clone_builder_button(interaction.guild.id, id.upper(), interaction.user.id)
        if not new_row:
            await interaction.response.send_message(embed=user_hint("Not found", "Source button missing."), ephemeral=True)
            return
        await db.log_button_builder_action(interaction.guild.id, interaction.user.id, "clone", str(new_row["button_id"]))
        view = ButtonBuilderView(self, new_row, interaction.user.id)
        await interaction.response.send_message(
            embeds=[_builder_header_embed(str(new_row["button_id"]), new_row)],
            view=view,
            ephemeral=True,
        )
        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            pass

    @button.command(name="list", description="List server buttons")
    async def list_cmd(self, interaction: discord.Interaction) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        rows = await db.list_builder_buttons(interaction.guild.id)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("Buttons", "None yet. `/button create`."),
                ephemeral=True,
            )
            return
        lines = []
        for r in rows[:40]:
            lines.append(
                f"`{r['button_id']}` · {str(r.get('label') or '')[:40]} · {r.get('action_type')} · <@{r['created_by']}>"
            )
        body = "\n".join(lines)
        if len(rows) > 40:
            body += f"\n… +{len(rows) - 40} more"
        await interaction.response.send_message(embed=info_embed(f"Buttons ({len(rows)})", body[:4000]), ephemeral=True)

    @button.command(name="post", description="Post button + embed to channel")
    @app_commands.describe(id="BTN-001", channel="Where to post")
    async def post_cmd(self, interaction: discord.Interaction, id: str, channel: discord.TextChannel) -> None:
        if not await self._can_use(interaction):
            return
        assert interaction.guild
        row = await db.get_builder_button(interaction.guild.id, id.upper())
        if not row:
            await interaction.response.send_message(embed=user_hint("Not found", f"No `{id.upper()}`."), ephemeral=True)
            return
        if not row.get("role_id"):
            await interaction.response.send_message(
                embed=user_hint("Incomplete", "Set **action + role** in builder first."),
                ephemeral=True,
            )
            return
        view = discord.ui.View(timeout=None)
        view.add_item(_live_button_from_row(interaction.guild.id, row))
        emb = info_embed(
            str(row["button_id"]),
            f"**{row['label']}** · {_action_summary(row)}",
        )
        try:
            await channel.send(embed=emb, view=view)
        except discord.HTTPException as e:
            await interaction.response.send_message(embed=user_warn("Post failed", str(e)[:400]), ephemeral=True)
            return
        await db.patch_builder_button(interaction.guild.id, str(row["button_id"]), {"status": "active"})
        await db.log_button_builder_action(interaction.guild.id, interaction.user.id, "post", str(row["button_id"]), channel.id)
        await interaction.response.send_message(
            embed=success_embed("Posted", f"{row['button_id']} → {channel.mention}"),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ButtonBuilderCog(bot))
