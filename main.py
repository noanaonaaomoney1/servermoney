import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from aiohttp import web
from db_manager import DiscordDB
from cogs.economy import Economy
from cogs.admin import Admin
from cogs.shop import Shop
from cogs.fun import Fun
from cogs.leveling import Leveling

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

class MultiGuildBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        self.db = DiscordDB(self)

    async def setup_hook(self):
        await self.add_cog(Economy(self, self.db))
        await self.add_cog(Admin(self, self.db))
        await self.add_cog(Shop(self, self.db))
        await self.add_cog(Fun(self, self.db))
        await self.add_cog(Leveling(self, self.db))
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")

bot = MultiGuildBot()

async def health_check(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    await site.start()
    print(f"Web server started on port {os.getenv('PORT', 10000)}")

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

async def main():
    if not TOKEN:
        print("Please provide a DISCORD_TOKEN in the environment variables.")
        return

    # Start the web server for health checks (Render requirement for Web Services)
    asyncio.create_task(start_web_server())

    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
