"""Vouch tracking and PlsVouch auto-remove."""

from __future__ import annotations

import secrets

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import guild_keys as gk
from utils.checks import is_staff
from utils.embeds import PRIMARY, info_embed, success_embed


class LeaveReviewView(discord.ui.View):
    """# CHANGED: button path for /review flow (cursor-prompt.md §6)."""

    def __init__(self, cog: "VouchCog", order_id: str) -> None:
        super().__init__(timeout=3600.0)
        self.cog = cog
        self.order_id = order_id

    @discord.ui.button(label="Leave a Review", style=discord.ButtonStyle.success, row=0)
    async def leave_review_btn(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        view = ReviewRatingsView(self.cog, self.order_id)
        await interaction.response.send_message(
            embed=info_embed(
                "Review form (step 1/3)",
                "Rate each item from **1** to **5**:\n"
                "• Artwork quality\n"
                "• Communication\n"
                "• Turnaround time\n"
                "• Process smoothness",
            ),
            view=view,
            ephemeral=True,
        )


class VouchPages(discord.ui.View):
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


class VouchCog(commands.Cog, name="VouchCog"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _staff_order_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        member = getattr(interaction.namespace, "member", None)
        if not isinstance(member, discord.Member):
            return []
        rows = await db.list_orders_for_client(member.id, limit=50)
        needle = str(current or "").strip().lower()
        out: list[app_commands.Choice[str]] = []
        for r in rows:
            oid = str(r.get("order_id") or "")
            if not oid:
                continue
            status = str(r.get("status") or "unknown")
            item = str(r.get("item") or "")
            mop = str(r.get("mop") or "")
            price = str(r.get("price") or "")
            label = f"{oid} · {status} · {item[:26]} · {price[:10]} {mop[:10]}".strip()
            hay = f"{oid} {status} {item} {mop} {price}".lower()
            if needle and needle not in hay:
                continue
            out.append(app_commands.Choice(name=label[:100], value=oid))
            if len(out) >= 25:
                break
        return out

    async def _review_order_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if not interaction.guild:
            return []
        rows = await db.list_reviewable_order_tags_for_client(
            interaction.guild.id, interaction.user.id, limit=50
        )
        needle = str(current or "").strip().lower()
        out: list[app_commands.Choice[str]] = []
        for r in rows:
            oid = str(r.get("order_id") or "")
            if not oid:
                continue
            source = str(r.get("source") or "order")
            ch_name = "no-ticket"
            ch_id = r.get("ticket_channel_id")
            if ch_id:
                ch = interaction.guild.get_channel(int(ch_id))
                if ch:
                    ch_name = ch.name
            source_label = "fallback-tag" if source == "fallback" else "registered-order"
            hay = f"{oid} {ch_name} {source_label}".lower()
            if needle and needle not in hay:
                continue
            out.append(
                app_commands.Choice(
                    name=f"{oid} · {ch_name} · {source_label}"[:100],
                    value=oid,
                )
            )
            if len(out) >= 25:
                break
        return out

    @app_commands.command(name="vouch", description="Send vouch and unlock review form")
    @app_commands.describe(
        staff="Staff who handled order (optional)",
        message="Your vouch message",
        proof="Optional proof image",
    )
    async def vouch_cmd(
        self,
        interaction: discord.Interaction,
        message: str,
        staff: discord.Member | None = None,
        proof: discord.Attachment | None = None,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Guild only command.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        # CHANGED: legacy vouches-channel listener removed; only /vouch and /vouchstaff.
        pvr = await db.get_guild_setting(interaction.guild.id, gk.PLEASE_VOUCH_ROLE)
        pvr_role = interaction.guild.get_role(int(pvr)) if pvr else None
        if not pvr_role or pvr_role not in interaction.user.roles:
            await interaction.followup.send(
                embed=info_embed(
                    "Heads up",
                    "You need `Please vouch` role. If you believe this is wrong, contact staff.",
                ),
                ephemeral=True,
            )
            return
        cur_ch_id = interaction.channel.id if isinstance(interaction.channel, discord.TextChannel) else None
        row = await db.resolve_order_for_client_vouch(interaction.guild.id, interaction.user.id, cur_ch_id)
        if not row or not row.get("order_id"):
            await interaction.followup.send(
                embed=info_embed(
                    "No registered order",
                    "This ticket has no registered order — ask staff to confirm payment first.",
                ),
                ephemeral=True,
            )
            return
        order_id = str(row["order_id"])
        await db.insert_vouch(interaction.user.id, order_id, message)
        vcid = await db.get_guild_setting(interaction.guild.id, gk.VOUCHES_CHANNEL)
        vch = interaction.guild.get_channel(int(vcid)) if vcid else None
        owner_mention = (
            f"<@{interaction.guild.owner_id}>"
            if interaction.guild.owner_id
            else "Owner not found"
        )
        staff_mention = staff.mention if staff else "Not provided"
        emb = discord.Embed(
            title="⭐ New vouch",
            description=message[:3000],
            color=PRIMARY,
        )
        emb.add_field(name="Client", value=interaction.user.mention, inline=False)
        emb.add_field(name="Order ID", value=f"`{order_id}`", inline=True)
        emb.add_field(name="Staff", value=staff_mention, inline=True)
        if proof and (proof.content_type or "").startswith("image/"):
            emb.set_image(url=proof.url)
        warn_lines: list[str] = []
        if isinstance(vch, discord.TextChannel):
            try:
                await vch.send(
                    content=f"{owner_mention} {staff.mention if staff else ''}".strip(),
                    embed=emb,
                )
            except discord.Forbidden:
                warn_lines.append(
                    "Could not post to vouches channel — bot lacks permission (tell an admin)."
                )
        elif vcid:
            warn_lines.append("Vouches channel missing or invalid — map in `/setup` / `/config`.")
        fpr = await db.get_guild_setting(interaction.guild.id, gk.FEEDBACK_PENDING_ROLE)
        fpr_role = interaction.guild.get_role(int(fpr)) if fpr else None
        if fpr_role and fpr_role not in interaction.user.roles:
            try:
                await interaction.user.add_roles(
                    fpr_role, reason="Optional cosmetic after vouch"
                )
            except discord.Forbidden:
                warn_lines.append(
                    "Could not assign Feedback pending role — move bot role higher in Server Settings."
                )
        try:
            await interaction.user.send(
                "Thanks for vouching. You can use `/review` or the **Leave a Review** button in your ticket."
            )
        except discord.Forbidden:
            pass
        try:
            from cogs.loyalty_cards import apply_vouch_to_loyalty_card

            await apply_vouch_to_loyalty_card(interaction.guild, interaction.user.id)
        except Exception:
            pass
        body = (
            f"Posted for order `{order_id}`. You can now leave a review with `/review`.\n"
            + ("\n".join(warn_lines) if warn_lines else "")
        )
        await interaction.followup.send(
            embed=success_embed("Vouch sent", body[:3800]),
            ephemeral=True,
        )
        tcid = row.get("ticket_channel_id")
        post_ch = None
        if tcid:
            c = interaction.guild.get_channel(int(tcid))
            if isinstance(c, discord.TextChannel):
                post_ch = c
        if post_ch:
            try:
                await post_ch.send(
                    content=f"{interaction.user.mention} — thanks for vouching! "
                    "You can now leave a review with `/review` or use the button below.",
                    view=LeaveReviewView(self, order_id),
                )
            except discord.Forbidden:
                pass

    @app_commands.command(name="vouchstaff", description="Manually log vouch (staff)")
    @app_commands.describe(member="Client", order_id="Related order ID", message="Vouch text")
    @app_commands.autocomplete(order_id=_staff_order_autocomplete)
    @is_staff()
    async def vouch_staff_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        order_id: str,
        message: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        await db.insert_vouch(member.id, order_id, message)
        try:
            from cogs.loyalty_cards import apply_vouch_to_loyalty_card

            await apply_vouch_to_loyalty_card(interaction.guild, member.id)
        except Exception:
            pass
        pvr = await db.get_guild_setting(interaction.guild.id, gk.PLEASE_VOUCH_ROLE)
        role = interaction.guild.get_role(int(pvr)) if pvr else None
        if role and role in member.roles:
            try:
                await member.remove_roles(role)
            except discord.Forbidden:
                pass
        elif role:
            try:
                await member.add_roles(role)
                await member.remove_roles(role)
            except discord.Forbidden:
                pass
        vcid = await db.get_guild_setting(interaction.guild.id, gk.VOUCHES_CHANNEL)
        ch = interaction.guild.get_channel(int(vcid)) if vcid else None
        emb = discord.Embed(
            title="⭐ Vouch",
            description=f"**{member.display_name}**\n{message}\nOrder: `{order_id}`",
            color=PRIMARY,
        )
        if isinstance(ch, discord.TextChannel):
            await ch.send(embed=emb)
        await interaction.followup.send(
            embed=success_embed("Logged", "Vouch posted."), ephemeral=True
        )

    async def _post_review_and_rewards(
        self,
        interaction: discord.Interaction,
        *,
        order_id: str,
        ratings: dict[str, int],
        enjoyed_most: str,
        improvements: str,
        commission_again: str,
        recommend_friend: str,
        testimonial_consent: str,
    ) -> tuple[bool, str]:
        if not interaction.guild:
            return False, "Guild only command."
        if await db.has_commission_review(interaction.guild.id, interaction.user.id, order_id):
            return False, "You've already submitted a review for this order."
        discount_code = f"BB-{order_id}-{secrets.token_hex(2).upper()}"
        await db.insert_commission_review(
            guild_id=interaction.guild.id,
            reviewer_id=interaction.user.id,
            order_id=order_id,
            overall_quality=ratings["overall_quality"],
            communication=ratings["communication"],
            turnaround=ratings["turnaround"],
            process_smoothness=ratings["process_smoothness"],
            enjoyed_most=enjoyed_most,
            improvements=improvements,
            commission_again=commission_again,
            recommend_friend=recommend_friend,
            testimonial_consent=testimonial_consent,
            discount_code=discount_code,
        )
        fcid = await db.get_guild_setting(interaction.guild.id, gk.FEEDBACK_CHANNEL)
        fch = interaction.guild.get_channel(int(fcid)) if fcid else None
        emb = discord.Embed(title="New client review", color=PRIMARY)
        emb.add_field(name="Client", value=interaction.user.mention, inline=False)
        emb.add_field(name="Order ID", value=f"`{order_id}`", inline=True)
        emb.add_field(name="Overall quality", value=str(ratings["overall_quality"]), inline=True)
        emb.add_field(name="Communication", value=str(ratings["communication"]), inline=True)
        emb.add_field(name="Turnaround", value=str(ratings["turnaround"]), inline=True)
        emb.add_field(
            name="Process smoothness", value=str(ratings["process_smoothness"]), inline=True
        )
        emb.add_field(name="Enjoyed most", value=enjoyed_most[:1024] or "—", inline=False)
        emb.add_field(name="Could improve", value=improvements[:1024] or "—", inline=False)
        emb.add_field(name="Commission again?", value=commission_again, inline=True)
        emb.add_field(name="Recommend friend?", value=recommend_friend, inline=True)
        emb.add_field(name="Testimonial consent", value=testimonial_consent, inline=False)
        if isinstance(fch, discord.TextChannel):
            await fch.send(embed=emb)

        pending_id = await db.get_guild_setting(interaction.guild.id, gk.FEEDBACK_PENDING_ROLE)
        reward_id = await db.get_guild_setting(interaction.guild.id, gk.REVIEW_REWARD_ROLE)
        pending_role = interaction.guild.get_role(int(pending_id)) if pending_id else None
        reward_role = interaction.guild.get_role(int(reward_id)) if reward_id else None
        if pending_role and pending_role in interaction.user.roles:
            try:
                await interaction.user.remove_roles(
                    pending_role, reason="Review submitted for order"
                )
            except discord.Forbidden:
                pass
        if reward_role and reward_role not in interaction.user.roles:
            try:
                await interaction.user.add_roles(reward_role, reason="Review reward")
            except discord.Forbidden:
                pass
        try:
            await interaction.user.send(
                "Thanks for feedback! Here your exclusive discount code: "
                f"`{discount_code}`\nUse on next commission."
            )
        except discord.Forbidden:
            pass
        return True, discount_code

    @app_commands.command(name="review", description="Submit private commission review")
    @app_commands.describe(order_id="Order ID to review")
    @app_commands.autocomplete(order_id=_review_order_autocomplete)
    async def review_cmd(self, interaction: discord.Interaction, order_id: str) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Guild only command.", ephemeral=True)
            return
        # CHANGED: gate with vouch + DB row; not Feedback-pending role (cursor-prompt.md §6).
        row = await db.get_order(order_id)
        if not row or int(row.get("client_id") or 0) != interaction.user.id:
            await interaction.response.send_message(
                embed=info_embed(
                    "Cannot review",
                    "Order not found for your account. Pick an order from the list.",
                ),
                ephemeral=True,
            )
            return
        if int(row.get("review_submitted") or 0) != 0:
            await interaction.response.send_message(
                "You've already submitted a review for this order.",
                ephemeral=True,
            )
            return
        if not await db.has_vouch_for_order(interaction.user.id, order_id):
            await interaction.response.send_message(
                "You haven't vouched for this order yet.",
                ephemeral=True,
            )
            return
        if await db.has_commission_review(interaction.guild.id, interaction.user.id, order_id):
            await interaction.response.send_message(
                "You've already submitted a review for this order.",
                ephemeral=True,
            )
            return
        view = ReviewRatingsView(self, order_id)
        await interaction.response.send_message(
            embed=info_embed(
                "Review form (step 1/3)",
                "Rate each item from **1** to **5**:\n"
                "• Artwork quality\n"
                "• Communication\n"
                "• Turnaround time\n"
                "• Process smoothness",
            ),
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name="vouches", description="List vouches for a member")
    @app_commands.describe(member="Member")
    async def vouches_list(self, interaction: discord.Interaction, member: discord.Member) -> None:
        rows = await db.list_vouches_for_user(member.id)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed("Vouches", "No vouches found."), ephemeral=True
            )
            return
        pages: list[discord.Embed] = []
        chunk = 5
        for i in range(0, len(rows), chunk):
            part = rows[i : i + chunk]
            lines = []
            for r in part:
                lines.append(
                    f"**#{r['vouch_id']}** — {r['created_at']}\n{r['message'][:500]}"
                )
            pages.append(
                discord.Embed(
                    title=f"Vouches for {member.display_name}",
                    description="\n\n".join(lines),
                    color=PRIMARY,
                )
            )
        v = VouchPages(interaction.user.id, pages)
        await interaction.response.send_message(embed=pages[0], view=v, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VouchCog(bot))


def _num_opts() -> list[discord.SelectOption]:
    labels = [
        ("1", "1"),
        ("2", "2"),
        ("3", "3"),
        ("4", "4"),
        ("5", "5"),
    ]
    return [discord.SelectOption(label=a, value=b) for a, b in labels]


class _NumSelect(discord.ui.Select):
    def __init__(self, key: str, label: str) -> None:
        super().__init__(placeholder=label, min_values=1, max_values=1, options=_num_opts())
        self.key = key

    async def callback(self, interaction: discord.Interaction) -> None:
        parent = self.view
        if not isinstance(parent, ReviewRatingsView):
            return
        parent.values[self.key] = int(self.values[0])
        await interaction.response.defer()


class ReviewRatingsView(discord.ui.View):
    def __init__(self, cog: VouchCog, order_id: str) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.order_id = order_id
        self.values: dict[str, int] = {}
        self.add_item(_NumSelect("overall_quality", "Quality of finished artwork"))
        self.add_item(_NumSelect("communication", "Communication during process"))
        self.add_item(_NumSelect("turnaround", "Satisfaction with turnaround time"))
        self.add_item(_NumSelect("process_smoothness", "How smooth commission process was"))

    @discord.ui.button(label="Next: comments", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        needed = {"overall_quality", "communication", "turnaround", "process_smoothness"}
        if not needed.issubset(self.values):
            await interaction.response.send_message(
                "Please answer all 4 ratings first.", ephemeral=True
            )
            return
        await interaction.response.send_modal(
            ReviewTextModal(self.cog, self.order_id, dict(self.values))
        )


class ReviewTextModal(discord.ui.Modal, title="Review form (step 2/3)"):
    enjoyed = discord.ui.TextInput(
        label="What did you enjoy most about experience?",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1200,
        placeholder="Feel free to share anything positive that stood out.",
    )
    improve = discord.ui.TextInput(
        label="Anything that could be improved?",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1200,
        placeholder="Honest feedback welcome. Helps improve future commissions.",
    )

    def __init__(self, cog: VouchCog, order_id: str, ratings: dict[str, int]) -> None:
        super().__init__()
        self.cog = cog
        self.order_id = order_id
        self.ratings = ratings

    async def on_submit(self, interaction: discord.Interaction) -> None:
        view = ReviewFinalView(
            self.cog,
            self.order_id,
            self.ratings,
            str(self.enjoyed),
            str(self.improve),
        )
        await interaction.response.send_message(
            embed=info_embed(
                "Review form (step 3/3)",
                "Select final responses, then press **Submit review**.",
            ),
            view=view,
            ephemeral=True,
        )


class _ChoiceSelect(discord.ui.Select):
    def __init__(self, key: str, placeholder: str, options: list[discord.SelectOption]) -> None:
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)
        self.key = key

    async def callback(self, interaction: discord.Interaction) -> None:
        parent = self.view
        if not isinstance(parent, ReviewFinalView):
            return
        parent.values[self.key] = self.values[0]
        await interaction.response.defer()


class ReviewFinalView(discord.ui.View):
    def __init__(
        self,
        cog: VouchCog,
        order_id: str,
        ratings: dict[str, int],
        enjoyed_most: str,
        improvements: str,
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.order_id = order_id
        self.ratings = ratings
        self.enjoyed_most = enjoyed_most
        self.improvements = improvements
        self.values: dict[str, str] = {}
        self.add_item(
            _ChoiceSelect(
                "commission_again",
                "Would you commission me again?",
                [
                    discord.SelectOption(label="Yes, definitely", value="Yes, definitely"),
                    discord.SelectOption(label="Yes, probably", value="Yes, probably"),
                    discord.SelectOption(label="Not sure", value="Not sure"),
                    discord.SelectOption(label="Probably not", value="Probably not"),
                    discord.SelectOption(label="No", value="No"),
                ],
            )
        )
        self.add_item(
            _ChoiceSelect(
                "recommend_friend",
                "Would you recommend me to friend?",
                [
                    discord.SelectOption(label="Yes", value="Yes"),
                    discord.SelectOption(label="Maybe", value="Maybe"),
                    discord.SelectOption(label="No", value="No"),
                ],
            )
        )
        self.add_item(
            _ChoiceSelect(
                "testimonial_consent",
                "May I share your feedback as testimonial?",
                [
                    discord.SelectOption(
                        label="Yes, share with my name",
                        value="Yes, share with my name",
                    ),
                    discord.SelectOption(
                        label="Yes, share anonymously",
                        value="Yes, share anonymously",
                    ),
                    discord.SelectOption(
                        label="No, keep it private",
                        value="No, keep it private",
                    ),
                ],
            )
        )

    @discord.ui.button(label="Submit review", style=discord.ButtonStyle.success)
    async def submit_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        needed = {"commission_again", "recommend_friend", "testimonial_consent"}
        if not needed.issubset(self.values):
            await interaction.response.send_message(
                "Please answer all dropdown questions first.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        ok, code = await self.cog._post_review_and_rewards(
            interaction,
            order_id=self.order_id,
            ratings=self.ratings,
            enjoyed_most=self.enjoyed_most,
            improvements=self.improvements,
            commission_again=self.values["commission_again"],
            recommend_friend=self.values["recommend_friend"],
            testimonial_consent=self.values["testimonial_consent"],
        )
        if not ok:
            await interaction.followup.send(code, ephemeral=True)
            return
        await interaction.followup.send(
            embed=success_embed(
                "Review submitted",
                f"Thanks for feedback. Discount code sent in DM: `{code}`",
            ),
            ephemeral=True,
        )
