"""
Session configuration cog.

Slash command: /config session
Allows changing session channel, ping roles, embed colors, vote threshold,
session texts, and cooldowns.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands, ui
from discord.ext import commands

from config.settings import SESSION_CONFIG_ROLE_IDS
from utils.embeds import success_embed, error_embed, info_embed

if TYPE_CHECKING:
    from bot import NJRPBot

logger = logging.getLogger(__name__)


def _has_session_config_role(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id in SESSION_CONFIG_ROLE_IDS for role in interaction.user.roles)


class SessionConfig(commands.Cog):
    """Session configuration management."""

    def __init__(self, bot: NJRPBot) -> None:
        self.bot = bot

    config_group = app_commands.Group(name="config", description="Configuration commands")

    @config_group.command(name="session", description="Configure the session system")
    async def config_session(self, interaction: discord.Interaction) -> None:
        if not _has_session_config_role(interaction):
            await interaction.response.send_message(
                embed=error_embed("Access Denied", "You do not have permission to use this command."),
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if guild is None:
            return

        config = await self.bot.db.get_session_config(guild.id)

        # Build current config embed
        embed = info_embed("Session Configuration")
        if config:
            channel_mention = f"<#{config['channel_id']}>" if config["channel_id"] else "Not set"
            ping_roles_raw = config["ping_roles"] or "[]"
            ping_ids: list[int] = json.loads(ping_roles_raw)
            pings = ", ".join(f"<@&{r}>" for r in ping_ids) if ping_ids else "None"

            embed.add_field(name="Channel", value=channel_mention, inline=True)
            embed.add_field(name="Ping Roles", value=pings, inline=True)
            embed.add_field(name="Embed Color", value=f"`#{config['embed_color']:06X}`" if config["embed_color"] else "Default", inline=True)
            embed.add_field(name="Vote Threshold", value=str(config["vote_threshold"]), inline=True)
            embed.add_field(name="Cooldown", value=f"{config['cooldown_seconds']}s", inline=True)

            image_keys = ["ssu_image", "ssd_image", "vote_image", "low_image", "full_image"]
            image_labels = ["SSU", "SSD", "Vote", "Low", "Full"]
            image_lines: list[str] = []
            for label, key in zip(image_labels, image_keys):
                val = config[key] if key in config.keys() else ""
                image_lines.append(f"**{label}:** {'Set' if val else 'Not set'}")
            embed.add_field(name="Session Images", value="\n".join(image_lines), inline=False)
        else:
            embed.description = "No session configuration found. Use the buttons below to set up."

        await interaction.response.send_message(
            embed=embed,
            view=SessionConfigView(self.bot),
            ephemeral=True,
        )


class SessionConfigView(ui.View):
    def __init__(self, bot: NJRPBot) -> None:
        super().__init__(timeout=180)
        self.bot = bot

    @ui.button(label="Set Channel", style=discord.ButtonStyle.secondary, row=0)
    async def set_channel(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await interaction.response.send_modal(SetChannelModal(self.bot))

    @ui.button(label="Set Ping Roles", style=discord.ButtonStyle.secondary, row=0)
    async def set_pings(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await interaction.response.send_modal(SetPingRolesModal(self.bot))

    @ui.button(label="Set Embed Color", style=discord.ButtonStyle.secondary, row=0)
    async def set_color(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await interaction.response.send_modal(SetEmbedColorModal(self.bot))

    @ui.button(label="Set Vote Threshold", style=discord.ButtonStyle.secondary, row=1)
    async def set_threshold(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await interaction.response.send_modal(SetVoteThresholdModal(self.bot))

    @ui.button(label="Set Cooldown", style=discord.ButtonStyle.secondary, row=1)
    async def set_cooldown(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await interaction.response.send_modal(SetCooldownModal(self.bot))

    @ui.button(label="Set Session Texts", style=discord.ButtonStyle.secondary, row=1)
    async def set_texts(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await interaction.response.send_modal(SetSessionTextsModal(self.bot))

    @ui.button(label="Set Session Images", style=discord.ButtonStyle.secondary, row=2)
    async def set_images(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await interaction.response.send_modal(SetSessionImagesModal(self.bot))


class SetChannelModal(ui.Modal, title="Set Session Channel"):
    channel_id_input = ui.TextInput(label="Channel ID", placeholder="e.g. 123456789012345678")

    def __init__(self, bot: NJRPBot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            cid = int(self.channel_id_input.value.strip())
        except ValueError:
            await interaction.response.send_message(embed=error_embed("Invalid", "Enter a valid channel ID."), ephemeral=True)
            return
        guild = interaction.guild
        if guild is None:
            return
        await self.bot.db.upsert_session_config(guild.id, channel_id=cid)
        await interaction.response.send_message(embed=success_embed("Channel Set", f"Session channel set to <#{cid}>."), ephemeral=True)


class SetPingRolesModal(ui.Modal, title="Set Ping Roles"):
    roles_input = ui.TextInput(
        label="Role IDs (comma-separated)",
        placeholder="e.g. 111111111111,222222222222",
        required=False,
    )

    def __init__(self, bot: NJRPBot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = self.roles_input.value.strip()
        if not raw:
            role_ids: list[int] = []
        else:
            try:
                role_ids = [int(r.strip()) for r in raw.split(",")]
            except ValueError:
                await interaction.response.send_message(embed=error_embed("Invalid", "Enter valid role IDs separated by commas."), ephemeral=True)
                return
        guild = interaction.guild
        if guild is None:
            return
        await self.bot.db.upsert_session_config(guild.id, ping_roles=json.dumps(role_ids))
        await interaction.response.send_message(embed=success_embed("Ping Roles Updated", f"Set {len(role_ids)} ping role(s)."), ephemeral=True)


class SetEmbedColorModal(ui.Modal, title="Set Embed Color"):
    color_input = ui.TextInput(label="Hex Color Code", placeholder="e.g. #5865F2 or 5865F2")

    def __init__(self, bot: NJRPBot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = self.color_input.value.strip().lstrip("#")
        try:
            color = int(raw, 16)
        except ValueError:
            await interaction.response.send_message(embed=error_embed("Invalid", "Enter a valid hex color."), ephemeral=True)
            return
        guild = interaction.guild
        if guild is None:
            return
        await self.bot.db.upsert_session_config(guild.id, embed_color=color)
        await interaction.response.send_message(embed=success_embed("Color Set", f"Embed color set to `#{raw.upper()}`."), ephemeral=True)


class SetVoteThresholdModal(ui.Modal, title="Set Vote Threshold"):
    threshold_input = ui.TextInput(label="Vote Threshold", placeholder="e.g. 5")

    def __init__(self, bot: NJRPBot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            val = int(self.threshold_input.value.strip())
        except ValueError:
            await interaction.response.send_message(embed=error_embed("Invalid", "Enter a valid number."), ephemeral=True)
            return
        guild = interaction.guild
        if guild is None:
            return
        await self.bot.db.upsert_session_config(guild.id, vote_threshold=val)
        await interaction.response.send_message(embed=success_embed("Threshold Set", f"Vote threshold set to **{val}**."), ephemeral=True)


class SetCooldownModal(ui.Modal, title="Set Session Cooldown"):
    cooldown_input = ui.TextInput(label="Cooldown (seconds)", placeholder="e.g. 60")

    def __init__(self, bot: NJRPBot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            val = int(self.cooldown_input.value.strip())
        except ValueError:
            await interaction.response.send_message(embed=error_embed("Invalid", "Enter a valid number."), ephemeral=True)
            return
        guild = interaction.guild
        if guild is None:
            return
        await self.bot.db.upsert_session_config(guild.id, cooldown_seconds=val)
        await interaction.response.send_message(embed=success_embed("Cooldown Set", f"Session cooldown set to **{val}s**."), ephemeral=True)


class SetSessionTextsModal(ui.Modal, title="Set Session Texts"):
    ssu_text = ui.TextInput(label="SSU Text", style=discord.TextStyle.paragraph, required=False, default="The server is starting up! Join now.")
    ssd_text = ui.TextInput(label="SSD Text", style=discord.TextStyle.paragraph, required=False, default="The server is shutting down. Thank you for playing!")
    vote_text = ui.TextInput(label="Vote Text", style=discord.TextStyle.paragraph, required=False, default="Vote for a session! React to participate.")
    low_text = ui.TextInput(label="Low Text", style=discord.TextStyle.paragraph, required=False, default="Player count is low. Join the server!")
    full_text = ui.TextInput(label="Full Text", style=discord.TextStyle.paragraph, required=False, default="The server is full! Please wait for a slot.")

    def __init__(self, bot: NJRPBot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            return
        updates: dict[str, str] = {}
        if self.ssu_text.value:
            updates["ssu_text"] = self.ssu_text.value
        if self.ssd_text.value:
            updates["ssd_text"] = self.ssd_text.value
        if self.vote_text.value:
            updates["vote_text"] = self.vote_text.value
        if self.low_text.value:
            updates["low_text"] = self.low_text.value
        if self.full_text.value:
            updates["full_text"] = self.full_text.value

        if updates:
            await self.bot.db.upsert_session_config(guild.id, **updates)

        await interaction.response.send_message(embed=success_embed("Texts Updated", "Session texts have been updated."), ephemeral=True)


class SetSessionImagesModal(ui.Modal, title="Set Session Images"):
    ssu_image = ui.TextInput(label="SSU Image URL", required=False, placeholder="https://example.com/ssu.png")
    ssd_image = ui.TextInput(label="SSD Image URL", required=False, placeholder="https://example.com/ssd.png")
    vote_image = ui.TextInput(label="Vote Image URL", required=False, placeholder="https://example.com/vote.png")
    low_image = ui.TextInput(label="Low Image URL", required=False, placeholder="https://example.com/low.png")
    full_image = ui.TextInput(label="Full Image URL", required=False, placeholder="https://example.com/full.png")

    def __init__(self, bot: NJRPBot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            return
        updates: dict[str, str] = {}
        if self.ssu_image.value:
            updates["ssu_image"] = self.ssu_image.value.strip()
        if self.ssd_image.value:
            updates["ssd_image"] = self.ssd_image.value.strip()
        if self.vote_image.value:
            updates["vote_image"] = self.vote_image.value.strip()
        if self.low_image.value:
            updates["low_image"] = self.low_image.value.strip()
        if self.full_image.value:
            updates["full_image"] = self.full_image.value.strip()

        if updates:
            await self.bot.db.upsert_session_config(guild.id, **updates)

        await interaction.response.send_message(embed=success_embed("Images Updated", "Session images have been updated."), ephemeral=True)


async def setup(bot: NJRPBot) -> None:
    await bot.add_cog(SessionConfig(bot))
