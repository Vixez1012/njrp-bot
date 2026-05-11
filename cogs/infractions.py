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
            separator = "━━━━━━━━━━━━━━━━━"

            log_embed = discord.Embed(
                title="Infraction Documentation",
                description=(
                    f"**Issued By:** {ctx.author.mention}\n\n"
                    f"{separator}\n\n"
                    f"**User:** {user.mention}\n\n"
                    f"{separator}\n\n"
                    f"**Action:** {matched}\n"
                    f"**Reason:** {reason}\n\n"
                    f"{separator}"
                ),
                color=0x2F3136,
                timestamp=discord.utils.utcnow(),
            )
            log_embed.set_author(
                name="New Jersey Systems | Staff Infraction Log",
                icon_url="https://images-ext-1.discordapp.net/external/J2hjKC42uN-qej9J5s5o-vgQPr7DmMC7Q8yP8VTQpMY/https/cdn.discordapp.com/icons/1439185420096114781/a943e755123bbe6e5ae5dff1868461e6.png",
            )
            log_embed.set_thumbnail(
                url="https://media.discordapp.net/attachments/1403383327108501534/1471846322335125555/image.png?ex=69b949b4&is=69b7f834&hm=606bd99fec1f5dfa31a50ec2ad79555e2e55637623ccbc2ae788b378d5116fc9&format=webp&quality=lossless&",
            )
            log_embed.set_image(
                url="https://media.discordapp.net/attachments/1446444245350223922/1446448150087729302/image.png?ex=69b92cd0&is=69b7db50&hm=c2c4d71e608bb5cec47bfb801f8d46003f6bcb4eb18a361e477ec54a9539d4c2&format=webp&quality=lossless&width=1872&height=67&",
            )
            log_embed.set_footer(
                text=f"Issued By: {ctx.author.display_name} | ",
                icon_url=ctx.author.display_avatar.url,
            )

            await log_channel.send(content=user.mention, embed=log_embed)

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
