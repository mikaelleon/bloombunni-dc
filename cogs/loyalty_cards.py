"""Loyalty stamp cards: ticket close posts card + thread; vouch advances stamp image."""

from __future__ import annotations

import asyncio
import io
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

import database as db
import guild_keys as gk
from utils.embeds import info_embed, success_embed, user_hint, user_warn
from utils.logging_setup import get_logger

log = get_logger("loyalty_cards")
_WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
_LCSTATES_DIR = _WORKSPACE_ROOT / "lcstates"

DEFAULT_CARD_TEMPLATE = (
    "🪄 thank you for purchasing\n\n"
    "**Buy again to unlock your stamps!**\n"
    "Make sure to present your card — in every purchase. More stamps: more sweet rewards for you! 🤍\n"
    "**Stamp will only add if you vouch.**\n\n"
    "loved by {mention}\n\n"
    "Loyalty card **LC-{card_no:03d}** · stamps **{stamps}** / **{max_stamps}**"
)


def _is_guild_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return False
    if interaction.user.id == interaction.guild.owner_id:
        return True
    return bool(interaction.user.guild_permissions.administrator)


def _format_card_body(
    guild_id: int,
    template: str | None,
    *,
    mention: str,
    card_no: int,
    stamps: int,
    max_stamps: int,
) -> str:
    raw = template or DEFAULT_CARD_TEMPLATE
    return raw.format(
        mention=mention,
        card_no=int(card_no),
        stamps=int(stamps),
        max_stamps=int(max_stamps),
    )[:2000]


async def _fetch_url_bytes(url: str, limit: int = 8_000_000) -> bytes:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            resp.raise_for_status()
            blob = await resp.content.read(limit + 1)
            if len(blob) > limit:
                raise ValueError("Image too large (max 8MB).")
            return blob


def _local_lcstate_path(stamp_index: int) -> Path:
    return _LCSTATES_DIR / f"{int(stamp_index)}-STAMP.png"


def _resolve_repo_text_path(raw: str) -> Path | None:
    rel = str(raw or "").strip().replace("\\", "/")
    if not rel or rel.startswith("/"):
        return None
    p = (_WORKSPACE_ROOT / rel).resolve()
    if not str(p).startswith(str(_WORKSPACE_ROOT)):
        return None
    return p


async def _load_loyalty_image_bytes(
    guild_id: int,
    stamp_index: int,
    configured_map: dict[int, str] | None = None,
) -> tuple[bytes, str]:
    local_default = _local_lcstate_path(stamp_index)
    if local_default.exists():
        return (local_default.read_bytes(), local_default.suffix.lstrip(".") or "png")

    imgs = configured_map if configured_map is not None else await db.list_loyalty_card_images(guild_id)
    src = imgs.get(int(stamp_index))
    if not src:
        raise ValueError(f"No loyalty image configured for stamp {stamp_index}.")
    s = str(src).strip()
    if s.startswith(("http://", "https://")):
        blob = await _fetch_url_bytes(s)
        ext = "png"
        if "." in s.split("?")[0].rsplit("/", 1)[-1]:
            ext = s.split("?")[0].rsplit(".", 1)[-1][:8] or "png"
        return (blob, ext)
    local = _resolve_repo_text_path(s)
    if not local or not local.exists():
        raise ValueError(f"Configured loyalty image path missing: {s}")
    return (local.read_bytes(), local.suffix.lstrip(".") or "png")


async def _delete_card_message(
    guild: discord.Guild,
    row: dict[str, Any],
) -> None:
    cid = row.get("channel_id")
    mid = row.get("message_id")
    if not cid or not mid:
        return
    ch = guild.get_channel(int(cid))
    if not isinstance(ch, discord.TextChannel):
        return
    try:
        msg = await ch.fetch_message(int(mid))
        await msg.delete()
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass


async def remove_active_loyalty_cards_for_user(
    guild: discord.Guild,
    user_id: int,
) -> None:
    rows = await db.get_active_loyalty_cards_for_user(guild.id, user_id)
    for row in rows:
        await _delete_card_message(guild, row)
        await db.delete_loyalty_card_row(int(row["id"]))


async def _ensure_loyalty_text_channel(
    guild: discord.Guild,
) -> discord.TextChannel | None:
    me = guild.me
    if not me:
        return None
    cat_id = await db.get_guild_setting(guild.id, gk.LOYALTY_CARD_CATEGORY)
    category: discord.CategoryChannel | None = None
    if cat_id:
        c = guild.get_channel(int(cat_id))
        if isinstance(c, discord.CategoryChannel):
            category = c
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=False,
            read_message_history=True,
        ),
        me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            manage_messages=True,
            create_public_threads=True,
            send_messages_in_threads=True,
        ),
    }
    try:
        chan = await guild.create_text_channel(
            "loyalty-cards",
            category=category,
            overwrites=overwrites,
            reason="Loyalty cards auto-create",
        )
    except discord.HTTPException:
        return None
    await db.set_guild_setting(guild.id, gk.LOYALTY_CARD_CHANNEL, chan.id)
    return chan


async def resolve_loyalty_channel(
    guild: discord.Guild,
) -> discord.TextChannel | None:
    cid = await db.get_guild_setting(guild.id, gk.LOYALTY_CARD_CHANNEL)
    if cid:
        ch = guild.get_channel(int(cid))
        if isinstance(ch, discord.TextChannel):
            return ch
    auto = await db.get_guild_setting(guild.id, gk.LOYALTY_CARD_AUTO_CREATE)
    if auto and int(auto) == 1:
        return await _ensure_loyalty_text_channel(guild)
    return None


async def issue_loyalty_card_for_ticket_closure(
    guild: discord.Guild,
    ticket: dict[str, Any],
    client: discord.Member | None,
) -> bool:
    """Post loyalty card for this ticket. Returns True if a new card was issued."""
    if not client:
        return False
    gid = guild.id
    imgs = await db.list_loyalty_card_images(gid)
    if not _local_lcstate_path(0).exists() and (not imgs or 0 not in imgs):
        return False
    ch = await resolve_loyalty_channel(guild)
    if not isinstance(ch, discord.TextChannel):
        log.warning("Loyalty card skipped (no channel): guild_id=%s", gid)
        return False
    try:
        # Idempotency: if same ticket already issued active card, do nothing.
        t_ch = ticket.get("channel_id")
        t_ch_id = int(t_ch) if t_ch is not None else None
        existing = await db.get_active_loyalty_cards_for_user(gid, client.id)
        for row in existing:
            if t_ch_id is not None and int(row.get("ticket_channel_id") or 0) == t_ch_id:
                return False

        await remove_active_loyalty_cards_for_user(guild, client.id)
        card_number = await db.allocate_loyalty_card_number(gid)
        max_idx = await db.loyalty_card_max_stamp_index(gid)
        if max_idx is None:
            return False
        void_h = await db.get_guild_setting(gid, gk.LOYALTY_CARD_VOID_HOURS) or 0
        void_deadline: int | None = None
        if int(void_h) > 0:
            void_deadline = int(datetime.now(timezone.utc).timestamp()) + int(void_h) * 3600
        tmpl = await db.get_guild_string_setting(gid, gk.LOYALTY_CARD_MESSAGE_TEMPLATE)
        body = _format_card_body(
            gid,
            tmpl,
            mention=client.mention,
            card_no=card_number,
            stamps=0,
            max_stamps=max_idx,
        )
        if int(void_h) > 0:
            body = (
                f"{body}\n\n_If no vouch within **{int(void_h)}** hours, this card may be voided (server rules)._"
            )[:2000]
        data, ext = await _load_loyalty_image_bytes(gid, 0, imgs)
        fp = discord.File(io.BytesIO(data), filename=f"loyalty-LC{card_number:03d}-0.{ext}")
        pk = await db.insert_loyalty_card(
            gid,
            card_number=card_number,
            user_id=client.id,
            stamp_count=0,
            message_id=None,
            thread_id=None,
            channel_id=ch.id,
            ticket_channel_id=t_ch_id,
            void_deadline_ts=void_deadline,
        )
        msg = await ch.send(content=body, file=fp)
        thread_name = await db.get_guild_string_setting(gid, gk.LOYALTY_CARD_THREAD_NAME)
        tname = (thread_name or "୨୧ card stamps").strip()[:100]
        thread_id: int | None = None
        try:
            th = await msg.create_thread(
                name=tname,
                auto_archive_duration=10080,
                reason="Loyalty card stamps",
            )
            thread_id = th.id
        except (discord.HTTPException, discord.Forbidden):
            pass
        await db.patch_loyalty_card(
            pk,
            {"message_id": int(msg.id), "thread_id": thread_id},
        )
        return True
    except Exception:
        log.exception("issue_loyalty_card_for_ticket_closure failed guild_id=%s", gid)
        return False


async def apply_vouch_to_loyalty_card(
    guild: discord.Guild,
    user_id: int,
) -> None:
    gid = guild.id
    imgs = await db.list_loyalty_card_images(gid)
    if not imgs and not _local_lcstate_path(0).exists():
        return
    max_idx_local = -1
    for i in range(0, 31):
        if _local_lcstate_path(i).exists():
            max_idx_local = i
    max_idx_db = await db.loyalty_card_max_stamp_index(gid)
    max_idx = max(max_idx_local, int(max_idx_db) if max_idx_db is not None else -1)
    if max_idx < 0:
        return
    rows = await db.get_active_loyalty_cards_for_user(gid, user_id)
    if not rows:
        return
    row = rows[0]
    pk = int(row["id"])
    cur = int(row["stamp_count"] or 0)
    if cur >= max_idx:
        return
    new_sc = min(cur + 1, max_idx)
    ch = guild.get_channel(int(row["channel_id"])) if row.get("channel_id") else None
    mid = row.get("message_id")
    if not isinstance(ch, discord.TextChannel) or not mid:
        return
    member = guild.get_member(user_id)
    mention = member.mention if member else f"<@{user_id}>"
    tmpl = await db.get_guild_string_setting(gid, gk.LOYALTY_CARD_MESSAGE_TEMPLATE)
    body = _format_card_body(
        gid,
        tmpl,
        mention=mention,
        card_no=int(row["card_number"]),
        stamps=new_sc,
        max_stamps=max_idx,
    )
    now_ts = int(datetime.now(timezone.utc).timestamp())
    try:
        data, ext = await _load_loyalty_image_bytes(gid, new_sc, imgs)
        fp = discord.File(
            io.BytesIO(data),
            filename=f"loyalty-LC{int(row['card_number']):03d}-{new_sc}.{ext}",
        )
        msg = await ch.fetch_message(int(mid))
        await msg.edit(content=body, attachments=[fp])
    except Exception:
        log.exception("apply_vouch_to_loyalty_card edit failed card_pk=%s", pk)
        return
    patch_u: dict[str, Any] = {"stamp_count": new_sc}
    if new_sc > 0:
        patch_u["void_deadline_ts"] = None
    if cur == 0 and new_sc >= 1:
        patch_u["first_vouch_ts"] = now_ts
    await db.patch_loyalty_card(pk, patch_u)


class LoyaltyCardCog(commands.Cog, name="LoyaltyCardCog"):
    """Loyalty stamp cards (LC-###) posted after ticket close."""

    loyalty_card = app_commands.Group(
        name="loyalty_card",
        description="Loyalty stamp cards (configure channel, images, void timer)",
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._void_task: asyncio.Task[None] | None = None

    async def cog_load(self) -> None:
        self._void_task = asyncio.create_task(self._void_loop())

    async def cog_unload(self) -> None:
        if self._void_task:
            self._void_task.cancel()

    async def _void_loop(self) -> None:
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                now_ts = int(datetime.now(timezone.utc).timestamp())
                due = await db.list_loyalty_cards_due_void(now_ts)
                for row in due:
                    gid = int(row["guild_id"])
                    g = self.bot.get_guild(gid)
                    if g:
                        await _delete_card_message(g, row)
                        await db.delete_loyalty_card_row(int(row["id"]))
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("loyalty void loop")
            await asyncio.sleep(120)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await remove_active_loyalty_cards_for_user(member.guild, member.id)

    @loyalty_card.command(name="showlist", description="List active loyalty cards (owner/admin)")
    async def showlist_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        if not _is_guild_admin(interaction):
            await interaction.response.send_message(
                embed=user_warn("Denied", "Owner or administrator only."),
                ephemeral=True,
            )
            return
        rows = await db.list_loyalty_cards_active_or_pending_void(interaction.guild.id)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("Loyalty cards", "No active cards."),
                ephemeral=True,
            )
            return
        max_idx = await db.loyalty_card_max_stamp_index(interaction.guild.id) or 0
        lines: list[str] = []
        for r in rows[:40]:
            uid = int(r["user_id"])
            lines.append(
                f"`LC-{int(r['card_number']):03d}` · <@{uid}> · stamps {int(r['stamp_count'])}/{max_idx}"
            )
        extra = ""
        if len(rows) > 40:
            extra = f"\n… +{len(rows) - 40} more"
        await interaction.response.send_message(
            embed=info_embed(f"Active loyalty cards ({len(rows)})", "\n".join(lines)[:3900] + extra),
            ephemeral=True,
        )

    @loyalty_card.command(name="channel", description="Set loyalty card channel (owner/admin)")
    @app_commands.describe(channel="Where cards are posted")
    async def channel_cmd(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        if not interaction.guild or not _is_guild_admin(interaction):
            await interaction.response.send_message("Owner/admin only.", ephemeral=True)
            return
        await db.set_guild_setting(interaction.guild.id, gk.LOYALTY_CARD_CHANNEL, channel.id)
        await interaction.response.send_message(
            embed=success_embed("Saved", f"Loyalty channel set to {channel.mention}."),
            ephemeral=True,
        )

    @loyalty_card.command(name="autocreate", description="Allow bot to auto-create #loyalty-cards (owner/admin)")
    @app_commands.describe(enabled="Create channel if none set")
    async def autocreate_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool,
    ) -> None:
        if not interaction.guild or not _is_guild_admin(interaction):
            await interaction.response.send_message("Owner/admin only.", ephemeral=True)
            return
        await db.set_guild_setting(
            interaction.guild.id,
            gk.LOYALTY_CARD_AUTO_CREATE,
            1 if enabled else 0,
        )
        await interaction.response.send_message(
            embed=success_embed("Saved", f"Auto-create loyalty channel: **{enabled}**."),
            ephemeral=True,
        )

    @loyalty_card.command(
        name="createchannel",
        description="Create #loyalty-cards and set it (owner/admin)",
    )
    async def createchannel_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not _is_guild_admin(interaction):
            await interaction.response.send_message("Owner/admin only.", ephemeral=True)
            return
        ch = await _ensure_loyalty_text_channel(interaction.guild)
        if not ch:
            await interaction.response.send_message(
                embed=user_warn("Failed", "Could not create channel (permissions?)."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=success_embed("Created", f"Loyalty channel: {ch.mention}"),
            ephemeral=True,
        )

    @loyalty_card.command(
        name="voidhours",
        description="Hours to first vouch before card voids (0 = off)",
    )
    @app_commands.describe(hours="0 disables deadline")
    async def voidhours_cmd(
        self,
        interaction: discord.Interaction,
        hours: app_commands.Range[int, 0, 8760],
    ) -> None:
        if not interaction.guild or not _is_guild_admin(interaction):
            await interaction.response.send_message("Owner/admin only.", ephemeral=True)
            return
        await db.set_guild_setting(interaction.guild.id, gk.LOYALTY_CARD_VOID_HOURS, int(hours))
        await interaction.response.send_message(
            embed=success_embed("Saved", f"Void if no vouch within **{hours}** hour(s) (0 = off)."),
            ephemeral=True,
        )

    @loyalty_card.command(name="setimage", description="Set image source for stamp index (URL or repo path)")
    @app_commands.describe(stamp_index="0 = empty, 1 = one stamp, …", url="https URL or repo path like lcstates/0-STAMP.png")
    async def setimage_cmd(
        self,
        interaction: discord.Interaction,
        stamp_index: app_commands.Range[int, 0, 30],
        url: str,
    ) -> None:
        if not interaction.guild or not _is_guild_admin(interaction):
            await interaction.response.send_message("Owner/admin only.", ephemeral=True)
            return
        u = url.strip()
        if u.startswith(("http://", "https://")):
            pass
        else:
            p = _resolve_repo_text_path(u)
            if not p or not p.exists():
                await interaction.response.send_message("Path not found in repo.", ephemeral=True)
                return
        await db.upsert_loyalty_card_image(interaction.guild.id, int(stamp_index), u)
        await interaction.response.send_message(
            embed=success_embed("Saved", f"Stamp **{stamp_index}** image set."),
            ephemeral=True,
        )

    @loyalty_card.command(name="images", description="List configured stamp images")
    async def images_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not _is_guild_admin(interaction):
            await interaction.response.send_message("Owner/admin only.", ephemeral=True)
            return
        imgs = await db.list_loyalty_card_images(interaction.guild.id)
        if not imgs:
            await interaction.response.send_message("No images yet. Use `/loyalty_card setimage`.", ephemeral=True)
            return
        lines = [f"`{k}` → {v[:80]}…" if len(v) > 80 else f"`{k}` → {v}" for k, v in sorted(imgs.items())]
        await interaction.response.send_message(
            embed=info_embed("Stamp images", "\n".join(lines)[:3900]),
            ephemeral=True,
        )

    @loyalty_card.command(name="abandon", description="Delete your own loyalty card")
    async def abandon_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        await remove_active_loyalty_cards_for_user(interaction.guild, interaction.user.id)
        await interaction.response.send_message(
            embed=success_embed("Removed", "Your loyalty card was removed."),
            ephemeral=True,
        )

    @loyalty_card.command(name="remove", description="Remove a member's loyalty card (owner/admin)")
    @app_commands.describe(member="Target user")
    async def remove_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ) -> None:
        if not interaction.guild or not _is_guild_admin(interaction):
            await interaction.response.send_message("Owner/admin only.", ephemeral=True)
            return
        await remove_active_loyalty_cards_for_user(interaction.guild, member.id)
        await interaction.response.send_message(
            embed=success_embed("Removed", f"Cleared loyalty card for {member.mention}."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LoyaltyCardCog(bot))
