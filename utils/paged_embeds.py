"""Button navigation for multi-page embed messages."""

from __future__ import annotations

import discord


class PagedEmbedView(discord.ui.View):
    """Previous / Next buttons to cycle embed pages (only the command invoker can use)."""

    def __init__(
        self,
        pages: list[discord.Embed],
        user_id: int,
        *,
        timeout: float = 600.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.pages = pages
        self._i = 0
        self._user_id = user_id
        n = len(pages)
        for idx, emb in enumerate(pages):
            base = emb.footer.text if emb.footer and emb.footer.text else ""
            suffix = f"Page {idx + 1}/{n}"
            emb.set_footer(text=f"{base} · {suffix}" if base else suffix)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._user_id:
            await interaction.response.send_message(
                "These buttons are only for whoever ran the command.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, row=0)
    async def prev_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self._i = (self._i - 1) % len(self.pages)
        await interaction.response.edit_message(
            embed=self.pages[self._i], view=self
        )

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=0)
    async def next_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self._i = (self._i + 1) % len(self.pages)
        await interaction.response.edit_message(
            embed=self.pages[self._i], view=self
        )
