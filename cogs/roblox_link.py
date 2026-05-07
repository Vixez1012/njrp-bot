"""
Roblox Link system cog.

Slash commands:
  /link   — Link Discord account to Roblox via verification code.
  /unlink — Remove linked Roblox account.
"""

from __future__ import annotations

import logging
import secrets
import string
from typing import TYPE_CHECKING

import discord
from discord import app_commands, ui
from discord.ext import commands

from utils.embeds import success_embed, error_embed, info_embed
from utils.roblox_api import get_user_by_username, check_profile_for_code

if TYPE_CHECKING:
    from bot import NJRPBot

logger = logging.getLogger(__name__)


def _generate_code(length: int = 8) -> str:
    """Generate a random alphanumeric verification code."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class RobloxLink(commands.Cog):
    """Roblox account linking and verification."""

    def __init__(self, bot: NJRPBot) -> None:
        self.bot = bot

    @app_commands.command(name="link", description="Link your Discord account to Roblox")
    async def link(self, interaction: discord.Interaction) -> None:
        existing = await self.bot.db.get_linked_account(interaction.user.id)
        if existing:
            await interaction.response.send_message(
                embed=error_embed(
                    "Already Linked",
                    f"You are already linked to **{existing['roblox_name']}** (ID: {existing['roblox_id']}).\n"
                    "Use `/unlink` to remove your linked account first.",
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(LinkUsernameModal(self.bot))

    @app_commands.command(name="unlink", description="Unlink your Roblox account")
    async def unlink(self, interaction: discord.Interaction) -> None:
        existing = await self.bot.db.get_linked_account(interaction.user.id)
        if not existing:
            await interaction.response.send_message(
                embed=error_embed("Not Linked", "You do not have a linked Roblox account."),
                ephemeral=True,
            )
            return

        await self.bot.db.unlink_account(interaction.user.id)
        await self.bot.db.delete_verification_code(interaction.user.id)
        await interaction.response.send_message(
            embed=success_embed("Unlinked", "Your Roblox account has been unlinked."),
            ephemeral=True,
        )


class LinkUsernameModal(ui.Modal, title="Link Roblox Account"):
    username_input = ui.TextInput(
        label="Roblox Username",
        placeholder="Enter your Roblox username",
        max_length=20,
    )

    def __init__(self, bot: NJRPBot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        username = self.username_input.value.strip()
        roblox_user = await get_user_by_username(username)

        if roblox_user is None:
            await interaction.response.send_message(
                embed=error_embed("User Not Found", f"No Roblox user found with username **{username}**."),
                ephemeral=True,
            )
            return

        # Check if this Roblox account is already linked to someone else
        existing_link = await self.bot.db.get_linked_by_roblox(roblox_user["id"])
        if existing_link and existing_link["discord_id"] != interaction.user.id:
            await interaction.response.send_message(
                embed=error_embed(
                    "Already Linked",
                    f"**{roblox_user['name']}** is already linked to another Discord account.",
                ),
                ephemeral=True,
            )
            return

        # Generate verification code
        code = _generate_code()
        await self.bot.db.save_verification_code(interaction.user.id, code)

        embed = info_embed(
            "Verification Required",
            f"To verify ownership of **{roblox_user['name']}**, please follow these steps:\n\n"
            f"1. Go to your [Roblox Profile](https://www.roblox.com/users/{roblox_user['id']}/profile)\n"
            f"2. Click **Edit Profile** (or the pencil icon)\n"
            f"3. Add the following code to your **About** / **Description** section:\n\n"
            f"```\n{code}\n```\n\n"
            f"4. **Save** your profile\n"
            f"5. Click the **Verify** button below\n\n"
            f"*The code will expire if you close this message.*",
        )

        await interaction.response.send_message(
            embed=embed,
            view=VerifyView(self.bot, roblox_user["id"], roblox_user["name"]),
            ephemeral=True,
        )


class VerifyView(ui.View):
    def __init__(self, bot: NJRPBot, roblox_id: int, roblox_name: str) -> None:
        super().__init__(timeout=300)
        self.bot = bot
        self.roblox_id = roblox_id
        self.roblox_name = roblox_name

    @ui.button(label="Verify", style=discord.ButtonStyle.success, emoji="✅")
    async def verify_btn(self, interaction: discord.Interaction, button: ui.Button) -> None:
        code = await self.bot.db.get_verification_code(interaction.user.id)
        if not code:
            await interaction.response.send_message(
                embed=error_embed("Expired", "Verification code expired. Please run `/link` again."),
                ephemeral=True,
            )
            return

        # Check if code is in the Roblox profile
        found = await check_profile_for_code(self.roblox_id, code)
        if not found:
            await interaction.response.send_message(
                embed=error_embed(
                    "Verification Failed",
                    "The code was not found in your Roblox profile description.\n"
                    "Make sure you saved your profile and try again.",
                ),
                ephemeral=True,
            )
            return

        # Link the account
        await self.bot.db.link_account(interaction.user.id, self.roblox_id, self.roblox_name)
        await self.bot.db.delete_verification_code(interaction.user.id)

        await interaction.response.send_message(
            embed=success_embed(
                "Account Linked",
                f"Successfully linked to **{self.roblox_name}** (ID: {self.roblox_id}).\n"
                f"You can now remove the verification code from your profile.",
            ),
            ephemeral=True,
        )


async def setup(bot: NJRPBot) -> None:
    await bot.add_cog(RobloxLink(bot))
