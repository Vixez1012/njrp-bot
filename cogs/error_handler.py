"""
Centralized error handler cog.

Catches command errors, app command errors, and unhandled exceptions
to prevent the bot from crashing and provide user-friendly messages.
"""

from __future__ import annotations

import logging
import traceback
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import error_embed

if TYPE_CHECKING:
    from bot import NJRPBot

logger = logging.getLogger(__name__)


class ErrorHandler(commands.Cog):
    """Global error handler for prefix and slash commands."""

    def __init__(self, bot: NJRPBot) -> None:
        self.bot = bot
        # Register the app command error handler
        self.bot.tree.on_error = self.on_app_command_error

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        # Ignore commands with their own local handlers
        if hasattr(ctx.command, "on_error"):
            return

        error = getattr(error, "original", error)

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                embed=error_embed(
                    "Missing Argument",
                    f"Missing required argument: `{error.param.name}`\n"
                    f"Usage: `{ctx.prefix}{ctx.command} {ctx.command.signature}`",
                )
            )
            return

        if isinstance(error, commands.CheckFailure):
            await ctx.send(
                embed=error_embed("Permission Denied", "You do not have permission to use this command."),
            )
            return

        if isinstance(error, commands.BadArgument):
            await ctx.send(
                embed=error_embed("Bad Argument", str(error)),
            )
            return

        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                embed=error_embed("Cooldown", f"Try again in **{error.retry_after:.1f}s**."),
            )
            return

        if isinstance(error, commands.MemberNotFound):
            await ctx.send(
                embed=error_embed("Member Not Found", f"Could not find member: `{error.argument}`"),
            )
            return

        # Unhandled error
        logger.error("Unhandled command error in %s: %s", ctx.command, error, exc_info=error)
        await ctx.send(
            embed=error_embed("Error", "An unexpected error occurred. Please try again later."),
        )

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        error = getattr(error, "original", error)

        if isinstance(error, app_commands.CheckFailure):
            if interaction.response.is_done():
                await interaction.followup.send(
                    embed=error_embed("Permission Denied", "You do not have permission to use this command."),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    embed=error_embed("Permission Denied", "You do not have permission to use this command."),
                    ephemeral=True,
                )
            return

        if isinstance(error, app_commands.CommandOnCooldown):
            msg = f"Try again in **{error.retry_after:.1f}s**."
            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed("Cooldown", msg), ephemeral=True)
            else:
                await interaction.response.send_message(embed=error_embed("Cooldown", msg), ephemeral=True)
            return

        logger.error("Unhandled app command error: %s", error, exc_info=error)
        msg = "An unexpected error occurred. Please try again later."
        if interaction.response.is_done():
            await interaction.followup.send(embed=error_embed("Error", msg), ephemeral=True)
        else:
            await interaction.response.send_message(embed=error_embed("Error", msg), ephemeral=True)


async def setup(bot: NJRPBot) -> None:
    await bot.add_cog(ErrorHandler(bot))
