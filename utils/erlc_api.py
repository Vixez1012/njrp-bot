"""
ERLC (Emergency Response: Liberty County) API handler.

Provides methods to interact with the ERLC API for server management,
including removing moderator/admin permissions from users.
"""

import aiohttp
import logging
from typing import Optional

from config.settings import ERLC_API_KEY, ERLC_SERVER_ID

logger = logging.getLogger(__name__)

BASE_URL = "https://api.policeroleplay.community/v1"


class ERLCApi:
    """Handler for ERLC Private Server API calls."""

    def __init__(self) -> None:
        self.api_key = ERLC_API_KEY
        self.server_id = ERLC_SERVER_ID
        self.headers = {
            "Server-Key": self.api_key,
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[dict] = None,
    ) -> Optional[dict]:
        url = f"{BASE_URL}/server/{endpoint}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method, url, headers=self.headers, json=json_data
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    logger.error(
                        "ERLC API %s %s returned %s: %s",
                        method,
                        endpoint,
                        resp.status,
                        await resp.text(),
                    )
                    return None
        except aiohttp.ClientError as exc:
            logger.error("ERLC API request failed: %s", exc)
            return None

    async def get_server_info(self) -> Optional[dict]:
        """Fetch current server information."""
        return await self._request("GET", "")

    async def get_server_status(self) -> Optional[dict]:
        """Fetch server status with players and queue via v2 API."""
        url = "https://api.erlc.gg/v2/server?Players=true&Queue=true"
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"server-key": self.api_key}
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    logger.error(
                        "ERLC v2 API GET /v2/server returned %s: %s",
                        resp.status,
                        await resp.text(),
                    )
                    return None
        except aiohttp.ClientError as exc:
            logger.error("ERLC v2 API request failed: %s", exc)
            return None

    async def get_players(self) -> Optional[list]:
        """Fetch the list of current players."""
        return await self._request("GET", "players")

    async def run_command(self, command: str) -> Optional[dict]:
        """Execute a command on the ERLC server."""
        return await self._request(
            "POST", "command", json_data={"command": command}
        )

    async def unadmin_player(self, roblox_username: str) -> bool:
        """Remove admin from a player in the ERLC server."""
        result = await self.run_command(f":unadmin {roblox_username}")
        if result is not None:
            logger.info("Removed admin from %s in ERLC.", roblox_username)
            return True
        logger.warning("Failed to unadmin %s in ERLC.", roblox_username)
        return False

    async def unmod_player(self, roblox_username: str) -> bool:
        """Remove moderator from a player in the ERLC server."""
        result = await self.run_command(f":unmod {roblox_username}")
        if result is not None:
            logger.info("Removed mod from %s in ERLC.", roblox_username)
            return True
        logger.warning("Failed to unmod %s in ERLC.", roblox_username)
        return False

    async def remove_permissions(self, roblox_username: str) -> None:
        """Remove both admin and mod permissions from a player."""
        await self.unadmin_player(roblox_username)
        await self.unmod_player(roblox_username)
