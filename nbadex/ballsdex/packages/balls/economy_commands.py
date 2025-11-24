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
    coins = app_commands.Group(name="coins", description="Coin system")

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


async def setup(bot: "BallsDexBot"):
    await bot.add_cog(EconomyCommands(bot))
