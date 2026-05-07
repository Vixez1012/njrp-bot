"""
Infraction system cog.

Prefix command: infract @user <punishment> <reason>
Logs infractions, sends to a log channel, and triggers ERLC permission
removal for certain punishment types.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from config.settings import (
    INFRACTION_LOG_CHANNEL_ID,
    VALID_PUNISHMENTS,
    ERLC_REMOVAL_PUNISHMENTS,
)
from utils.checks import has_infraction_role
from utils.embeds import success_embed, error_embed, primary_embed
from utils.erlc_api import ERLCApi

if TYPE_CHECKING:
    from bot import NJRPBot

logger = logging.getLogger(__name__)


class Infractions(commands.Cog):
    """Infraction management system."""

    def __init__(self, bot: NJRPBot) -> None:
        self.bot = bot
        self.erlc = ERLCApi()

    @commands.command(name="infract")
    @has_infraction_role()
    async def infract(
        self,
        ctx: commands.Context,
        user: discord.Member,
        punishment: str,
        *,
        reason: str,
    ) -> None:
        """Issue an infraction to a member.

        Usage: !infract @user <punishment> <reason>
        Valid punishments: Warning, Strike, Suspension, Termination,
        Blacklist, Under Investigation, Retirement
        """
        # Normalize punishment (title-case match)
        matched = next(
            (p for p in VALID_PUNISHMENTS if p.lower() == punishment.lower()),
            None,
        )
        if matched is None:
            valid_list = "\n".join(f"• {p}" for p in VALID_PUNISHMENTS)
            await ctx.send(
                embed=error_embed(
                    "Invalid Punishment",
                    f"**`{punishment}`** is not a valid punishment type.\n\n"
                    f"Valid types:\n{valid_list}",
                )
            )
            return

        # Store infraction
        infraction_id = await self.bot.db.add_infraction(
            user.id, ctx.author.id, matched, reason
        )

        # Build confirmation embed
        embed = success_embed("Infraction Issued")
        embed.add_field(name="Infraction ID", value=f"`{infraction_id}`", inline=True)
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="Punishment", value=matched, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=embed)

        # Send to log channel
        log_channel = self.bot.get_channel(INFRACTION_LOG_CHANNEL_ID)
        if isinstance(log_channel, discord.TextChannel):
            log_embed = primary_embed("Infraction Log")
            log_embed.add_field(name="Infraction ID", value=f"`{infraction_id}`", inline=True)
            log_embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=True)
            log_embed.add_field(name="Moderator", value=f"{ctx.author.mention} ({ctx.author.id})", inline=True)
            log_embed.add_field(name="Punishment", value=matched, inline=True)
            log_embed.add_field(name="Reason", value=reason, inline=False)
            log_embed.set_footer(text=f"ID: {infraction_id}")
            await log_channel.send(embed=log_embed)

        # ERLC permission removal for severe punishments
        if matched in ERLC_REMOVAL_PUNISHMENTS:
            linked = await self.bot.db.get_linked_account(user.id)
            if linked:
                roblox_name = linked["roblox_name"]
                await self.erlc.remove_permissions(roblox_name)
                await ctx.send(
                    embed=success_embed(
                        "ERLC Permissions Removed",
                        f"Removed admin/mod from **{roblox_name}** in ERLC.",
                    )
                )
            else:
                await ctx.send(
                    embed=error_embed(
                        "ERLC Warning",
                        f"{user.mention} does not have a linked Roblox account. "
                        "ERLC permissions could not be removed automatically.",
                    )
                )


async def setup(bot: NJRPBot) -> None:
    await bot.add_cog(Infractions(bot))
