"""
Session system cog.

Slash command: /session <option>
Options: SSU, SSD, Vote, Low, Full

Sends configurable embeds to a configured channel with optional role pings.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from config.settings import SESSION_ROLE_IDS, EMBED_COLOR_INFO
from utils.embeds import error_embed

if TYPE_CHECKING:
    from bot import NJRPBot

logger = logging.getLogger(__name__)

SESSION_TYPES = {
    "ssu": {"title": "Server Startup", "emoji": "🟢"},
    "ssd": {"title": "Server Shutdown", "emoji": "🔴"},
    "vote": {"title": "Vote Session", "emoji": "🗳️"},
    "low": {"title": "Low Player Count", "emoji": "⚠️"},
    "full": {"title": "Server Full", "emoji": "🔵"},
}

# In-memory cooldown tracking: guild_id -> last_used_timestamp
_cooldowns: dict[int, float] = {}


def _has_session_role(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id in SESSION_ROLE_IDS for role in interaction.user.roles)


class Sessions(commands.Cog):
    """Session management system with configurable announcements."""

    def __init__(self, bot: NJRPBot) -> None:
        self.bot = bot

    session_group = app_commands.Group(name="session", description="Session commands")

    @session_group.command(name="start", description="Send a session announcement")
    @app_commands.describe(option="Session type: SSU, SSD, Vote, Low, Full")
    @app_commands.choices(
        option=[
            app_commands.Choice(name="SSU — Server Startup", value="ssu"),
            app_commands.Choice(name="SSD — Server Shutdown", value="ssd"),
            app_commands.Choice(name="Vote — Vote Session", value="vote"),
            app_commands.Choice(name="Low — Low Player Count", value="low"),
            app_commands.Choice(name="Full — Server Full", value="full"),
        ]
    )
    async def session_start(
        self, interaction: discord.Interaction, option: app_commands.Choice[str]
    ) -> None:
        if not _has_session_role(interaction):
            await interaction.response.send_message(
                embed=error_embed("Access Denied", "You do not have permission to use this command."),
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if guild is None:
            return

        config = await self.bot.db.get_session_config(guild.id)
        if config is None:
            await interaction.response.send_message(
                embed=error_embed(
                    "Not Configured",
                    "Session system is not configured. Use `/config session` to set it up.",
                ),
                ephemeral=True,
            )
            return

        # Cooldown check
        cooldown_seconds = config["cooldown_seconds"] or 60
        now = time.time()
        last_used = _cooldowns.get(guild.id, 0)
        if now - last_used < cooldown_seconds:
            remaining = int(cooldown_seconds - (now - last_used))
            await interaction.response.send_message(
                embed=error_embed("Cooldown", f"Please wait **{remaining}s** before sending another session."),
                ephemeral=True,
            )
            return

        channel_id = config["channel_id"]
        if not channel_id:
            await interaction.response.send_message(
                embed=error_embed("No Channel", "No session channel configured. Use `/config session`."),
                ephemeral=True,
            )
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("Invalid Channel", "The configured session channel is invalid."),
                ephemeral=True,
            )
            return

        session_key = option.value
        meta = SESSION_TYPES[session_key]
        text_key = f"{session_key}_text"
        text = config[text_key] if text_key in config.keys() else f"{meta['title']} announcement."
        color = config["embed_color"] or EMBED_COLOR_INFO

        embed = discord.Embed(
            title=f"{meta['emoji']}  {meta['title']}",
            description=text,
            color=color,
        )
        embed.set_footer(text=f"Announced by {interaction.user.display_name}")
        embed.timestamp = discord.utils.utcnow()

        # Build ping string
        ping_roles_raw = config["ping_roles"] or "[]"
        ping_role_ids: list[int] = json.loads(ping_roles_raw)
        pings = " ".join(f"<@&{rid}>" for rid in ping_role_ids)

        await channel.send(content=pings or None, embed=embed)
        _cooldowns[guild.id] = now

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Session Sent",
                description=f"**{meta['title']}** announcement sent to {channel.mention}.",
                color=0x57F287,
            ),
            ephemeral=True,
        )


async def setup(bot: NJRPBot) -> None:
    await bot.add_cog(Sessions(bot))
