"""
Admin Panel cog — prefix command that opens the admin panel UI.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from discord.ext import commands

from utils.checks import has_admin_panel_role
from utils.embeds import info_embed
from views.admin_panel import AdminPanelView

if TYPE_CHECKING:
    from bot import NJRPBot

logger = logging.getLogger(__name__)


class AdminPanel(commands.Cog):
    """Administrative panel with member, command, and server management."""

    def __init__(self, bot: NJRPBot) -> None:
        self.bot = bot

    @commands.command(name="adminpanel", aliases=["admin panel"])
    @has_admin_panel_role()
    async def admin_panel(self, ctx: commands.Context) -> None:
        """Open the admin panel."""
        embed = info_embed(
            "NJRP Admin Panel",
            "Select a section below to manage the server.",
        )
        embed.set_footer(text=f"Requested by {ctx.author}")
        await ctx.send(embed=embed, view=AdminPanelView(self.bot))


async def setup(bot: NJRPBot) -> None:
    await bot.add_cog(AdminPanel(bot))
