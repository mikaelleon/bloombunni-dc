"""Per-guild channel, role, and payment mapping (no .env except BOT_TOKEN)."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import guild_keys as gk
from utils.channel_resolve import resolve_category, resolve_text_channel
from utils.checks import can_manage_server_config
from utils.embeds import error_embed, info_embed, success_embed
from utils.paged_embeds import PagedEmbedView


def _label_map(choices: list[tuple[str, str]]) -> dict[str, str]:
    return {v: n for n, v in choices}


_CHANNEL_LABELS = _label_map(gk.CHANNEL_SLOT_CHOICES)
_CATEGORY_LABELS = _label_map(gk.CATEGORY_SLOT_CHOICES)
_ROLE_LABELS = _label_map(gk.ROLE_SLOT_CHOICES)

_ERR_BAD_TEXT_CH = (
    "Could not find that **text channel**. Paste a channel mention "
    "(`<#channel_id>` — pick the channel in the option field so Discord fills it in) "
    "or paste the **numeric channel ID** (User Settings → App Settings → Advanced → "
    "Developer Mode → right‑click channel → Copy Channel ID)."
)

_ERR_BAD_CAT = (
    "Could not find that **category**. Paste the **numeric category ID** "
    "(Developer Mode → right‑click the category name → Copy Category ID). "
    "Categories use the same ID format as channels; the bot resolves it under your server."
)

# One-line explanations for the interactive guide (value key → blurb)
_CHANNEL_HELP: dict[str, str] = {
    gk.QUEUE_CHANNEL: "Where `/queue` posts and maintains order cards for the live queue.",
    gk.SHOP_STATUS_CHANNEL: "Shop open/closed status embed; `/shop open` and `/shop close` edit it.",
    gk.TRANSCRIPT_CHANNEL: "Archived ticket transcripts are posted here when tickets close.",
    gk.VOUCHES_CHANNEL: "Where `/vouch` logs public vouches (must match this channel when used).",
    gk.ORDER_NOTIFS_CHANNEL: "Optional pings for order updates (if your workflow uses it).",
    gk.START_HERE_CHANNEL: "Home for the ticket panel from `/setup tickets` (after you pick the channel).",
    gk.TOS_CHANNEL: "Terms of Service text and agree button; `/setup tos` posts here.",
    gk.PAYMENT_CHANNEL: "Payment method panel; `/setup payment` posts the buttons here.",
    gk.WARN_LOG_CHANNEL: "Staff `/warn` entries are copied here for moderation records.",
}

_CATEGORY_HELP: dict[str, str] = {
    gk.TICKET_CATEGORY: "New private ticket channels open under this category.",
    gk.NOTED_CATEGORY: "Orders move here after staff mark them as noted.",
    gk.PROCESSING_CATEGORY: "Active work-in-progress orders.",
    gk.DONE_CATEGORY: "Completed orders (optional final archive column).",
}

_ROLE_HELP: dict[str, str] = {
    gk.STAFF_ROLE: "Staff permissions for queue, tickets, and setup commands.",
    gk.TOS_AGREED_ROLE: "Given when a member agrees via the TOS panel (required to open tickets).",
    gk.COMMISSIONS_OPEN_ROLE: "Who can see the shop when commissions are open (optional gating).",
    gk.PLEASE_VOUCH_ROLE: "Optional role used in vouch reminders / workflow.",
}


def _is_http_url(s: str) -> bool:
    t = str(s).strip().lower()
    return t.startswith("http://") or t.startswith("https://")


def _guide_overview_embed() -> discord.Embed:
    body = (
        "This guide lists every **configuration command** in order. Use **◀ Previous** and "
        "**Next ▶** to move between pages.\n\n"
        "**Roadmap**\n"
        "1. **`/serverconfig channel`** — Map each feature to a text channel (mention or ID).\n"
        "2. **`/serverconfig category`** — Place ticket columns (new → done).\n"
        "3. **`/serverconfig role`** — Staff and automation roles (picker).\n"
        "4. **`/serverconfig payment`** — GCash / PayPal / Ko-fi text and image URLs.\n"
        "5. **`/setup`** — Deploy ticket, TOS, and payment panels; each command asks which "
        "channel to use and saves that slot for you.\n\n"
        "When you are done, run **`/serverconfig show`** anytime to review mappings (last pages)."
    )
    return info_embed("Server configuration — overview", body)


def _guide_channels_embed() -> discord.Embed:
    lines: list[str] = [
        "Run **`/serverconfig channel`**, choose the **slot**, then type the **channel** field as "
        "a mention (`<#…>`) or paste the **channel ID**.\n",
    ]
    for name, value in gk.CHANNEL_SLOT_CHOICES:
        tip = _CHANNEL_HELP.get(value, "")
        lines.append(f"**{name}**\n_{tip}_\n")
    return info_embed("Step 1 — `/serverconfig channel`", "\n".join(lines).strip())


def _guide_categories_embed() -> discord.Embed:
    lines: list[str] = [
        "Run **`/serverconfig category`**, choose the **slot**, then paste the **category ID** "
        "(or a `<#id>` mention if Discord provides one for that category).\n",
    ]
    for name, value in gk.CATEGORY_SLOT_CHOICES:
        tip = _CATEGORY_HELP.get(value, "")
        lines.append(f"**{name}**\n_{tip}_\n")
    return info_embed("Step 2 — `/serverconfig category`", "\n".join(lines).strip())


def _guide_roles_embed() -> discord.Embed:
    lines: list[str] = [
        "Run **`/serverconfig role`** and pick the **slot** and **role** from the lists.\n",
    ]
    for name, value in gk.ROLE_SLOT_CHOICES:
        tip = _ROLE_HELP.get(value, "")
        lines.append(f"**{name}**\n_{tip}_\n")
    return info_embed("Step 3 — `/serverconfig role`", "\n".join(lines).strip())


def _guide_payment_embed() -> discord.Embed:
    body = (
        "Run these under **`/serverconfig payment`** (text and direct image URLs):\n\n"
        "• **`gcash_details`** — Body text in the GCash embed.\n"
        "• **`gcash_qr`** — Image URL for the GCash QR (png/jpg).\n"
        "• **`paypal_link`** — PayPal checkout link (`https://…`).\n"
        "• **`paypal_qr`** — Image URL for the PayPal QR.\n"
        "• **`kofi_link`** — Ko-fi page link.\n\n"
        "URLs must start with `http://` or `https://`."
    )
    return info_embed("Step 4 — `/serverconfig payment`", body)


def _guide_setup_embed() -> discord.Embed:
    body = (
        "**Step 5 — Deploy panels (`/setup`)**\n\n"
        "Each command requires a **channel** (mention or ID) where the panel should appear. "
        "The bot saves the matching **`/serverconfig channel`** slot at the same time "
        "(Start Here, TOS, or Payment).\n\n"
        "• **`/setup tickets`** — Ticket open button (needs categories + roles configured).\n"
        "• **`/setup tos`** — Terms of Service message and agree button.\n"
        "• **`/setup payment`** — GCash / PayPal / Ko-fi buttons (needs payment strings set).\n\n"
        "After deploying, use **`/serverconfig show`** to verify everything."
    )
    return info_embed("Step 5 — `/setup` (post panels)", body)


def _status_lines_for_guild(
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
    return lines


def _chunk_lines(lines: list[str], max_chars: int = 3500) -> list[str]:
    """Split lines into description chunks under max_chars (breaks on newlines)."""
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


def _build_show_pages(
    guild: discord.Guild, rows: dict[str, int], str_rows: dict[str, str]
) -> list[discord.Embed]:
    guide: list[discord.Embed] = [
        _guide_overview_embed(),
        _guide_channels_embed(),
        _guide_categories_embed(),
        _guide_roles_embed(),
        _guide_payment_embed(),
        _guide_setup_embed(),
    ]
    status_lines = _status_lines_for_guild(guild, rows, str_rows)
    chunks = _chunk_lines(status_lines)
    status_embeds: list[discord.Embed] = []
    for i, chunk in enumerate(chunks):
        title = "Current server configuration"
        if len(chunks) > 1:
            title = f"Current server configuration ({i + 1}/{len(chunks)})"
        status_embeds.append(info_embed(title, chunk[:4000]))
    return guide + status_embeds


class ServerConfigCog(commands.Cog, name="ServerConfigCog"):
    serverconfig = app_commands.Group(
        name="serverconfig",
        description="Configure this server (channels, roles, payment) — no IDs in .env",
    )

    serverconfig_payment = app_commands.Group(
        name="payment",
        description="GCash / PayPal / Ko-fi text and QR image URLs for the payment panel",
        parent=serverconfig,
    )

    @serverconfig.command(name="channel", description="Set a text channel for a feature")
    @app_commands.describe(
        slot="Which feature this channel is for",
        channel="Text channel: mention, ID, or pick from the list (all supported)",
    )
    @app_commands.choices(
        slot=[
            app_commands.Choice(name=n, value=v)
            for n, v in gk.CHANNEL_SLOT_CHOICES
        ]
    )
    @can_manage_server_config()
    async def serverconfig_channel(
        self,
        interaction: discord.Interaction,
        slot: str,
        channel: str,
    ) -> None:
        if not interaction.guild:
            return
        ch = resolve_text_channel(interaction.guild, channel)
        if not ch:
            await interaction.response.send_message(
                embed=error_embed("Invalid channel", _ERR_BAD_TEXT_CH),
                ephemeral=True,
            )
            return
        await db.set_guild_setting(interaction.guild.id, slot, ch.id)
        label = _CHANNEL_LABELS.get(slot, slot)
        await interaction.response.send_message(
            embed=success_embed(
                "Saved",
                f"**{label}** → {ch.mention}",
            ),
            ephemeral=True,
        )

    @serverconfig.command(name="category", description="Set a category for tickets / order stages")
    @app_commands.describe(
        slot="Which stage",
        category="Category: ID, mention, or pick from the list (all supported)",
    )
    @app_commands.choices(
        slot=[
            app_commands.Choice(name=n, value=v)
            for n, v in gk.CATEGORY_SLOT_CHOICES
        ]
    )
    @can_manage_server_config()
    async def serverconfig_category(
        self,
        interaction: discord.Interaction,
        slot: str,
        category: str,
    ) -> None:
        if not interaction.guild:
            return
        cat = resolve_category(interaction.guild, category)
        if not cat:
            await interaction.response.send_message(
                embed=error_embed("Invalid category", _ERR_BAD_CAT),
                ephemeral=True,
            )
            return
        await db.set_guild_setting(interaction.guild.id, slot, cat.id)
        label = _CATEGORY_LABELS.get(slot, slot)
        await interaction.response.send_message(
            embed=success_embed("Saved", f"**{label}** → `{cat.name}`"),
            ephemeral=True,
        )

    @serverconfig.command(name="role", description="Set a role for staff / TOS / shop")
    @app_commands.describe(
        slot="Which role",
        role="Pick the role",
    )
    @app_commands.choices(
        slot=[
            app_commands.Choice(name=n, value=v)
            for n, v in gk.ROLE_SLOT_CHOICES
        ]
    )
    @can_manage_server_config()
    async def serverconfig_role(
        self,
        interaction: discord.Interaction,
        slot: str,
        role: discord.Role,
    ) -> None:
        await db.set_guild_setting(interaction.guild.id, slot, role.id)
        label = _ROLE_LABELS.get(slot, slot)
        await interaction.response.send_message(
            embed=success_embed("Saved", f"**{label}** → {role.mention}"),
            ephemeral=True,
        )

    @serverconfig.command(
        name="show",
        description="Interactive setup guide + current channel, role, and payment mappings",
    )
    @can_manage_server_config()
    async def serverconfig_show(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        rows = await db.list_guild_settings(interaction.guild.id)
        str_rows = await db.list_guild_string_settings(interaction.guild.id)
        pages = _build_show_pages(interaction.guild, rows, str_rows)
        view = PagedEmbedView(pages, interaction.user.id)
        await interaction.response.send_message(
            embed=pages[0], view=view, ephemeral=True
        )

    # --- /serverconfig payment (nested) ---

    @serverconfig_payment.command(
        name="gcash_details",
        description="Body text for the GCash button (name, number, instructions)",
    )
    @app_commands.describe(text="Plain text shown in the GCash embed (max ~4000 characters)")
    @can_manage_server_config()
    async def payment_gcash_details(self, interaction: discord.Interaction, text: str) -> None:
        t = text.strip()
        if len(t) > 4000:
            await interaction.response.send_message(
                embed=error_embed("Too long", "Keep GCash text at or under 4000 characters."),
                ephemeral=True,
            )
            return
        await db.set_guild_string_setting(interaction.guild.id, gk.PAYMENT_GCASH_DETAILS, t)
        await interaction.response.send_message(
            embed=success_embed("Saved", "GCash embed body updated."),
            ephemeral=True,
        )

    @serverconfig_payment.command(name="paypal_link", description="PayPal payment link (https://…)")
    @app_commands.describe(url="Must start with http:// or https://")
    @can_manage_server_config()
    async def payment_paypal_link(self, interaction: discord.Interaction, url: str) -> None:
        if not _is_http_url(url):
            await interaction.response.send_message(
                embed=error_embed("Invalid URL", "Use a link starting with `http://` or `https://`."),
                ephemeral=True,
            )
            return
        await db.set_guild_string_setting(
            interaction.guild.id, gk.PAYMENT_PAYPAL_LINK, url.strip()
        )
        await interaction.response.send_message(
            embed=success_embed("Saved", "PayPal link updated."),
            ephemeral=True,
        )

    @serverconfig_payment.command(name="kofi_link", description="Ko-fi page link (https://…)")
    @app_commands.describe(url="Must start with http:// or https://")
    @can_manage_server_config()
    async def payment_kofi_link(self, interaction: discord.Interaction, url: str) -> None:
        if not _is_http_url(url):
            await interaction.response.send_message(
                embed=error_embed("Invalid URL", "Use a link starting with `http://` or `https://`."),
                ephemeral=True,
            )
            return
        await db.set_guild_string_setting(
            interaction.guild.id, gk.PAYMENT_KOFI_LINK, url.strip()
        )
        await interaction.response.send_message(
            embed=success_embed("Saved", "Ko-fi link updated."),
            ephemeral=True,
        )

    @serverconfig_payment.command(
        name="gcash_qr",
        description="Direct image URL for the GCash QR (png/jpg)",
    )
    @app_commands.describe(url="Must start with http:// or https://")
    @can_manage_server_config()
    async def payment_gcash_qr(self, interaction: discord.Interaction, url: str) -> None:
        if not _is_http_url(url):
            await interaction.response.send_message(
                embed=error_embed("Invalid URL", "Use a link starting with `http://` or `https://`."),
                ephemeral=True,
            )
            return
        await db.set_guild_string_setting(
            interaction.guild.id, gk.PAYMENT_GCASH_QR_URL, url.strip()
        )
        await interaction.response.send_message(
            embed=success_embed("Saved", "GCash QR image URL updated."),
            ephemeral=True,
        )

    @serverconfig_payment.command(
        name="paypal_qr",
        description="Direct image URL for the PayPal QR (png/jpg)",
    )
    @app_commands.describe(url="Must start with http:// or https://")
    @can_manage_server_config()
    async def payment_paypal_qr(self, interaction: discord.Interaction, url: str) -> None:
        if not _is_http_url(url):
            await interaction.response.send_message(
                embed=error_embed("Invalid URL", "Use a link starting with `http://` or `https://`."),
                ephemeral=True,
            )
            return
        await db.set_guild_string_setting(
            interaction.guild.id, gk.PAYMENT_PAYPAL_QR_URL, url.strip()
        )
        await interaction.response.send_message(
            embed=success_embed("Saved", "PayPal QR image URL updated."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerConfigCog(bot))
