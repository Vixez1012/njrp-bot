"""
Reusable embed builders for consistency across the bot.
"""

import discord
from datetime import datetime

from config.settings import (
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_SUCCESS,
    EMBED_COLOR_ERROR,
    EMBED_COLOR_WARNING,
    EMBED_COLOR_INFO,
)


def success_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=EMBED_COLOR_SUCCESS,
        timestamp=datetime.utcnow(),
    )


def error_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=EMBED_COLOR_ERROR,
        timestamp=datetime.utcnow(),
    )


def warning_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=EMBED_COLOR_WARNING,
        timestamp=datetime.utcnow(),
    )


def info_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=EMBED_COLOR_INFO,
        timestamp=datetime.utcnow(),
    )


def primary_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=EMBED_COLOR_PRIMARY,
        timestamp=datetime.utcnow(),
    )
