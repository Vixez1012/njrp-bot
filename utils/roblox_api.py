"""
Roblox API utilities for user lookup and verification.
"""

import aiohttp
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def get_user_by_username(username: str) -> Optional[dict]:
    """Look up a Roblox user by username. Returns dict with 'id' and 'name'."""
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [username], "excludeBannedUsers": False}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    users = data.get("data", [])
                    if users:
                        return {"id": users[0]["id"], "name": users[0]["name"]}
        return None
    except aiohttp.ClientError as exc:
        logger.error("Roblox username lookup failed: %s", exc)
        return None


async def get_user_by_id(user_id: int) -> Optional[dict]:
    """Look up a Roblox user by ID. Returns dict with 'id', 'name', 'description'."""
    url = f"https://users.roblox.com/v1/users/{user_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "id": data.get("id"),
                        "name": data.get("name"),
                        "description": data.get("description", ""),
                    }
        return None
    except aiohttp.ClientError as exc:
        logger.error("Roblox user ID lookup failed: %s", exc)
        return None


async def check_profile_for_code(user_id: int, code: str) -> bool:
    """Check if a Roblox user's profile description contains the verification code."""
    user = await get_user_by_id(user_id)
    if user and code in user.get("description", ""):
        return True
    return False
