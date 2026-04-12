"""Configurable ticket panel, modal forms, and ticket channels."""

from __future__ import annotations

import asyncio
import io
import json
import re
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import guild_keys as gk
from guild_config import get_category, get_role, get_text_channel
from utils.channel_resolve import resolve_category, resolve_text_channel
from utils.checks import is_staff
from utils.embeds import PRIMARY, info_embed, success_embed, user_hint, user_warn

_SETUP_CH_ERR = (
    "Could not find that **text channel**. Use a channel mention (`<#id>`) or paste the "
    "**numeric channel ID** (Developer Mode → Copy Channel ID)."
)

# Modal-only fields (commission type is chosen in a Select menu first).
DEFAULT_MODAL_FIELDS: list[dict[str, Any]] = [
    {
        "label": "Number of Characters",
        "placeholder": "e.g. 1, 2",
        "required": True,
        "long": False,
    },
    {
        "label": "Mode of Payment",
        "placeholder": "e.g. GCash, PayPal",
        "required": True,
        "long": False,
    },
    {
        "label": "Reference Links",
        "placeholder": "Paste image links here",
        "required": False,
        "long": True,
    },
    {
        "label": "Additional Notes",
        "placeholder": "Any extra requests?",
        "required": False,
        "long": True,
    },
]

DEFAULT_SELECT_OPTIONS: list[str] = [
    "Chibi",
    "Chibi Scene",
    "Normal / Semi-Realistic",
    "Bust",
    "Fullbody",
    "Other",
]

# Welcome embed field order (commission type is prepended from the Select, not the modal).
WELCOME_FIELD_ORDER: tuple[str, ...] = (
    "Commission Type",
    "Number of Characters",
    "Mode of Payment",
    "Reference Links",
    "Additional Notes",
)

BUTTON_STYLE_MAP: dict[str, discord.ButtonStyle] = {
    "blurple": discord.ButtonStyle.primary,
    "green": discord.ButtonStyle.success,
    "red": discord.ButtonStyle.danger,
    "grey": discord.ButtonStyle.secondary,
}


def _hex_to_color(s: str) -> int:
    t = (s or "").strip()
    if t.startswith("#"):
        t = t[1:]
    try:
        return int(t, 16)
    except ValueError:
        return 0x669B9A


def _slug_button_id(label: str, guild_id: int) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")[:40] or "btn"
    bid = f"btn_{base}"
    return bid  # uniqueness checked in add loop with suffix


async def _ensure_unique_button_id(guild_id: int, base_id: str) -> str:
    bid = base_id
    n = 2
    while await db.get_ticket_button_by_id(bid):
        bid = f"{base_id}_{n}"
        n += 1
    return bid


def _parse_form_fields_json(raw: str | None) -> list[dict[str, Any]]:
    if not raw or not str(raw).strip():
        return [dict(f) for f in DEFAULT_MODAL_FIELDS]
    try:
        data = json.loads(raw)
        if not isinstance(data, list) or len(data) < 1:
            raise ValueError("invalid list")
        return data
    except (json.JSONDecodeError, ValueError):
        return [dict(f) for f in DEFAULT_MODAL_FIELDS]


def _parse_select_options_from_row(row: dict[str, Any]) -> list[str]:
    raw = row.get("select_options")
    if not raw or not str(raw).strip():
        return list(DEFAULT_SELECT_OPTIONS)
    try:
        data = json.loads(raw)
        if isinstance(data, list) and len(data) >= 1:
            out = [str(x).strip()[:100] for x in data if str(x).strip()]
            return out[:25]
    except json.JSONDecodeError:
        pass
    return list(DEFAULT_SELECT_OPTIONS)


def _validate_form_fields(data: Any) -> tuple[list[dict[str, Any]] | None, str | None]:
    if not isinstance(data, list):
        return None, "JSON must be an array of field objects."
    if len(data) < 1:
        return None, "Provide at least one field."
    if len(data) > 4:
        return None, "Maximum 4 modal fields (commission type uses the select menu first)."
    out: list[dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            return None, f"Item {i} must be an object."
        lab = item.get("label")
        if not lab or not str(lab).strip():
            return None, f"Item {i} needs a non-empty `label`."
        out.append(
            {
                "label": str(lab)[:45],
                "placeholder": str(item.get("placeholder", ""))[:100],
                "required": bool(item.get("required", True)),
                "long": bool(item.get("long", False)),
            }
        )
    return out, None


def _parse_comma_select_options(text: str) -> tuple[list[str] | None, str | None]:
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) < 1:
        return None, "Provide at least one option."
    if len(parts) > 25:
        return None, "Maximum 25 options (Discord select limit)."
    for i, p in enumerate(parts):
        if len(p) > 100:
            return None, f"Option {i + 1} is longer than 100 characters."
    return parts, None


class CloseTicketView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        cog = interaction.client.get_cog("TicketsCog")
        if not isinstance(cog, TicketsCog):
            await interaction.response.send_message(
                embed=user_warn("Tickets unavailable", "Try again in a moment."), ephemeral=True
            )
            return
        await cog.handle_close_button(interaction)


class CommissionTypeSelectView(discord.ui.View):
    """Ephemeral-only: commission type select → modal. Not registered with add_view."""

    def __init__(
        self,
        cog: TicketsCog,
        guild_id: int,
        button_id: str,
        button_label: str,
        row: dict[str, Any],
    ) -> None:
        super().__init__(timeout=60.0)
        self.cog = cog
        self.guild_id = guild_id
        self.button_id = button_id
        self.button_label = button_label
        self._row = row

        opts = _parse_select_options_from_row(row)[:25]
        select = discord.ui.Select(
            placeholder="Choose a commission type…",
            custom_id="ticket_commission_type",
            options=[
                discord.SelectOption(label=t[:100], value=t[:100]) for t in opts
            ],
        )

        async def _select_cb(interaction: discord.Interaction) -> None:
            if not interaction.data or "values" not in interaction.data:
                return
            commission_type = str(interaction.data["values"][0])[:100]
            fields = _parse_form_fields_json(self._row.get("form_fields"))
            modal = CommissionModal(
                self.cog,
                self.guild_id,
                self.button_id,
                self.button_label,
                commission_type,
                fields,
            )
            await interaction.response.send_modal(modal)

        select.callback = _select_cb
        self.add_item(select)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(
                    embed=info_embed(
                        "Timed out",
                        "Timed out. Click the button again to restart.",
                    ),
                    view=self,
                )
            except discord.HTTPException:
                pass


class CommissionModal(discord.ui.Modal):
    def __init__(
        self,
        cog: TicketsCog,
        guild_id: int,
        button_id: str,
        button_label: str,
        commission_type: str,
        fields: list[dict[str, Any]],
    ) -> None:
        super().__init__(title="Please answer the question below.")
        self.cog = cog
        self.guild_id = guild_id
        self.button_id = button_id
        self.button_label = button_label
        self.commission_type = commission_type
        self._field_labels: list[str] = []
        for i, f in enumerate(fields[:4]):
            lab = str(f.get("label", "Field"))[:45]
            self._field_labels.append(lab)
            ph = str(f.get("placeholder", ""))[:100]
            req = bool(f.get("required", True))
            long = bool(f.get("long", False))
            style = discord.TextStyle.paragraph if long else discord.TextStyle.short
            mx = 4000 if long else 400
            ti = discord.ui.TextInput(
                label=lab,
                style=style,
                placeholder=ph or None,
                required=req,
                max_length=mx,
                custom_id=f"tf_{i}",
            )
            self.add_item(ti)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        values: list[str] = []
        for child in self.children:
            if isinstance(child, discord.ui.TextInput):
                values.append((child.value or "").strip())
        answers = dict(zip(self._field_labels, values))
        await self.cog.handle_modal_submit(
            interaction,
            self.guild_id,
            self.button_id,
            self.button_label,
            self.commission_type,
            answers,
        )


class TicketsCog(commands.Cog, name="TicketsCog"):
    setup_group = app_commands.Group(name="setup", description="Staff setup commands")
    ticketbutton = app_commands.Group(name="ticketbutton", description="Ticket panel buttons (staff)")
    ticketform = app_commands.Group(name="ticketform", description="Ticket form fields (staff)")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # --- /ticketpanel ---

    @app_commands.command(name="ticketpanel", description="Post or update the configurable ticket panel")
    @app_commands.describe(
        channel="Channel for the panel",
        title="Embed title",
        description="Embed description/body",
        color="Embed color hex (e.g. #669b9a)",
        footer="Optional footer text",
    )
    @is_staff()
    async def ticketpanel_cmd(
        self,
        interaction: discord.Interaction,
        channel: str,
        title: str,
        description: str,
        color: str | None = None,
        footer: str | None = None,
    ) -> None:
        if not interaction.guild:
            return
        cat = await get_category(interaction.guild, gk.TICKET_CATEGORY)
        staff_role = await get_role(interaction.guild, gk.STAFF_ROLE)
        if not cat or not staff_role:
            await interaction.response.send_message(
                embed=user_hint(
                    "Configuration required",
                    "Please run `/serverconfig` first to set your **ticket category** "
                    "and **staff role**.",
                ),
                ephemeral=True,
            )
            return

        ch = resolve_text_channel(interaction.guild, channel)
        if not ch:
            await interaction.response.send_message(
                embed=user_hint("Invalid channel", _SETUP_CH_ERR), ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        col = (color or "#669b9a").strip()
        emb = discord.Embed(
            title=title[:256],
            description=description[:4096],
            color=_hex_to_color(col),
        )
        if footer:
            emb.set_footer(text=footer[:2048])

        rows = await db.list_ticket_buttons(interaction.guild.id)
        view = self._build_panel_view(interaction.guild.id, rows)
        old = await db.get_ticket_panel(interaction.guild.id)
        if old and old.get("channel_id") and old.get("message_id"):
            old_ch = interaction.guild.get_channel(int(old["channel_id"]))
            if isinstance(old_ch, discord.TextChannel):
                try:
                    om = await old_ch.fetch_message(int(old["message_id"]))
                    await om.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass

        if not rows:
            emb.description = (emb.description or "") + (
                "\n\n_No ticket types configured yet. Use `/ticketbutton add` to add buttons._"
            )

        kwargs: dict[str, Any] = {"embed": emb}
        if view is not None:
            kwargs["view"] = view
        msg = await ch.send(**kwargs)

        await db.upsert_ticket_panel(
            interaction.guild.id,
            ch.id,
            msg.id,
            title[:256],
            description[:4096],
            col,
            footer[:2048] if footer else None,
        )
        if view is not None:
            try:
                self.bot.add_view(view, message_id=msg.id)
            except ValueError:
                pass

        await interaction.followup.send(
            embed=success_embed("Ticket panel", f"✅ Ticket panel posted in {ch.mention}."),
            ephemeral=True,
        )

    # --- /ticketbutton ---

    @ticketbutton.command(name="add", description="Add a ticket type button to the panel")
    @app_commands.describe(
        label="Button label (e.g. order, report)",
        emoji="Optional emoji for the button",
        color="Button color",
        category="Category where tickets open (optional; defaults to server ticket category)",
    )
    @app_commands.choices(
        color=[
            app_commands.Choice(name="blurple", value="blurple"),
            app_commands.Choice(name="green", value="green"),
            app_commands.Choice(name="red", value="red"),
            app_commands.Choice(name="grey", value="grey"),
        ]
    )
    @is_staff()
    async def ticketbutton_add(
        self,
        interaction: discord.Interaction,
        label: str,
        emoji: str | None = None,
        color: str | None = None,
        category: str | None = None,
    ) -> None:
        if not interaction.guild:
            return
        if await db.count_ticket_buttons(interaction.guild.id) >= 5:
            await interaction.response.send_message(
                embed=user_hint("Limit", "Maximum 5 ticket buttons per server."),
                ephemeral=True,
            )
            return
        if await db.find_ticket_button_by_label(interaction.guild.id, label):
            await interaction.response.send_message(
                embed=user_hint(
                    "Duplicate",
                    "A button with that label already exists. Use `/ticketbutton remove` first.",
                ),
                ephemeral=True,
            )
            return

        base = _slug_button_id(label, interaction.guild.id)
        bid = await _ensure_unique_button_id(interaction.guild.id, base)

        col = (color or "blurple").lower()
        if col not in BUTTON_STYLE_MAP:
            col = "blurple"
        cat_id: int | None = None
        if category and str(category).strip():
            cat_ch = resolve_category(interaction.guild, category)
            if not cat_ch:
                await interaction.response.send_message(
                    embed=user_hint("Invalid category", "Could not resolve that category."),
                    ephemeral=True,
                )
                return
            cat_id = cat_ch.id
        else:
            gc = await get_category(interaction.guild, gk.TICKET_CATEGORY)
            if gc:
                cat_id = gc.id

        emoji_val = emoji.strip() if emoji and emoji.strip() else None

        await db.insert_ticket_button(
            bid,
            interaction.guild.id,
            label.strip()[:80],
            emoji_val,
            col,
            cat_id,
            None,
        )

        await interaction.response.defer(ephemeral=True)
        err = await self._refresh_panel_message(interaction.guild)
        if err:
            await interaction.followup.send(embed=user_hint("Panel", err), ephemeral=True)
            return
        rows = await db.list_ticket_buttons(interaction.guild.id)
        preview = ", ".join(f"**{r['label']}**" for r in rows) or "—"
        await interaction.followup.send(
            embed=success_embed("Button added", f"Updated panel. Buttons: {preview}"),
            ephemeral=True,
        )

    @ticketbutton.command(name="remove", description="Remove a ticket button by label")
    @app_commands.describe(label="The button label to remove")
    @is_staff()
    async def ticketbutton_remove(
        self, interaction: discord.Interaction, label: str
    ) -> None:
        if not interaction.guild:
            return
        ok = await db.delete_ticket_button_by_label(interaction.guild.id, label)
        if not ok:
            await interaction.response.send_message(
                embed=user_hint("Not found", "No button with that label."),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        err = await self._refresh_panel_message(interaction.guild)
        if err:
            await interaction.followup.send(embed=user_hint("Panel", err), ephemeral=True)
            return
        await interaction.followup.send(
            embed=success_embed("Removed", f"Removed **{label}** and refreshed the panel."),
            ephemeral=True,
        )

    @ticketbutton.command(name="list", description="List configured ticket buttons")
    @is_staff()
    async def ticketbutton_list(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        rows = await db.list_ticket_buttons(interaction.guild.id)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("Ticket buttons", "No buttons configured."),
                ephemeral=True,
            )
            return
        lines = []
        for r in rows:
            cat = (
                interaction.guild.get_channel(int(r["category_id"]))
                if r.get("category_id")
                else None
            )
            cname = cat.name if isinstance(cat, discord.CategoryChannel) else "default"
            ff = "custom" if r.get("form_fields") else "default"
            em = r.get("emoji") or "—"
            lines.append(
                f"**{r['label']}** — emoji: {em} — color: `{r['color']}` — category: {cname} — form: {ff}"
            )
        await interaction.response.send_message(
            embed=info_embed("Ticket buttons", "\n".join(lines)[:4000]),
            ephemeral=True,
        )

    # --- /ticketform ---

    @ticketform.command(name="set", description="Set modal form fields (JSON) for a button")
    @app_commands.describe(button="Button label", fields="JSON array of field objects")
    @is_staff()
    async def ticketform_set(
        self, interaction: discord.Interaction, button: str, fields: str
    ) -> None:
        if not interaction.guild:
            return
        row = await db.find_ticket_button_by_label(interaction.guild.id, button)
        if not row:
            await interaction.response.send_message(
                embed=user_hint("Not found", "No button with that label."),
                ephemeral=True,
            )
            return
        try:
            parsed = json.loads(fields)
        except json.JSONDecodeError:
            await interaction.response.send_message(
                embed=user_hint("JSON", "Invalid JSON."),
                ephemeral=True,
            )
            return
        valid, err = _validate_form_fields(parsed)
        if valid is None:
            await interaction.response.send_message(
                embed=user_hint("Validation", err or "Invalid fields."),
                ephemeral=True,
            )
            return
        await db.update_ticket_button_form_fields(
            row["button_id"], json.dumps(valid, ensure_ascii=False)
        )
        lines = [f"• **{f['label']}** ({'paragraph' if f['long'] else 'short'})" for f in valid]
        await interaction.response.send_message(
            embed=success_embed("Form saved", "\n".join(lines)[:4000]),
            ephemeral=True,
        )

    @ticketform.command(name="reset", description="Reset form fields to defaults for a button")
    @app_commands.describe(button="Button label")
    @is_staff()
    async def ticketform_reset(self, interaction: discord.Interaction, button: str) -> None:
        if not interaction.guild:
            return
        row = await db.find_ticket_button_by_label(interaction.guild.id, button)
        if not row:
            await interaction.response.send_message(
                embed=user_hint("Not found", "No button with that label."),
                ephemeral=True,
            )
            return
        await db.update_ticket_button_form_fields(row["button_id"], None)
        await interaction.response.send_message(
            embed=success_embed("Reset", f"Form for **{row['label']}** reset to defaults."),
            ephemeral=True,
        )

    @ticketform.command(name="preview", description="Preview form fields for a button")
    @app_commands.describe(button="Button label")
    @is_staff()
    async def ticketform_preview(self, interaction: discord.Interaction, button: str) -> None:
        if not interaction.guild:
            return
        row = await db.find_ticket_button_by_label(interaction.guild.id, button)
        if not row:
            await interaction.response.send_message(
                embed=user_hint("Not found", "No button with that label."),
                ephemeral=True,
            )
            return
        fields = _parse_form_fields_json(row.get("form_fields"))
        lines = [
            f"• **{f['label']}** — placeholder: {f.get('placeholder','')} — required: {f.get('required', True)} — long: {f.get('long', False)}"
            for f in fields
        ]
        await interaction.response.send_message(
            embed=info_embed(f"Form: {row['label']}", "\n".join(lines)[:4000]),
            ephemeral=True,
        )

    @ticketform.command(
        name="setoptions",
        description="Set commission type options for the select menu (comma-separated)",
    )
    @app_commands.describe(
        button="Button label",
        options="Comma-separated, e.g. Chibi, Chibi Scene, Fullbody",
    )
    @is_staff()
    async def ticketform_setoptions(
        self, interaction: discord.Interaction, button: str, options: str
    ) -> None:
        if not interaction.guild:
            return
        row = await db.find_ticket_button_by_label(interaction.guild.id, button)
        if not row:
            await interaction.response.send_message(
                embed=user_hint("Not found", "No button with that label."),
                ephemeral=True,
            )
            return
        parsed, err = _parse_comma_select_options(options)
        if parsed is None:
            await interaction.response.send_message(
                embed=user_hint("Options", err or "Invalid options."),
                ephemeral=True,
            )
            return
        await db.update_ticket_button_select_options(
            row["button_id"], json.dumps(parsed, ensure_ascii=False)
        )
        listed = "\n".join(f"• {o}" for o in parsed)
        await interaction.response.send_message(
            embed=success_embed("Select options saved", listed[:4000]),
            ephemeral=True,
        )

    @ticketform.command(
        name="resetoptions",
        description="Reset commission type select options to the default list",
    )
    @app_commands.describe(button="Button label")
    @is_staff()
    async def ticketform_resetoptions(
        self, interaction: discord.Interaction, button: str
    ) -> None:
        if not interaction.guild:
            return
        row = await db.find_ticket_button_by_label(interaction.guild.id, button)
        if not row:
            await interaction.response.send_message(
                embed=user_hint("Not found", "No button with that label."),
                ephemeral=True,
            )
            return
        await db.update_ticket_button_select_options(row["button_id"], None)
        listed = "\n".join(f"• {o}" for o in DEFAULT_SELECT_OPTIONS)
        await interaction.response.send_message(
            embed=success_embed("Options reset", f"Restored defaults:\n{listed}"),
            ephemeral=True,
        )

    # --- /setup (tos, payment) ---

    @setup_group.command(
        name="tos",
        description="Post the TOS agreement panel in the channel you specify (mention or ID)",
    )
    @app_commands.describe(
        channel="Where to post the panel — mention, ID, or pick a channel",
    )
    @is_staff()
    async def setup_tos(self, interaction: discord.Interaction, channel: str) -> None:
        ch = resolve_text_channel(interaction.guild, channel)
        if not ch:
            await interaction.response.send_message(
                embed=user_hint("Invalid channel", _SETUP_CH_ERR), ephemeral=True
            )
            return
        await db.set_guild_setting(interaction.guild.id, gk.TOS_CHANNEL, ch.id)
        shop = self.bot.get_cog("ShopCog")
        if not shop or not hasattr(shop, "run_setup_tos"):
            await interaction.response.send_message(
                embed=user_hint("Shop module unavailable", "Try again later or contact the bot owner."), ephemeral=True
            )
            return
        await shop.run_setup_tos(interaction, ch)

    @setup_group.command(
        name="payment",
        description="Post the payment methods panel in the channel you specify (mention or ID)",
    )
    @app_commands.describe(
        channel="Where to post the panel — mention, ID, or pick a channel",
    )
    @is_staff()
    async def setup_payment(self, interaction: discord.Interaction, channel: str) -> None:
        ch = resolve_text_channel(interaction.guild, channel)
        if not ch:
            await interaction.response.send_message(
                embed=user_hint("Invalid channel", _SETUP_CH_ERR), ephemeral=True
            )
            return
        await db.set_guild_setting(interaction.guild.id, gk.PAYMENT_CHANNEL, ch.id)
        pay = self.bot.get_cog("PaymentCog")
        if not pay or not hasattr(pay, "run_setup_payment"):
            await interaction.response.send_message(
                embed=user_hint("Payment module unavailable", "Try again later or contact the bot owner."), ephemeral=True
            )
            return
        await pay.run_setup_payment(interaction, ch)

    def _build_panel_view(
        self, guild_id: int, rows: list[dict[str, Any]]
    ) -> discord.ui.View | None:
        if not rows:
            return None
        view = discord.ui.View(timeout=None)
        for row in rows[:5]:
            style = BUTTON_STYLE_MAP.get(
                str(row.get("color") or "blurple").lower(), discord.ButtonStyle.primary
            )
            cid = f"bbtp:{guild_id}:{row['button_id']}"
            emoji = row.get("emoji") or None

            btn = discord.ui.Button(
                label=str(row["label"])[:80],
                style=style,
                custom_id=cid,
                emoji=emoji,
            )
            bid = str(row["button_id"])

            def _handler(button_id: str):
                async def _inner(interaction: discord.Interaction) -> None:
                    await self.handle_panel_button(interaction, button_id)

                return _inner

            btn.callback = _handler(bid)
            view.add_item(btn)
        return view

    async def _refresh_panel_message(self, guild: discord.Guild) -> str | None:
        """Rebuild ticket panel message; returns error string or None."""
        panel = await db.get_ticket_panel(guild.id)
        if not panel:
            return "No ticket panel yet. Run `/ticketpanel` first."
        ch = guild.get_channel(int(panel["channel_id"]))
        if not isinstance(ch, discord.TextChannel):
            return "Ticket panel channel is missing."
        rows = await db.list_ticket_buttons(guild.id)
        emb = discord.Embed(
            title=panel["embed_title"][:256],
            description=panel["embed_description"][:4096],
            color=_hex_to_color(panel.get("embed_color") or "#669b9a"),
        )
        if panel.get("embed_footer"):
            emb.set_footer(text=str(panel["embed_footer"])[:2048])
        if not rows:
            emb.description = (emb.description or "") + (
                "\n\n_No ticket types configured yet. Use `/ticketbutton add` to add buttons._"
            )
        view = self._build_panel_view(guild.id, rows)
        try:
            old = await ch.fetch_message(int(panel["message_id"]))
            await old.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass
        kwargs: dict[str, Any] = {"embed": emb}
        if view is not None:
            kwargs["view"] = view
        try:
            msg = await ch.send(**kwargs)
        except discord.HTTPException:
            return "Could not post the panel message."
        await db.upsert_ticket_panel(
            guild.id,
            ch.id,
            msg.id,
            panel["embed_title"],
            panel["embed_description"],
            panel.get("embed_color") or "#669b9a",
            panel.get("embed_footer"),
        )
        if view is not None:
            try:
                self.bot.add_view(view, message_id=msg.id)
            except ValueError:
                pass
        return None

    async def handle_panel_button(self, interaction: discord.Interaction, button_id: str) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=user_hint("Use this in a server", "Open this from inside the Discord server."), ephemeral=True
            )
            return

        row = await db.get_ticket_button_by_id(button_id)
        if not row or int(row["guild_id"]) != interaction.guild.id:
            await interaction.response.send_message(
                embed=user_hint(
                    "Button needs a refresh",
                    "Ask staff to run **`/ticketpanel`** again so buttons stay in sync.",
                ),
                ephemeral=True,
            )
            return

        tos_role = await get_role(interaction.guild, gk.TOS_AGREED_ROLE)
        if tos_role is None or tos_role not in interaction.user.roles:
            tos_cid = await db.get_guild_setting(interaction.guild.id, gk.TOS_CHANNEL)
            hint = f"Please read and agree in <#{tos_cid}> first." if tos_cid else "Please agree to the TOS first."
            await interaction.response.send_message(embed=user_warn("Terms required", hint), ephemeral=True)
            return

        if not await db.shop_is_open_db():
            await interaction.response.send_message(
                embed=user_warn("Shop is closed", "Commissions are closed right now — check back when staff reopen."),
                ephemeral=True,
            )
            return

        existing = await db.get_open_ticket_by_user(interaction.user.id, interaction.guild.id)
        if existing:
            await interaction.response.send_message(
                f"You already have an open ticket at <#{existing['channel_id']}>.",
                ephemeral=True,
            )
            return

        emb = info_embed(
            "Commission type",
            "What type of commission are you ordering?",
        )
        view = CommissionTypeSelectView(
            self,
            interaction.guild.id,
            button_id,
            str(row["label"]),
            row,
        )
        await interaction.response.send_message(embed=emb, view=view, ephemeral=True)

    async def handle_modal_submit(
        self,
        interaction: discord.Interaction,
        guild_id: int,
        button_id: str,
        button_label: str,
        commission_type: str,
        answers: dict[str, str],
    ) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer(ephemeral=True)

        row = await db.get_ticket_button_by_id(button_id)
        if not row:
            await interaction.followup.send(
                embed=user_hint("Configuration missing", "That ticket type isn’t set up anymore. Ask staff to check `/ticketbutton`."), ephemeral=True
            )
            return

        category = None
        if row.get("category_id"):
            c = interaction.guild.get_channel(int(row["category_id"]))
            if isinstance(c, discord.CategoryChannel):
                category = c
        if category is None:
            category = await get_category(interaction.guild, gk.TICKET_CATEGORY)
        if not category:
            await interaction.followup.send(
                embed=user_hint("Config", "Ticket category missing. Set `/serverconfig category`."),
                ephemeral=True,
            )
            return

        staff_role = await get_role(interaction.guild, gk.STAFF_ROLE)
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.followup.send(
                embed=user_hint("Couldn’t verify member", "Try the command again from the server."), ephemeral=True
            )
            return

        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True, manage_channels=True, send_messages=True
            ),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                manage_channels=True,
                attach_files=True,
                embed_links=True,
            )

        raw_name = re.sub(r"[^a-z0-9\s]", "", member.name.lower())
        raw_name = re.sub(r"\s+", "_", raw_name).strip("_")[:80] or "user"

        try:
            ticket_ch = await interaction.guild.create_text_channel(
                f"ticket-{raw_name}",
                category=category,
                overwrites=overwrites,
                reason=f"Ticket ({button_label}) for {member}",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=user_warn(
                    "Missing permissions",
                    "The bot needs permission to **manage channels** in that category. Ask an admin to adjust role/channel settings.",
                ),
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            await interaction.followup.send(
                embed=user_warn("Couldn’t create channel", "Discord blocked channel creation — try again or ask an admin to check limits and permissions."),
                ephemeral=True,
            )
            return

        full_answers: dict[str, str] = {"Commission Type": commission_type}
        full_answers.update(answers)
        await db.insert_ticket_open(
            ticket_ch.id,
            interaction.guild.id,
            member.id,
            button_id=button_id,
            answers=full_answers,
        )

        try:
            await ticket_ch.send(member.mention)
        except discord.HTTPException:
            pass

        desc_lines: list[str] = []
        for key in WELCOME_FIELD_ORDER:
            if key in full_answers:
                desc_lines.append(f"**{key}:** {full_answers[key]}")
        for k, v in full_answers.items():
            if k not in WELCOME_FIELD_ORDER:
                desc_lines.append(f"**{k}:** {v}")
        body = "\n".join(desc_lines)[:3900]
        welcome = discord.Embed(
            title=f"🎀 {button_label} ticket — {member.display_name}",
            description=body,
            color=PRIMARY,
        )
        await ticket_ch.send(embed=welcome, view=CloseTicketView())
        await interaction.followup.send(
            embed=success_embed("Ticket opened", f"Go to {ticket_ch.mention}"),
            ephemeral=True,
        )

    async def handle_close_button(self, interaction: discord.Interaction) -> None:
        await self._run_close(interaction)

    async def _run_close(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=user_hint("Wrong channel", "Use this inside an open ticket channel."), ephemeral=True
            )
            return
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message(
                embed=user_hint("Not a ticket", "This channel isn’t linked to an open ticket."), ephemeral=True
            )
            return
        staff_role = await get_role(interaction.guild, gk.STAFF_ROLE)
        is_staff_u = (
            staff_role
            and isinstance(interaction.user, discord.Member)
            and staff_role in interaction.user.roles
        )
        is_owner = interaction.user.id == int(ticket["client_id"])
        if not is_staff_u and not is_owner:
            await interaction.response.send_message(
                embed=user_warn("Can’t close this", "Only **staff** or the **ticket owner** can close it."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        from utils.transcript import generate_transcript

        try:
            file = await generate_transcript(interaction.channel)
        except Exception:
            await interaction.followup.send(
                embed=user_warn("Transcript issue", "Couldn’t build the transcript file. Ask an admin to check bot permissions in this channel."),
            )
            return

        raw = file.fp.read()
        filename = file.filename or "transcript.html"
        dm_file = discord.File(io.BytesIO(raw), filename=filename)
        trans_file = discord.File(io.BytesIO(raw), filename=filename)

        client = interaction.guild.get_member(int(ticket["client_id"]))
        dm_ok = True
        if client:
            try:
                await client.send(
                    embed=info_embed("Ticket closed", "Transcript attached."),
                    file=dm_file,
                )
            except discord.Forbidden:
                dm_ok = False

        trans_ch = await get_text_channel(interaction.guild, gk.TRANSCRIPT_CHANNEL)
        if trans_ch:
            try:
                await trans_ch.send(
                    embed=info_embed("Transcript", f"Ticket {interaction.channel.name}"),
                    file=trans_file,
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        if not dm_ok and trans_ch:
            try:
                await trans_ch.send(
                    content=f"⚠️ Could not DM transcript to <@{ticket['client_id']}>.",
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        if dm_ok:
            await interaction.followup.send(
                embed=success_embed("Closing", "Transcript sent. Channel deletes in 15 seconds."),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                embed=user_hint(
                    "DM failed",
                    "Transcript was posted to the transcript channel only.",
                ),
                ephemeral=True,
            )

        await db.close_ticket_record(interaction.channel.id, 1)

        ch = interaction.channel
        for i in range(15, 0, -1):
            try:
                await ch.send(f"Channel closing in **{i}** seconds...")
            except discord.HTTPException:
                break
            await asyncio.sleep(1)
        try:
            await ch.delete(reason="Ticket closed")
        except (discord.Forbidden, discord.NotFound):
            pass

    @app_commands.command(name="close", description="Close this ticket with transcript")
    async def close_cmd(self, interaction: discord.Interaction) -> None:
        await self._run_close(interaction)


async def register_ticket_persistent_views(bot: commands.Bot) -> None:
    try:
        bot.add_view(CloseTicketView())
    except ValueError:
        pass
    panels = await db.all_ticket_panels()
    cog = bot.get_cog("TicketsCog")
    if not isinstance(cog, TicketsCog):
        return
    for panel in panels:
        gid = int(panel["guild_id"])
        mid = int(panel["message_id"])
        rows = await db.list_ticket_buttons(gid)
        if not rows:
            continue
        view = cog._build_panel_view(gid, rows)
        if view:
            try:
                bot.add_view(view, message_id=mid)
            except ValueError:
                pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketsCog(bot))
