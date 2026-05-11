# NJRP Bot — New Jersey Roleplay Discord Bot

A production-ready Discord bot for the **New Jersey Roleplay** ERLC community, built with Python and [discord.py](https://discordpy.readthedocs.io/).

## Features

- **Admin Panel** — Interactive UI with buttons, dropdowns, and modals for member management, command toggling, and server analytics
- **Member Management** — View Discord/Roblox info, infractions, flags, blacklist status; link Roblox accounts manually
- **Command & Event Management** — Enable/disable any command or event system, persisted in the database
- **Emergency Lockdown** — Lock all channels, remove staff roles; fully reversible with a single button
- **Infraction System** — Issue warnings, strikes, suspensions, terminations, blacklists, and more; auto-removes ERLC permissions for severe punishments
- **Session System** — Slash command to announce server startups, shutdowns, votes, low/full player counts with configurable embeds and role pings
- **Session Configuration** — Change channel, ping roles, embed colors, cooldowns, and texts via `/config session`
- **Roblox Link** — Verification code flow to link Discord accounts to Roblox; prevents duplicate linking
- **MyInfo** — Users can view their own Discord info, Roblox link status, flags, and infractions
- **Jishaku** — Developer debugging tool with configurable user authorization
- **Blacklist Middleware** — Blacklisted users cannot use any bot commands
- **Centralized Error Handler** — User-friendly error messages for all command types
- **SQLite Database** — Persistent storage for all data across restarts

## Project Structure

```
njrp-bot/
├── bot.py                  # Main entry point
├── requirements.txt        # Python dependencies
├── .env.example            # Example environment variables
├── .gitignore
├── config/
│   ├── __init__.py
│   └── settings.py         # All configurable values
├── cogs/
│   ├── __init__.py
│   ├── admin_panel.py      # Admin panel prefix command
│   ├── error_handler.py    # Centralized error handler
│   ├── infractions.py      # Infraction system
│   ├── myinfo.py           # MyInfo command
│   ├── roblox_link.py      # /link and /unlink commands
│   ├── sessions.py         # /session slash command
│   └── session_config.py   # /config session slash command
├── database/
│   ├── __init__.py
│   └── manager.py          # Async SQLite database manager
├── utils/
│   ├── __init__.py
│   ├── checks.py           # Permission checks and middleware
│   ├── embeds.py           # Reusable embed builders
│   ├── erlc_api.py         # ERLC Private Server API handler
│   └── roblox_api.py       # Roblox API utilities
├── views/
│   ├── __init__.py
│   └── admin_panel.py      # Admin panel UI views (buttons, modals, selects)
└── logs/
    └── .gitkeep
```

## Prerequisites

- Python **3.10+**
- A Discord Bot application with the following **Privileged Gateway Intents** enabled:
  - Server Members Intent
  - Message Content Intent
  - Presence Intent
- Bot must be invited with `applications.commands` scope for slash commands

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/Vixez1012/njrp-bot.git
cd njrp-bot
```

### 2. Create a Virtual Environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` and set:

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Your Discord bot token from the [Discord Developer Portal](https://discord.com/developers/applications) |
| `BOT_PREFIX` | Command prefix (default: `!`) |
| `GUILD_ID` | Your Discord server ID |
| `ERLC_API_KEY` | Your ERLC Private Server API key |
| `ERLC_SERVER_ID` | Your ERLC server ID |
| `ROBLOX_API_KEY` | Your Roblox API key (if applicable) |
| `INFRACTION_LOG_CHANNEL_ID` | Channel ID where infraction logs are sent |

### 5. Configure Role IDs, Channel IDs, and Authorized Users

Open `config/settings.py` and fill in:

- **`JSK_AUTHORIZED_USERS`** — Discord User IDs allowed to use Jishaku debug commands
- **`ADMIN_PANEL_ROLE_IDS`** — Role IDs that can access the admin panel
- **`INFRACTION_ROLE_IDS`** — Role IDs that can issue infractions
- **`SESSION_ROLE_IDS`** — Role IDs that can use `/session` commands
- **`SESSION_CONFIG_ROLE_IDS`** — Role IDs that can use `/config session` (separate from session hosts)
- **`STAFF_ROLE_IDS`** — Role IDs removed during emergency lockdown

### 6. Run the Bot

```bash
python bot.py
```

## Where to Insert Values

| Value | Location |
|---|---|
| Bot Token | `.env` → `BOT_TOKEN` |
| Role IDs (Admin, Infraction, Session, Session Config, Staff) | `config/settings.py` |
| Channel IDs (Infraction Log) | `.env` → `INFRACTION_LOG_CHANNEL_ID` |
| ERLC API Key | `.env` → `ERLC_API_KEY` |
| ERLC Server ID | `.env` → `ERLC_SERVER_ID` |
| Roblox API Key | `.env` → `ROBLOX_API_KEY` |
| JSK Authorized User IDs | `config/settings.py` → `JSK_AUTHORIZED_USERS` |

## Commands

### Prefix Commands (default prefix: `!`)

| Command | Description | Permissions |
|---|---|---|
| `!adminpanel` | Opens the admin panel UI | Admin Panel Roles |
| `!infract @user <punishment> <reason>` | Issue an infraction | Infraction Roles |
| `!myinfo` | View your own profile info | Everyone |

### Slash Commands

| Command | Description | Permissions |
|---|---|---|
| `/session start <option>` | Send a session announcement | Session Roles |
| `/config session` | Configure the session system | Session Roles |
| `/link` | Link your Discord to Roblox | Everyone |
| `/unlink` | Unlink your Roblox account | Everyone |

### Jishaku (Debug)

Jishaku commands are restricted to user IDs listed in `JSK_AUTHORIZED_USERS`.

## Valid Punishment Types

- Warning
- Strike
- Suspension
- Termination
- Blacklist
- Under Investigation
- Retirement

Punishments of **Suspension**, **Termination**, **Blacklist**, **Under Investigation**, or **Retirement** will automatically remove the user's admin/mod permissions in ERLC.

## Database

The bot uses **SQLite** (`database/bot.db`), created automatically on first run. Tables:

- `linked_accounts` — Discord-to-Roblox links
- `infractions` — Infraction history
- `flags` — Custom user flags
- `blacklist` — Blacklisted users
- `command_states` — Enabled/disabled commands
- `event_states` — Enabled/disabled events
- `lockdown_data` — Saved channel permissions during lockdown
- `lockdown_roles` — Saved role assignments during lockdown
- `lockdown_state` — Lockdown active/inactive state
- `session_config` — Session system configuration
- `verification_codes` — Roblox link verification codes

## License

This project is for the NJRP community. All rights reserved.
