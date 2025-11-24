"""Economy system commands for Discord bot"""
import discord
from discord import app_commands
from discord.ext import commands
from ballsdex.core.models import Player
from ballsdex.settings import settings
from asgiref.sync import sync_to_async

if False:
    from ballsdex.core.bot import BallsDexBot


class EconomyCommands(commands.Cog):
    """Economy system commands"""

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot

    # ===== COINS GROUP =====
    coins = app_commands.Group(name="coins", description="Coin management and administration")

    @coins.command(description="Check your coin balance")
    async def balance(self, interaction: discord.Interaction["BallsDexBot"]):
        """Check your coin balance"""
        await interaction.response.defer(ephemeral=True)
        try:
            player, _ = await Player.get_or_create(discord_id=interaction.user.id)
            embed = discord.Embed(
                title="💰 Coin Balance",
                description=f"**{player.coins:,}** coins",
                color=discord.Color.gold(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @coins.command(description="View top coin holders")
    async def leaderboard(self, interaction: discord.Interaction["BallsDexBot"]):
        """View top coin holders"""
        await interaction.response.defer()
        try:
            top_players = await Player.all().order_by("-coins").limit(10)
            embed = discord.Embed(
                title="🏆 Coin Leaderboard",
                color=discord.Color.gold(),
            )
            for i, player in enumerate(top_players, 1):
                embed.add_field(
                    name=f"#{i}",
                    value=f"<@{player.discord_id}>: **{player.coins:,}** coins",
                    inline=False,
                )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    # ===== NESTED: COINS PLAYER GROUP =====
    coins_player = app_commands.Group(
        name="player",
        description="Player coin management",
        parent=coins,
    )

    @coins_player.command(description="Give coins to a player")
    @app_commands.describe(
        user="User to give coins to",
        amount="Amount of coins to give",
        reason="Reason for giving coins",
    )
    async def give(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        user: discord.User,
        amount: int,
        reason: str = "Admin gift",
    ):
        """Give coins to a player"""
        await interaction.response.defer(ephemeral=True)
        try:
            if amount <= 0:
                await interaction.followup.send("Amount must be positive!", ephemeral=True)
                return
            player, _ = await Player.get_or_create(discord_id=user.id)
            player.coins += amount
            await player.save()
            
            # Log transaction
            await log_transaction(user.id, amount, reason)
            
            embed = discord.Embed(
                title="✅ Coins Given",
                description=f"Gave **{amount:,}** coins to {user.mention}\nReason: {reason}",
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    # ===== NESTED: COINS TRADE GROUP =====
    coins_trade = app_commands.Group(
        name="trade",
        description="Trade coin management",
        parent=coins,
    )

    @coins_trade.command(description="Add coins in a trade")
    @app_commands.describe(
        user="User to add coins to",
        amount="Amount of coins to add",
        reason="Reason for adding coins",
    )
    async def add(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        user: discord.User,
        amount: int,
        reason: str = "Trade",
    ):
        """Add coins to a player"""
        await interaction.response.defer(ephemeral=True)
        try:
            if amount <= 0:
                await interaction.followup.send("Amount must be positive!", ephemeral=True)
                return
            player, _ = await Player.get_or_create(discord_id=user.id)
            player.coins += amount
            await player.save()
            
            # Log transaction
            await log_transaction(user.id, amount, reason)
            
            embed = discord.Embed(
                title="✅ Coins Added",
                description=f"Added **{amount:,}** coins to {user.mention}\nReason: {reason}",
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @coins_trade.command(description="Remove coins in a trade")
    @app_commands.describe(
        user="User to remove coins from",
        amount="Amount of coins to remove",
        reason="Reason for removing coins",
    )
    async def remove(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        user: discord.User,
        amount: int,
        reason: str = "Trade",
    ):
        """Remove coins from a player"""
        await interaction.response.defer(ephemeral=True)
        try:
            if amount <= 0:
                await interaction.followup.send("Amount must be positive!", ephemeral=True)
                return
            player, _ = await Player.get_or_create(discord_id=user.id)
            if player.coins < amount:
                await interaction.followup.send(
                    f"Player only has {player.coins:,} coins!", ephemeral=True
                )
                return
            player.coins -= amount
            await player.save()
            
            # Log transaction
            await log_transaction(user.id, -amount, reason)
            
            embed = discord.Embed(
                title="✅ Coins Removed",
                description=f"Removed **{amount:,}** coins from {user.mention}\nReason: {reason}",
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    # ===== PACKS GROUP =====
    packs = app_commands.Group(name="packs", description="Pack shop and management")

    @packs.command(description="List available packs")
    async def list(self, interaction: discord.Interaction["BallsDexBot"]):
        """List available packs"""
        await interaction.response.defer()
        try:
            packs = await get_enabled_packs()
            if not packs:
                await interaction.followup.send("No packs available!", ephemeral=True)
                return
            embed = discord.Embed(title="📦 Available Packs", color=discord.Color.blue())
            for pack in packs:
                embed.add_field(
                    name=f"{pack['emoji']} {pack['name']} ({pack['cost']} coins)",
                    value=pack['description'] or "No description",
                    inline=False,
                )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"Error loading packs: {e}", ephemeral=True)

    @packs.command(description="Buy a pack with coins")
    @app_commands.describe(pack_name="Name of the pack to buy")
    async def buy(self, interaction: discord.Interaction["BallsDexBot"], pack_name: str):
        """Buy a pack"""
        await interaction.response.defer(ephemeral=True)
        try:
            pack = await get_pack_by_name(pack_name)
            if not pack:
                await interaction.followup.send("Pack not found!", ephemeral=True)
                return
            
            player, _ = await Player.get_or_create(discord_id=interaction.user.id)
            
            if player.coins < pack['cost']:
                await interaction.followup.send(
                    f"Not enough coins! You have {player.coins:,} but need {pack['cost']:,}.",
                    ephemeral=True,
                )
                return
            
            player.coins -= pack['cost']
            await player.save()
            
            # Log transaction
            await log_transaction(interaction.user.id, -pack['cost'], f"Pack purchase: {pack_name}")
            
            embed = discord.Embed(
                title="✅ Pack Purchased",
                description=f"You bought **{pack['name']}**!\nCost: {pack['cost']:,} coins",
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error buying pack: {e}", ephemeral=True)

    @packs.command(description="View your pack inventory")
    async def inventory(self, interaction: discord.Interaction["BallsDexBot"]):
        """View your pack inventory"""
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.followup.send("Pack inventory coming soon!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @packs.command(description="Give a pack to another player")
    @app_commands.describe(
        user="User to give pack to",
        pack_name="Name of the pack to give",
    )
    async def give(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        user: discord.User,
        pack_name: str,
    ):
        """Give a pack to another player"""
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.followup.send("Pack gifting coming soon!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @packs.command(description="Open a pack from your inventory")
    @app_commands.describe(pack_name="Name of the pack to open")
    async def open(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        pack_name: str,
    ):
        """Open a pack"""
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.followup.send("Pack opening coming soon!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)


# Helper functions for database operations
async def get_enabled_packs():
    """Get all enabled packs from the database"""
    try:
        from bd_models.models import Pack
        
        def fetch_packs():
            return list(
                Pack.objects.filter(enabled=True).values('id', 'name', 'cost', 'emoji', 'description')
            )
        
        packs = await sync_to_async(fetch_packs)()
        return packs
    except Exception as e:
        print(f"Error fetching packs: {e}")
        return []


async def get_pack_by_name(name: str):
    """Get a pack by name from the database"""
    try:
        from bd_models.models import Pack
        
        def fetch_pack():
            pack = Pack.objects.get(name=name, enabled=True)
            return {
                'id': pack.id,
                'name': pack.name,
                'cost': pack.cost,
                'emoji': pack.emoji,
                'description': pack.description,
            }
        
        pack = await sync_to_async(fetch_pack)()
        return pack
    except Exception as e:
        print(f"Error fetching pack: {e}")
        return None


async def log_transaction(discord_id: int, amount: int, reason: str):
    """Log a coin transaction to the database"""
    try:
        from bd_models.models import CoinTransaction, Player as DjangoPlayer
        
        def create_transaction():
            player = DjangoPlayer.objects.get(discord_id=discord_id)
            CoinTransaction.objects.create(
                player=player,
                amount=amount,
                reason=reason,
            )
        
        await sync_to_async(create_transaction)()
    except Exception as e:
        print(f"Error logging transaction: {e}")


async def setup(bot: "BallsDexBot"):
    await bot.add_cog(EconomyCommands(bot))
