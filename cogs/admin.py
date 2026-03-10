import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

class Admin(commands.Cog):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    async def ensure_guild_loaded(self, guild_id: int):
        await self.db.load_guild_data(guild_id)

    def is_admin():
        def predicate(interaction: discord.Interaction) -> bool:
            if interaction.user.guild_permissions.administrator:
                return True
            # Check for custom admin role if needed
            return False
        return app_commands.check(predicate)

    @app_commands.command(name="setup", description="Initial setup for the bot in this guild.")
    @is_admin()
    async def setup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.ensure_guild_loaded(interaction.guild_id)
        channel = await self.db.get_db_channel(interaction.guild)
        await interaction.followup.send(f"Setup complete! Database channel: {channel.mention}", ephemeral=True)

    @app_commands.command(name="set-currency-name", description="Set the name of the server currency.")
    @is_admin()
    async def set_currency(self, interaction: discord.Interaction, name: str):
        await self.ensure_guild_loaded(interaction.guild_id)
        self.db.update_guild_config(interaction.guild_id, {"currency_name": name})
        await self.db.save_guild_data(interaction.guild_id)
        await interaction.response.send_message(f"Currency name updated to **{name}**.")

    @app_commands.command(name="set-tax", description="Set the tax rate for transfers and gambling (0-100).")
    @is_admin()
    async def set_tax(self, interaction: discord.Interaction, percent: float):
        if not 0 <= percent <= 100:
            return await interaction.response.send_message("Tax percent must be between 0 and 100.", ephemeral=True)

        await self.ensure_guild_loaded(interaction.guild_id)
        self.db.update_guild_config(interaction.guild_id, {"tax_rate": percent / 100})
        await self.db.save_guild_data(interaction.guild_id)
        await interaction.response.send_message(f"Tax rate updated to **{percent}%**.")

    @app_commands.command(name="config-xp", description="Configure XP gain multiplier.")
    @is_admin()
    async def config_xp(self, interaction: discord.Interaction, multiplier: float):
        await self.ensure_guild_loaded(interaction.guild_id)
        self.db.update_guild_config(interaction.guild_id, {"xp_rate": multiplier})
        await self.db.save_guild_data(interaction.guild_id)
        await interaction.response.send_message(f"XP rate updated to **{multiplier}x**.")

    @app_commands.command(name="set-audit-channel", description="Set the channel for audit logs.")
    @is_admin()
    async def set_audit_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.ensure_guild_loaded(interaction.guild_id)
        self.db.update_guild_config(interaction.guild_id, {"audit_channel_id": str(channel.id)})
        await self.db.save_guild_data(interaction.guild_id)
        await interaction.response.send_message(f"Audit channel set to {channel.mention}.")

    @app_commands.command(name="give", description="Give currency to a user.")
    @is_admin()
    async def give(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        await self.ensure_guild_loaded(interaction.guild_id)
        user_data = self.db.get_user_data(interaction.guild_id, user.id)
        new_balance = user_data["balance"] + amount
        self.db.update_user_data(interaction.guild_id, user.id, {"balance": new_balance})

        import datetime
        await self.db.log_audit(interaction.guild_id, {
            "actor_id": interaction.user.id,
            "action": "give_currency",
            "target_id": user.id,
            "amount": amount,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })

        await self.db.save_guild_data(interaction.guild_id)
        config = self.db.get_guild_config(interaction.guild_id)
        currency = config.get("currency_name", "Coin")
        await interaction.response.send_message(f"Gave **{amount} {currency}** to {user.mention}.")

    @app_commands.command(name="audit-logs", description="View recent audit logs.")
    @is_admin()
    async def audit_logs(self, interaction: discord.Interaction, limit: int = 10):
        await self.ensure_guild_loaded(interaction.guild_id)
        logs = self.db.cache.get(interaction.guild_id, {}).get("audit_logs", [])
        if not logs:
            return await interaction.response.send_message("No audit logs found.")

        display_logs = logs[-limit:]
        log_text = ""
        for log in reversed(display_logs):
            log_text += f"`{log['timestamp']}`: <@{log['actor_id']}> {log['action']} target:<@{log.get('target_id')}> {log.get('amount') or ''}\n"

        embed = discord.Embed(title="Audit Logs", description=log_text or "No logs to display.")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    pass
