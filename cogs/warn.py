"""Warning system — reason presets, staff audit log, optional warn-appeal tickets."""

from __future__ import annotations

import json
import re
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import guild_keys as gk
from guild_config import get_category, get_role, get_text_channel
from utils.checks import is_staff
from utils.embeds import DEFAULT_EMBED_COLOR, HINT_BLUE, PRIMARY, info_embed, success_embed, user_hint, user_warn, warning_embed

WARN_THRESHOLD_DEFAULT = 3

DEFAULT_WARN_REASONS: tuple[str, ...] = (
    "Chargeback attempt",
    "Harassment",
    "TOS violation",
    "Spam / scam",
    "Disrespectful behavior",
    "Other (see notes)",
)

_MAX_CUSTOM_REASONS = 20
_MAX_REASON_LEN = 100


def _norm_reason(reason: str | None) -> str:
    r = (reason or "").strip()
    return r if r else "no reason specified"


def _warn_notice_embed(
    *, shop_name: str, reason: str, total: int, threshold: int
) -> discord.Embed:
    return discord.Embed(
        title="⚠️ WARNED NOTICE !",
        description=(
            f"hello ! you have been **warned** from **{shop_name}** for **{reason}**. "
            f"**take note** that once you received a total of **{threshold} warnings** from them you will be "
            f"**automatically banned** from their **server**. so, please **follow** their **rules. thank you !** "
            f"your **warning count : {total}** ⚠️"
        ),
        color=DEFAULT_EMBED_COLOR,
    )


def _appeal_dm_embed(guild_name: str) -> discord.Embed:
    return discord.Embed(
        title="Appeal this warn",
        description=(
            f"If you believe this warn was a mistake, you can open a **private appeal ticket** in **{guild_name}** "
            "for staff to review. Use the button below (you must still be in the server)."
        ),
        color=HINT_BLUE,
    )


async def _guild_warn_threshold(guild_id: int) -> int:
    v = await db.get_guild_setting(guild_id, gk.WARN_THRESHOLD_KEY)
    if v is None:
        return WARN_THRESHOLD_DEFAULT
    return max(1, min(100, int(v)))


async def _load_merged_reasons(guild_id: int) -> list[str]:
    raw = await db.get_guild_string_setting(guild_id, gk.WARN_REASON_TEMPLATES_JSON)
    custom: list[str] = []
    if raw and raw.strip():
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                custom = [str(x).strip() for x in data if str(x).strip()]
        except json.JSONDecodeError:
            pass
    seen: set[str] = set()
    out: list[str] = []
    for t in (*DEFAULT_WARN_REASONS, *custom):
        k = t.casefold()
        if k in seen or len(t) > _MAX_REASON_LEN:
            continue
        seen.add(k)
        out.append(t)
    return out


def _audit_warn_embed(
    *,
    guild: discord.Guild,
    warned: discord.Member,
    moderator: discord.Member,
    reason: str,
    warn_id: int,
    total: int,
    threshold: int,
    source_channel: discord.abc.GuildChannel | None,
) -> discord.Embed:
    e = discord.Embed(
        title="📋 Warn — staff log",
        color=PRIMARY,
        description=f"**Reason:** {reason}",
    )
    e.add_field(name="Member", value=warned.mention, inline=True)
    e.add_field(name="Moderator", value=moderator.mention, inline=True)
    e.add_field(name="Warn ID", value=f"`{warn_id}`", inline=True)
    e.add_field(name="Total / threshold", value=f"{total} / {threshold}", inline=True)
    if source_channel:
        e.add_field(name="Issued in", value=source_channel.mention, inline=True)
    return e


class WarnPages(discord.ui.View):
    def __init__(self, user_id: int, pages: list[discord.Embed]) -> None:
        super().__init__(timeout=180.0)
        self.user_id = user_id
        self.pages = pages
        self.idx = 0

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your pager.", ephemeral=True)
            return
        self.idx = max(0, self.idx - 1)
        await interaction.response.edit_message(embed=self.pages[self.idx], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your pager.", ephemeral=True)
            return
        self.idx = min(len(self.pages) - 1, self.idx + 1)
        await interaction.response.edit_message(embed=self.pages[self.idx], view=self)


class WarnAppealDMView(discord.ui.View):
    """DM button view — interaction also routed via listener for persistence after restart."""

    def __init__(self, guild_id: int, warn_id: int) -> None:
        super().__init__(timeout=None)
        cid = f"wa|{guild_id}|{warn_id}"
        if len(cid) > 100:
            cid = cid[:100]

        btn = discord.ui.Button(
            label="Open warn appeal ticket",
            style=discord.ButtonStyle.primary,
            custom_id=cid,
        )

        async def _cb(i: discord.Interaction) -> None:
            cog = i.client.get_cog("WarnCog")
            if isinstance(cog, WarnCog):
                await cog.handle_warn_appeal_click(i, guild_id, warn_id)
            else:
                await i.response.send_message(
                    embed=user_warn("Unavailable", "Try again in a moment."), ephemeral=True
                )

        btn.callback = _cb
        self.add_item(btn)


class WarnCog(commands.Cog, name="WarnCog"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    warnreason = app_commands.Group(
        name="warnreason",
        description="Manage extra warn reason presets for this server",
    )

    async def handle_warn_appeal_click(
        self, interaction: discord.Interaction, guild_id: int, warn_id: int
    ) -> None:
        guild = self.bot.get_guild(guild_id)
        if not guild:
            await interaction.response.send_message(
                embed=user_warn("Server unavailable", "Could not load that server."), ephemeral=True
            )
            return

        row = await db.get_warn(warn_id)
        if not row:
            await interaction.response.send_message(
                embed=user_hint("Warn not found", "This warn may have been cleared already."),
                ephemeral=True,
            )
            return

        if int(row["user_id"]) != interaction.user.id:
            await interaction.response.send_message(
                embed=user_warn("Not your appeal", "Only the warned member can open this appeal."),
                ephemeral=True,
            )
            return

        existing = await db.get_open_warn_appeal_ticket(interaction.user.id, guild_id)
        if existing:
            ch = guild.get_channel(int(existing["channel_id"]))
            mention = ch.mention if isinstance(ch, discord.TextChannel) else "your appeal channel"
            await interaction.response.send_message(
                embed=user_hint("Appeal already open", f"You already have an open warn appeal: {mention}"),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            member = await guild.fetch_member(interaction.user.id)
        except discord.NotFound:
            await interaction.followup.send(
                embed=user_warn("Not in server", "You must be a member of the server to open an appeal."),
                ephemeral=True,
            )
            return

        staff_role = await get_role(guild, gk.STAFF_ROLE)
        category = await get_category(guild, gk.TICKET_CATEGORY)
        if not category:
            await interaction.followup.send(
                embed=user_hint(
                    "Not configured",
                    "This server has no **ticket category** — staff must run **`/setup`** (Tickets) before appeals work.",
                ),
                ephemeral=True,
            )
            return

        slug = re.sub(r"[^a-z0-9_-]+", "", member.name.lower())[:40] or "user"
        ch_name = f"warn-appeal-{slug}"[:100]

        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                manage_channels=True,
                send_messages=True,
                read_message_history=True,
            ),
            member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
            ),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                manage_channels=True,
            )

        try:
            ticket_ch = await guild.create_text_channel(
                ch_name,
                category=category,
                overwrites=overwrites,
                reason=f"Warn appeal #{warn_id} for {member}",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=user_warn(
                    "Missing permissions",
                    "The bot needs **Manage Channels** in the ticket category.",
                ),
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            await interaction.followup.send(
                embed=user_warn("Couldn’t create channel", "Try again or ask an admin."),
                ephemeral=True,
            )
            return

        reason_s = str(row.get("reason") or "")
        answers: dict[str, Any] = {
            "Appeal type": "Warn appeal",
            "Warn ID": str(warn_id),
            "Original reason": reason_s[:1000],
        }
        await db.insert_ticket_open(
            ticket_ch.id,
            guild_id,
            member.id,
            button_id=gk.WARN_APPEAL_BUTTON_ID,
            answers=answers,
            ticket_status="warn_appeal",
        )

        emb = info_embed(
            "Warn appeal",
            f"{member.mention} is appealing **warn #{warn_id}**.\n\n"
            f"**Original reason:** {reason_s[:500]}\n\n"
            "Staff can use **`/clearwarn`** here (warn ID is detected from this ticket) or **`/close`** when done.",
        )
        try:
            content = staff_role.mention if staff_role else None
            await ticket_ch.send(content=content, embed=emb)
        except discord.HTTPException:
            pass

        await interaction.followup.send(
            embed=success_embed("Appeal opened", f"Go to {ticket_ch.mention}"),
            ephemeral=True,
        )

    @warnreason.command(name="list", description="List extra warn reason presets (staff)")
    @is_staff()
    async def warnreason_list(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        merged = await _load_merged_reasons(interaction.guild.id)
        customs = [t for t in merged if t not in DEFAULT_WARN_REASONS]
        lines = [f"{i + 1}. {s}" for i, s in enumerate(customs)] or ["_No custom presets — defaults only._"]
        await interaction.response.send_message(
            embed=info_embed("Custom warn reasons", "\n".join(lines)[:3900]), ephemeral=True
        )

    @warnreason.command(name="add", description="Add a custom warn reason preset (staff)")
    @app_commands.describe(text="Reason text (shown in /warn autocomplete)")
    @is_staff()
    async def warnreason_add(self, interaction: discord.Interaction, text: str) -> None:
        if not interaction.guild:
            return
        t = text.strip()
        if not t or len(t) > _MAX_REASON_LEN:
            await interaction.response.send_message(
                embed=user_hint("Invalid", f"Use 1–{_MAX_REASON_LEN} characters."), ephemeral=True
            )
            return
        raw = await db.get_guild_string_setting(interaction.guild.id, gk.WARN_REASON_TEMPLATES_JSON)
        cur: list[str] = []
        if raw and raw.strip():
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    cur = [str(x).strip() for x in data if str(x).strip()]
            except json.JSONDecodeError:
                cur = []
        low = {x.casefold() for x in (*DEFAULT_WARN_REASONS, *cur)}
        if t.casefold() in low:
            await interaction.response.send_message(
                embed=user_hint("Duplicate", "That reason already exists."), ephemeral=True
            )
            return
        if len(cur) >= _MAX_CUSTOM_REASONS:
            await interaction.response.send_message(
                embed=user_hint("Limit", f"Maximum {_MAX_CUSTOM_REASONS} custom reasons."), ephemeral=True
            )
            return
        cur.append(t)
        await db.set_guild_string_setting(
            interaction.guild.id, gk.WARN_REASON_TEMPLATES_JSON, json.dumps(cur, ensure_ascii=False)
        )
        await interaction.response.send_message(
            embed=success_embed("Saved", f"Added: **{t}**"), ephemeral=True
        )

    @warnreason.command(name="remove", description="Remove a custom preset by exact text (staff)")
    @app_commands.describe(text="Exact text to remove")
    @is_staff()
    async def warnreason_remove(self, interaction: discord.Interaction, text: str) -> None:
        if not interaction.guild:
            return
        raw = await db.get_guild_string_setting(interaction.guild.id, gk.WARN_REASON_TEMPLATES_JSON)
        if not raw or not raw.strip():
            await interaction.response.send_message(
                embed=user_hint("Nothing to remove", "No custom presets saved."), ephemeral=True
            )
            return
        try:
            data = json.loads(raw)
            cur = [str(x).strip() for x in data if str(x).strip()] if isinstance(data, list) else []
        except json.JSONDecodeError:
            cur = []
        tgt = text.strip()
        new = [x for x in cur if x != tgt]
        if len(new) == len(cur):
            await interaction.response.send_message(
                embed=user_hint("Not found", "No custom preset matched that text exactly."), ephemeral=True
            )
            return
        await db.set_guild_string_setting(
            interaction.guild.id, gk.WARN_REASON_TEMPLATES_JSON, json.dumps(new, ensure_ascii=False)
        )
        await interaction.response.send_message(embed=success_embed("Removed", f"**{tgt}**"), ephemeral=True)

    @warnreason.command(name="reset", description="Remove all custom presets (staff)")
    @is_staff()
    async def warnreason_reset(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        await db.delete_guild_string_settings_keys(
            interaction.guild.id, [gk.WARN_REASON_TEMPLATES_JSON]
        )
        await interaction.response.send_message(
            embed=success_embed("Reset", "Custom warn reasons cleared — built-in defaults remain."), ephemeral=True
        )

    @app_commands.command(name="warn", description="Warn a member (staff)")
    @app_commands.describe(user="User to warn", reason="Pick a preset or type a custom reason")
    @is_staff()
    async def warn_cmd(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str | None = None,
    ) -> None:
        if not interaction.guild or interaction.channel is None:
            await interaction.response.send_message(
                embed=user_hint("Use this in a server", "Run **`/warn`** from a channel in your Discord server."),
                ephemeral=True,
            )
            return

        reason_s = _norm_reason(reason)
        await interaction.response.defer(ephemeral=True)

        thr = await _guild_warn_threshold(interaction.guild.id)
        wid = await db.add_warn(user.id, interaction.user.id, reason_s)
        total = await db.count_warns(user.id)
        shop_name = interaction.guild.name

        dm_emb = _warn_notice_embed(
            shop_name=shop_name, reason=reason_s, total=total, threshold=thr
        )
        appeal_view = WarnAppealDMView(interaction.guild.id, wid)
        appeal_emb = _appeal_dm_embed(shop_name)
        try:
            await user.send(embed=dm_emb)
            await user.send(embed=appeal_emb, view=appeal_view)
        except discord.Forbidden:
            pass

        log_ch = await get_text_channel(interaction.guild, gk.WARN_LOG_CHANNEL)
        source_ch = interaction.channel
        same_as_log = (
            isinstance(log_ch, discord.TextChannel)
            and isinstance(source_ch, discord.TextChannel)
            and log_ch.id == source_ch.id
        )

        audit = _audit_warn_embed(
            guild=interaction.guild,
            warned=user,
            moderator=interaction.user,
            reason=reason_s,
            warn_id=wid,
            total=total,
            threshold=thr,
            source_channel=source_ch,
        )

        public = f"⚠️ {user.mention} now has {total} warning(s).\n\n**reason**: {reason_s}"
        public_ok = True

        if log_ch:
            try:
                await log_ch.send(embed=audit)
            except discord.Forbidden:
                pass

        if not same_as_log:
            try:
                await interaction.channel.send(
                    content=public,
                    allowed_mentions=discord.AllowedMentions(users=[user]),
                )
            except discord.Forbidden:
                public_ok = False
        elif not log_ch:
            try:
                await interaction.channel.send(
                    content=public,
                    allowed_mentions=discord.AllowedMentions(users=[user]),
                )
            except discord.Forbidden:
                public_ok = False

        staff_note = f"Warn ID `{wid}`. Total: {total}."
        if not log_ch:
            staff_note += "\n\n_Set a **Warn log** channel in **`/setup`** (Channels & roles) or **`/config view`** for a private audit trail._"
        if not public_ok:
            staff_note = (
                "Could not post the public confirmation here (missing **Send Messages**). "
                f"Warn was still logged.\n{staff_note}"
            )
        await interaction.followup.send(embed=success_embed("Warn logged", staff_note), ephemeral=True)

        if total >= thr:
            try:
                await user.ban(reason="Warn threshold reached", delete_message_days=0)
            except discord.Forbidden:
                await interaction.followup.send(
                    embed=user_warn("Couldn’t ban", "The bot needs **Ban Members** (and the member must be bannable)."),
                    ephemeral=True,
                )
                return
            if log_ch:
                try:
                    await log_ch.send(embed=warning_embed("Auto-ban", f"{user} banned — warn threshold."))
                except discord.Forbidden:
                    pass

    @warn_cmd.autocomplete("reason")
    async def warn_reason_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if not interaction.guild:
            return []
        merged = await _load_merged_reasons(interaction.guild.id)
        cur = (current or "").strip().lower()
        picks = [t for t in merged if cur in t.lower()][:25]
        if not picks and cur:
            picks = merged[:25]
        return [app_commands.Choice(name=t[:100], value=t[:100]) for t in picks]

    @app_commands.command(name="warns", description="List warns for a member (staff)")
    @app_commands.describe(member="Member")
    @is_staff()
    async def warns_list(self, interaction: discord.Interaction, member: discord.Member) -> None:
        rows = await db.list_warns(member.id)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("Warns", "No warns."), ephemeral=True
            )
            return
        pages: list[discord.Embed] = []
        for r in rows:
            mod = self.bot.get_user(int(r["moderator_id"]))
            mod_s = mod.mention if mod else str(r["moderator_id"])
            pages.append(
                discord.Embed(
                    title=f"Warn #{r['warn_id']}",
                    description=f"**Reason:** {r['reason']}\n**Mod:** {mod_s}\n**When:** {r['created_at']}",
                    color=PRIMARY,
                )
            )
        if len(pages) == 1:
            await interaction.response.send_message(embed=pages[0], ephemeral=True)
            return
        v = WarnPages(interaction.user.id, pages)
        await interaction.response.send_message(embed=pages[0], view=v, ephemeral=True)

    @app_commands.command(name="clearwarn", description="Delete a warn by ID (staff)")
    @app_commands.describe(
        warn_id="Warn ID (optional inside a warn appeal ticket — uses this ticket’s warn)",
    )
    @is_staff()
    async def clearwarn(
        self, interaction: discord.Interaction, warn_id: int | None = None
    ) -> None:
        wid = warn_id
        if wid is None and interaction.guild and isinstance(interaction.channel, discord.TextChannel):
            t = await db.get_ticket_by_channel(interaction.channel.id)
            if t and t.get("button_id") == gk.WARN_APPEAL_BUTTON_ID:
                raw = t.get("answers")
                try:
                    ans: dict[str, Any] = (
                        json.loads(raw) if isinstance(raw, str) else (raw or {})
                    )
                except json.JSONDecodeError:
                    ans = {}
                s = ans.get("Warn ID")
                if s is not None:
                    try:
                        wid = int(s)
                    except (TypeError, ValueError):
                        wid = None
        if wid is None:
            await interaction.response.send_message(
                embed=user_hint("Warn ID required", "Pass **`warn_id`**, or use this inside a **warn appeal** ticket."),
                ephemeral=True,
            )
            return

        ok = await db.delete_warn(wid)
        if not ok:
            await interaction.response.send_message(
                embed=user_hint("Warn not found", "Check the ID with **`/warns`** — it may have been removed already."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=success_embed("Cleared", f"Warn `{wid}` removed."), ephemeral=True
        )

    @app_commands.command(
        name="setwarnthreshold",
        description="Auto-ban after this many warns (default 3)",
    )
    @app_commands.describe(threshold="1–100")
    @is_staff()
    async def setwarnthreshold_cmd(
        self,
        interaction: discord.Interaction,
        threshold: app_commands.Range[int, 1, 100],
    ) -> None:
        if not interaction.guild:
            return
        await db.set_guild_setting(
            interaction.guild.id, gk.WARN_THRESHOLD_KEY, int(threshold)
        )
        await interaction.response.send_message(
            embed=success_embed("Saved", f"Warn threshold set to **{threshold}**."),
            ephemeral=True,
        )

    @app_commands.command(name="clearallwarns", description="Clear all warns for a member (staff)")
    @app_commands.describe(member="Member")
    @is_staff()
    async def clearallwarns(self, interaction: discord.Interaction, member: discord.Member) -> None:
        n = await db.clear_warns_user(member.id)
        await interaction.response.send_message(
            embed=success_embed("Cleared", f"Removed {n} warn(s)."), ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WarnCog(bot))
