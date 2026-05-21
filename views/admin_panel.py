"""
Admin Panel Discord UI Views — buttons, dropdowns, modals, and embeds.

Sections:
  1. Member Management
  2. Command Management
  3. Server Management (including Emergency Lockdown)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import discord
from discord import ui

from config.settings import (
    ADMIN_PANEL_ROLE_IDS,
    DEPARTMENT_GUILDS,
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_SUCCESS,
    EMBED_COLOR_ERROR,
    EMBED_COLOR_WARNING,
    GUILD_ID,
    STAFF_ROLE_IDS,
)
from utils.embeds import success_embed, error_embed, info_embed, primary_embed

if TYPE_CHECKING:
    from bot import NJRPBot

logger = logging.getLogger(__name__)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _has_admin_role(member: discord.Member) -> bool:
    return any(role.id in ADMIN_PANEL_ROLE_IDS for role in member.roles)


async def _reject(interaction: discord.Interaction) -> bool:
    """Send an error if the user lacks admin panel roles. Returns True if rejected."""
    if not isinstance(interaction.user, discord.Member) or not _has_admin_role(interaction.user):
        await interaction.response.send_message(
            embed=error_embed("Access Denied", "You do not have permission to use this panel."),
            ephemeral=True,
        )
        return True
    return False


# ─── Main Panel View ────────────────────────────────────────────────────────

class AdminPanelView(ui.View):
    """Root view for the admin panel with a dropdown select menu."""

    def __init__(self, bot: NJRPBot) -> None:
        super().__init__(timeout=300)
        self.bot = bot

    @ui.select(
        placeholder="Select a section...",
        options=[
            discord.SelectOption(label="Member Management", value="member", emoji="👤", description="Search members, view info, manage flags & blacklist"),
            discord.SelectOption(label="Command Management", value="command", emoji="⚙️", description="Enable or disable commands and events"),
            discord.SelectOption(label="Server Management", value="server", emoji="🖥️", description="Server analytics & emergency lockdown"),
        ],
    )
    async def section_select(self, interaction: discord.Interaction, select: ui.Select) -> None:
        if await _reject(interaction):
            return

        choice = select.values[0]

        if choice == "member":
            await interaction.response.send_message(
                embed=info_embed(
                    "Member Management",
                    "Enter a Discord User ID or @mention to search for a member.",
                ),
                view=MemberSearchView(self.bot),
                ephemeral=True,
            )
        elif choice == "command":
            embed = await self._build_command_embed()
            await interaction.response.send_message(
                embed=embed,
                view=CommandManagementView(self.bot),
                ephemeral=True,
            )
        elif choice == "server":
            embed = await self._build_server_embed(interaction)
            await interaction.response.send_message(
                embed=embed,
                view=ServerManagementView(self.bot),
                ephemeral=True,
            )

    async def _build_command_embed(self) -> discord.Embed:
        cmd_states = await self.bot.db.get_all_command_states()
        evt_states = await self.bot.db.get_all_event_states()

        all_cmds: list[str] = []
        for cmd in self.bot.commands:
            name = cmd.qualified_name
            enabled = cmd_states.get(name, True)
            status = "🟢" if enabled else "🔴"
            all_cmds.append(f"{status} `{name}`")

        all_events = ["on_member_join", "on_member_remove", "on_message"]
        event_lines: list[str] = []
        for evt in all_events:
            enabled = evt_states.get(evt, True)
            status = "🟢" if enabled else "🔴"
            event_lines.append(f"{status} `{evt}`")

        embed = primary_embed("Command & Event Management")
        embed.add_field(
            name="Commands",
            value="\n".join(all_cmds) if all_cmds else "No commands loaded.",
            inline=False,
        )
        embed.add_field(
            name="Events / Systems",
            value="\n".join(event_lines) if event_lines else "No events tracked.",
            inline=False,
        )
        return embed

    async def _build_server_embed(self, interaction: discord.Interaction) -> discord.Embed:
        guild = interaction.guild
        if guild is None:
            return error_embed("Error", "This command can only be used in a server.")

        linked_count = await self.bot.db.get_linked_count()
        lockdown_active = await self.bot.db.get_lockdown_state("active")

        online = sum(
            1 for m in guild.members
            if m.status != discord.Status.offline
        )

        embed = primary_embed("Server Management")
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Online", value=str(online), inline=True)
        embed.add_field(name="Boosts", value=str(guild.premium_subscription_count), inline=True)
        embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Linked Users", value=str(linked_count), inline=True)
        embed.add_field(
            name="Lockdown Status",
            value="🔴 **ACTIVE**" if lockdown_active == "true" else "🟢 Normal",
            inline=False,
        )
        return embed


# ─── Member Management ──────────────────────────────────────────────────────

class MemberSearchView(ui.View):
    """Prompts for a member ID and displays their profile."""

    def __init__(self, bot: NJRPBot) -> None:
        super().__init__(timeout=120)
        self.bot = bot

    @ui.button(label="Search by User ID", style=discord.ButtonStyle.secondary)
    async def search_btn(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if await _reject(interaction):
            return
        await interaction.response.send_modal(MemberSearchModal(self.bot))


class MemberSearchModal(ui.Modal, title="Search Member"):
    user_input = ui.TextInput(label="Discord User ID or @mention", placeholder="e.g. 123456789012345678")

    def __init__(self, bot: NJRPBot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = self.user_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        try:
            user_id = int(raw)
        except ValueError:
            await interaction.response.send_message(
                embed=error_embed("Invalid Input", "Please provide a valid User ID."),
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if guild is None:
            return

        member = guild.get_member(user_id)
        if member is None:
            await interaction.response.send_message(
                embed=error_embed("Not Found", f"No member found with ID `{user_id}`."),
                ephemeral=True,
            )
            return

        embed = await self._build_member_embed(member)
        await interaction.response.send_message(
            embed=embed,
            view=MemberActionsView(self.bot, member),
            ephemeral=True,
        )

    async def _build_member_embed(self, member: discord.Member) -> discord.Embed:
        db = self.bot.db
        linked = await db.get_linked_account(member.id)
        flags = await db.get_flags(member.id)
        infraction_count = await db.get_infraction_count(member.id)
        is_bl = await db.is_blacklisted(member.id)

        embed = primary_embed(f"Member Info — {member}")
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(
            name="Created",
            value=discord.utils.format_dt(member.created_at, style="R"),
            inline=True,
        )
        embed.add_field(
            name="Joined",
            value=discord.utils.format_dt(member.joined_at, style="R") if member.joined_at else "Unknown",
            inline=True,
        )
        embed.add_field(
            name="Roles",
            value=", ".join(r.mention for r in member.roles[1:][:15]) or "None",
            inline=False,
        )

        if linked:
            embed.add_field(name="Roblox Username", value=linked["roblox_name"], inline=True)
            embed.add_field(name="Roblox ID", value=str(linked["roblox_id"]), inline=True)
        else:
            embed.add_field(name="Roblox Account", value="Not linked", inline=False)

        flag_text = ", ".join(f["flag_text"] for f in flags) if flags else "None"
        embed.add_field(name="Flags", value=flag_text, inline=False)
        embed.add_field(name="Infractions", value=str(infraction_count), inline=True)
        embed.add_field(name="Blacklisted", value="Yes" if is_bl else "No", inline=True)
        return embed


class MemberActionsView(ui.View):
    """Action buttons for a selected member."""

    def __init__(self, bot: NJRPBot, member: discord.Member) -> None:
        super().__init__(timeout=120)
        self.bot = bot
        self.member = member

    @ui.button(label="Link Roblox", style=discord.ButtonStyle.secondary, row=0)
    async def link_roblox(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if await _reject(interaction):
            return
        await interaction.response.send_modal(ManualLinkModal(self.bot, self.member))

    @ui.button(label="Toggle Blacklist", style=discord.ButtonStyle.danger, row=0)
    async def toggle_bl(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if await _reject(interaction):
            return
        is_bl = await self.bot.db.is_blacklisted(self.member.id)
        await self.bot.db.set_blacklist(self.member.id, not is_bl, interaction.user.id)
        status = "blacklisted" if not is_bl else "un-blacklisted"
        await interaction.response.send_message(
            embed=success_embed("Blacklist Updated", f"{self.member.mention} has been **{status}**."),
            ephemeral=True,
        )

    @ui.button(label="Add Flag", style=discord.ButtonStyle.secondary, row=1)
    async def add_flag(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if await _reject(interaction):
            return
        await interaction.response.send_modal(AddFlagModal(self.bot, self.member))

    @ui.button(label="Remove Flag", style=discord.ButtonStyle.secondary, row=1)
    async def remove_flag(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if await _reject(interaction):
            return
        flags = await self.bot.db.get_flags(self.member.id)
        if not flags:
            await interaction.response.send_message(
                embed=error_embed("No Flags", "This member has no flags to remove."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=info_embed("Remove Flag", "Select a flag to remove."),
            view=RemoveFlagView(self.bot, self.member, flags),
            ephemeral=True,
        )

    @ui.button(label="Ban from Departments", style=discord.ButtonStyle.danger, row=2)
    async def ban_departments(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if await _reject(interaction):
            return
        await interaction.response.send_message(
            embed=info_embed(
                "Ban from Departments",
                f"Select which servers to ban **{self.member}** from.",
            ),
            view=DepartmentBanSelectView(self.bot, self.member),
            ephemeral=True,
        )

    @ui.button(label="View Infractions", style=discord.ButtonStyle.secondary, row=1)
    async def view_infractions(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if await _reject(interaction):
            return
        infractions = await self.bot.db.get_infractions(self.member.id)
        if not infractions:
            await interaction.response.send_message(
                embed=info_embed("No Infractions", f"{self.member.mention} has no infractions."),
                ephemeral=True,
            )
            return

        embed = primary_embed(f"Infractions — {self.member}")
        for inf in infractions[:10]:
            embed.add_field(
                name=f"#{inf['infraction_id']} — {inf['punishment']}",
                value=f"**Reason:** {inf['reason']}\n**By:** <@{inf['moderator_id']}>\n**Date:** {inf['created_at']}",
                inline=False,
            )
        if len(infractions) > 10:
            embed.set_footer(text=f"Showing 10 of {len(infractions)} infractions.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ManualLinkModal(ui.Modal, title="Link Roblox Account"):
    roblox_username = ui.TextInput(label="Roblox Username", placeholder="e.g. builderman")
    roblox_id = ui.TextInput(label="Roblox User ID", placeholder="e.g. 156")

    def __init__(self, bot: NJRPBot, member: discord.Member) -> None:
        super().__init__()
        self.bot = bot
        self.member = member

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            rid = int(self.roblox_id.value.strip())
        except ValueError:
            await interaction.response.send_message(
                embed=error_embed("Invalid ID", "Roblox ID must be a number."),
                ephemeral=True,
            )
            return

        await self.bot.db.link_account(
            self.member.id, rid, self.roblox_username.value.strip()
        )
        await interaction.response.send_message(
            embed=success_embed(
                "Account Linked",
                f"Linked **{self.roblox_username.value.strip()}** ({rid}) to {self.member.mention}.",
            ),
            ephemeral=True,
        )


class AddFlagModal(ui.Modal, title="Add Custom Flag"):
    flag_text = ui.TextInput(
        label="Flag Text",
        placeholder="e.g. Flight Risk, Watchlisted, Staff Abuse Monitoring",
        max_length=100,
    )

    def __init__(self, bot: NJRPBot, member: discord.Member) -> None:
        super().__init__()
        self.bot = bot
        self.member = member

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.bot.db.add_flag(
            self.member.id, self.flag_text.value.strip(), interaction.user.id
        )
        await interaction.response.send_message(
            embed=success_embed(
                "Flag Added",
                f"Added flag **{self.flag_text.value.strip()}** to {self.member.mention}.",
            ),
            ephemeral=True,
        )


class RemoveFlagView(ui.View):
    def __init__(self, bot: NJRPBot, member: discord.Member, flags: list) -> None:
        super().__init__(timeout=60)
        options = [
            discord.SelectOption(label=f["flag_text"][:100], value=str(f["id"]))
            for f in flags[:25]
        ]
        self.add_item(RemoveFlagSelect(bot, member, options))


class RemoveFlagSelect(ui.Select):
    def __init__(
        self, bot: NJRPBot, member: discord.Member, options: list[discord.SelectOption]
    ) -> None:
        super().__init__(placeholder="Select a flag to remove", options=options)
        self.bot = bot
        self.member = member

    async def callback(self, interaction: discord.Interaction) -> None:
        if await _reject(interaction):
            return
        flag_id = int(self.values[0])
        await self.bot.db.remove_flag(flag_id)
        await interaction.response.send_message(
            embed=success_embed("Flag Removed", f"Flag removed from {self.member.mention}."),
            ephemeral=True,
        )


# ─── Department Ban ──────────────────────────────────────────────────────────

class DepartmentBanSelectView(ui.View):
    """Multi-select of departments (and main server) to ban a member from."""

    def __init__(self, bot: NJRPBot, member: discord.Member) -> None:
        super().__init__(timeout=120)
        self.bot = bot
        self.member = member

        options = [
            discord.SelectOption(label="Main Server", value=str(GUILD_ID), description="The main NJRP server"),
        ]
        for dept_name, guild_id in DEPARTMENT_GUILDS.items():
            options.append(
                discord.SelectOption(label=dept_name, value=str(guild_id))
            )

        self.add_item(DepartmentBanSelect(bot, member, options))


class DepartmentBanSelect(ui.Select):
    def __init__(
        self,
        bot: NJRPBot,
        member: discord.Member,
        options: list[discord.SelectOption],
    ) -> None:
        super().__init__(
            placeholder="Select servers to ban from...",
            options=options,
            min_values=1,
            max_values=len(options),
        )
        self.bot = bot
        self.member = member

    async def callback(self, interaction: discord.Interaction) -> None:
        if await _reject(interaction):
            return
        await interaction.response.send_modal(
            DepartmentBanReasonModal(self.bot, self.member, self.values)
        )


class DepartmentBanReasonModal(ui.Modal, title="Ban Reason"):
    reason_input = ui.TextInput(
        label="Reason for ban",
        placeholder="Enter the reason...",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=512,
    )

    def __init__(self, bot: NJRPBot, member: discord.Member, guild_ids: list[str]) -> None:
        super().__init__()
        self.bot = bot
        self.member = member
        self.guild_ids = [int(gid) for gid in guild_ids]

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        reason = self.reason_input.value.strip() or "No reason provided"
        results: list[str] = []

        # Build a name map for nice output
        name_map: dict[int, str] = {GUILD_ID: "Main Server"}
        for dept_name, gid in DEPARTMENT_GUILDS.items():
            name_map[gid] = dept_name

        for gid in self.guild_ids:
            guild = self.bot.get_guild(gid)
            label = name_map.get(gid, str(gid))
            if guild is None:
                results.append(f"❌ **{label}** — Bot not in server")
                continue
            try:
                await guild.ban(
                    self.member,
                    reason=f"Banned by {interaction.user} via admin panel: {reason}",
                    delete_message_days=0,
                )
                results.append(f"✅ **{label}** — Banned")
            except discord.Forbidden:
                results.append(f"❌ **{label}** — Missing permissions")
            except discord.HTTPException as exc:
                results.append(f"❌ **{label}** — {exc.text}")

        embed = primary_embed(f"Ban Results — {self.member}")
        embed.description = "\n".join(results)
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)


# ─── Command Management ─────────────────────────────────────────────────────

class CommandManagementView(ui.View):
    def __init__(self, bot: NJRPBot) -> None:
        super().__init__(timeout=120)
        self.bot = bot

    @ui.button(label="Toggle Command", style=discord.ButtonStyle.secondary, row=0)
    async def toggle_cmd(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if await _reject(interaction):
            return
        cmds = [cmd.qualified_name for cmd in self.bot.commands]
        if not cmds:
            await interaction.response.send_message(
                embed=error_embed("No Commands", "No commands are loaded."),
                ephemeral=True,
            )
            return
        options = [discord.SelectOption(label=c, value=c) for c in cmds[:25]]
        await interaction.response.send_message(
            embed=info_embed("Toggle Command", "Select a command to toggle."),
            view=ToggleCommandView(self.bot, options),
            ephemeral=True,
        )

    @ui.button(label="Toggle Event", style=discord.ButtonStyle.secondary, row=0)
    async def toggle_event(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if await _reject(interaction):
            return
        events = ["on_member_join", "on_member_remove", "on_message"]
        options = [discord.SelectOption(label=e, value=e) for e in events]
        await interaction.response.send_message(
            embed=info_embed("Toggle Event", "Select an event to toggle."),
            view=ToggleEventView(self.bot, options),
            ephemeral=True,
        )


class ToggleCommandView(ui.View):
    def __init__(self, bot: NJRPBot, options: list[discord.SelectOption]) -> None:
        super().__init__(timeout=60)
        self.add_item(ToggleCommandSelect(bot, options))


class ToggleCommandSelect(ui.Select):
    def __init__(self, bot: NJRPBot, options: list[discord.SelectOption]) -> None:
        super().__init__(placeholder="Select command", options=options)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        if await _reject(interaction):
            return
        cmd_name = self.values[0]
        current = await self.bot.db.is_command_enabled(cmd_name)
        await self.bot.db.set_command_state(cmd_name, not current)
        status = "enabled" if not current else "disabled"
        await interaction.response.send_message(
            embed=success_embed("Command Updated", f"`{cmd_name}` has been **{status}**."),
            ephemeral=True,
        )


class ToggleEventView(ui.View):
    def __init__(self, bot: NJRPBot, options: list[discord.SelectOption]) -> None:
        super().__init__(timeout=60)
        self.add_item(ToggleEventSelect(bot, options))


class ToggleEventSelect(ui.Select):
    def __init__(self, bot: NJRPBot, options: list[discord.SelectOption]) -> None:
        super().__init__(placeholder="Select event", options=options)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        if await _reject(interaction):
            return
        event_name = self.values[0]
        current = await self.bot.db.is_event_enabled(event_name)
        await self.bot.db.set_event_state(event_name, not current)
        status = "enabled" if not current else "disabled"
        await interaction.response.send_message(
            embed=success_embed("Event Updated", f"`{event_name}` has been **{status}**."),
            ephemeral=True,
        )


# ─── Server Management / Lockdown ───────────────────────────────────────────

class ServerManagementView(ui.View):
    def __init__(self, bot: NJRPBot) -> None:
        super().__init__(timeout=120)
        self.bot = bot

    @ui.button(label="🔒 Emergency Lockdown", style=discord.ButtonStyle.danger, row=0)
    async def lockdown(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if await _reject(interaction):
            return

        active = await self.bot.db.get_lockdown_state("active")
        if active == "true":
            await interaction.response.send_message(
                embed=error_embed("Already Locked", "A lockdown is already active. Use Restore to undo it."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            return

        # Save current permissions and lock channels
        for channel in guild.channels:
            if isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel)):
                overwrites_data = {}
                for target, overwrite in channel.overwrites.items():
                    pair = overwrite.pair()
                    overwrites_data[str(target.id)] = {
                        "type": "role" if isinstance(target, discord.Role) else "member",
                        "allow": pair[0].value,
                        "deny": pair[1].value,
                    }
                await self.bot.db.save_lockdown_overwrites(
                    channel.id, json.dumps(overwrites_data)
                )
                # Deny send messages for @everyone
                await channel.set_permissions(
                    guild.default_role,
                    send_messages=False,
                    add_reactions=False,
                    connect=False,
                    reason="Emergency Lockdown",
                )

        # Remove staff roles from members
        for role_id in STAFF_ROLE_IDS:
            role = guild.get_role(role_id)
            if role is None:
                continue
            for member in role.members:
                try:
                    await member.remove_roles(role, reason="Emergency Lockdown")
                    await self.bot.db.save_lockdown_role(member.id, role_id)
                except discord.Forbidden:
                    logger.warning("Cannot remove role %s from %s", role_id, member.id)

        await self.bot.db.set_lockdown_state("active", "true")
        await self.bot.db.set_lockdown_state("locked_by", str(interaction.user.id))
        await self.bot.db.set_lockdown_state("locked_at", datetime.utcnow().isoformat())

        await interaction.followup.send(
            embed=success_embed(
                "🔒 Lockdown Activated",
                "All channels locked. Staff roles removed. Use **Restore Lockdown** to undo.",
            ),
            ephemeral=True,
        )

    @ui.button(label="🔓 Restore Lockdown", style=discord.ButtonStyle.success, row=0)
    async def restore(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if await _reject(interaction):
            return

        active = await self.bot.db.get_lockdown_state("active")
        if active != "true":
            await interaction.response.send_message(
                embed=error_embed("No Lockdown", "There is no active lockdown to restore."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            return

        # Restore channel permissions
        saved_overwrites = await self.bot.db.get_lockdown_overwrites()
        for row in saved_overwrites:
            channel = guild.get_channel(row["channel_id"])
            if channel is None or not isinstance(
                channel, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel)
            ):
                continue

            overwrites_data: dict = json.loads(row["overwrites_json"])
            new_overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {}

            for target_id_str, perms in overwrites_data.items():
                target_id = int(target_id_str)
                if perms["type"] == "role":
                    target = guild.get_role(target_id)
                else:
                    target = guild.get_member(target_id)

                if target is not None:
                    allow = discord.Permissions(perms["allow"])
                    deny = discord.Permissions(perms["deny"])
                    overwrite = discord.PermissionOverwrite.from_pair(allow, deny)
                    new_overwrites[target] = overwrite

            try:
                await channel.edit(overwrites=new_overwrites, reason="Lockdown Restore")
            except discord.Forbidden:
                logger.warning("Cannot restore permissions for channel %s", channel.id)

        # Restore staff roles
        saved_roles = await self.bot.db.get_lockdown_roles()
        for row in saved_roles:
            member = guild.get_member(row["user_id"])
            role = guild.get_role(row["role_id"])
            if member and role:
                try:
                    await member.add_roles(role, reason="Lockdown Restore")
                except discord.Forbidden:
                    logger.warning("Cannot restore role %s to %s", row["role_id"], row["user_id"])

        # Clear lockdown data
        await self.bot.db.clear_lockdown_overwrites()
        await self.bot.db.clear_lockdown_roles()
        await self.bot.db.clear_lockdown_state()

        await interaction.followup.send(
            embed=success_embed(
                "🔓 Lockdown Restored",
                "All permissions and roles have been restored to their previous state.",
            ),
            ephemeral=True,
        )
