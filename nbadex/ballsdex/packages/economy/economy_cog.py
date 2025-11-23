import logging

import discord
from discord import app_commands
from discord.ext import commands

from ballsdex.core.bot import BallsDexBot
from ballsdex.core.models import Pack, Player, CoinTransaction
from ballsdex.settings import settings

log = logging.getLogger("ballsdex.packages.economy")


class Economy(commands.Cog):
    """Economy system for collecting coins and buying packs"""

    def __init__(self, bot: BallsDexBot):
        self.bot = bot
        
        # Create command groups
        self.coins = app_commands.Group(
            name="coins", 
            description="Coin commands"
        )
        self.packs = app_commands.Group(
            name="packs",
            description="Pack commands"
        )
        self.pack = app_commands.Group(
            name="pack",
            description="Single pack commands"
        )
        
        # Add commands to groups
        self.coins.add_command(self.balance_cmd)
        self.coins.add_command(self.leaderboard_cmd)
        self.packs.add_command(self.info_cmd)
        self.packs.add_command(self.buy_cmd)
        self.packs.add_command(self.open_cmd)
        self.pack.add_command(self.give_cmd)
        
        # Add groups to bot tree
        self.bot.tree.add_command(self.coins)
        self.bot.tree.add_command(self.packs)
        self.bot.tree.add_command(self.pack)

    @app_commands.command(name="balance", description="Check your coin balance")
    async def balance_cmd(self, interaction: discord.Interaction):
        """Check your coin balance"""
        player, _ = await Player.get_or_create(discord_id=interaction.user.id)
        await interaction.response.send_message(
            f"💰 You have **{player.coins:,}** coins",
            ephemeral=True,
        )

    @app_commands.command(name="leaderboard", description="Show top 10 players by coins")
    async def leaderboard_cmd(self, interaction: discord.Interaction):
        """Show top 10 players by coins"""
        await interaction.response.defer()

        top_players = await Player.all().order_by("-coins").limit(10)

        if not top_players:
            await interaction.followup.send("No players yet!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🏆 Coins Leaderboard",
            color=discord.Color.gold(),
        )

        for idx, player in enumerate(top_players, 1):
            medal = ["🥇", "🥈", "🥉"][idx - 1] if idx <= 3 else f"{idx}️⃣"
            embed.add_field(
                name=f"{medal} User #{player.discord_id}",
                value=f"**{player.coins:,}** coins",
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="info", description="See available packs and their contents")
    async def info_cmd(self, interaction: discord.Interaction):
        """See available packs and their contents"""
        await interaction.response.defer()

        packs = await Pack.filter(enabled=True).order_by("cost")

        if not packs:
            await interaction.followup.send(
                "No packs available at the moment.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📦 Available Packs",
            color=discord.Color.blurple(),
        )

        for pack in packs:
            embed.add_field(
                name=f"{pack.name} - {pack.cost} coins",
                value=pack.description,
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="buy", description="Buy a pack")
    @app_commands.describe(pack_name="Name of the pack to buy")
    async def buy_cmd(self, interaction: discord.Interaction, pack_name: str):
        """Buy a pack"""
        player, _ = await Player.get_or_create(discord_id=interaction.user.id)

        pack = await Pack.filter(name=pack_name, enabled=True).first()
        if not pack:
            await interaction.response.send_message(
                f"Pack '{pack_name}' not found or is disabled.", ephemeral=True
            )
            return

        if player.coins < pack.cost:
            await interaction.response.send_message(
                f"❌ Insufficient coins! You need {pack.cost} coins but only have {player.coins}.",
                ephemeral=True,
            )
            return

        player.coins -= pack.cost
        await player.save(update_fields=("coins",))

        await CoinTransaction.create(
            player=player, amount=-pack.cost, reason=f"Pack Purchase: {pack.name}"
        )

        await interaction.response.send_message(
            f"✅ Purchased **{pack.name}** for {pack.cost} coins!\n"
            f"Remaining balance: **{player.coins:,}** coins",
            ephemeral=True,
        )

    @app_commands.command(name="open", description="Open a pack")
    @app_commands.describe(pack_name="Name of the pack to open")
    async def open_cmd(self, interaction: discord.Interaction, pack_name: str):
        """Open a pack (admin configured via admin panel)"""
        await interaction.response.send_message(
            f"📦 Opening {pack_name}... (Contents configured in admin panel)",
            ephemeral=True,
        )

    @app_commands.command(name="give", description="Give coins to another player")
    @app_commands.describe(
        user="User to give coins to", amount="Number of coins to give"
    )
    async def give_cmd(
        self, interaction: discord.Interaction, user: discord.User, amount: int
    ):
        """Give coins to another player"""
        if amount <= 0:
            await interaction.response.send_message(
                "❌ Amount must be positive!", ephemeral=True
            )
            return

        sender, _ = await Player.get_or_create(discord_id=interaction.user.id)
        receiver, _ = await Player.get_or_create(discord_id=user.id)

        if sender.coins < amount:
            await interaction.response.send_message(
                f"❌ Insufficient coins! You need {amount} coins but only have {sender.coins}.",
                ephemeral=True,
            )
            return

        sender.coins -= amount
        receiver.coins += amount

        await sender.save(update_fields=("coins",))
        await receiver.save(update_fields=("coins",))

        await CoinTransaction.create(
            player=sender, amount=-amount, reason=f"Coin transfer to {user.id}"
        )
        await CoinTransaction.create(
            player=receiver, amount=amount, reason=f"Coin transfer from {interaction.user.id}"
        )

        await interaction.response.send_message(
            f"✅ Sent **{amount}** coins to {user.mention}!",
            ephemeral=True,
        )


async def setup(bot: BallsDexBot):
    await bot.add_cog(Economy(bot))
