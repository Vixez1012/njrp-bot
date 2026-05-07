"""
MyInfo cog — prefix command for users to view their own info.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from utils.embeds import primary_embed

if TYPE_CHECKING:
    from bot import NJRPBot

logger = logging.getLogger(__name__)


class MyInfo(commands.Cog):
    """Allows users to view their own profile information."""

    def __init__(self, bot: NJRPBot) -> None:
        self.bot = bot

    @commands.command(name="myinfo")
    async def my_info(self, ctx: commands.Context) -> None:
        """View your Discord and Roblox information."""
        member = ctx.author
        if not isinstance(member, discord.Member):
            return

        db = self.bot.db
        linked = await db.get_linked_account(member.id)
        flags = await db.get_flags(member.id)
        infraction_count = await db.get_infraction_count(member.id)
        is_bl = await db.is_blacklisted(member.id)

        embed = primary_embed(f"Your Info — {member.display_name}")
        embed.set_thumbnail(url=member.display_avatar.url)

        # Discord info
        embed.add_field(name="Username", value=str(member), inline=True)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(
            name="Account Created",
            value=discord.utils.format_dt(member.created_at, style="R"),
            inline=True,
        )
        embed.add_field(
            name="Joined Server",
            value=discord.utils.format_dt(member.joined_at, style="R") if member.joined_at else "Unknown",
            inline=True,
        )

        # Roblox info
        if linked:
            embed.add_field(name="Roblox Username", value=linked["roblox_name"], inline=True)
            embed.add_field(name="Roblox ID", value=str(linked["roblox_id"]), inline=True)
        else:
            embed.add_field(
                name="Roblox Account",
                value="Your Roblox account is not linked.",
                inline=False,
            )

        # Flags
        flag_text = ", ".join(f["flag_text"] for f in flags) if flags else "None"
        embed.add_field(name="Flags", value=flag_text, inline=False)

        # Infractions & Blacklist
        embed.add_field(name="Infraction Count", value=str(infraction_count), inline=True)
        embed.add_field(name="Blacklisted", value="Yes" if is_bl else "No", inline=True)

        await ctx.send(embed=embed)


async def setup(bot: NJRPBot) -> None:
    await bot.add_cog(MyInfo(bot))
