"""
Roblox Link system cog.

Slash commands:
  /link   — Link Discord account to Roblox via OAuth 2.0.
  /unlink — Remove linked Roblox account.

Runs a small aiohttp web server to handle the OAuth callback.
"""

from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING, Optional

import aiohttp
from aiohttp import web
import discord
from discord import app_commands, ui
from discord.ext import commands

from config.settings import (
    ROBLOX_CLIENT_ID,
    ROBLOX_CLIENT_SECRET,
    ROBLOX_REDIRECT_URI,
    ROBLOX_OAUTH_PORT,
)
from utils.embeds import success_embed, error_embed

if TYPE_CHECKING:
    from bot import NJRPBot

logger = logging.getLogger(__name__)

ROBLOX_AUTH_URL = "https://apis.roblox.com/oauth/v1/authorize"
ROBLOX_TOKEN_URL = "https://apis.roblox.com/oauth/v1/token"
ROBLOX_USERINFO_URL = "https://apis.roblox.com/oauth/v1/userinfo"

# In-memory store of pending OAuth states: state_string -> discord_user_id
_pending_states: dict[str, int] = {}

# Completed OAuth results: discord_user_id -> {"roblox_id": ..., "roblox_name": ...}
_completed_links: dict[int, dict] = {}

# Failed OAuth results: discord_user_id -> error message
_failed_links: dict[int, str] = {}


def _build_oauth_url(state: str) -> str:
    """Build the Roblox OAuth authorization URL."""
    params = {
        "client_id": ROBLOX_CLIENT_ID,
        "redirect_uri": ROBLOX_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid profile",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{ROBLOX_AUTH_URL}?{query}"


async def _exchange_code(code: str) -> Optional[dict]:
    """Exchange authorization code for access token."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": ROBLOX_REDIRECT_URI,
        "client_id": ROBLOX_CLIENT_ID,
        "client_secret": ROBLOX_CLIENT_SECRET,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                ROBLOX_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.error(
                    "Roblox token exchange failed (%s): %s",
                    resp.status,
                    await resp.text(),
                )
                return None
    except aiohttp.ClientError as exc:
        logger.error("Roblox token exchange error: %s", exc)
        return None


async def _get_userinfo(access_token: str) -> Optional[dict]:
    """Fetch Roblox user info using the access token."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                ROBLOX_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.error(
                    "Roblox userinfo failed (%s): %s",
                    resp.status,
                    await resp.text(),
                )
                return None
    except aiohttp.ClientError as exc:
        logger.error("Roblox userinfo error: %s", exc)
        return None


async def _handle_callback(request: web.Request) -> web.Response:
    """Handle the OAuth callback from Roblox."""
    code = request.query.get("code")
    state = request.query.get("state")
    error = request.query.get("error")

    if error:
        discord_user_id = _pending_states.pop(state, None) if state else None
        if discord_user_id:
            _failed_links[discord_user_id] = f"Authorization denied: {error}"
        return web.Response(
            text="Authorization denied. You can close this tab and return to Discord.",
            content_type="text/html",
        )

    if not code or not state:
        return web.Response(
            text="Invalid callback. Missing code or state.",
            content_type="text/html",
            status=400,
        )

    discord_user_id = _pending_states.pop(state, None)
    if discord_user_id is None:
        return web.Response(
            text="Invalid or expired state. Please run /link again in Discord.",
            content_type="text/html",
            status=400,
        )

    # Exchange code for token
    token_data = await _exchange_code(code)
    if token_data is None:
        _failed_links[discord_user_id] = "Failed to exchange authorization code."
        return web.Response(
            text="Failed to verify with Roblox. Please try again.",
            content_type="text/html",
            status=500,
        )

    access_token = token_data.get("access_token")
    if not access_token:
        _failed_links[discord_user_id] = "No access token received."
        return web.Response(
            text="Failed to verify with Roblox. Please try again.",
            content_type="text/html",
            status=500,
        )

    # Get user info
    userinfo = await _get_userinfo(access_token)
    if userinfo is None:
        _failed_links[discord_user_id] = "Failed to fetch Roblox user info."
        return web.Response(
            text="Failed to fetch your Roblox account info. Please try again.",
            content_type="text/html",
            status=500,
        )

    roblox_id = int(userinfo.get("sub", 0))
    roblox_name = userinfo.get("preferred_username") or userinfo.get("name", "Unknown")

    if not roblox_id:
        _failed_links[discord_user_id] = "Could not determine Roblox user ID."
        return web.Response(
            text="Could not determine your Roblox account. Please try again.",
            content_type="text/html",
            status=500,
        )

    _completed_links[discord_user_id] = {
        "roblox_id": roblox_id,
        "roblox_name": roblox_name,
    }

    return web.Response(
        text=(
            f"Successfully verified as {roblox_name}! "
            "You can close this tab and return to Discord. "
            "Click the 'Complete Link' button to finish linking."
        ),
        content_type="text/html",
    )


class CompleteLinkView(ui.View):
    """View with a button to finalize the OAuth link after callback."""

    def __init__(self, bot: NJRPBot) -> None:
        super().__init__(timeout=300)
        self.bot = bot

    @ui.button(label="Complete Link", style=discord.ButtonStyle.success)
    async def complete_btn(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        user_id = interaction.user.id

        # Check for errors
        if user_id in _failed_links:
            error_msg = _failed_links.pop(user_id)
            await interaction.response.send_message(
                embed=error_embed("Link Failed", error_msg),
                ephemeral=True,
            )
            return

        # Check for completed link
        result = _completed_links.pop(user_id, None)
        if result is None:
            await interaction.response.send_message(
                embed=error_embed(
                    "Not Verified Yet",
                    "Please click the **Authorize with Roblox** button first, "
                    "complete the authorization, then click this button.",
                ),
                ephemeral=True,
            )
            return

        roblox_id = result["roblox_id"]
        roblox_name = result["roblox_name"]

        # Check if this Roblox account is already linked to someone else
        existing_link = await self.bot.db.get_linked_by_roblox(roblox_id)
        if existing_link and existing_link["discord_id"] != user_id:
            await interaction.response.send_message(
                embed=error_embed(
                    "Already Linked",
                    f"**{roblox_name}** is already linked to another Discord account.",
                ),
                ephemeral=True,
            )
            return

        # Link the account
        await self.bot.db.link_account(user_id, roblox_id, roblox_name)

        await interaction.response.send_message(
            embed=success_embed(
                "Account Linked",
                f"Successfully linked to **{roblox_name}** (ID: {roblox_id}).",
            ),
            ephemeral=True,
        )


class RobloxLink(commands.Cog):
    """Roblox account linking via OAuth 2.0."""

    def __init__(self, bot: NJRPBot) -> None:
        self.bot = bot
        self._web_app: Optional[web.Application] = None
        self._web_runner: Optional[web.AppRunner] = None

    async def cog_load(self) -> None:
        """Start the OAuth callback web server."""
        self._web_app = web.Application()
        self._web_app.router.add_get("/roblox/callback", _handle_callback)

        self._web_runner = web.AppRunner(self._web_app)
        await self._web_runner.setup()
        site = web.TCPSite(self._web_runner, "0.0.0.0", ROBLOX_OAUTH_PORT)
        await site.start()
        logger.info("OAuth callback server started on port %s", ROBLOX_OAUTH_PORT)

    async def cog_unload(self) -> None:
        """Stop the OAuth callback web server."""
        if self._web_runner:
            await self._web_runner.cleanup()
            logger.info("OAuth callback server stopped.")

    @app_commands.command(
        name="link", description="Link your Discord account to Roblox"
    )
    async def link(self, interaction: discord.Interaction) -> None:
        existing = await self.bot.db.get_linked_account(interaction.user.id)
        if existing:
            await interaction.response.send_message(
                embed=error_embed(
                    "Already Linked",
                    f"You are already linked to **{existing['roblox_name']}** "
                    f"(ID: {existing['roblox_id']}).\n"
                    "Use `/unlink` to remove your linked account first.",
                ),
                ephemeral=True,
            )
            return

        # Generate state and build OAuth URL
        state = secrets.token_urlsafe(32)
        _pending_states[state] = interaction.user.id
        oauth_url = _build_oauth_url(state)

        embed = discord.Embed(
            title="Link Roblox Account",
            description=(
                "Click the button below to authorize with Roblox.\n\n"
                "After authorizing, return to Discord and click **Complete Link**."
            ),
            color=0x5865F2,
        )

        view = CompleteLinkView(self.bot)
        view.add_item(
            ui.Button(
                label="Authorize with Roblox",
                style=discord.ButtonStyle.link,
                url=oauth_url,
            )
        )

        await interaction.response.send_message(
            embed=embed, view=view, ephemeral=True
        )

    @app_commands.command(
        name="unlink", description="Unlink your Roblox account"
    )
    async def unlink(self, interaction: discord.Interaction) -> None:
        existing = await self.bot.db.get_linked_account(interaction.user.id)
        if not existing:
            await interaction.response.send_message(
                embed=error_embed(
                    "Not Linked", "You do not have a linked Roblox account."
                ),
                ephemeral=True,
            )
            return

        await self.bot.db.unlink_account(interaction.user.id)
        await interaction.response.send_message(
            embed=success_embed("Unlinked", "Your Roblox account has been unlinked."),
            ephemeral=True,
        )


async def setup(bot: NJRPBot) -> None:
    await bot.add_cog(RobloxLink(bot))
