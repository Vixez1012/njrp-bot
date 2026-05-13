"""
Live Session Status cog.

Sends a persistent embed to the session channel that auto-updates with
live server data (player count, online staff, queue length).
Includes a "Session Role" toggle button and a dynamic
"Session Offline" / "Quick Join" button.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands, ui
from discord.ext import commands, tasks

from config.settings import SESSION_ROLE_IDS, EMBED_COLOR_INFO
from utils.embeds import error_embed
from utils.erlc_api import ERLCApi

if TYPE_CHECKING:
    from bot import NJRPBot

logger = logging.getLogger(__name__)

AUTHOR_ICON_URL = "https://cdn.discordapp.com/attachments/1403383327108501534/1471846322335125555/image.png?ex=6a031db4&is=6a01cc34&hm=7e0894370018ed310d000bc6d05f5576e5ed0fc130f5118d8d947245c8466e56&"

SESSION_INFO_IMAGE_URL = "https://cdn.discordapp.com/attachments/1483408064945328220/1483413466856292392/image.png?ex=6a030272&is=6a01b0f2&hm=c7216d6fc525351d5ddfb1f464d98c2b6e901af444eb53a2d6db5c1cb0e7d9e7&"

# Role IDs
SESSION_ROLE_TO_GIVE = 1446452632263589931  # Role given when clicking "Session Role"
STAFF_ROLE_ID = 1446906296816107676  # Role checked for online staff count

QUICK_JOIN_URL = "https://erlc.gg/join/NewJerseyX"


def _has_session_role(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id in SESSION_ROLE_IDS for role in interaction.user.roles)


class SessionRoleButton(ui.Button):
    """Persistent button that toggles the session notification role."""

    def __init__(self) -> None:
        super().__init__(
            label="Session Role",
            style=discord.ButtonStyle.secondary,
            custom_id="live_session:session_role",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.user, discord.Member) or interaction.guild is None:
            return
        role = interaction.guild.get_role(SESSION_ROLE_TO_GIVE)
        if role is None:
            await interaction.response.send_message(
                "Session role not found.", ephemeral=True
            )
            return
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(
                f"Removed {role.mention} from you.", ephemeral=True
            )
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                f"Added {role.mention} to you.", ephemeral=True
            )


class LiveSessionView(ui.View):
    """Persistent view with Session Role button and status button."""

    def __init__(self, is_online: bool = False) -> None:
        super().__init__(timeout=None)
        self.add_item(SessionRoleButton())
        if is_online:
            self.add_item(
                ui.Button(
                    label="Quick Join",
                    style=discord.ButtonStyle.link,
                    url=QUICK_JOIN_URL,
                )
            )
        else:
            self.add_item(
                ui.Button(
                    label="Session Offline",
                    style=discord.ButtonStyle.danger,
                    custom_id="live_session:offline_placeholder",
                    disabled=True,
                )
            )


def _build_live_embed(
    server_data: Optional[dict],
    online_staff_count: int,
    session_status: str,
) -> tuple[discord.Embed, discord.Embed]:
    """Build the live session status embeds (info + game status)."""
    if server_data:
        current_players = server_data.get("CurrentPlayers", 0)
        max_players = server_data.get("MaxPlayers", 40)
        queue = server_data.get("Queue", [])
        queue_count = len(queue) if isinstance(queue, list) else 0
    else:
        current_players = 0
        max_players = 40
        queue_count = 0

    now = discord.utils.format_dt(datetime.now(timezone.utc), style="F")

    embed = discord.Embed(color=EMBED_COLOR_INFO)
    embed.set_author(
        name="New Jersey | Session Information",
        icon_url=AUTHOR_ICON_URL,
    )
    embed.title = "Live Session Status"
    embed.description = (
        "Below you can find useful information about our in game session, "
        "along with our usual session schedule. Do not join our in game "
        "server when the server is shutdown."
    )

    embed.add_field(
        name="<:Regulations:1446219196009550108> Server Name",
        value="```New Jersey Roleplay```",
        inline=False,
    )
    embed.add_field(
        name="<:Session:1442980201687679048> Join Code",
        value="```NewJerseyX```",
        inline=False,
    )

    embed.set_image(url=SESSION_INFO_IMAGE_URL)

    # Game status section as a second embed
    game_embed = discord.Embed(color=EMBED_COLOR_INFO)
    game_embed.set_author(
        name="New Jersey | Game Status",
        icon_url=AUTHOR_ICON_URL,
    )
    game_embed.description = (
        f"**Session Status:** {session_status}\n"
        f"**Last Updated:** {now}"
    )
    game_embed.add_field(
        name="Player Count",
        value=f"```{current_players}/{max_players}```",
        inline=False,
    )
    game_embed.add_field(
        name="Online Staff",
        value=f"```{online_staff_count}```",
        inline=True,
    )
    game_embed.add_field(
        name="Queue Length",
        value=f"```{queue_count}```",
        inline=True,
    )

    return embed, game_embed


class LiveSession(commands.Cog):
    """Live session status panel that auto-updates in the session channel."""

    def __init__(self, bot: NJRPBot) -> None:
        self.bot = bot
        self.erlc = ERLCApi()
        self._last_session_status: str = "Session Shutdown"
        self._is_online: bool = False

    async def cog_load(self) -> None:
        self.bot.add_view(LiveSessionView(is_online=False))
        self.bot.add_view(LiveSessionView(is_online=True))
        self.update_live_status.start()

    async def cog_unload(self) -> None:
        self.update_live_status.cancel()

    session_group = app_commands.Group(
        name="livestatus",
        description="Live session status commands",
    )

    @session_group.command(name="setup", description="Send the live session status panel")
    async def setup_live_status(self, interaction: discord.Interaction) -> None:
        if not _has_session_role(interaction):
            await interaction.response.send_message(
                embed=error_embed("Access Denied", "You do not have permission."),
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
                    "Session system is not configured. Use `/config session` first.",
                ),
                ephemeral=True,
            )
            return

        channel_id = config["channel_id"]
        if not channel_id:
            await interaction.response.send_message(
                embed=error_embed("No Channel", "No session channel configured."),
                ephemeral=True,
            )
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("Invalid Channel", "Configured channel is invalid."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Fetch initial data
        server_data = await self.erlc.get_server_status()
        is_online = server_data is not None and server_data.get("CurrentPlayers", 0) > 0
        self._is_online = is_online

        if is_online:
            self._last_session_status = "Session Startup"
        else:
            self._last_session_status = "Session Shutdown"

        staff_count = self._count_online_staff(guild)
        embed, game_embed = _build_live_embed(
            server_data, staff_count, self._last_session_status
        )
        view = LiveSessionView(is_online=is_online)

        msg = await channel.send(embeds=[embed, game_embed], view=view)

        # Save the message ID for future updates
        await self.bot.db.upsert_session_config(
            guild.id, live_status_message_id=msg.id
        )

        await interaction.followup.send(
            embed=discord.Embed(
                title="Live Status Panel Created",
                description=f"Live session status panel sent to {channel.mention}.",
                color=0x57F287,
            ),
            ephemeral=True,
        )

    def _count_online_staff(self, guild: discord.Guild) -> int:
        """Count members with the staff role who are currently online."""
        role = guild.get_role(STAFF_ROLE_ID)
        if role is None:
            return 0
        return sum(
            1
            for m in role.members
            if m.status in (discord.Status.online, discord.Status.idle, discord.Status.dnd)
        )

    @tasks.loop(seconds=60)
    async def update_live_status(self) -> None:
        """Periodically update the live session status embed."""
        for guild in self.bot.guilds:
            try:
                await self._update_guild_status(guild)
            except Exception:
                logger.exception("Failed to update live status for guild %s", guild.id)

    @update_live_status.before_loop
    async def _before_update(self) -> None:
        await self.bot.wait_until_ready()

    async def _update_guild_status(self, guild: discord.Guild) -> None:
        config = await self.bot.db.get_session_config(guild.id)
        if config is None:
            return

        message_id = config.get("live_status_message_id", 0)
        if not message_id:
            return

        channel_id = config["channel_id"]
        if not channel_id:
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            return
        except discord.HTTPException:
            return

        server_data = await self.erlc.get_server_status()
        is_online = server_data is not None and server_data.get("CurrentPlayers", 0) > 0
        self._is_online = is_online

        if is_online:
            self._last_session_status = "Session Startup"
        else:
            self._last_session_status = "Session Shutdown"

        staff_count = self._count_online_staff(guild)
        embed, game_embed = _build_live_embed(
            server_data, staff_count, self._last_session_status
        )
        view = LiveSessionView(is_online=is_online)

        await message.edit(embeds=[embed, game_embed], view=view)


async def setup(bot: NJRPBot) -> None:
    await bot.add_cog(LiveSession(bot))
