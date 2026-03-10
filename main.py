import os
import asyncio
import discord
import logging
from contextlib import asynccontextmanager
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the bot as a background task
    if not TOKEN:
        logger.error("Please provide a DISCORD_TOKEN in the environment variables.")
    else:
        asyncio.create_task(bot.start(TOKEN))
        logger.info("Discord bot background task started.")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await bot.close()

app = FastAPI(lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    status = "Online" if not bot.is_closed() else "Offline"
    try:
        latency = round(bot.latency * 1000) if not bot.is_closed() and bot.latency is not None and not (isinstance(bot.latency, float) and bot.latency != bot.latency) else "N/A"
    except (ValueError, TypeError):
        latency = "N/A"

    html_content = f"""
    <html>
        <head>
            <title>MultiGuildBot Status</title>
            <style>
                body {{ font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; background-color: #2c2f33; color: white; }}
                .card {{ background: #23272a; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); text-align: center; }}
                h1 {{ color: #7289da; }}
                .status {{ font-size: 1.5rem; margin: 1rem 0; }}
                .online {{ color: #43b581; }}
                .offline {{ color: #f04747; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Multi-Guild Economy Bot</h1>
                <p class="status">Status: <span class="{status.lower()}">{status}</span></p>
                <p>Latency: {latency}ms</p>
                <p>Bot is running as a FastAPI web application.</p>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

@app.get("/health")
async def health():
    return {{"status": "ok", "bot_online": not bot.is_closed()}}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
