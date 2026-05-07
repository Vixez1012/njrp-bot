"""
Permission checks and middleware for the bot.
"""

import discord
from discord.ext import commands

from config.settings import (
    ADMIN_PANEL_ROLE_IDS,
    INFRACTION_ROLE_IDS,
    SESSION_ROLE_IDS,
    JSK_AUTHORIZED_USERS,
)


def has_admin_panel_role():
    """Check if the user has an admin panel role."""

    async def predicate(ctx: commands.Context) -> bool:
        if not isinstance(ctx.author, discord.Member):
            return False
        return any(role.id in ADMIN_PANEL_ROLE_IDS for role in ctx.author.roles)

    return commands.check(predicate)


def has_infraction_role():
    """Check if the user has an infraction role."""

    async def predicate(ctx: commands.Context) -> bool:
        if not isinstance(ctx.author, discord.Member):
            return False
        return any(role.id in INFRACTION_ROLE_IDS for role in ctx.author.roles)

    return commands.check(predicate)


def has_session_role():
    """Check if the user has a session role."""

    async def predicate(ctx: commands.Context) -> bool:
        if not isinstance(ctx.author, discord.Member):
            return False
        return any(role.id in SESSION_ROLE_IDS for role in ctx.author.roles)

    return commands.check(predicate)


def is_jsk_authorized():
    """Check if the user is authorized to use Jishaku."""

    async def predicate(ctx: commands.Context) -> bool:
        return ctx.author.id in JSK_AUTHORIZED_USERS

    return commands.check(predicate)


async def blacklist_check(ctx: commands.Context) -> bool:
    """Global check — prevents blacklisted users from using any command."""
    db = ctx.bot.db  # type: ignore[attr-defined]
    if await db.is_blacklisted(ctx.author.id):
        embed = discord.Embed(
            title="Blacklisted",
            description="You are blacklisted from using this bot.",
            color=0xED4245,
        )
        await ctx.send(embed=embed, ephemeral=True)
        return False
    return True


async def command_enabled_check(ctx: commands.Context) -> bool:
    """Global check — prevents use of disabled commands."""
    if ctx.command is None:
        return True
    db = ctx.bot.db  # type: ignore[attr-defined]
    if not await db.is_command_enabled(ctx.command.qualified_name):
        embed = discord.Embed(
            title="Command Disabled",
            description="This command is currently disabled by an administrator.",
            color=0xED4245,
        )
        await ctx.send(embed=embed, ephemeral=True)
        return False
    return True
