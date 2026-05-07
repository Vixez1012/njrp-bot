"""
NJRP Bot — Main entry point.

A production-ready Discord bot for the New Jersey Roleplay ERLC community.
Uses a modular cog-based architecture with discord.py.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

import discord
from discord.ext import commands

from config.settings import BOT_TOKEN, BOT_PREFIX, GUILD_ID, JSK_AUTHORIZED_USERS
from database.manager import DatabaseManager
from utils.checks import blacklist_check, command_enabled_check

# ─── Logging Setup ───────────────────────────────────────────────────────────

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("njrp")

# ─── Intents ─────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True

# ─── Bot Class ───────────────────────────────────────────────────────────────


class NJRPBot(commands.Bot):
    """Custom bot class with database integration and automatic cog loading."""

    def __init__(self) -> None:
        super().__init__(
            command_prefix=BOT_PREFIX,
            intents=intents,
            help_command=commands.DefaultHelpCommand(),
            case_insensitive=True,
        )
        self.db = DatabaseManager()

    async def setup_hook(self) -> None:
        """Called when the bot is starting up. Loads cogs and syncs commands."""
        # Connect database
        await self.db.connect()
        logger.info("Database connected.")

        # Add global checks
        self.add_check(blacklist_check)
        self.add_check(command_enabled_check)

        # Load Jishaku with authorization guard
        try:
            await self.load_extension("jishaku")
            logger.info("Jishaku loaded.")
        except Exception as exc:
            logger.warning("Failed to load Jishaku: %s", exc)

        # Auto-load all cogs from the cogs/ directory
        cogs_dir = Path("cogs")
        for filepath in sorted(cogs_dir.glob("*.py")):
            if filepath.name.startswith("_"):
                continue
            cog_name = f"cogs.{filepath.stem}"
            try:
                await self.load_extension(cog_name)
                logger.info("Loaded cog: %s", cog_name)
            except Exception as exc:
                logger.error("Failed to load cog %s: %s", cog_name, exc)

        # Sync slash commands to the guild
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Slash commands synced to guild %s.", GUILD_ID)
        else:
            await self.tree.sync()
            logger.info("Slash commands synced globally.")

    async def on_ready(self) -> None:
        """Called when the bot is fully connected."""
        logger.info("Logged in as %s (ID: %s)", self.user, self.user.id if self.user else "?")
        logger.info("Connected to %d guild(s).", len(self.guilds))

        # Set bot status: Watching New Jersey Roleplay
        activity = discord.Activity(
            type=discord.ActivityType.watching, name="New Jersey Roleplay"
        )
        await self.change_presence(activity=activity)
        logger.info("Status set to: Watching New Jersey Roleplay")

    async def on_message(self, message: discord.Message) -> None:
        """Process messages, enforcing Jishaku authorization."""
        if message.author.bot:
            return

        # Block unauthorized Jishaku usage
        if message.content and message.content.strip().lower().startswith(
            (f"{BOT_PREFIX}jsk", f"{BOT_PREFIX}jishaku")
        ):
            if message.author.id not in JSK_AUTHORIZED_USERS:
                embed = discord.Embed(
                    title="Access Denied",
                    description="You are not authorized to use Jishaku commands.",
                    color=0xED4245,
                )
                await message.channel.send(embed=embed)
                return

        await self.process_commands(message)

    async def close(self) -> None:
        """Clean up on shutdown."""
        await self.db.close()
        await super().close()


# ─── Startup ─────────────────────────────────────────────────────────────────


def main() -> None:
    """Validate configuration and start the bot."""
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN is not set. Add it to your .env file.")
        sys.exit(1)

    bot = NJRPBot()

    async def runner() -> None:
        async with bot:
            await bot.start(BOT_TOKEN)

    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        logger.info("Bot shut down by user.")


if __name__ == "__main__":
    main()
