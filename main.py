import os
import asyncio
import discord
import logging
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from aiohttp import web
from db_manager import DiscordDB
from cogs.economy import Economy
from cogs.admin import Admin
from cogs.shop import Shop
from cogs.fun import Fun
from cogs.leveling import Leveling

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MultiGuildBot")

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
        logger.info("Setting up cogs...")
        try:
            await self.add_cog(Economy(self, self.db))
            await self.add_cog(Admin(self, self.db))
            await self.add_cog(Shop(self, self.db))
            await self.add_cog(Fun(self, self.db))
            await self.add_cog(Leveling(self, self.db))
            logger.info("Successfully loaded all cogs.")
        except Exception as e:
            logger.error(f"Error loading cogs: {e}", exc_info=True)

        # Add a simple ping command to the tree
        @self.tree.command(name="ping", description="Ping the bot.")
        async def ping(interaction: discord.Interaction):
            await interaction.response.send_message(f"Pong! Latency: {round(self.latency * 1000)}ms")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Error syncing tree: {e}")
        logger.info("------")

bot = MultiGuildBot()

async def health_check(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    port = int(os.getenv("PORT", 10000))
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Web server started on port {port}")

async def main():
    if not TOKEN:
        logger.error("Please provide a DISCORD_TOKEN in the environment variables.")
        return

    # Start the web server for health checks (Render requirement for Web Services)
    await start_web_server()

    async with bot:
        try:
            await bot.start(TOKEN)
        except Exception as e:
            logger.error(f"Bot failed to start: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
