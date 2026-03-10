import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime
from typing import Literal

class Fun(commands.Cog):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    async def ensure_guild_loaded(self, guild_id: int):
        await self.db.load_guild_data(guild_id)

    @app_commands.command(name="coinflip", description="Flip a coin and bet money.")
    async def coinflip(self, interaction: discord.Interaction, bet: int, side: Literal["heads", "tails"]):
        if bet <= 0:
            return await interaction.response.send_message("Bet must be positive.", ephemeral=True)

        await self.ensure_guild_loaded(interaction.guild_id)
        user_data = self.db.get_user_data(interaction.guild_id, interaction.user.id)
        if user_data['balance'] < bet:
            return await interaction.response.send_message("Insufficient balance.", ephemeral=True)

        result = random.choice(["heads", "tails"])
        win = result == side

        config = self.db.get_guild_config(interaction.guild_id)
        tax_rate = config.get("tax_rate", 0.05)
        currency = config.get("currency_name", "Coin")

        now = datetime.datetime.utcnow().isoformat()
        if win:
            winnings = bet # Get bet back + bet winnings = 2x bet total.
            # If bet is 100, balance was 1000. Balance became 900. After win, it becomes 1100.
            # Tax on winnings?
            tax = int(winnings * tax_rate)
            net_winnings = winnings - tax
            new_balance = user_data['balance'] + net_winnings
            msg = f"It's **{result}**! You won **{net_winnings} {currency}** (Tax: {tax})."
        else:
            new_balance = user_data['balance'] - bet
            msg = f"It's **{result}**! You lost **{bet} {currency}**."

        self.db.update_user_data(interaction.guild_id, interaction.user.id, {"balance": new_balance})
        self.db.log_transaction(interaction.guild_id, {
            "user_id": interaction.user.id,
            "type": "coinflip",
            "win": win,
            "bet": bet,
            "before": user_data['balance'],
            "after": new_balance,
            "timestamp": now
        })

        await self.db.save_guild_data(interaction.guild_id)
        await interaction.response.send_message(msg)

    @app_commands.command(name="slot", description="Try your luck on the slot machine.")
    async def slot(self, interaction: discord.Interaction, bet: int):
        if bet <= 0:
            return await interaction.response.send_message("Bet must be positive.", ephemeral=True)

        await self.ensure_guild_loaded(interaction.guild_id)
        user_data = self.db.get_user_data(interaction.guild_id, interaction.user.id)
        if user_data['balance'] < bet:
            return await interaction.response.send_message("Insufficient balance.", ephemeral=True)

        emojis = ["🍎", "🍊", "🍇", "🍒", "💎"]
        result = [random.choice(emojis) for _ in range(3)]

        config = self.db.get_guild_config(interaction.guild_id)
        tax_rate = config.get("tax_rate", 0.05)
        currency = config.get("currency_name", "Coin")

        win = False
        multiplier = 0
        if result[0] == result[1] == result[2]:
            win = True
            multiplier = 5 if result[0] == "💎" else 3
        elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
            win = True
            multiplier = 1.5

        now = datetime.datetime.utcnow().isoformat()
        if win:
            winnings = int(bet * multiplier)
            tax = int(winnings * tax_rate)
            net_winnings = winnings - tax
            new_balance = user_data['balance'] + net_winnings
            msg = f"| {' | '.join(result)} |\n\n**Jackpot!** You won **{net_winnings} {currency}** (Tax: {tax})."
        else:
            new_balance = user_data['balance'] - bet
            msg = f"| {' | '.join(result)} |\n\nYou lost **{bet} {currency}**."

        self.db.update_user_data(interaction.guild_id, interaction.user.id, {"balance": new_balance})
        self.db.log_transaction(interaction.guild_id, {
            "user_id": interaction.user.id,
            "type": "slot",
            "win": win,
            "bet": bet,
            "before": user_data['balance'],
            "after": new_balance,
            "timestamp": now
        })

        await self.db.save_guild_data(interaction.guild_id)
        await interaction.response.send_message(msg)

    @app_commands.command(name="leaderboard", description="View the richest or most active users.")
    async def leaderboard(self, interaction: discord.Interaction, type: Literal["coins", "xp"] = "coins"):
        await self.ensure_guild_loaded(interaction.guild_id)
        guild_data = self.db.cache.get(interaction.guild_id, {})
        balances = guild_data.get("balances", {})

        if not balances:
            return await interaction.response.send_message("No data found for this guild.")

        # Sort users
        if type == "coins":
            sorted_users = sorted(balances.items(), key=lambda x: x[1].get('balance', 0), reverse=True)
            key_name = "balance"
        else:
            sorted_users = sorted(balances.items(), key=lambda x: x[1].get('xp', 0), reverse=True)
            key_name = "xp"

        config = self.db.get_guild_config(interaction.guild_id)
        currency = config.get("currency_name", "Coin")

        embed = discord.Embed(title=f"Leaderboard: {type.capitalize()}", color=discord.Color.gold())
        for i, (uid, data) in enumerate(sorted_users[:10], 1):
            user = self.bot.get_user(int(uid))
            name = user.display_name if user else f"User {uid}"
            suffix = currency if type == "coins" else "XP"
            embed.add_field(name=f"{i}. {name}", value=f"{data.get(key_name, 0):,} {suffix}", inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    pass
