"""Order queue board and status updates."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
from utils.checks import is_staff
from utils.embeds import error_embed, info_embed, queue_embed, success_embed

LOYALTY_MILESTONES = [5, 10, 20]
LOYALTY_REWARDS = [
    "5% off your next commission",
    "Free simple background upgrade",
    "Priority queue slot for one order",
]

STATUS_CHOICES = ["Noted", "WIP", "Processing", "Done", "Cancelled"]

PREFIX_MAP = {
    "Noted": "noted",
    "WIP": "wip",
    "Processing": "processing",
    "Done": "done",
    "Cancelled": "cancelled",
}


def _category_for_status(status: str) -> int:
    if status in ("Noted", "WIP"):
        return config.NOTED_CATEGORY_ID
    if status == "Processing":
        return config.PROCESSING_CATEGORY_ID
    if status in ("Done", "Cancelled"):
        return config.DONE_CATEGORY_ID
    return config.TICKET_CATEGORY_ID


class StatusSelectView(discord.ui.View):
    def __init__(self, order_id: str) -> None:
        super().__init__(timeout=300.0)
        self.order_id = order_id
        opts = [
            discord.SelectOption(label=s, value=s) for s in STATUS_CHOICES
        ]
        sel = discord.ui.Select(placeholder="Set status", options=opts, custom_id="queue_status_pick")
        sel.callback = self._pick
        self.add_item(sel)

    async def _pick(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.user, discord.Member):
            return
        staff_role = interaction.guild.get_role(config.STAFF_ROLE_ID) if interaction.guild else None
        if not staff_role or staff_role not in interaction.user.roles:
            await interaction.response.send_message(
                embed=error_embed("Denied", "Staff only."), ephemeral=True
            )
            return
        status = interaction.data["values"][0]
        await interaction.response.defer(ephemeral=True)
        cog = interaction.client.get_cog("QueueCog")
        if cog and hasattr(cog, "apply_status"):
            await cog.apply_status(interaction, self.order_id, status, respond=True)


class QueueCog(commands.Cog, name="QueueCog"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._queue_message: discord.Message | None = None

    async def load_queue_message(self) -> None:
        row = await db.get_queue_message()
        if not row or not row.get("message_id") or not row.get("channel_id"):
            return
        ch = self.bot.get_channel(int(row["channel_id"]))
        if not isinstance(ch, discord.TextChannel):
            return
        try:
            self._queue_message = await ch.fetch_message(int(row["message_id"]))
        except (discord.NotFound, discord.Forbidden):
            self._queue_message = None

    async def refresh_queue_board(self) -> None:
        orders = await db.list_active_orders()
        emb = queue_embed(orders)
        if self._queue_message:
            try:
                await self._queue_message.edit(embed=emb)
            except (discord.NotFound, discord.HTTPException):
                pass
            return
        row = await db.get_queue_message()
        if not row or not row.get("message_id") or not row.get("channel_id"):
            return
        ch = self.bot.get_channel(int(row["channel_id"]))
        if isinstance(ch, discord.TextChannel):
            try:
                msg = await ch.fetch_message(int(row["message_id"]))
                self._queue_message = msg
                await msg.edit(embed=emb)
            except (discord.NotFound, discord.Forbidden):
                pass

    async def apply_status(
        self,
        interaction: discord.Interaction | None,
        order_id: str,
        status: str,
        respond: bool = True,
    ) -> None:
        order = await db.get_order(order_id)
        if not order:
            if interaction and respond:
                emb = error_embed("Error", "Order not found.")
                if interaction.response.is_done():
                    await interaction.followup.send(embed=emb, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=emb, ephemeral=True)
            return

        await db.update_order_status(order_id, status)
        await self.refresh_queue_board()

        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild:
            return

        ticket = await db.get_ticket_by_order(order_id)
        if ticket:
            ch = guild.get_channel(int(ticket["channel_id"]))
            if isinstance(ch, discord.TextChannel):
                client_id = int(order["client_id"])
                try:
                    await ch.send(
                        content=f"<@{client_id}>",
                        embed=info_embed(
                            "Order status updated",
                            f"Order `{order_id}` is now **{status}**.",
                        ),
                    )
                except discord.Forbidden:
                    pass
                safe = "".join(c for c in str(order["client_name"]) if c.isalnum() or c in "-_")[:80] or "user"
                prefix = PREFIX_MAP.get(status, "ticket")
                new_name = f"{prefix}-{safe.lower()}"
                cat_id = _category_for_status(status)
                category = guild.get_channel(cat_id)
                try:
                    await ch.edit(name=new_name[:100])
                    if isinstance(category, discord.CategoryChannel):
                        await ch.edit(category=category)
                except (discord.Forbidden, discord.HTTPException):
                    pass

        if status == "Done":
            member = guild.get_member(int(order["client_id"]))
            role = guild.get_role(config.PLEASE_VOUCH_ROLE_ID)
            if member and role:
                try:
                    await member.add_roles(role, reason="Order done — please vouch")
                except discord.Forbidden:
                    pass
            count = await db.increment_loyalty(
                int(order["client_id"]),
                str(order["client_name"]),
            )
            for idx, m in enumerate(LOYALTY_MILESTONES):
                if count == m and idx < len(LOYALTY_REWARDS):
                    if member:
                        try:
                            await member.send(
                                embed=success_embed(
                                    "Loyalty milestone",
                                    f"You reached **{m}** completed orders! Reward: {LOYALTY_REWARDS[idx]}",
                                )
                            )
                        except discord.Forbidden:
                            pass
            if member:
                try:
                    await member.send(
                        embed=info_embed(
                            "Delivery",
                            "Your order is marked **Done**. Thank you! "
                            f"Please leave a vouch in <#{config.VOUCHES_CHANNEL_ID}> when ready.",
                        )
                    )
                except discord.Forbidden:
                    pass

        if interaction and respond:
            if interaction.response.is_done():
                await interaction.followup.send(
                    embed=success_embed("Updated", f"Order `{order_id}` → **{status}**"),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    embed=success_embed("Updated", f"Order `{order_id}` → **{status}**"),
                    ephemeral=True,
                )

    async def run_setup_queue(self, interaction: discord.Interaction) -> None:
        """Called from TicketsCog `/setup queue`."""
        ch = interaction.guild.get_channel(config.QUEUE_CHANNEL_ID)
        if not isinstance(ch, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("Config", "Queue channel invalid."), ephemeral=True
            )
            return
        orders = await db.list_active_orders()
        emb = queue_embed(orders)
        await interaction.response.send_message(
            embed=success_embed("Posted", "Queue board created."), ephemeral=True
        )
        msg = await ch.send(embed=emb)
        self._queue_message = msg
        await db.set_queue_message(ch.id, msg.id)

    @app_commands.command(name="status", description="Update order status (staff)")
    @app_commands.describe(order_id="Order ID", new_status="New status")
    @app_commands.choices(
        new_status=[
            app_commands.Choice(name="Noted", value="Noted"),
            app_commands.Choice(name="WIP", value="WIP"),
            app_commands.Choice(name="Processing", value="Processing"),
            app_commands.Choice(name="Done", value="Done"),
            app_commands.Choice(name="Cancelled", value="Cancelled"),
        ]
    )
    @is_staff()
    async def status_cmd(
        self,
        interaction: discord.Interaction,
        order_id: str,
        new_status: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        await self.apply_status(interaction, order_id, new_status, respond=True)

    @app_commands.command(name="queuepanel", description="Ephemeral status dropdown for an order (staff)")
    @app_commands.describe(order_id="Order ID")
    @is_staff()
    async def queuepanel(self, interaction: discord.Interaction, order_id: str) -> None:
        o = await db.get_order(order_id)
        if not o:
            await interaction.response.send_message(
                embed=error_embed("Error", "Order not found."), ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=info_embed("Status", f"Order `{order_id}`"),
            view=StatusSelectView(order_id),
            ephemeral=True,
        )

    @app_commands.command(name="loyalty", description="View loyalty progress for a member")
    @app_commands.describe(member="Member to look up")
    async def loyalty(self, interaction: discord.Interaction, member: discord.Member) -> None:
        row = await db.get_loyalty(member.id)
        count = int(row["completed_count"]) if row else 0
        next_m = None
        for m in LOYALTY_MILESTONES:
            if count < m:
                next_m = m
                break
        bar_len = 10
        if next_m:
            prog = min(1.0, count / next_m)
        else:
            prog = 1.0
        filled = int(prog * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        desc = f"**Completed orders:** {count}\n**Next milestone:** {next_m or 'max'}\n`{bar}`"
        await interaction.response.send_message(embed=info_embed("Loyalty", desc), ephemeral=True)

    @app_commands.command(name="loyaltytop", description="Top 10 clients by completed orders")
    async def loyaltytop(self, interaction: discord.Interaction) -> None:
        rows = await db.loyalty_top(10)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("Top loyalty", "No data yet."), ephemeral=True
            )
            return
        lines = []
        for i, r in enumerate(rows, 1):
            lines.append(f"{i}. <@{r['client_id']}> — **{r['completed_count']}** orders")
        await interaction.response.send_message(
            embed=info_embed("Top loyalty", "\n".join(lines)),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(QueueCog(bot))
