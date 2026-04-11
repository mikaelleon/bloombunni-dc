"""Order delivery drops via DM."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
from utils.checks import is_staff
from utils.embeds import PRIMARY, error_embed, info_embed, success_embed


class DropLinkView(discord.ui.View):
    def __init__(self, url: str) -> None:
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(label="Open link", style=discord.ButtonStyle.link, url=url)
        )


def delivery_ready_embed() -> discord.Embed:
    return discord.Embed(
        title="📦 Your Order is Ready!",
        description=(
            "Your commission is complete. Please respect watermark & TOS.\n"
            f"When you can, leave a vouch in <#{config.VOUCHES_CHANNEL_ID}>."
        ),
        color=PRIMARY,
    )


async def send_completion_delivery_dm(
    bot: commands.Bot, member: discord.Member, order_id: str
) -> None:
    """Optional delivery-style DM when an order is marked completed (no file link)."""
    try:
        await member.send(embed=delivery_ready_embed())
    except discord.Forbidden:
        pass


class DropCog(commands.Cog, name="DropCog"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="drop", description="DM the member a delivery link (staff)")
    @app_commands.describe(member="Recipient", link="Item URL", order_id="Optional order ID for ticket ping")
    @is_staff()
    async def drop_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        link: str,
        order_id: str | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        emb = delivery_ready_embed()
        view = DropLinkView(link)
        try:
            await member.send(embed=emb, view=view)
        except discord.Forbidden:
            await interaction.followup.send(
                embed=error_embed(
                    "DM blocked",
                    "Could not DM this user. Deliver the link manually and ask them to fix privacy settings.",
                ),
                ephemeral=True,
            )
            return
        await db.insert_drop(order_id, member.id, link)
        await interaction.followup.send(
            embed=success_embed("Sent", f"Drop logged for {member.mention}."), ephemeral=True
        )
        if order_id and interaction.guild:
            o = await db.get_order(order_id)
            if o:
                ch = interaction.guild.get_channel(int(o["ticket_channel_id"]))
                if isinstance(ch, discord.TextChannel):
                    await ch.send(
                        embed=info_embed("Drop sent", f"Delivery DM sent to {member.mention}.")
                    )

    @app_commands.command(name="drophistory", description="Show drops for a member (staff)")
    @app_commands.describe(member="Member")
    @is_staff()
    async def drophistory(self, interaction: discord.Interaction, member: discord.Member) -> None:
        rows = await db.list_drops_for_user(member.id)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("Drops", "No drops recorded."), ephemeral=True
            )
            return
        lines = [f"`{r['sent_at']}` — {r['link']}" for r in rows[:25]]
        await interaction.response.send_message(
            embed=info_embed(f"Drops — {member.display_name}", "\n".join(lines)),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DropCog(bot))
