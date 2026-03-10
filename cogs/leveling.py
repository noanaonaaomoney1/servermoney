import discord
from discord.ext import commands, tasks
import random
import math
import time

class Leveling(commands.Cog):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.cooldowns = {} # user_id -> timestamp
        self.background_save.start()

    async def ensure_guild_loaded(self, guild_id: int):
        await self.db.load_guild_data(guild_id)

    def calculate_level(self, xp: int) -> int:
        # Simple level calculation: 100 * (level^2)
        # Level 1: 0 XP
        # Level 2: 100 XP
        # Level 3: 400 XP
        return int(math.sqrt(xp / 100)) + 1 if xp >= 100 else 1

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        guild_id = message.guild.id

        # Simple cooldown to prevent spamming XP
        now = time.time()
        last_gain = self.cooldowns.get(user_id, 0)
        if now - last_gain < 60: # 1 minute cooldown per user
            return

        self.cooldowns[user_id] = now

        await self.ensure_guild_loaded(guild_id)
        config = self.db.get_guild_config(guild_id)
        xp_multiplier = config.get("xp_rate", 1.0)

        xp_to_add = int(random.randint(15, 25) * xp_multiplier)
        user_data = self.db.get_user_data(guild_id, user_id)

        new_xp = user_data.get("xp", 0) + xp_to_add
        new_level = self.calculate_level(new_xp)
        old_level = user_data.get("level", 1)

        updates = {"xp": new_xp, "level": new_level}
        self.db.update_user_data(guild_id, user_id, updates)

        if new_level > old_level:
            # Level up!
            try:
                await message.channel.send(f"Congratulations {message.author.mention}, you leveled up to **Level {new_level}**!")
            except:
                pass # Silently fail if can't send message

        # We don't save to Discord on every message to avoid rate limits.
        # We use a periodic background task to save all pending changes.
        self.db.pending_saves.add(guild_id)

    def cog_unload(self):
        self.background_save.cancel()

    @tasks.loop(minutes=5)
    async def background_save(self):
        for guild_id in list(self.db.pending_saves):
            try:
                await self.db.save_guild_data(guild_id)
                self.db.pending_saves.discard(guild_id)
            except Exception as e:
                print(f"Error in background save for guild {guild_id}: {e}")

async def setup(bot):
    pass
