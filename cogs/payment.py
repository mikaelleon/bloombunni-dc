"""Payment method panel with persistent buttons."""

from __future__ import annotations

import discord
from discord.ext import commands

import database as db
import guild_keys as gk
from guild_config import is_payment_config_complete
from utils.embeds import PRIMARY, success_embed, user_hint


class PaymentView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="GCash", style=discord.ButtonStyle.primary, custom_id="pay_gcash")
    async def gcash(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                embed=user_hint("Use this in a server", "Open the payment panel from inside your Discord server."), ephemeral=True
            )
            return
        details = await db.get_guild_string_setting(interaction.guild.id, gk.PAYMENT_GCASH_DETAILS)
        qr = await db.get_guild_string_setting(interaction.guild.id, gk.PAYMENT_GCASH_QR_URL)
        if not details or not qr:
            await interaction.response.send_message(
                embed=user_hint(
                    "Payment not set up yet",
                    "Ask a manager to set **GCash** text and QR with **`/config payment gcash_details`** (and QR URL).",
                ),
                ephemeral=True,
            )
            return
        emb = discord.Embed(title="GCash", description=details, color=PRIMARY)
        emb.set_image(url=qr)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @discord.ui.button(label="PayPal", style=discord.ButtonStyle.secondary, custom_id="pay_paypal")
    async def paypal(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                embed=user_hint("Use this in a server", "Open the payment panel from inside your Discord server."), ephemeral=True
            )
            return
        link = await db.get_guild_string_setting(interaction.guild.id, gk.PAYMENT_PAYPAL_LINK)
        qr = await db.get_guild_string_setting(interaction.guild.id, gk.PAYMENT_PAYPAL_QR_URL)
        if not link or not qr:
            await interaction.response.send_message(
                embed=user_hint(
                    "Payment not set up yet",
                    "Ask a manager to set **PayPal** link and QR with **`/config payment`** commands.",
                ),
                ephemeral=True,
            )
            return
        emb = discord.Embed(
            title="PayPal",
            description=f"[PayPal link]({link})",
            color=PRIMARY,
        )
        emb.set_image(url=qr)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @discord.ui.button(label="Ko-fi", style=discord.ButtonStyle.success, custom_id="pay_kofi")
    async def kofi(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                embed=user_hint("Use this in a server", "Open the payment panel from inside your Discord server."), ephemeral=True
            )
            return
        link = await db.get_guild_string_setting(interaction.guild.id, gk.PAYMENT_KOFI_LINK)
        if not link:
            await interaction.response.send_message(
                embed=user_hint(
                    "Payment not set up yet",
                    "Ask a manager to set **Ko-fi** link with **`/config payment kofi_link`**.",
                ),
                ephemeral=True,
            )
            return
        emb = discord.Embed(
            title="Ko-fi",
            description=f"[Ko-fi]({link})",
            color=PRIMARY,
        )
        await interaction.response.send_message(embed=emb, ephemeral=True)


class PaymentCog(commands.Cog, name="PaymentCog"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def run_setup_payment(
        self, interaction: discord.Interaction, ch: discord.TextChannel
    ) -> None:
        """Invoked from `/deploy payment` with a resolved payment channel."""
        if not await is_payment_config_complete(interaction.guild.id):
            await interaction.response.send_message(
                embed=user_hint(
                    "Finish payment settings first",
                    "Run **`/config payment`** subcommands for GCash text/QR, PayPal link/QR, and Ko-fi (see **`/config view`**).",
                ),
                ephemeral=True,
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
