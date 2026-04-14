"""Interactive `/setup` wizard (ephemeral, single-message edits)."""

from __future__ import annotations

from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import guild_keys as gk
from utils.checks import can_manage_server_config
from utils.embeds import info_embed, success_embed, user_hint
from utils.logging_setup import get_logger

log = get_logger("setup_wizard")

TICKET_FLOW: list[tuple[str, str, list[discord.ChannelType]]] = [
    ("**New tickets** — pick a **category**", gk.TICKET_CATEGORY, [discord.ChannelType.category]),
    ("**Noted** orders — category", gk.NOTED_CATEGORY, [discord.ChannelType.category]),
    ("**Processing** — category", gk.PROCESSING_CATEGORY, [discord.ChannelType.category]),
    ("**Done** archive — category", gk.DONE_CATEGORY, [discord.ChannelType.category]),
    ("**Transcript** archive — **text** channel", gk.TRANSCRIPT_CHANNEL, [discord.ChannelType.text]),
    ("**Start here** / panel — **text** channel", gk.START_HERE_CHANNEL, [discord.ChannelType.text]),
]


async def _config_check_summary(guild: discord.Guild) -> str:
    rows = await db.list_guild_settings(guild.id)
    str_rows = await db.list_guild_string_settings(guild.id)
    ok = 0
    warn = 0
    err = 0

    def _role_exists(key: str) -> bool:
        rid = rows.get(key)
        return bool(rid and guild.get_role(int(rid)))

    def _channel_exists(key: str) -> bool:
        cid = rows.get(key)
        return bool(cid and guild.get_channel(int(cid)))

    payment_values = [str_rows.get(k, "").strip() for k in gk.PAYMENT_ALL_KEYS]
    if _channel_exists(gk.PAYMENT_CHANNEL):
        if any(payment_values):
            ok += 1
        else:
            err += 1
    else:
        warn += 1

    if await db.shop_is_open_db():
        if _role_exists(gk.TOS_AGREED_ROLE):
            ok += 1
        else:
            err += 1
    else:
        ok += 1

    btns = await db.list_ticket_buttons(guild.id)
    if btns:
        if _channel_exists(gk.TICKET_CATEGORY):
            ok += 1
        else:
            err += 1
    else:
        warn += 1

    wt = rows.get(gk.WARN_THRESHOLD_KEY)
    if wt is not None:
        if _channel_exists(gk.WARN_LOG_CHANNEL):
            ok += 1
        else:
            err += 1
    else:
        warn += 1

    if _channel_exists(gk.TOS_CHANNEL):
        panel = await db.get_persist_panel("tos")
        if panel:
            ok += 1
        else:
            warn += 1
    else:
        warn += 1

    return f"Config check summary: ✅ {ok} | ⚠️ {warn} | ❌ {err}\nRun **`/config check`** for full details."


class WizardMainView(discord.ui.View):
    def __init__(self, cog: SetupWizardCog) -> None:
        super().__init__(timeout=600.0)
        self.cog = cog

    async def _edit(
        self, interaction: discord.Interaction, title: str, desc: str, view: discord.ui.View | None
    ) -> None:
        await interaction.response.edit_message(
            embed=info_embed(title, desc),
            view=view,
        )

    @discord.ui.button(label="🎫 Tickets & Panels", style=discord.ButtonStyle.primary, row=0)
    async def b_tickets(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._edit(
            interaction,
            "Setup — Tickets & Panels",
            "Step **1** of 6 — pick the category for **new tickets**.",
            TicketStepView(self.cog, 0, {}),
        )

    @discord.ui.button(label="📋 Queue & Orders", style=discord.ButtonStyle.secondary, row=0)
    async def b_queue(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._edit(
            interaction,
            "Setup — Queue",
            "Pick the **queue** channel (order list).",
            QueueStepView(self.cog, 0, {}),
        )

    @discord.ui.button(label="🏪 Shop & TOS", style=discord.ButtonStyle.secondary, row=1)
    async def b_shop(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._edit(
            interaction,
            "Setup — Shop & TOS",
            "Pick the **TOS** text channel.",
            ShopStepView(self.cog, 0, {}),
        )

    @discord.ui.button(label="💳 Payment", style=discord.ButtonStyle.secondary, row=1)
    async def b_pay(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._edit(
            interaction,
            "Setup — Payment",
            "Pick the **payment panel** channel. After this, run **`/deploy payment`** and set GCash/PayPal strings via staff tools if needed.",
            PaymentChView(self.cog),
        )

    @discord.ui.button(label="🔔 Channels & Roles", style=discord.ButtonStyle.secondary, row=2)
    async def b_roles(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._edit(
            interaction,
            "Setup — Staff role",
            "Pick the **staff** role.",
            RolesStepView(self.cog, 0, {}),
        )

    @discord.ui.button(label="🎨 Pricing", style=discord.ButtonStyle.success, row=2)
    async def b_price(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._edit(
            interaction,
            "Setup — Pricing",
            "Use **`/setprice`**, **`/quoteextras`**, **`/setdiscount`**, and **`/setcurrency`** to fill the quote calculator. Run **`/pricelist`** to verify.",
            WizardMainView(self.cog),
        )


class TicketStepView(discord.ui.View):
    def __init__(self, cog: SetupWizardCog, step: int, acc: dict[str, int]) -> None:
        super().__init__(timeout=600.0)
        self.cog = cog
        self.step = step
        self.acc = acc
        title, key, types = TICKET_FLOW[step]
        sel = discord.ui.ChannelSelect(
            custom_id=f"tw_{step}",
            channel_types=types,
            placeholder="Select channel or category",
            min_values=1,
            max_values=1,
        )

        async def cb(interaction: discord.Interaction) -> None:
            raw = interaction.data.get("resolved", {}).get("channels", {})
            if not raw:
                return
            cid = int(next(iter(raw.keys())))
            self.acc[key] = cid
            if self.step + 1 >= len(TICKET_FLOW):
                if not interaction.guild:
                    return
                for k, vid in self.acc.items():
                    await db.set_guild_setting(interaction.guild.id, k, vid)
                await db.delete_wizard_session(interaction.guild.id, interaction.user.id)
                summary = "\n".join(f"• `{k}` → <#{vid}>" for k, vid in self.acc.items())
                health = await _config_check_summary(interaction.guild)
                await interaction.response.edit_message(
                    embed=success_embed(
                        "Tickets & Panels saved",
                        summary[:3400] + "\n\nUse **`/ticketpanel`** to post panel.\n\n" + health,
                    ),
                    view=WizardMainView(self.cog),
                )
                return
            n_title, _, _ = TICKET_FLOW[self.step + 1]
            await interaction.response.edit_message(
                embed=info_embed(
                    f"Setup — Tickets & Panels ({self.step + 2}/6)",
                    n_title,
                ),
                view=TicketStepView(self.cog, self.step + 1, self.acc),
            )

        sel.callback = cb
        self.add_item(sel)


class QueueStepView(discord.ui.View):
    """Queue channel → order notifs → finish (prefix via modal could be added later)."""

    def __init__(self, cog: SetupWizardCog, step: int, acc: dict[str, int]) -> None:
        super().__init__(timeout=600.0)
        self.cog = cog
        self.step = step
        self.acc = acc
        if step == 0:
            sel = discord.ui.ChannelSelect(
                custom_id="q_q",
                channel_types=[discord.ChannelType.text],
                placeholder="Queue channel",
            )

            async def cb(interaction: discord.Interaction) -> None:
                raw = interaction.data.get("resolved", {}).get("channels", {})
                if not raw:
                    return
                cid = int(next(iter(raw.keys())))
                acc[gk.QUEUE_CHANNEL] = cid
                await interaction.response.edit_message(
                    embed=info_embed("Setup — Queue (2/2)", "Pick **order notifications** channel (optional)."),
                    view=QueueStepView(cog, 1, acc),
                )

            sel.callback = cb
            self.add_item(sel)
        else:
            sel = discord.ui.ChannelSelect(
                custom_id="q_n",
                channel_types=[discord.ChannelType.text],
                placeholder="Order notifications channel",
            )

            async def cb2(interaction: discord.Interaction) -> None:
                raw = interaction.data.get("resolved", {}).get("channels", {})
                if not raw:
                    return
                cid = int(next(iter(raw.keys())))
                acc[gk.ORDER_NOTIFS_CHANNEL] = cid
                if interaction.guild:
                    for k, vid in acc.items():
                        await db.set_guild_setting(interaction.guild.id, k, vid)
                await db.delete_wizard_session(interaction.guild.id, interaction.user.id)
                health = await _config_check_summary(interaction.guild)
                await interaction.response.edit_message(
                    embed=success_embed(
                        "Queue saved",
                        "Queue + order notifications stored.\n\n" + health,
                    ),
                    view=WizardMainView(self.cog),
                )

            sel.callback = cb2
            self.add_item(sel)


class ShopStepView(discord.ui.View):
    """TOS channel → TOS role → shop status → commissions open role (4 steps)."""

    FLOW = [
        ("TOS **text** channel", gk.TOS_CHANNEL, [discord.ChannelType.text]),
        ("**TOS agreed** role", "role_tos", None),
        ("**Shop status** embed channel", gk.SHOP_STATUS_CHANNEL, [discord.ChannelType.text]),
        ("**Commissions open** role", "role_open", None),
    ]

    def __init__(self, cog: SetupWizardCog, step: int, acc: dict[str, Any]) -> None:
        super().__init__(timeout=600.0)
        self.cog = cog
        self.step = step
        self.acc = acc
        label, key, ctypes = self.FLOW[step]
        if ctypes:
            sel = discord.ui.ChannelSelect(
                custom_id=f"sh_{step}",
                channel_types=ctypes,
                placeholder=label[:150],
            )

            async def cb(interaction: discord.Interaction) -> None:
                raw = interaction.data.get("resolved", {}).get("channels", {})
                if not raw:
                    return
                cid = int(next(iter(raw.keys())))
                self.acc[key] = cid
                await self._advance(interaction)

            sel.callback = cb
            self.add_item(sel)
        else:
            sel = discord.ui.RoleSelect(
                custom_id=f"sr_{step}",
                placeholder=label[:150],
                min_values=1,
                max_values=1,
            )

            async def cb_r(interaction: discord.Interaction) -> None:
                raw = interaction.data.get("resolved", {}).get("roles", {})
                if not raw:
                    return
                rid = int(next(iter(raw.keys())))
                if key == "role_tos":
                    self.acc[gk.TOS_AGREED_ROLE] = rid
                else:
                    self.acc[gk.COMMISSIONS_OPEN_ROLE] = rid
                await self._advance(interaction)

            sel.callback = cb_r
            self.add_item(sel)

    async def _advance(self, interaction: discord.Interaction) -> None:
        if self.step + 1 >= len(self.FLOW):
            if interaction.guild:
                for k, v in self.acc.items():
                    if isinstance(v, int):
                        await db.set_guild_setting(interaction.guild.id, k, v)
            await db.delete_wizard_session(interaction.guild.id, interaction.user.id)
            health = await _config_check_summary(interaction.guild)
            await interaction.response.edit_message(
                embed=success_embed(
                    "Shop & TOS saved",
                    "Run **`/deploy tos`** and manage shop with **`/shop`**.\n\n" + health,
                ),
                view=WizardMainView(self.cog),
            )
            return
        n_label, n_key, n_ct = self.FLOW[self.step + 1]
        await interaction.response.edit_message(
            embed=info_embed(f"Setup — Shop & TOS ({self.step + 2}/4)", n_label),
            view=ShopStepView(self.cog, self.step + 1, self.acc),
        )


class PaymentChView(discord.ui.View):
    def __init__(self, cog: SetupWizardCog) -> None:
        super().__init__(timeout=300.0)
        self.cog = cog
        sel = discord.ui.ChannelSelect(
            custom_id="pay_ch",
            channel_types=[discord.ChannelType.text],
            placeholder="Payment panel channel",
        )

        async def cb(interaction: discord.Interaction) -> None:
            raw = interaction.data.get("resolved", {}).get("channels", {})
            if not raw or not interaction.guild:
                return
            cid = int(next(iter(raw.keys())))
            await db.set_guild_setting(interaction.guild.id, gk.PAYMENT_CHANNEL, cid)
            health = await _config_check_summary(interaction.guild)
            await interaction.response.edit_message(
                embed=success_embed(
                    "Payment channel saved",
                    f"Panel channel: <#{cid}>. Configure payment fields, then run **`/deploy payment`**.\n\n{health}",
                ),
                view=WizardMainView(self.cog),
            )

        sel.callback = cb
        self.add_item(sel)


class RolesStepView(discord.ui.View):
    """Staff → Boostie → Reseller → PlsVouch → vouches ch → warn log (compact: 3 roles then 2 channels)."""

    def __init__(self, cog: SetupWizardCog, step: int, acc: dict[str, int]) -> None:
        super().__init__(timeout=600.0)
        self.cog = cog
        self.step = step
        self.acc = acc
        role_steps = [
            ("**Staff** role", gk.STAFF_ROLE),
            ("**Boostie** role (quote discount)", gk.BOOSTIE_ROLE),
            ("**Reseller** role", gk.RESELLER_ROLE),
            ("**Please vouch** role", gk.PLEASE_VOUCH_ROLE),
        ]
        ch_steps = [
            ("**Vouches** channel", gk.VOUCHES_CHANNEL),
            ("**Warn log** channel", gk.WARN_LOG_CHANNEL),
        ]
        if step < len(role_steps):
            label, sk = role_steps[step]

            sel = discord.ui.RoleSelect(
                custom_id=f"rs_{step}",
                placeholder=label[:150],
                min_values=1,
                max_values=1,
            )

            async def cb(interaction: discord.Interaction) -> None:
                raw = interaction.data.get("resolved", {}).get("roles", {})
                if not raw:
                    return
                rid = int(next(iter(raw.keys())))
                self.acc[sk] = rid
                await interaction.response.edit_message(
                    embed=info_embed(
                        f"Setup — Roles ({step + 2}/{len(role_steps) + len(ch_steps)})",
                        role_steps[step + 1][0] if step + 1 < len(role_steps) else ch_steps[0][0],
                    ),
                    view=RolesStepView(self.cog, step + 1, self.acc),
                )

            sel.callback = cb
            self.add_item(sel)
        else:
            ci = step - len(role_steps)
            label, sk = ch_steps[ci]
            sel = discord.ui.ChannelSelect(
                custom_id=f"rch_{ci}",
                channel_types=[discord.ChannelType.text],
                placeholder=label[:150],
            )

            async def cb2(interaction: discord.Interaction) -> None:
                raw = interaction.data.get("resolved", {}).get("channels", {})
                if not raw:
                    return
                cid = int(next(iter(raw.keys())))
                self.acc[sk] = cid
                if ci + 1 < len(ch_steps):
                    n_label, _ = ch_steps[ci + 1]
                    await interaction.response.edit_message(
                        embed=info_embed(
                            f"Setup — Channels ({ci + 2}/{len(ch_steps)})",
                            n_label,
                        ),
                        view=RolesStepView(self.cog, step + 1, self.acc),
                    )
                else:
                    if interaction.guild:
                        for k, vid in self.acc.items():
                            await db.set_guild_setting(interaction.guild.id, k, vid)
                    await db.delete_wizard_session(interaction.guild.id, interaction.user.id)
                    health = await _config_check_summary(interaction.guild)
                    await interaction.response.edit_message(
                        embed=success_embed(
                            "Channels & roles saved",
                            "Configuration stored.\n\n" + health,
                        ),
                        view=WizardMainView(self.cog),
                    )

            sel.callback = cb2
            self.add_item(sel)


class SetupWizardCog(commands.Cog, name="SetupWizardCog"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="setup", description="Interactive server configuration wizard")
    @can_manage_server_config()
    async def setup_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        await db.save_wizard_session(
            interaction.guild.id,
            interaction.user.id,
            {"group": "main", "step": 0},
        )
        emb = info_embed(
            "⚙️ Server Setup Wizard",
            "Welcome! Pick a **group** below. Each flow saves to the database when you finish that group.\n"
            "Use **`/config view`** to audit settings.",
        )
        await interaction.response.send_message(
            embed=emb,
            view=WizardMainView(self),
            ephemeral=True,
        )

    @app_commands.command(
        name="setup_resume",
        description="Re-open the setup wizard (session is not restored — start a group again)",
    )
    @can_manage_server_config()
    async def setup_resume_cmd(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            embed=user_hint(
                "Setup",
                "Ephemeral wizard state cannot be restored after you close it. Run **`/setup`** again and pick a group.",
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SetupWizardCog(bot))
