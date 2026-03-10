import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal
import datetime
import uuid

class Shop(commands.Cog):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    async def ensure_guild_loaded(self, guild_id: int):
        await self.db.load_guild_data(guild_id)

    @app_commands.command(name="product-add", description="Add a product to the shop.")
    @app_commands.checks.has_permissions(administrator=True)
    async def product_add(
        self,
        interaction: discord.Interaction,
        title: str,
        price: int,
        type: Literal["role", "file", "key", "item"],
        stock: int = -1,
        metadata: Optional[str] = None # For role_id, etc.
    ):
        await self.ensure_guild_loaded(interaction.guild_id)

        product = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "price": price,
            "type": type,
            "stock": stock,
            "metadata": metadata
        }

        guild_data = self.db.cache.get(interaction.guild_id, {})
        products = guild_data.setdefault("products", [])
        products.append(product)

        await self.db.save_guild_data(interaction.guild_id)
        await interaction.response.send_message(f"Product **{title}** added with ID: `{product['id']}`.")

    @app_commands.command(name="product-edit", description="Edit a product in the shop.")
    @app_commands.checks.has_permissions(administrator=True)
    async def product_edit(
        self,
        interaction: discord.Interaction,
        product_id: str,
        price: Optional[int] = None,
        stock: Optional[int] = None,
        title: Optional[str] = None
    ):
        await self.ensure_guild_loaded(interaction.guild_id)
        guild_data = self.db.cache.get(interaction.guild_id, {})
        products = guild_data.get("products", [])
        product = next((p for p in products if p['id'] == product_id), None)

        if not product:
            return await interaction.response.send_message("Product not found.", ephemeral=True)

        if price is not None: product['price'] = price
        if stock is not None: product['stock'] = stock
        if title is not None: product['title'] = title

        await self.db.save_guild_data(interaction.guild_id)
        await interaction.response.send_message(f"Product `{product_id}` updated.")

    @app_commands.command(name="product-remove", description="Remove a product from the shop.")
    @app_commands.checks.has_permissions(administrator=True)
    async def product_remove(self, interaction: discord.Interaction, product_id: str):
        await self.ensure_guild_loaded(interaction.guild_id)
        guild_data = self.db.cache.get(interaction.guild_id, {})
        products = guild_data.get("products", [])

        new_products = [p for p in products if p['id'] != product_id]
        if len(new_products) == len(products):
            return await interaction.response.send_message("Product not found.", ephemeral=True)

        guild_data["products"] = new_products
        await self.db.save_guild_data(interaction.guild_id)
        await interaction.response.send_message(f"Product `{product_id}` removed.")

    @app_commands.command(name="orders", description="List orders.")
    @app_commands.checks.has_permissions(administrator=True)
    async def orders(self, interaction: discord.Interaction, status: Optional[Literal["pending", "paid", "delivered", "refunded"]] = None):
        await self.ensure_guild_loaded(interaction.guild_id)
        orders = self.db.cache.get(interaction.guild_id, {}).get("orders", [])
        if status:
            orders = [o for o in orders if o['status'] == status]

        if not orders:
            return await interaction.response.send_message(f"No orders found with status: {status or 'any'}")

        text = ""
        for o in orders[-10:]:
            text += f"ID: `{o['order_id']}` | User: <@{o['user_id']}> | Product: {o['product_id']} | Status: {o['status']}\n"

        embed = discord.Embed(title="Recent Orders", description=text)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="refund", description="Refund an order.")
    @app_commands.checks.has_permissions(administrator=True)
    async def refund(self, interaction: discord.Interaction, order_id: str, reason: str):
        await self.ensure_guild_loaded(interaction.guild_id)
        guild_data = self.db.cache.get(interaction.guild_id, {})
        orders = guild_data.get("orders", [])
        order = next((o for o in orders if o['order_id'] == order_id), None)

        if not order:
            return await interaction.response.send_message("Order not found.", ephemeral=True)
        if order['status'] == "refunded":
            return await interaction.response.send_message("Order already refunded.", ephemeral=True)

        # Refund money
        user_id = order['user_id']
        amount = order['amount']
        user_data = self.db.get_user_data(interaction.guild_id, user_id)
        new_balance = user_data['balance'] + amount
        self.db.update_user_data(interaction.guild_id, user_id, {"balance": new_balance})

        order['status'] = "refunded"

        # Log transaction
        now = datetime.datetime.utcnow().isoformat()
        self.db.log_transaction(interaction.guild_id, {
            "user_id": user_id,
            "type": "refund",
            "amount": amount,
            "order_id": order_id,
            "reason": reason,
            "before": user_data['balance'],
            "after": new_balance,
            "timestamp": now
        })

        await self.db.log_audit(interaction.guild_id, {
            "actor_id": interaction.user.id,
            "action": "refund",
            "order_id": order_id,
            "target_id": user_id,
            "timestamp": now
        })

        await self.db.save_guild_data(interaction.guild_id)
        await interaction.response.send_message(f"Order `{order_id}` refunded to <@{user_id}>. Reason: {reason}")

    @app_commands.command(name="inventory", description="View your purchased items.")
    async def inventory(self, interaction: discord.Interaction):
        await self.ensure_guild_loaded(interaction.guild_id)
        orders = self.db.cache.get(interaction.guild_id, {}).get("orders", [])
        my_orders = [o for o in orders if o['user_id'] == interaction.user.id and o['status'] == "delivered"]

        if not my_orders:
            return await interaction.response.send_message("You don't have any items.")

        products = self.db.cache.get(interaction.guild_id, {}).get("products", [])

        text = ""
        for o in my_orders:
            prod = next((p for p in products if p['id'] == o['product_id']), None)
            title = prod['title'] if prod else f"Unknown Product ({o['product_id']})"
            text += f"• **{title}** (Order ID: `{o['order_id']}`)\n"

        embed = discord.Embed(title=f"{interaction.user.display_name}'s Inventory", description=text)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="shop", description="View the server shop.")
    async def shop(self, interaction: discord.Interaction):
        await self.ensure_guild_loaded(interaction.guild_id)
        products = self.db.cache.get(interaction.guild_id, {}).get("products", [])
        config = self.db.get_guild_config(interaction.guild_id)
        currency = config.get("currency_name", "Coin")

        if not products:
            return await interaction.response.send_message("The shop is empty.")

        embed = discord.Embed(title=f"{interaction.guild.name} Shop", color=discord.Color.green())
        for p in products:
            stock_text = "Infinite" if p['stock'] == -1 else p['stock']
            embed.add_field(
                name=f"{p['title']} (ID: {p['id']})",
                value=f"Price: {p['price']} {currency}\nType: {p['type']}\nStock: {stock_text}",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="Buy a product from the shop.")
    async def buy(self, interaction: discord.Interaction, product_id: str):
        await self.ensure_guild_loaded(interaction.guild_id)
        guild_data = self.db.cache.get(interaction.guild_id, {})
        products = guild_data.get("products", [])
        product = next((p for p in products if p['id'] == product_id), None)

        if not product:
            return await interaction.response.send_message("Product not found.", ephemeral=True)

        if product['stock'] != -1 and product['stock'] <= 0:
            return await interaction.response.send_message("Out of stock.", ephemeral=True)

        user_data = self.db.get_user_data(interaction.guild_id, interaction.user.id)
        if user_data['balance'] < product['price']:
            return await interaction.response.send_message("Insufficient balance.", ephemeral=True)

        # Deduct balance
        new_balance = user_data['balance'] - product['price']
        self.db.update_user_data(interaction.guild_id, interaction.user.id, {"balance": new_balance})

        # Deduct stock
        if product['stock'] != -1:
            product['stock'] -= 1

        # Create Order
        order_id = str(uuid.uuid4())[:8]
        order = {
            "order_id": order_id,
            "user_id": interaction.user.id,
            "product_id": product_id,
            "amount": product['price'],
            "status": "delivered",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        guild_data.setdefault("orders", []).append(order)

        # Log transaction
        now = datetime.datetime.utcnow().isoformat()
        self.db.log_transaction(interaction.guild_id, {
            "user_id": interaction.user.id,
            "type": "purchase",
            "amount": -product['price'],
            "product_id": product_id,
            "order_id": order_id,
            "before": user_data['balance'],
            "after": new_balance,
            "timestamp": now
        })

        # Fulfill purchase
        fulfillment_msg = ""
        if product['type'] == "role":
            role_id = product.get("metadata")
            if role_id:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    try:
                        await interaction.user.add_roles(role)
                        fulfillment_msg = f"Successfully assigned the **{role.name}** role."
                    except Exception as e:
                        fulfillment_msg = f"Error assigning role: {e}. Please contact an admin."
                else:
                    fulfillment_msg = "Role not found. Please contact an admin."
        elif product['type'] in ["file", "key"]:
            try:
                await interaction.user.send(f"Thank you for your purchase of **{product['title']}**! Your data: `{product.get('metadata')}`")
                fulfillment_msg = "Sent delivery details to your DMs."
            except:
                fulfillment_msg = "I couldn't DM you! Please open your DMs and contact an admin."
        else:
            fulfillment_msg = "Purchase completed. Please contact an admin for your item."

        # Audit Log
        await self.db.log_audit(interaction.guild_id, {
            "actor_id": interaction.user.id,
            "action": "purchase",
            "product_id": product_id,
            "price": product['price'],
            "timestamp": now
        })

        await self.db.save_guild_data(interaction.guild_id)

        config = self.db.get_guild_config(interaction.guild_id)
        currency = config.get("currency_name", "Coin")
        await interaction.response.send_message(f"Purchased **{product['title']}** for {product['price']} {currency}. {fulfillment_msg}")

async def setup(bot):
    pass
