"""Payment method panel with persistent buttons."""

from __future__ import annotations

import config
import discord
from discord.ext import commands

import database as db
import guild_keys as gk
from guild_config import get_text_channel
from utils.embeds import PRIMARY, error_embed, success_embed

class PaymentView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="GCash", style=discord.ButtonStyle.primary, custom_id="pay_gcash")
    async def gcash(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        emb = discord.Embed(
            title="GCash",
            description=config.GCASH_DETAILS,
            color=PRIMARY,
        )
        emb.set_image(url=config.GCASH_QR_URL)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @discord.ui.button(label="PayPal", style=discord.ButtonStyle.secondary, custom_id="pay_paypal")
    async def paypal(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        emb = discord.Embed(
            title="PayPal",
            description=f"[PayPal link]({config.PAYPAL_LINK})",
            color=PRIMARY,
        )
        emb.set_image(url=config.PAYPAL_QR_URL)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @discord.ui.button(label="Ko-fi", style=discord.ButtonStyle.success, custom_id="pay_kofi")
    async def kofi(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        emb = discord.Embed(
            title="Ko-fi",
            description=f"[Ko-fi]({config.KOFI_LINK})",
            color=PRIMARY,
        )
        await interaction.response.send_message(embed=emb, ephemeral=True)


class PaymentCog(commands.Cog, name="PaymentCog"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def run_setup_payment(self, interaction: discord.Interaction) -> None:
        """Invoked from `/setup payment`."""
        ch = await get_text_channel(interaction.guild, gk.PAYMENT_CHANNEL)
        if not ch:
            await interaction.response.send_message(
                embed=error_embed("Config", "Payment channel invalid."), ephemeral=True
            )
            return
        emb = discord.Embed(
            title="Mode of Payment",
            description="Choose a method below for details (ephemeral).",
            color=PRIMARY,
        )
        await interaction.response.send_message(
            embed=success_embed("Posted", "Payment panel deployed."), ephemeral=True
        )
        msg = await ch.send(embed=emb, view=PaymentView())
        await db.set_persist_panel("payment", ch.id, msg.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PaymentCog(bot))
