"""Roblox utilities: tax, gamepass scan, group funds, stocks."""

from __future__ import annotations

import json
import math
import re
from typing import Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
from utils.checks import is_staff
from utils.embeds import PRIMARY, error_embed, info_embed, success_embed

ELIGIBILITY_MIN_ROBUX = 1000


def _roblox_cookie_headers() -> dict[str, str]:
    c = config.ROBLOX_COOKIE.strip()
    if not c.startswith(".ROBLOSECURITY="):
        c = f".ROBLOSECURITY={c}"
    return {"Cookie": c}


class RobloxCog(commands.Cog, name="RobloxCog"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._session: aiohttp.ClientSession | None = None

    async def cog_load(self) -> None:
        self._session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    def _http(self) -> aiohttp.ClientSession:
        if not self._session:
            self._session = aiohttp.ClientSession()
        return self._session

    @app_commands.command(name="tax", description="Game pass price to receive an exact Robux amount after 30% fee")
    @app_commands.describe(robux_amount="Robux you want to receive after tax")
    async def tax_cmd(self, interaction: discord.Interaction, robux_amount: app_commands.Range[int, 1, 100000000]) -> None:
        fee = 0.30
        required = math.ceil(robux_amount / (1 - fee))
        taken = required - robux_amount
        emb = info_embed(
            "Roblox tax (30% marketplace fee)",
            f"**Desired receive:** {robux_amount} Robux\n"
            f"**Required listing price:** {required} Robux\n"
            f"**Marketplace fee (~30%):** {taken} Robux\n"
            f"**You receive:** {robux_amount} Robux (if priced at {required})",
        )
        await interaction.response.send_message(embed=emb)

    @app_commands.command(name="taxreverse", description="Robux you receive after 30% fee from a listing price")
    @app_commands.describe(listing_price="Game pass price in Robux")
    async def taxreverse(
        self,
        interaction: discord.Interaction,
        listing_price: app_commands.Range[int, 1, 100000000],
    ) -> None:
        fee = 0.30
        receive = math.floor(listing_price * (1 - fee))
        taken = listing_price - receive
        emb = info_embed(
            "Roblox tax (reverse)",
            f"**Listing price:** {listing_price} Robux\n"
            f"**Fee taken (~30%):** {taken} Robux\n"
            f"**Seller receives:** {receive} Robux",
        )
        await interaction.response.send_message(embed=emb)

    @staticmethod
    def _parse_gamepass_id(url: str) -> int | None:
        url = url.strip()
        m = re.search(r"game-pass/(\d+)", url, re.I) or re.search(r"catalog/(\d+)", url, re.I)
        if m:
            return int(m.group(1))
        m = re.search(r"/(\d{6,})", url)
        if m:
            return int(m.group(1))
        return None

    @app_commands.command(name="scanpass", description="Verify a game pass price (staff)")
    @app_commands.describe(gamepass_url="Game pass URL", expected_robux="Expected price in Robux")
    @is_staff()
    async def scanpass(
        self,
        interaction: discord.Interaction,
        gamepass_url: str,
        expected_robux: int,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        gid = self._parse_gamepass_id(gamepass_url)
        if not gid:
            await interaction.followup.send(
                embed=error_embed("Invalid URL", "Could not parse a game pass ID."), ephemeral=True
            )
            return
        sess = self._http()
        url = f"https://apis.roblox.com/game-passes/v1/game-passes/{gid}/product-info"
        try:
            async with sess.get(url) as resp:
                data = await resp.json(content_type=None)
                if resp.status != 200:
                    await interaction.followup.send(
                        embed=error_embed("API error", str(data)[:1000]), ephemeral=True
                    )
                    return
        except aiohttp.ClientError as e:
            await interaction.followup.send(
                embed=error_embed("Network error", str(e)), ephemeral=True
            )
            return

        name = data.get("Name") or "Unknown"
        creator = data.get("Creator", {})
        creator_name = creator.get("Name") if isinstance(creator, dict) else str(creator)
        price = int(data.get("PriceInRobux") or data.get("priceInRobux") or 0)
        product_id = data.get("ProductId") or data.get("productId")
        match_ok = price == expected_robux

        regional = False
        if product_id:
            sub_url = f"https://economy.roblox.com/v1/purchases/products/{product_id}/subscriptions"
            try:
                async with sess.get(sub_url) as sresp:
                    if sresp.status == 200:
                        sdata = await sresp.json(content_type=None)
                        if isinstance(sdata, list) and len(sdata) > 0:
                            regional = True
                        elif isinstance(sdata, dict) and sdata.get("data"):
                            regional = True
            except aiohttp.ClientError:
                pass

        emb = discord.Embed(title="Game pass scan", color=PRIMARY)
        emb.add_field(name="Name", value=str(name)[:1024], inline=False)
        emb.add_field(name="Creator", value=str(creator_name)[:256], inline=True)
        emb.add_field(name="Listed price", value=str(price), inline=True)
        emb.add_field(name="Expected", value=str(expected_robux), inline=True)
        emb.add_field(
            name="Match",
            value="✅ Match" if match_ok else "❌ Mismatch",
            inline=False,
        )
        emb.add_field(
            name="Regional pricing",
            value="⚠️ Regional pricing possible" if regional else "No flag from API",
            inline=False,
        )
        emb.add_field(name="Link", value=gamepass_url[:1024], inline=False)
        await interaction.followup.send(embed=emb, ephemeral=True)

    @app_commands.command(name="eligible", description="Check group Robux funds (staff)")
    @is_staff()
    async def eligible(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        sess = self._http()
        gid = config.ROBLOX_GROUP_ID
        headers = _roblox_cookie_headers()
        cur_url = f"https://economy.roblox.com/v1/groups/{gid}/currency"
        try:
            async with sess.get(cur_url, headers=headers) as resp:
                raw = await resp.text()
                if resp.status == 401 or resp.status == 403:
                    await interaction.followup.send(
                        embed=error_embed(
                            "Auth failed",
                            "Update `ROBLOX_COOKIE` in your environment — cookie may be expired.",
                        ),
                        ephemeral=True,
                    )
                    return
                if resp.status != 200:
                    await interaction.followup.send(
                        embed=error_embed("API error", raw[:500]), ephemeral=True
                    )
                    return
                try:
                    cj = json.loads(raw)
                except json.JSONDecodeError:
                    await interaction.followup.send(
                        embed=error_embed("Bad response", raw[:300]), ephemeral=True
                    )
                    return
                current = int(cj.get("robux") or 0)
        except aiohttp.ClientError as e:
            await interaction.followup.send(
                embed=error_embed("Network", str(e)), ephemeral=True
            )
            return

        pend = 0
        sum_url = f"https://economy.roblox.com/v1/groups/{gid}/revenue/summary/month"
        try:
            async with sess.get(sum_url, headers=headers) as resp2:
                if resp2.status == 200:
                    sj = await resp2.json(content_type=None)
                    pend = int(sj.get("pendingRobux") or sj.get("pending_robux") or 0)
        except (aiohttp.ClientError, TypeError, ValueError):
            pass

        total = current + pend
        verdict = "✅ Eligible" if total >= ELIGIBILITY_MIN_ROBUX else "❌ Below threshold"
        emb = info_embed(
            "Group funds",
            f"**Current:** {current} Robux\n**Pending:** {pend} Robux\n**Total (approx):** {total} Robux\n"
            f"**Threshold:** {ELIGIBILITY_MIN_ROBUX}\n**Verdict:** {verdict}",
        )
        await interaction.followup.send(embed=emb, ephemeral=True)

    @app_commands.command(name="stocks", description="Show shop stock levels")
    async def stocks_cmd(self, interaction: discord.Interaction) -> None:
        data = db.load_stocks()
        if not data:
            await interaction.response.send_message(
                embed=info_embed("Stocks", "No items yet."), ephemeral=True
            )
            return
        emb = discord.Embed(title="Shop stock", color=PRIMARY)
        for name, meta in data.items():
            if not isinstance(meta, dict):
                continue
            stock = int(meta.get("stock", 0))
            price = meta.get("price", "?")
            desc = str(meta.get("description", ""))[:200]
            if stock <= 0:
                ind = "🔴 Out of Stock"
            elif stock <= 3:
                ind = "🟡 Low Stock"
            else:
                ind = "🟢 In Stock"
            emb.add_field(
                name=name,
                value=f"{ind}\nPrice: **{price}** Robux\nStock: **{stock}**\n{desc}",
                inline=False,
            )
        await interaction.response.send_message(embed=emb)

    def _stock_mutate(self, item: str, delta: int | None, absolute: int | None) -> dict[str, Any]:
        data = db.load_stocks()
        if item not in data:
            raise KeyError("item")
        cur = int(data[item].get("stock", 0))
        if absolute is not None:
            data[item]["stock"] = max(0, absolute)
        elif delta is not None:
            data[item]["stock"] = max(0, cur + delta)
        db.save_stocks(data)
        return data

    @app_commands.command(name="addstock", description="Add stock to an item (staff)")
    @app_commands.describe(item="Item name", amount="Amount to add")
    @is_staff()
    async def addstock(
        self,
        interaction: discord.Interaction,
        item: str,
        amount: app_commands.Range[int, 1, 1000000],
    ) -> None:
        try:
            self._stock_mutate(item, amount, None)
        except KeyError:
            await interaction.response.send_message(
                embed=error_embed("Error", "Unknown item."), ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=success_embed("Stock", f"Added {amount} to `{item}`."), ephemeral=True
        )

    @app_commands.command(name="removestock", description="Remove stock from an item (staff)")
    @app_commands.describe(item="Item name", amount="Amount to remove")
    @is_staff()
    async def removestock(
        self,
        interaction: discord.Interaction,
        item: str,
        amount: app_commands.Range[int, 1, 1000000],
    ) -> None:
        try:
            self._stock_mutate(item, -amount, None)
        except KeyError:
            await interaction.response.send_message(
                embed=error_embed("Error", "Unknown item."), ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=success_embed("Stock", f"Removed {amount} from `{item}`."), ephemeral=True
        )

    @app_commands.command(name="setstock", description="Set absolute stock for an item (staff)")
    @app_commands.describe(item="Item name", amount="New stock count")
    @is_staff()
    async def setstock(
        self,
        interaction: discord.Interaction,
        item: str,
        amount: app_commands.Range[int, 0, 1000000],
    ) -> None:
        try:
            self._stock_mutate(item, None, amount)
        except KeyError:
            await interaction.response.send_message(
                embed=error_embed("Error", "Unknown item."), ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=success_embed("Stock", f"`{item}` stock set to {amount}."), ephemeral=True
        )

    @app_commands.command(name="additem", description="Add a new item to stocks.json (staff)")
    @app_commands.describe(
        item="Item name",
        price="Price in Robux",
        description="Description",
        initial_stock="Starting stock",
    )
    @is_staff()
    async def additem(
        self,
        interaction: discord.Interaction,
        item: str,
        price: int,
        description: str,
        initial_stock: app_commands.Range[int, 0, 1000000],
    ) -> None:
        data = db.load_stocks()
        data[item] = {"stock": initial_stock, "price": price, "description": description}
        db.save_stocks(data)
        await interaction.response.send_message(
            embed=success_embed("Item added", item), ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RobloxCog(bot))
