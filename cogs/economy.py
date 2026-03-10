import discord
import datetime
import random
from discord import app_commands
from discord.ext import commands
from typing import Optional

class Economy(commands.Cog):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    async def ensure_guild_loaded(self, guild_id: int):
        await self.db.load_guild_data(guild_id)

    @app_commands.command(name="balance", description="Check your balance or another user's balance.")
    async def balance(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        user = user or interaction.user
        await self.ensure_guild_loaded(interaction.guild_id)

        user_data = self.db.get_user_data(interaction.guild_id, user.id)
        config = self.db.get_guild_config(interaction.guild_id)
        currency = config.get("currency_name", "Coin")

        embed = discord.Embed(title=f"{user.display_name}'s Balance", color=discord.Color.blue())
        embed.add_field(name=currency, value=f"{user_data['balance']:,}")
        embed.add_field(name="XP", value=f"{user_data['xp']:,}")
        embed.add_field(name="Level", value=user_data['level'])

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="Claim your daily reward.")
    async def daily(self, interaction: discord.Interaction):
        await self.ensure_guild_loaded(interaction.guild_id)
        user_id = interaction.user.id
        user_data = self.db.get_user_data(interaction.guild_id, user_id)

        now = datetime.datetime.utcnow()
        last_daily_str = user_data.get("last_daily")

        if last_daily_str:
            last_daily = datetime.datetime.fromisoformat(last_daily_str)
            if (now - last_daily).total_seconds() < 86400:
                remaining = 86400 - (now - last_daily).total_seconds()
                hours, remainder = divmod(int(remaining), 3600)
                minutes, seconds = divmod(remainder, 60)
                return await interaction.response.send_message(
                    f"You already claimed your daily reward! Try again in {hours}h {minutes}m {seconds}s.",
                    ephemeral=True
                )

        reward = 500 # Default reward
        new_balance = user_data["balance"] + reward
        self.db.update_user_data(interaction.guild_id, user_id, {
            "balance": new_balance,
            "last_daily": now.isoformat()
        })

        self.db.log_transaction(interaction.guild_id, {
            "user_id": user_id,
            "type": "daily",
            "amount": reward,
            "before": user_data["balance"],
            "after": new_balance,
            "timestamp": now.isoformat()
        })

        await self.db.save_guild_data(interaction.guild_id)

        config = self.db.get_guild_config(interaction.guild_id)
        currency = config.get("currency_name", "Coin")
        await interaction.response.send_message(f"You claimed your daily reward of **{reward} {currency}**!")

    @app_commands.command(name="work", description="Work to earn some money.")
    async def work(self, interaction: discord.Interaction):
        await self.ensure_guild_loaded(interaction.guild_id)
        user_id = interaction.user.id
        user_data = self.db.get_user_data(interaction.guild_id, user_id)

        now = datetime.datetime.utcnow()
        last_work_str = user_data.get("last_work")

        cooldown = 3600 # 1 hour
        if last_work_str:
            last_work = datetime.datetime.fromisoformat(last_work_str)
            if (now - last_work).total_seconds() < cooldown:
                remaining = cooldown - (now - last_work).total_seconds()
                minutes, seconds = divmod(int(remaining), 60)
                return await interaction.response.send_message(
                    f"You're tired! Try working again in {minutes}m {seconds}s.",
                    ephemeral=True
                )

        reward = random.randint(50, 200)
        new_balance = user_data["balance"] + reward
        self.db.update_user_data(interaction.guild_id, user_id, {
            "balance": new_balance,
            "last_work": now.isoformat()
        })

        self.db.log_transaction(interaction.guild_id, {
            "user_id": user_id,
            "type": "work",
            "amount": reward,
            "before": user_data["balance"],
            "after": new_balance,
            "timestamp": now.isoformat()
        })

        await self.db.save_guild_data(interaction.guild_id)

        config = self.db.get_guild_config(interaction.guild_id)
        currency = config.get("currency_name", "Coin")
        await interaction.response.send_message(f"You worked and earned **{reward} {currency}**!")

    @app_commands.command(name="pay", description="Transfer money to another user.")
    async def pay(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if amount <= 0:
            return await interaction.response.send_message("Amount must be positive.", ephemeral=True)
        if user.id == interaction.user.id:
            return await interaction.response.send_message("You cannot pay yourself.", ephemeral=True)

        await self.ensure_guild_loaded(interaction.guild_id)
        sender_data = self.db.get_user_data(interaction.guild_id, interaction.user.id)

        config = self.db.get_guild_config(interaction.guild_id)
        tax_rate = config.get("tax_rate", 0.05)
        tax = int(amount * tax_rate)
        total_deduction = amount # Amount user chose to pay includes tax or is net? Usually amount is what recipient gets.
        # Let's say amount is what is sent. Total deduction = amount + tax?
        # Requirement says "transfer tax". Let's say user pays `amount`, recipient gets `amount - tax`.

        if sender_data["balance"] < amount:
            return await interaction.response.send_message("Insufficient balance.", ephemeral=True)

        receiver_data = self.db.get_user_data(interaction.guild_id, user.id)
        net_amount = amount - tax

        # Update sender
        new_sender_bal = sender_data["balance"] - amount
        self.db.update_user_data(interaction.guild_id, interaction.user.id, {"balance": new_sender_bal})

        # Update receiver
        new_receiver_bal = receiver_data["balance"] + net_amount
        self.db.update_user_data(interaction.guild_id, user.id, {"balance": new_receiver_bal})

        now = datetime.datetime.utcnow().isoformat()
        self.db.log_transaction(interaction.guild_id, {
            "user_id": interaction.user.id,
            "type": "transfer_out",
            "amount": -amount,
            "to": user.id,
            "tax": tax,
            "before": sender_data["balance"],
            "after": new_sender_bal,
            "timestamp": now
        })
        self.db.log_transaction(interaction.guild_id, {
            "user_id": user.id,
            "type": "transfer_in",
            "amount": net_amount,
            "from": interaction.user.id,
            "before": receiver_data["balance"],
            "after": new_receiver_bal,
            "timestamp": now
        })

        await self.db.save_guild_data(interaction.guild_id)

        currency = config.get("currency_name", "Coin")
        await interaction.response.send_message(
            f"Transferred **{net_amount} {currency}** to {user.mention} (Tax: {tax} {currency})."
        )

async def setup(bot):
    # This setup will be slightly different since we need to pass db
    pass
