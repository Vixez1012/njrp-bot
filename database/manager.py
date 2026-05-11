"""
Database manager using aiosqlite for persistent storage.

Handles all CRUD operations for users, infractions, flags, linked accounts,
command states, lockdown data, and session configuration.
"""

import aiosqlite
import logging
import uuid
from datetime import datetime
from typing import Optional

from config.settings import DATABASE_PATH

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Async SQLite database manager."""

    def __init__(self) -> None:
        self.db_path = DATABASE_PATH
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Open the database connection and create tables."""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._create_tables()
        logger.info("Database connected and tables initialized.")

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            logger.info("Database connection closed.")

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._db

    # ─── Table Creation ──────────────────────────────────────────────────

    async def _create_tables(self) -> None:
        await self._create_schema()
        await self._run_migrations()

    async def _run_migrations(self) -> None:
        """Add columns that may be missing in databases created before updates."""
        image_columns = [
            "ssu_image", "ssd_image", "vote_image", "low_image", "full_image"
        ]
        for col in image_columns:
            try:
                await self.db.execute(
                    f"ALTER TABLE session_config ADD COLUMN {col} TEXT DEFAULT ''"
                )
            except Exception:
                pass  # Column already exists
        await self.db.commit()

    async def _create_schema(self) -> None:
        await self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS linked_accounts (
                discord_id   INTEGER PRIMARY KEY,
                roblox_id    INTEGER NOT NULL,
                roblox_name  TEXT    NOT NULL,
                linked_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS infractions (
                infraction_id TEXT    PRIMARY KEY,
                discord_id    INTEGER NOT NULL,
                moderator_id  INTEGER NOT NULL,
                punishment    TEXT    NOT NULL,
                reason        TEXT    NOT NULL,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS flags (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id INTEGER NOT NULL,
                flag_text  TEXT    NOT NULL,
                added_by   INTEGER NOT NULL,
                added_at   TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS blacklist (
                discord_id    INTEGER PRIMARY KEY,
                blacklisted   INTEGER NOT NULL DEFAULT 0,
                blacklisted_by INTEGER,
                blacklisted_at TEXT
            );

            CREATE TABLE IF NOT EXISTS command_states (
                command_name TEXT PRIMARY KEY,
                enabled      INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS event_states (
                event_name TEXT PRIMARY KEY,
                enabled    INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS lockdown_data (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id       INTEGER NOT NULL,
                overwrites_json  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lockdown_roles (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                role_id    INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lockdown_state (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS session_config (
                guild_id         INTEGER PRIMARY KEY,
                channel_id       INTEGER,
                ping_roles       TEXT    DEFAULT '[]',
                embed_color      INTEGER DEFAULT 5793266,
                vote_threshold   INTEGER DEFAULT 5,
                cooldown_seconds INTEGER DEFAULT 60,
                ssu_text         TEXT    DEFAULT 'The server is starting up! Join now.',
                ssd_text         TEXT    DEFAULT 'The server is shutting down. Thank you for playing!',
                vote_text        TEXT    DEFAULT 'Vote for a session! React to participate.',
                low_text         TEXT    DEFAULT 'Player count is low. Join the server!',
                full_text        TEXT    DEFAULT 'The server is full! Please wait for a slot.',
                ssu_image        TEXT    DEFAULT '',
                ssd_image        TEXT    DEFAULT '',
                vote_image       TEXT    DEFAULT '',
                low_image        TEXT    DEFAULT '',
                full_image       TEXT    DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS verification_codes (
                discord_id  INTEGER PRIMARY KEY,
                code        TEXT    NOT NULL,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        await self.db.commit()

    # ─── Linked Accounts ─────────────────────────────────────────────────

    async def link_account(
        self, discord_id: int, roblox_id: int, roblox_name: str
    ) -> None:
        await self.db.execute(
            "INSERT OR REPLACE INTO linked_accounts (discord_id, roblox_id, roblox_name, linked_at) "
            "VALUES (?, ?, ?, ?)",
            (discord_id, roblox_id, roblox_name, datetime.utcnow().isoformat()),
        )
        await self.db.commit()

    async def unlink_account(self, discord_id: int) -> None:
        await self.db.execute(
            "DELETE FROM linked_accounts WHERE discord_id = ?", (discord_id,)
        )
        await self.db.commit()

    async def get_linked_account(self, discord_id: int) -> Optional[aiosqlite.Row]:
        async with self.db.execute(
            "SELECT * FROM linked_accounts WHERE discord_id = ?", (discord_id,)
        ) as cursor:
            return await cursor.fetchone()

    async def get_linked_by_roblox(self, roblox_id: int) -> Optional[aiosqlite.Row]:
        async with self.db.execute(
            "SELECT * FROM linked_accounts WHERE roblox_id = ?", (roblox_id,)
        ) as cursor:
            return await cursor.fetchone()

    async def get_linked_count(self) -> int:
        async with self.db.execute("SELECT COUNT(*) FROM linked_accounts") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    # ─── Infractions ─────────────────────────────────────────────────────

    async def add_infraction(
        self,
        discord_id: int,
        moderator_id: int,
        punishment: str,
        reason: str,
    ) -> str:
        infraction_id = str(uuid.uuid4())[:8].upper()
        await self.db.execute(
            "INSERT INTO infractions (infraction_id, discord_id, moderator_id, punishment, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                infraction_id,
                discord_id,
                moderator_id,
                punishment,
                reason,
                datetime.utcnow().isoformat(),
            ),
        )
        await self.db.commit()
        return infraction_id

    async def get_infractions(self, discord_id: int) -> list[aiosqlite.Row]:
        async with self.db.execute(
            "SELECT * FROM infractions WHERE discord_id = ? ORDER BY created_at DESC",
            (discord_id,),
        ) as cursor:
            return await cursor.fetchall()

    async def get_infraction_count(self, discord_id: int) -> int:
        async with self.db.execute(
            "SELECT COUNT(*) FROM infractions WHERE discord_id = ?", (discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    # ─── Flags ───────────────────────────────────────────────────────────

    async def add_flag(self, discord_id: int, flag_text: str, added_by: int) -> None:
        await self.db.execute(
            "INSERT INTO flags (discord_id, flag_text, added_by, added_at) VALUES (?, ?, ?, ?)",
            (discord_id, flag_text, added_by, datetime.utcnow().isoformat()),
        )
        await self.db.commit()

    async def remove_flag(self, flag_id: int) -> None:
        await self.db.execute("DELETE FROM flags WHERE id = ?", (flag_id,))
        await self.db.commit()

    async def get_flags(self, discord_id: int) -> list[aiosqlite.Row]:
        async with self.db.execute(
            "SELECT * FROM flags WHERE discord_id = ?", (discord_id,)
        ) as cursor:
            return await cursor.fetchall()

    # ─── Blacklist ───────────────────────────────────────────────────────

    async def set_blacklist(
        self, discord_id: int, blacklisted: bool, blacklisted_by: Optional[int] = None
    ) -> None:
        await self.db.execute(
            "INSERT OR REPLACE INTO blacklist (discord_id, blacklisted, blacklisted_by, blacklisted_at) "
            "VALUES (?, ?, ?, ?)",
            (
                discord_id,
                1 if blacklisted else 0,
                blacklisted_by,
                datetime.utcnow().isoformat() if blacklisted else None,
            ),
        )
        await self.db.commit()

    async def is_blacklisted(self, discord_id: int) -> bool:
        async with self.db.execute(
            "SELECT blacklisted FROM blacklist WHERE discord_id = ?", (discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return bool(row and row[0])

    # ─── Command / Event States ──────────────────────────────────────────

    async def set_command_state(self, command_name: str, enabled: bool) -> None:
        await self.db.execute(
            "INSERT OR REPLACE INTO command_states (command_name, enabled) VALUES (?, ?)",
            (command_name, 1 if enabled else 0),
        )
        await self.db.commit()

    async def is_command_enabled(self, command_name: str) -> bool:
        async with self.db.execute(
            "SELECT enabled FROM command_states WHERE command_name = ?",
            (command_name,),
        ) as cursor:
            row = await cursor.fetchone()
            return bool(row[0]) if row else True  # default enabled

    async def get_all_command_states(self) -> dict[str, bool]:
        async with self.db.execute("SELECT * FROM command_states") as cursor:
            rows = await cursor.fetchall()
            return {row["command_name"]: bool(row["enabled"]) for row in rows}

    async def set_event_state(self, event_name: str, enabled: bool) -> None:
        await self.db.execute(
            "INSERT OR REPLACE INTO event_states (event_name, enabled) VALUES (?, ?)",
            (event_name, 1 if enabled else 0),
        )
        await self.db.commit()

    async def is_event_enabled(self, event_name: str) -> bool:
        async with self.db.execute(
            "SELECT enabled FROM event_states WHERE event_name = ?", (event_name,)
        ) as cursor:
            row = await cursor.fetchone()
            return bool(row[0]) if row else True

    async def get_all_event_states(self) -> dict[str, bool]:
        async with self.db.execute("SELECT * FROM event_states") as cursor:
            rows = await cursor.fetchall()
            return {row["event_name"]: bool(row["enabled"]) for row in rows}

    # ─── Lockdown ────────────────────────────────────────────────────────

    async def save_lockdown_overwrites(
        self, channel_id: int, overwrites_json: str
    ) -> None:
        await self.db.execute(
            "INSERT INTO lockdown_data (channel_id, overwrites_json) VALUES (?, ?)",
            (channel_id, overwrites_json),
        )
        await self.db.commit()

    async def get_lockdown_overwrites(self) -> list[aiosqlite.Row]:
        async with self.db.execute("SELECT * FROM lockdown_data") as cursor:
            return await cursor.fetchall()

    async def clear_lockdown_overwrites(self) -> None:
        await self.db.execute("DELETE FROM lockdown_data")
        await self.db.commit()

    async def save_lockdown_role(self, user_id: int, role_id: int) -> None:
        await self.db.execute(
            "INSERT INTO lockdown_roles (user_id, role_id) VALUES (?, ?)",
            (user_id, role_id),
        )
        await self.db.commit()

    async def get_lockdown_roles(self) -> list[aiosqlite.Row]:
        async with self.db.execute("SELECT * FROM lockdown_roles") as cursor:
            return await cursor.fetchall()

    async def clear_lockdown_roles(self) -> None:
        await self.db.execute("DELETE FROM lockdown_roles")
        await self.db.commit()

    async def set_lockdown_state(self, key: str, value: str) -> None:
        await self.db.execute(
            "INSERT OR REPLACE INTO lockdown_state (key, value) VALUES (?, ?)",
            (key, value),
        )
        await self.db.commit()

    async def get_lockdown_state(self, key: str) -> Optional[str]:
        async with self.db.execute(
            "SELECT value FROM lockdown_state WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def clear_lockdown_state(self) -> None:
        await self.db.execute("DELETE FROM lockdown_state")
        await self.db.commit()

    # ─── Session Config ──────────────────────────────────────────────────

    async def get_session_config(self, guild_id: int) -> Optional[aiosqlite.Row]:
        async with self.db.execute(
            "SELECT * FROM session_config WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            return await cursor.fetchone()

    async def upsert_session_config(self, guild_id: int, **kwargs: object) -> None:
        existing = await self.get_session_config(guild_id)
        if existing is None:
            columns = "guild_id, " + ", ".join(kwargs.keys())
            placeholders = "?, " + ", ".join("?" for _ in kwargs)
            values = [guild_id] + list(kwargs.values())
            await self.db.execute(
                f"INSERT INTO session_config ({columns}) VALUES ({placeholders})",
                values,
            )
        else:
            set_clause = ", ".join(f"{k} = ?" for k in kwargs)
            values = list(kwargs.values()) + [guild_id]
            await self.db.execute(
                f"UPDATE session_config SET {set_clause} WHERE guild_id = ?",
                values,
            )
        await self.db.commit()

    # ─── Verification Codes ──────────────────────────────────────────────

    async def save_verification_code(self, discord_id: int, code: str) -> None:
        await self.db.execute(
            "INSERT OR REPLACE INTO verification_codes (discord_id, code, created_at) "
            "VALUES (?, ?, ?)",
            (discord_id, code, datetime.utcnow().isoformat()),
        )
        await self.db.commit()

    async def get_verification_code(self, discord_id: int) -> Optional[str]:
        async with self.db.execute(
            "SELECT code FROM verification_codes WHERE discord_id = ?", (discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def delete_verification_code(self, discord_id: int) -> None:
        await self.db.execute(
            "DELETE FROM verification_codes WHERE discord_id = ?", (discord_id,)
        )
        await self.db.commit()
