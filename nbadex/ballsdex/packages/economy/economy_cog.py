import logging

import discord
from discord import app_commands
from discord.ext import commands

from ballsdex.core.bot import BallsDexBot
from ballsdex.core.models import Pack, Player, CoinTransaction

log = logging.getLogger("ballsdex.packages.economy")


class Economy(commands.Cog):
    """Economy system for collecting coins and buying packs"""

    def __init__(self, bot: BallsDexBot):
        self.bot = bot

    # COINS COMMAND GROUP
    coins = app_commands.Group(name="coins", description="Coin management commands")

    @coins.command(name="balance", description="Check your coin balance")
    async def coins_balance(self, interaction: discord.Interaction):
        """Check your coin balance"""
        try:
            player, _ = await Player.get_or_create(discord_id=interaction.user.id)
            await interaction.response.send_message(
                f"💰 You have **{player.coins:,}** coins",
                ephemeral=True,
            )
        except Exception as e:
            log.error(f"Error in coins balance: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ An error occurred. Please try again.", ephemeral=True
            )

    @coins.command(name="leaderboard", description="Show top 10 players by coins")
    async def coins_leaderboard(self, interaction: discord.Interaction):
        """Show top 10 players by coins"""
        try:
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
        except Exception as e:
            log.error(f"Error in coins leaderboard: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred. Please try again.", ephemeral=True
            )

    @coins.command(name="send", description="Send coins to another player")
    @app_commands.describe(user="User to send coins to", amount="Amount of coins to send")
    async def coins_send(
        self, interaction: discord.Interaction, user: discord.User, amount: int
    ):
        """Send coins to another player"""
        try:
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
        except Exception as e:
            log.error(f"Error in coins send: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ An error occurred. Please try again.", ephemeral=True
            )

    # PACKS COMMAND GROUP
    packs = app_commands.Group(name="packs", description="Pack management commands")

    @packs.command(name="info", description="See available packs and their contents")
    async def packs_info(self, interaction: discord.Interaction):
        """See available packs and their contents"""
        try:
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
        except Exception as e:
            log.error(f"Error in packs info: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred. Please try again.", ephemeral=True
            )

    @packs.command(name="buy", description="Buy a pack")
    @app_commands.describe(pack_name="Name of the pack to buy")
    async def pack_buy(self, interaction: discord.Interaction, pack_name: str):
        """Buy a pack"""
        try:
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
        except Exception as e:
            log.error(f"Error in pack buy: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ An error occurred. Please try again.", ephemeral=True
            )

    @packs.command(name="open", description="Open a pack")
    @app_commands.describe(pack_name="Name of the pack to open")
    async def pack_open(self, interaction: discord.Interaction, pack_name: str):
        """Open a pack (admin configured via admin panel)"""
        try:
            await interaction.response.send_message(
                f"📦 Opening {pack_name}... (Contents configured in admin panel)",
                ephemeral=True,
            )
        except Exception as e:
            log.error(f"Error in pack open: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ An error occurred. Please try again.", ephemeral=True
            )


async def setup(bot: BallsDexBot):
    await bot.add_cog(Economy(bot))
