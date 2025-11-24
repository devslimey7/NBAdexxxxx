"""Economy system commands for Discord bot"""
import discord
from discord import app_commands
from discord.ext import commands
from ballsdex.core.models import Player
from ballsdex.settings import settings

if False:
    from ballsdex.core.bot import BallsDexBot


class EconomyCommands(commands.Cog):
    """Economy system commands"""

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot

    # ===== COINS GROUP =====
    coins = app_commands.Group(name="coins", description="Coin management commands")

    @coins.command(name="balance", description="Check your coin balance")
    async def coins_balance(self, interaction: discord.Interaction["BallsDexBot"]):
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

    @coins.command(name="leaderboard", description="View top coin holders")
    async def coins_leaderboard(self, interaction: discord.Interaction["BallsDexBot"]):
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

    # ===== PLAYER COINS GROUP =====
    player_coins = app_commands.Group(
        name="player_coins",
        description="Player coin management",
        parent=None,
    )

    @player_coins.command(name="give", description="Give coins to a player")
    @app_commands.describe(
        user="User to give coins to",
        amount="Amount of coins to give",
        reason="Reason for giving coins",
    )
    async def player_coins_give(
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
            embed = discord.Embed(
                title="✅ Coins Given",
                description=f"Gave **{amount:,}** coins to {user.mention}\nReason: {reason}",
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    # ===== TRADE COINS GROUP =====
    trade_coins = app_commands.Group(
        name="trade_coins",
        description="Trade coin management",
        parent=None,
    )

    @trade_coins.command(name="add", description="Add coins to a player's balance")
    @app_commands.describe(
        user="User to add coins to",
        amount="Amount of coins to add",
        reason="Reason for adding coins",
    )
    async def trade_coins_add(
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
            embed = discord.Embed(
                title="✅ Coins Added",
                description=f"Added **{amount:,}** coins to {user.mention}\nReason: {reason}",
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @trade_coins.command(name="remove", description="Remove coins from a player's balance")
    @app_commands.describe(
        user="User to remove coins from",
        amount="Amount of coins to remove",
        reason="Reason for removing coins",
    )
    async def trade_coins_remove(
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
            embed = discord.Embed(
                title="✅ Coins Removed",
                description=f"Removed **{amount:,}** coins from {user.mention}\nReason: {reason}",
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    # ===== PACKS GROUP =====
    packs = app_commands.Group(name="packs", description="Pack management commands")

    @packs.command(name="list", description="List available packs")
    async def packs_list(self, interaction: discord.Interaction["BallsDexBot"]):
        """List available packs"""
        await interaction.response.defer()
        try:
            from bd_models.models import Pack

            packs = await Pack.objects.all()
            if not packs:
                await interaction.followup.send("No packs available!")
                return
            embed = discord.Embed(title="📦 Available Packs", color=discord.Color.blue())
            for pack in packs:
                status = "✅ Available" if pack.enabled else "❌ Disabled"
                embed.add_field(
                    name=f"{pack.name} ({pack.cost} coins)",
                    value=f"{pack.description}\n{status}",
                    inline=False,
                )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @packs.command(name="buy", description="Buy a pack")
    @app_commands.describe(pack_name="Name of the pack to buy")
    async def packs_buy(self, interaction: discord.Interaction["BallsDexBot"], pack_name: str):
        """Buy a pack"""
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.followup.send("Pack buying coming soon!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @packs.command(name="inventory", description="View your pack inventory")
    async def packs_inventory(self, interaction: discord.Interaction["BallsDexBot"]):
        """View your pack inventory"""
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.followup.send("Pack inventory coming soon!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @packs.command(name="give", description="Give a pack to another player")
    @app_commands.describe(
        user="User to give pack to",
        pack_name="Name of the pack to give",
    )
    async def packs_give(
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

    @packs.command(name="open", description="Open a pack from your inventory")
    @app_commands.describe(pack_name="Name of the pack to open")
    async def packs_open(
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


async def setup(bot: "BallsDexBot"):
    await bot.add_cog(EconomyCommands(bot))
