import json
import io
import asyncio
import discord
from typing import Dict, Any, Optional

class DiscordDB:
    """
    Handles data persistence using Discord channels and message attachments.
    Each guild gets a hidden category and data channel.
    """
    CATEGORY_NAME = "Bot-Database"
    CHANNEL_NAME = "data-store"

    def __init__(self, bot):
        self.bot = bot
        self.cache: Dict[int, Dict[str, Any]] = {}  # guild_id -> data
        self.locks: Dict[int, asyncio.Lock] = {}    # guild_id -> Lock
        self.pending_saves = set()

    def get_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self.locks:
            self.locks[guild_id] = asyncio.Lock()
        return self.locks[guild_id]

    async def get_db_channel(self, guild: discord.Guild) -> discord.TextChannel:
        category = discord.utils.get(guild.categories, name=self.CATEGORY_NAME)
        if not category:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True)
            }
            category = await guild.create_category(self.CATEGORY_NAME, overwrites=overwrites)

        channel = discord.utils.get(category.text_channels, name=self.CHANNEL_NAME)
        if not channel:
            channel = await category.create_text_channel(self.CHANNEL_NAME)

        return channel

    async def load_guild_data(self, guild_id: int) -> Dict[str, Any]:
        async with self.get_lock(guild_id):
            if guild_id in self.cache:
                return self.cache[guild_id]

            guild = self.bot.get_guild(guild_id) or await self.bot.fetch_guild(guild_id)
            if not guild:
                return {}

            channel = await self.get_db_channel(guild)

        # Look for the last message with an attachment named 'db.json'
        async for message in channel.history(limit=50):
            if message.attachments:
                for attachment in message.attachments:
                    if attachment.filename == "db.json":
                        data_bytes = await attachment.read()
                        data = json.loads(data_bytes.decode('utf-8'))
                        self.cache[guild_id] = data
                        return data

        # If no data found, return default
        default_data = {
            "config": {
                "currency_name": "Coin",
                "tax_rate": 0.05,
                "xp_rate": 1.0,
                "admin_role_id": None
            },
            "balances": {}, # user_id_str -> {balance, xp, level, last_daily, last_work}
            "products": [], # list of dicts
            "orders": [], # list of dicts
            "transactions": [], # list of dicts
            "audit_logs": [] # list of dicts
        }
        self.cache[guild_id] = default_data
        return default_data

    async def save_guild_data(self, guild_id: int):
        async with self.get_lock(guild_id):
            if guild_id not in self.cache:
                return

            guild = self.bot.get_guild(guild_id) or await self.bot.fetch_guild(guild_id)
            if not guild:
                return

            channel = await self.get_db_channel(guild)
        data = self.cache[guild_id]

        # Serialize data to JSON
        json_data = json.dumps(data, indent=4, ensure_ascii=False)
        data_file = discord.File(io.BytesIO(json_data.encode('utf-8')), filename="db.json")

        # Purge old messages to keep it clean (keep last 5 for safety/backup)
        try:
            old_messages = []
            async for message in channel.history(limit=50):
                if message.attachments and any(a.filename == "db.json" for a in message.attachments):
                    old_messages.append(message)

            if len(old_messages) > 5:
                for msg in old_messages[5:]:
                    await msg.delete()
        except Exception as e:
            print(f"Error cleaning up old DB messages: {e}")

        await channel.send("Database Update", file=data_file)

    def get_guild_config(self, guild_id: int) -> Dict[str, Any]:
        return self.cache.get(guild_id, {}).get("config", {
            "currency_name": "Coin",
            "tax_rate": 0.05,
            "xp_rate": 1.0,
            "admin_role_id": None
        })

    def update_guild_config(self, guild_id: int, updates: Dict[str, Any]):
        guild_data = self.cache.setdefault(guild_id, {})
        config = guild_data.setdefault("config", {
            "currency_name": "Coin",
            "tax_rate": 0.05,
            "xp_rate": 1.0,
            "admin_role_id": None,
            "audit_channel_id": None,
            "enabled": True
        })
        config.update(updates)

    def get_user_data(self, guild_id: int, user_id: int) -> Dict[str, Any]:
        guild_data = self.cache.get(guild_id, {})
        balances = guild_data.get("balances", {})
        user_id_str = str(user_id)
        if user_id_str not in balances:
            balances[user_id_str] = {
                "balance": 0,
                "xp": 0,
                "level": 1,
                "last_daily": None,
                "last_work": None
            }
        return balances[user_id_str]

    def update_user_data(self, guild_id: int, user_id: int, updates: Dict[str, Any]):
        guild_data = self.cache.setdefault(guild_id, {})
        balances = guild_data.setdefault("balances", {})
        user_id_str = str(user_id)
        user_data = balances.setdefault(user_id_str, {
            "balance": 0, "xp": 0, "level": 1, "last_daily": None, "last_work": None
        })
        user_data.update(updates)

    def log_transaction(self, guild_id: int, tx_data: Dict[str, Any]):
        guild_data = self.cache.setdefault(guild_id, {})
        transactions = guild_data.setdefault("transactions", [])
        transactions.append(tx_data)
        # Limit transaction history size in the single JSON if needed
        if len(transactions) > 1000:
            transactions.pop(0)

    async def log_audit(self, guild_id: int, audit_data: Dict[str, Any]):
        guild_data = self.cache.setdefault(guild_id, {})
        audit_logs = guild_data.setdefault("audit_logs", [])
        audit_logs.append(audit_data)
        if len(audit_logs) > 500:
            audit_logs.pop(0)

        # Also try to send to audit channel if configured
        config = self.get_guild_config(guild_id)
        channel_id = config.get("audit_channel_id")
        if channel_id:
            guild = self.bot.get_guild(guild_id)
            channel = guild.get_channel(int(channel_id))
            if channel:
                embed = discord.Embed(title="Audit Log", color=discord.Color.red())
                for k, v in audit_data.items():
                    embed.add_field(name=k, value=str(v))
                try:
                    await channel.send(embed=embed)
                except:
                    pass
