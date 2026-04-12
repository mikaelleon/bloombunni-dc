"""Queue orders: /queue, status dropdown, templates, loyalty."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import guild_keys as gk
from guild_config import ticket_category_ids
from utils.checks import is_staff
from utils.embeds import PRIMARY, info_embed, queue_embed, success_embed, user_hint, user_warn

LOYALTY_MILESTONES: dict[int, str] = {
    5: "10% discount on next order",
    10: "Free chibi sketch",
    20: "Free fullbody flat color",
}

TEMPLATE_KEYS: frozenset[str] = frozenset(db.load_default_templates().keys())


def resolve_template(text: str, **kwargs: Any) -> str:
    """Replace {name} placeholders; leave unknown placeholders unchanged."""

    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key in kwargs and kwargs[key] is not None:
            return str(kwargs[key])
        return m.group(0)

    return re.sub(r"\{(\w+)\}", repl, text)


async def get_template(key: str) -> str:
    """DB override first, else templates.json."""
    row = await db.get_message_template_row(key)
    if row and row.get("content"):
        return str(row["content"])
    defaults = db.load_default_templates()
    return str(defaults.get(key, f"[missing template: {key}]"))


def sanitize_buyer_name(name: str) -> str:
    s = name.lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_]", "", s) or "buyer"


def queue_jump_url(guild_id: int, queue_channel_id: int, message_id: int) -> str:
    return f"https://discord.com/channels/{guild_id}/{queue_channel_id}/{message_id}"


async def build_queue_entry_text(
    order: dict[str, Any],
    guild: discord.Guild,
    queue_message_id: int,
    status: str,
    *,
    order_number: int,
    buyer_display_name: str,
    queue_channel_id: int,
    vouches_channel_id: int,
) -> str:
    """Multi-line queue card body for the queue channel embed."""
    buyer = guild.get_member(int(order["client_id"]))
    handler = guild.get_member(int(order["handler_id"]))
    buyer_mention = buyer.mention if buyer else f"<@{order['client_id']}>"
    handler_mention = handler.mention if handler else f"<@{order['handler_id']}>"

    slug = f"{sanitize_buyer_name(buyer_display_name)}.{order_number}"

    qlink = queue_jump_url(guild.id, queue_channel_id, queue_message_id)
    vouches_ch = f"<#{vouches_channel_id}>"

    ctx = {
        "buyer": buyer_mention,
        "handler": handler_mention,
        "item": order.get("item", ""),
        "amount": order.get("amount", ""),
        "mop": order.get("mop", ""),
        "price": order.get("price", ""),
        "channel_name": slug,
        "queue_link": qlink,
        "vouches_channel": vouches_ch,
    }

    header = resolve_template(await get_template("noted_queue_header"), **ctx)
    ch_line = resolve_template(await get_template("noted_queue_channel"), **ctx)
    buyer_line = resolve_template(await get_template("noted_queue_buyer"), **ctx)
    item_line = resolve_template(await get_template("noted_queue_item"), **ctx)
    price_line = resolve_template(await get_template("noted_queue_price"), **ctx)
    handler_line = resolve_template(await get_template("noted_queue_handler"), **ctx)

    if status == "Noted":
        status_line = resolve_template(await get_template("noted_queue_status"), **ctx)
    elif status == "Processing":
        status_line = resolve_template(await get_template("processing_label"), **ctx)
    else:
        status_line = resolve_template(await get_template("completed_label"), **ctx)

    block = (
        f"{header}\n\n"
        f"🧺  {ch_line}  ✦✧\n"
        f"✦  {buyer_line}\n"
        f"✦  {item_line}\n"
        f"✦  {price_line}\n\n"
        f"....  {status_line}\n"
        f"      {handler_line}"
    )
    return block


class OrderStatusView(discord.ui.View):
    """Persistent staff-only status dropdown. custom_id encodes order + queue message."""

    def __init__(
        self,
        bot: commands.Bot,
        order_id: str,
        queue_message_id: int,
        processing_label: str,
        processing_description: str,
        completed_label: str,
        completed_description: str,
    ) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.order_id = order_id
        self.queue_message_id = queue_message_id
        cid = f"ordst|{order_id}|{queue_message_id}"
        if len(cid) > 100:
            cid = cid[:100]
        sel = discord.ui.Select(
            custom_id=cid,
            placeholder="Update order status",
            options=[
                discord.SelectOption(
                    label=processing_label[:100],
                    value="processing",
                    description=(processing_description or "")[:100] or None,
                ),
                discord.SelectOption(
                    label=completed_label[:100],
                    value="completed",
                    description=(completed_description or "")[:100] or None,
                ),
            ],
        )
        sel.callback = self._on_select
        self.add_item(sel)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=user_hint("Use this in a server", "The status menu only works inside your Discord server."), ephemeral=True
            )
            return
        staff_rid = await db.get_guild_setting(interaction.guild.id, gk.STAFF_ROLE)
        staff = (
            interaction.guild.get_role(int(staff_rid))
            if staff_rid
            else None
        )
        if not staff or staff not in interaction.user.roles:
            await interaction.response.send_message(
                embed=user_warn("Staff only", "This menu is for staff — pick a status option only if you’re handling the order."), ephemeral=True
            )
            return

        cog = interaction.client.get_cog("QueueCog")
        if not isinstance(cog, QueueCog):
            await interaction.response.send_message(
                embed=user_warn("Queue unavailable", "The queue module isn’t loaded — try again after a restart or contact the bot owner."), ephemeral=True
            )
            return

        val = interaction.data.get("values", [""])[0]
        await interaction.response.defer(ephemeral=True)
        if val == "processing":
            await cog.apply_processing(self.order_id, interaction)
        elif val == "completed":
            await cog.apply_completed(self.order_id, interaction)


class TemplatePager(discord.ui.View):
    def __init__(self, user_id: int, chunks: list[str]) -> None:
        super().__init__(timeout=300.0)
        self.user_id = user_id
        self.chunks = chunks
        self.idx = 0

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your list.", ephemeral=True)
            return
        self.idx = max(0, self.idx - 1)
        await interaction.response.edit_message(
            content=self.chunks[self.idx], view=self
        )

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your list.", ephemeral=True)
            return
        self.idx = min(len(self.chunks) - 1, self.idx + 1)
        await interaction.response.edit_message(
            content=self.chunks[self.idx], view=self
        )


class ResetConfirmView(discord.ui.View):
    def __init__(self, staff_id: int) -> None:
        super().__init__(timeout=120.0)
        self.staff_id = staff_id

    @discord.ui.button(label="Confirm reset", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.staff_id:
            await interaction.response.send_message("Not your confirmation.", ephemeral=True)
            return
        n = await db.delete_all_message_templates()
        await interaction.response.edit_message(
            content=f"✅ Cleared **{n}** DB template override(s). Defaults from `templates.json` apply.",
            view=None,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Cancelled.", view=None)


DUMMY_PREVIEW = {
    "buyer": "@buyer",
    "handler": "@handler",
    "item": "chibi fullbody",
    "amount": "2",
    "mop": "GCash",
    "price": "₱300",
    "channel_name": "noted_buyer.1",
    "queue_link": "https://discord.com/channels/0/0/0",
    "vouches_channel": "#vouches",
}


class QueueCog(commands.Cog, name="QueueCog"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def apply_processing(self, order_id: str, interaction: discord.Interaction) -> None:
        order = await db.get_order(order_id)
        if not order or order.get("status") != "Noted":
            await interaction.followup.send(
                embed=user_hint("Can’t set Processing", "This order isn’t in **Noted** state anymore — refresh the queue message or check the ticket."), ephemeral=True
            )
            return
        guild = interaction.guild
        if not guild:
            return
        qcid = await db.get_guild_setting(guild.id, gk.QUEUE_CHANNEL)
        vcid = await db.get_guild_setting(guild.id, gk.VOUCHES_CHANNEL)
        if not qcid or not vcid:
            await interaction.followup.send(
                embed=user_hint(
                    "Channels not configured",
                    "Set **Queue** and **Vouches** under **`/setup`** (Queue group) or **`/config view`** first.",
                ),
                ephemeral=True,
            )
            return
        await db.update_order_status(order_id, "Processing")
        qmid = int(order["queue_message_id"])
        trow = await db.get_ticket_by_channel(int(order["ticket_channel_id"]))
        onum = int(trow["order_number"]) if trow and trow.get("order_number") else 1
        body = await build_queue_entry_text(
            order,
            guild,
            qmid,
            "Processing",
            order_number=onum,
            buyer_display_name=str(order.get("client_name") or "buyer"),
            queue_channel_id=int(qcid),
            vouches_channel_id=int(vcid),
        )
        emb = queue_embed(order, body)
        ch = guild.get_channel(int(qcid))
        if isinstance(ch, discord.TextChannel):
            try:
                msg = await ch.fetch_message(qmid)
                await msg.edit(embed=emb)
            except (discord.NotFound, discord.Forbidden):
                pass

        tick = guild.get_channel(int(order["ticket_channel_id"]))
        if isinstance(tick, discord.TextChannel):
            slug = sanitize_buyer_name(order.get("client_name") or "buyer")
            trow = await db.get_ticket_by_channel(tick.id)
            num = int(trow["order_number"]) if trow and trow.get("order_number") else 1
            try:
                pcid = await db.get_guild_setting(guild.id, gk.PROCESSING_CATEGORY)
                pcat = guild.get_channel(int(pcid)) if pcid else None
                p_kw: dict[str, Any] = {"name": f"processing_{slug}.{num}"[:100]}
                if isinstance(pcat, discord.CategoryChannel):
                    p_kw["category"] = pcat
                await tick.edit(**p_kw)
            except discord.Forbidden:
                pass
        buyer = guild.get_member(int(order["client_id"]))
        if isinstance(tick, discord.TextChannel):
            proc_msg = resolve_template(
                await get_template("processing_message"),
                **{
                    "buyer": buyer.mention if buyer else "",
                    "handler": "",
                    "item": order.get("item", ""),
                    "amount": order.get("amount", ""),
                    "mop": order.get("mop", ""),
                    "price": order.get("price", ""),
                    "channel_name": tick.name,
                    "queue_link": queue_jump_url(guild.id, int(qcid), qmid),
                    "vouches_channel": f"<#{vcid}>",
                },
            )
            if buyer:
                try:
                    await tick.send(content=f"{buyer.mention}\n{proc_msg}")
                except discord.Forbidden:
                    pass

        await interaction.followup.send(
            content="✅ Order marked as processing.", ephemeral=True
        )

    async def apply_completed(self, order_id: str, interaction: discord.Interaction) -> None:
        order = await db.get_order(order_id)
        if not order or order.get("status") not in ("Noted", "Processing"):
            await interaction.followup.send(
                embed=user_hint("Can’t set Completed", "This order must be **Noted** or **Processing** first — refresh if it already moved."), ephemeral=True
            )
            return
        guild = interaction.guild
        if not guild:
            return
        qcid = await db.get_guild_setting(guild.id, gk.QUEUE_CHANNEL)
        vcid = await db.get_guild_setting(guild.id, gk.VOUCHES_CHANNEL)
        if not qcid or not vcid:
            await interaction.followup.send(
                embed=user_hint("Channels not configured", "Set **Queue** and **Vouches** via **`/setup`** or check **`/config view`**."),
                ephemeral=True,
            )
            return

        await db.update_order_status(order_id, "Done")
        qmid = int(order["queue_message_id"])
        trow = await db.get_ticket_by_channel(int(order["ticket_channel_id"]))
        onum = int(trow["order_number"]) if trow and trow.get("order_number") else 1
        body = await build_queue_entry_text(
            order,
            guild,
            qmid,
            "Done",
            order_number=onum,
            buyer_display_name=str(order.get("client_name") or "buyer"),
            queue_channel_id=int(qcid),
            vouches_channel_id=int(vcid),
        )
        emb = queue_embed(order, body)
        qch = guild.get_channel(int(qcid))
        if isinstance(qch, discord.TextChannel):
            try:
                msg = await qch.fetch_message(qmid)
                await msg.edit(embed=emb)
            except (discord.NotFound, discord.Forbidden):
                pass

        tick = guild.get_channel(int(order["ticket_channel_id"]))
        buyer = guild.get_member(int(order["client_id"]))
        slug = sanitize_buyer_name(order.get("client_name") or "buyer")
        trow = await db.get_ticket_by_channel(tick.id) if isinstance(tick, discord.TextChannel) else None
        num = int(trow["order_number"]) if trow and trow.get("order_number") else 1

        if isinstance(tick, discord.TextChannel):
            try:
                dcid = await db.get_guild_setting(guild.id, gk.DONE_CATEGORY)
                dcat = guild.get_channel(int(dcid)) if dcid else None
                d_kw: dict[str, Any] = {"name": f"done_{slug}.{num}"[:100]}
                if isinstance(dcat, discord.CategoryChannel):
                    d_kw["category"] = dcat
                await tick.edit(**d_kw)
            except discord.Forbidden:
                pass
            ctx = {
                "buyer": buyer.mention if buyer else "",
                "handler": "",
                "item": order.get("item", ""),
                "amount": order.get("amount", ""),
                "mop": order.get("mop", ""),
                "price": order.get("price", ""),
                "channel_name": tick.name,
                "queue_link": queue_jump_url(guild.id, int(qcid), qmid),
                "vouches_channel": f"<#{vcid}>",
            }
            done_msg = resolve_template(await get_template("completed_message"), **ctx)
            if buyer:
                try:
                    await tick.send(content=f"{buyer.mention}\n{done_msg}")
                except discord.Forbidden:
                    pass

        if buyer:
            pvr = await db.get_guild_setting(guild.id, gk.PLEASE_VOUCH_ROLE)
            role = guild.get_role(int(pvr)) if pvr else None
            if role:
                try:
                    await buyer.add_roles(role, reason="Order completed")
                except discord.Forbidden:
                    pass
            count = await db.increment_loyalty(buyer.id, buyer.display_name)
            for milestone in sorted(LOYALTY_MILESTONES.keys()):
                if count != milestone:
                    continue
                reward = LOYALTY_MILESTONES[milestone]
                try:
                    await buyer.send(
                        embed=success_embed(
                            "Loyalty milestone",
                            f"You reached **{milestone}** completed orders!\n**Reward:** {reward}",
                        )
                    )
                except discord.Forbidden:
                    pass
                break

            from cogs.drop import send_completion_delivery_dm

            await send_completion_delivery_dm(self.bot, buyer, order_id)

        await interaction.followup.send(
            content="✅ Order marked as completed.", ephemeral=True
        )

    @app_commands.command(name="queue", description="Register order in queue from an open ticket (staff)")
    @app_commands.describe(
        handler="Staff handling the order",
        buyer="Buyer (client)",
        amount="Amount / quantity description",
        item="Item / commission description",
        mop="Mode of payment label",
        price="Price text",
        channel="Ticket channel for this order",
    )
    @is_staff()
    async def queue_cmd(
        self,
        interaction: discord.Interaction,
        handler: discord.Member,
        buyer: discord.Member,
        amount: str,
        item: str,
        mop: str,
        price: str,
        channel: discord.TextChannel,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        valid_cats = await ticket_category_ids(interaction.guild.id)
        if not valid_cats or channel.category_id not in valid_cats:
            await interaction.followup.send(
                embed=user_hint("Wrong channel", "Pick a channel under your configured **ticket** categories."), ephemeral=True
            )
            return

        now = datetime.now(timezone.utc)
        mm = now.month
        yy = now.year % 100
        raw_pf = await db.get_guild_string_setting(
            interaction.guild.id, gk.ORDER_ID_PREFIX
        )
        op = re.sub(r"[^A-Za-z0-9_-]", "", (raw_pf or "MIKA").strip())[:24] or "MIKA"
        month_count = await db.count_orders_in_month(now.year, now.month, op) + 1
        order_id = f"{op}-{mm:02d}{yy:02d}-{month_count:04d}"

        buyer_count_before = await db.count_orders_for_buyer(buyer.id)
        order_number = buyer_count_before + 1

        await db.insert_order(
            order_id,
            handler.id,
            buyer.id,
            buyer.display_name,
            item,
            amount,
            mop,
            price,
            channel.id,
            "Noted",
        )

        await db.update_ticket_order(channel.id, order_id, order_number)

        noted_cid = await db.get_guild_setting(interaction.guild.id, gk.NOTED_CATEGORY)
        noted_cat = (
            interaction.guild.get_channel(int(noted_cid))
            if noted_cid
            else None
        )
        slug = sanitize_buyer_name(buyer.display_name)
        try:
            edit_kw: dict[str, Any] = {"name": f"noted_{slug}.{order_number}"[:100]}
            if isinstance(noted_cat, discord.CategoryChannel):
                edit_kw["category"] = noted_cat
            await channel.edit(**edit_kw)
        except discord.Forbidden:
            pass

        guild = interaction.guild
        order_row = await db.get_order(order_id)
        assert order_row

        qcid = await db.get_guild_setting(guild.id, gk.QUEUE_CHANNEL)
        vcid = await db.get_guild_setting(guild.id, gk.VOUCHES_CHANNEL)
        if not qcid or not vcid:
            await interaction.followup.send(
                embed=user_hint(
                    "Channels not configured",
                    "Set **Queue** and **Vouches** with **`/setup`** (wizard) first.",
                ),
                ephemeral=True,
            )
            return

        q_ch = guild.get_channel(int(qcid))
        qmid = 0
        if isinstance(q_ch, discord.TextChannel):
            try:
                qmsg = await q_ch.send(
                    embed=discord.Embed(description="\u200b", color=PRIMARY)
                )
                qmid = qmsg.id
                await db.set_order_queue_message_id(order_id, qmid)
            except discord.Forbidden:
                pass

        if not qmid:
            await interaction.followup.send(
                embed=user_warn("Queue channel issue", "Couldn’t post to the queue channel — check bot **Send Messages** there or remap the queue channel."),
                ephemeral=True,
            )
            return

        order_row = await db.get_order(order_id)
        body = await build_queue_entry_text(
            order_row,
            guild,
            qmid,
            "Noted",
            order_number=order_number,
            buyer_display_name=buyer.display_name,
            queue_channel_id=int(qcid),
            vouches_channel_id=int(vcid),
        )
        emb_q = queue_embed(order_row, body)
        try:
            msg = await q_ch.fetch_message(qmid)
            await msg.edit(embed=emb_q)
        except (discord.NotFound, discord.Forbidden):
            pass

        qlink = queue_jump_url(guild.id, int(qcid), qmid)
        noted_title = resolve_template(await get_template("noted_channel"), buyer=buyer.mention)
        noted_buyer = resolve_template(
            await get_template("noted_buyer_line"),
            buyer=buyer.mention,
            handler=handler.mention,
            item=item,
            amount=amount,
            mop=mop,
            price=price,
            channel_name=channel.name,
            queue_link=qlink,
            vouches_channel=f"<#{vcid}>",
        )
        noted_inst = resolve_template(
            await get_template("noted_instructions"),
            buyer=buyer.mention,
            handler=handler.mention,
            item=item,
            amount=amount,
            mop=mop,
            price=price,
            channel_name=channel.name,
            queue_link=qlink,
            vouches_channel=f"<#{vcid}>",
        )
        emb_ticket = discord.Embed(
            title=noted_title[:256],
            description=f"{noted_buyer}\n\n{noted_inst}",
            color=PRIMARY,
        )
        try:
            await channel.send(content=buyer.mention, embed=emb_ticket)
        except discord.Forbidden:
            pass

        pl = await get_template("processing_label")
        pd = await get_template("processing_description")
        cl = await get_template("completed_label")
        cd = await get_template("completed_description")
        view = OrderStatusView(self.bot, order_id, qmid, pl, pd, cl, cd)
        staff_header = "ςωϑ — staff only | do not touch .!"
        try:
            await channel.send(content=staff_header, view=view)
        except discord.Forbidden:
            pass

        self.bot.add_view(
            OrderStatusView(self.bot, order_id, qmid, pl, pd, cl, cd)
        )

        await interaction.followup.send(
            embed=success_embed("Queue", f"Order `{order_id}` registered."), ephemeral=True
        )

    @app_commands.command(name="settemplate", description="Set a message template override (staff)")
    @app_commands.describe(key="Template key", value="New text (placeholders allowed)")
    @is_staff()
    async def settemplate(
        self,
        interaction: discord.Interaction,
        key: str,
        value: str,
    ) -> None:
        if key not in TEMPLATE_KEYS:
            await interaction.response.send_message(
                embed=user_hint("Unknown template key", f"Use one of: {', '.join(sorted(TEMPLATE_KEYS))}"),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        await db.upsert_message_template(key, value, interaction.user.id)
        preview = resolve_template(value, **DUMMY_PREVIEW)
        await interaction.followup.send(
            embed=info_embed(
                "Template saved",
                f"**{key}**\n\nPreview (dummy data):\n{preview[:1800]}",
            ),
            ephemeral=True,
        )

    @app_commands.command(name="viewtemplate", description="View a template (staff)")
    @app_commands.describe(key="Template key")
    @is_staff()
    async def viewtemplate(self, interaction: discord.Interaction, key: str) -> None:
        if key not in TEMPLATE_KEYS:
            await interaction.response.send_message(
                embed=user_hint("Unknown template key", "Run **`/listtemplates`** for valid keys."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        row = await db.get_message_template_row(key)
        db_val = row["content"] if row else None
        default = db.load_default_templates().get(key, "")
        current = db_val if db_val else default
        preview = resolve_template(current, **DUMMY_PREVIEW)
        src = "database override" if db_val else "templates.json default"
        await interaction.followup.send(
            embed=info_embed(
                f"Template `{key}` ({src})",
                f"{current[:900]}\n\n--- Preview ---\n{preview[:900]}",
            ),
            ephemeral=True,
        )

    @app_commands.command(name="resettemplates", description="Reset all template DB overrides (staff)")
    @is_staff()
    async def resettemplates(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "Reset all custom templates to `templates.json` defaults?",
            view=ResetConfirmView(interaction.user.id),
            ephemeral=True,
        )

    @app_commands.command(name="listtemplates", description="List all templates and sources (staff)")
    @is_staff()
    async def listtemplates(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        defaults = db.load_default_templates()
        rows = {r["template_key"]: r["content"] for r in await db.list_message_template_rows()}
        lines: list[str] = []
        for k in sorted(TEMPLATE_KEYS):
            if k in rows:
                lines.append(f"**{k}** `[custom]` — {rows[k][:80]}...")
            else:
                lines.append(f"**{k}** `[default]` — {defaults.get(k, '')[:80]}...")
        chunks: list[str] = []
        page: list[str] = []
        for line in lines:
            page.append(line)
            if len(page) >= 5:
                chunks.append("\n".join(page))
                page = []
        if page:
            chunks.append("\n".join(page))
        if not chunks:
            chunks = ["(none)"]
        v = TemplatePager(interaction.user.id, chunks)
        await interaction.followup.send(content=chunks[0], view=v, ephemeral=True)

    @app_commands.command(name="loyalty", description="View loyalty progress for a member")
    @app_commands.describe(member="Member")
    async def loyalty_cmd(self, interaction: discord.Interaction, member: discord.Member) -> None:
        row = await db.get_loyalty(member.id)
        count = int(row["completed_count"]) if row else 0
        next_m = None
        for m in sorted(LOYALTY_MILESTONES.keys()):
            if count < m:
                next_m = m
                break
        bar_len = 10
        prog = min(1.0, count / next_m) if next_m else 1.0
        filled = int(prog * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        desc = f"**Completed orders:** {count}\n**Next milestone:** {next_m or 'max'}\n`{bar}`"
        await interaction.response.send_message(
            embed=info_embed("Loyalty", desc), ephemeral=True
        )

    @app_commands.command(
        name="setorderprefix",
        description="Set order ID prefix (e.g. MIKA). Letters, numbers, _ and - only.",
    )
    @app_commands.describe(prefix="Prefix before -MMYY-#### (default MIKA)")
    @is_staff()
    async def setorderprefix_cmd(self, interaction: discord.Interaction, prefix: str) -> None:
        if not interaction.guild:
            return
        cleaned = re.sub(r"[^A-Za-z0-9_-]", "", prefix.strip())[:24] or "MIKA"
        await db.set_guild_string_setting(
            interaction.guild.id, gk.ORDER_ID_PREFIX, cleaned
        )
        await interaction.response.send_message(
            embed=success_embed("Saved", f"Order IDs will use **`{cleaned}-`**…"),
            ephemeral=True,
        )

    @app_commands.command(name="loyaltytop", description="Top 10 clients by completed orders")
    async def loyaltytop(self, interaction: discord.Interaction) -> None:
        rows = await db.loyalty_top(10)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("Top loyalty", "No data yet."), ephemeral=True
            )
            return
        lines = [f"{i}. <@{r['client_id']}> — **{r['completed_count']}**" for i, r in enumerate(rows, 1)]
        await interaction.response.send_message(
            embed=info_embed("Top loyalty", "\n".join(lines)), ephemeral=True
        )


async def register_order_status_views(bot: commands.Bot) -> None:
    orders = await db.list_orders_for_status_views()
    for o in orders:
        qmid = o.get("queue_message_id")
        if not qmid:
            continue
        pl = await get_template("processing_label")
        pd = await get_template("processing_description")
        cl = await get_template("completed_label")
        cd = await get_template("completed_description")
        bot.add_view(
            OrderStatusView(
                bot, o["order_id"], int(qmid), pl, pd, cl, cd
            )
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(QueueCog(bot))
