"""
Bot configuration settings.

All configurable values are stored here. Update these values with your
actual Discord Role IDs, Channel IDs, and User IDs before running the bot.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Bot Core ────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
BOT_PREFIX: str = os.getenv("BOT_PREFIX", "!")
GUILD_ID: int = int(os.getenv("GUILD_ID", "0"))

# ─── ERLC API ────────────────────────────────────────────────────────────────
ERLC_API_KEY: str = os.getenv("ERLC_API_KEY", "")
ERLC_SERVER_ID: str = os.getenv("ERLC_SERVER_ID", "")

# ─── Roblox ──────────────────────────────────────────────────────────────────
ROBLOX_API_KEY: str = os.getenv("ROBLOX_API_KEY", "")

# ─── Roblox OAuth 2.0 ────────────────────────────────────────────────────────
ROBLOX_CLIENT_ID: str = os.getenv("ROBLOX_CLIENT_ID", "")
ROBLOX_CLIENT_SECRET: str = os.getenv("ROBLOX_CLIENT_SECRET", "")
ROBLOX_REDIRECT_URI: str = os.getenv("ROBLOX_REDIRECT_URI", "http://localhost:8080/roblox/callback")
ROBLOX_OAUTH_PORT: int = int(os.getenv("ROBLOX_OAUTH_PORT", "8080"))

# ─── Channels ────────────────────────────────────────────────────────────────
INFRACTION_LOG_CHANNEL_ID: int = int(os.getenv("INFRACTION_LOG_CHANNEL_ID", "0"))

# ─── Jishaku Authorized User IDs ─────────────────────────────────────────────
# Add Discord User IDs (as integers) of users allowed to use JSK commands.
JSK_AUTHORIZED_USERS: list[int] = [
    # 123456789012345678,  # Example: Your Discord User ID
]

# ─── Admin Panel Authorized Role IDs ─────────────────────────────────────────
# Add Discord Role IDs (as integers) that can access the admin panel.
ADMIN_PANEL_ROLE_IDS: list[int] = [
    # 123456789012345678,  # Example: Admin Role
]

# ─── Infraction Command Authorized Role IDs ──────────────────────────────────
INFRACTION_ROLE_IDS: list[int] = [
    # 123456789012345678,  # Example: Moderator Role
]

# ─── Session Command Authorized Role IDs ─────────────────────────────────────
SESSION_ROLE_IDS: list[int] = [
    # 123456789012345678,  # Example: Session Host Role
]

# ─── Session Config Command Authorized Role IDs ─────────────────────────────
# Separate from SESSION_ROLE_IDS — controls who can use /config session.
SESSION_CONFIG_ROLE_IDS: list[int] = [
    # 123456789012345678,  # Example: Admin Role
]

# ─── Staff Roles (removed during lockdown) ───────────────────────────────────
STAFF_ROLE_IDS: list[int] = [
    # 123456789012345678,  # Example: Staff Role
]

# ─── Valid Punishment Types ──────────────────────────────────────────────────
VALID_PUNISHMENTS: list[str] = [
    "Warning",
    "Strike",
    "Suspension",
    "Termination",
    "Blacklist",
    "Under Investigation",
    "Retirement",
]

# Punishments that trigger ERLC permission removal
ERLC_REMOVAL_PUNISHMENTS: list[str] = [
    "Suspension",
    "Termination",
    "Blacklist",
    "Under Investigation",
    "Retirement",
]

# ─── Department Servers ──────────────────────────────────────────────────────
# Map of department name -> Discord Guild ID.
DEPARTMENT_GUILDS: dict[str, int] = {
    "Department Hub": 1482782359144108152,
    "Police Department": 1473736892431470614,
    "State Police": 1424814688339755020,
    "Medical Center": 1477711167580274688,
    "Fire & Rescue": 1475593954824290345,
    "Department of Justice": 1253324336962736190,
    "Department of Transportation": 1479557928011960503,
}

# ─── Embed Colors ────────────────────────────────────────────────────────────
EMBED_COLOR_PRIMARY: int = 0x2B2D31
EMBED_COLOR_SUCCESS: int = 0x57F287
EMBED_COLOR_ERROR: int = 0xED4245
EMBED_COLOR_WARNING: int = 0xFEE75C
EMBED_COLOR_INFO: int = 0x5865F2

# ─── Database ────────────────────────────────────────────────────────────────
DATABASE_PATH: str = "database/bot.db"
