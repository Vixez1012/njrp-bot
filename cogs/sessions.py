"""
Session system cog.

Slash command: /session <option>
Options: SSU, SSD, Vote, Low, Full

Sends configurable embeds (Components V2) to a configured channel with
optional role pings.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

import discord
from discord import app_commands, ui
from discord.ext import commands

from config.settings import SESSION_ROLE_IDS, EMBED_COLOR_INFO
from utils.embeds import error_embed

if TYPE_CHECKING:
    from bot import NJRPBot

logger = logging.getLogger(__name__)

SESSION_TYPES = {
    "ssu": {"title": "Server Startup", "status": "Startup"},
    "ssd": {"title": "Server Shutdown", "status": "Shutdown"},
    "vote": {"title": "Vote Session", "status": "Vote"},
    "low": {"title": "Low Player Count", "status": "Low"},
    "full": {"title": "Server Full", "status": "Full"},
}

AUTHOR_ICON_URL = "https://cdn.discordapp.com/attachments/1403383327108501534/1471846322335125555/image.png?ex=6a031db4&is=6a01cc34&hm=7e0894370018ed310d000bc6d05f5576e5ed0fc130f5118d8d947245c8466e56&"

SESSION_FOOTER_IMAGE_URL = "https://cdn.discordapp.com/attachments/1483408064945328220/1483413466856292392/image.png?ex=6a030272&is=6a01b0f2&hm=c7216d6fc525351d5ddfb1f464d98c2b6e901af444eb53a2d6db5c1cb0e7d9e7&"

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

        # Per-session-type image
        image_key = f"{session_key}_image"
        image_url = config[image_key] if image_key in config.keys() else ""

        # Build v2 layout
        container_children: list[ui.Item] = []

        # Banner image at top (if configured)
        if image_url:
            container_children.append(
                ui.MediaGallery(discord.MediaGalleryItem(media=image_url))
            )

        # Section: session title with author icon thumbnail
        container_children.append(
            ui.Section(
                ui.TextDisplay(f"**NJRP | Session {meta['status']}**"),
                accessory=ui.Thumbnail(AUTHOR_ICON_URL),
            )
        )

        # Description text
        container_children.append(
            ui.TextDisplay(text)
        )

        # Server info
        container_children.append(
            ui.TextDisplay(
                "• <:Regulations:1446219196009550108> **Server Name:** New Jersey Roleplay\n"
                "• **Server Owner:** Boltiscool1000"
            )
        )

        # Separator before button and footer image
        container_children.append(
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )

        # Join link button
        container_children.append(
            ui.ActionRow(
                ui.Button(
                    label="Server Code: NewJerseyX",
                    url="https://policeroleplay.community/join/NewJerseyX",
                    style=discord.ButtonStyle.link,
                )
            )
        )

        # Hardcoded footer image
        container_children.append(
            ui.MediaGallery(discord.MediaGalleryItem(media=SESSION_FOOTER_IMAGE_URL))
        )

        container = ui.Container(
            *container_children,
            accent_colour=color,
        )

        layout = ui.LayoutView()
        layout.add_item(container)

        # Build ping string and send as separate message (content not allowed with v2)
        ping_roles_raw = config["ping_roles"] or "[]"
        ping_role_ids: list[int] = json.loads(ping_roles_raw)
        pings = " ".join(f"<@&{rid}>" for rid in ping_role_ids)

        if pings:
            await channel.send(content=pings)
        await channel.send(view=layout)
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
