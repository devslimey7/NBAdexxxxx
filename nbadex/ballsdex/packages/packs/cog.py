import random
import discord
from discord.ext import commands
from discord import app_commands

from ballsdex.core.models import Pack, PlayerPack, Player, Ball
from ballsdex.settings import settings

log = __import__("logging").getLogger("ballsdex.packages.packs")


class Packs(commands.Cog):
    """Packs management commands"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command()
    async def packs_list(self, interaction: discord.Interaction):
        """List all available packs."""
        await interaction.response.defer(thinking=True)

        try:
            packs = await Pack.all().filter(enabled=True)

            if not packs:
                await interaction.followup.send(
                    "No packs available at the moment.",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title="📦 Available Packs",
                color=discord.Color.blue(),
            )

            for pack in packs:
                embed.add_field(
                    name=f"**{pack.name}**",
                    value=f"{pack.description or 'No description'}\n💰 **Cost:** {pack.cost} coins",
                    inline=False,
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            log.error(f"Error in packs_list command: {e}")
            await interaction.followup.send(
                "An error occurred while fetching packs.",
                ephemeral=True,
            )

    @app_commands.command()
    @app_commands.describe(pack_name="Name of the pack to buy")
    async def packs_buy(self, interaction: discord.Interaction, pack_name: str):
        """Buy a pack."""
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            player, _ = await Player.get_or_create(discord_id=interaction.user.id)
            pack = await Pack.get_or_none(name=pack_name, enabled=True)

            if not pack:
                await interaction.followup.send(
                    f"Pack '{pack_name}' not found.",
                    ephemeral=True,
                )
                return

            if player.coins < pack.cost:
                await interaction.followup.send(
                    f"You don't have enough coins! You need {pack.cost}, you have {player.coins}.",
                    ephemeral=True,
                )
                return

            player.coins -= pack.cost
            await player.save()

            player_pack, created = await PlayerPack.get_or_create(
                player=player, pack=pack
            )
            if not created:
                player_pack.quantity += 1
                await player_pack.save()

            await interaction.followup.send(
                f"✅ You bought **{pack.name}**! Use `/packs open` to open it.",
                ephemeral=True,
            )

        except Exception as e:
            log.error(f"Error in packs_buy command: {e}")
            await interaction.followup.send(
                "An error occurred while buying the pack.",
                ephemeral=True,
            )

    @app_commands.command()
    async def packs_inventory(self, interaction: discord.Interaction):
        """View your pack inventory."""
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            player, _ = await Player.get_or_create(discord_id=interaction.user.id)
            packs = await PlayerPack.filter(player=player).prefetch_related("pack")

            if not packs:
                await interaction.followup.send(
                    "You don't have any packs.",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title="📦 Your Packs",
                color=discord.Color.blue(),
            )

            for player_pack in packs:
                embed.add_field(
                    name=player_pack.pack.name,
                    value=f"Quantity: **{player_pack.quantity}**",
                    inline=False,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            log.error(f"Error in packs_inventory command: {e}")
            await interaction.followup.send(
                "An error occurred while fetching your inventory.",
                ephemeral=True,
            )

    @app_commands.command()
    @app_commands.describe(pack_name="Name of the pack to open")
    async def packs_open(self, interaction: discord.Interaction, pack_name: str):
        """Open a pack and get a random card."""
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            player, _ = await Player.get_or_create(discord_id=interaction.user.id)
            pack = await Pack.get_or_none(name=pack_name)

            if not pack:
                await interaction.followup.send(
                    f"Pack '{pack_name}' not found.",
                    ephemeral=True,
                )
                return

            player_pack = await PlayerPack.get_or_none(player=player, pack=pack)

            if not player_pack or player_pack.quantity < 1:
                await interaction.followup.send(
                    f"You don't have this pack.",
                    ephemeral=True,
                )
                return

            # Get rewards with weighted selection
            rewards = await pack.pack_rewards.all()

            if not rewards:
                await interaction.followup.send(
                    "This pack has no rewards configured.",
                    ephemeral=True,
                )
                return

            weights = [r.weight for r in rewards]
            selected_reward = random.choices(rewards, weights=weights, k=1)[0]
            ball = selected_reward.ball

            player_pack.quantity -= 1
            if player_pack.quantity <= 0:
                await player_pack.delete()
            else:
                await player_pack.save()

            await interaction.followup.send(
                f"🎉 You got **{ball.country}** from {pack.name}!",
                ephemeral=True,
            )

        except Exception as e:
            log.error(f"Error in packs_open command: {e}")
            await interaction.followup.send(
                "An error occurred while opening the pack.",
                ephemeral=True,
            )

    @app_commands.command()
    @app_commands.describe(user="User to give the pack to", pack_name="Name of the pack", quantity="Number of packs")
    async def packs_give(
        self, interaction: discord.Interaction, user: discord.User, pack_name: str, quantity: int = 1
    ):
        """Give a pack to another user."""
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            sender = await Player.get_or_create(discord_id=interaction.user.id)
            receiver, _ = await Player.get_or_create(discord_id=user.id)
            pack = await Pack.get_or_none(name=pack_name)

            if not pack:
                await interaction.followup.send(
                    f"Pack '{pack_name}' not found.",
                    ephemeral=True,
                )
                return

            sender_pack = await PlayerPack.get_or_none(player=sender[0], pack=pack)

            if not sender_pack or sender_pack.quantity < quantity:
                await interaction.followup.send(
                    f"You don't have {quantity} of this pack.",
                    ephemeral=True,
                )
                return

            sender_pack.quantity -= quantity
            if sender_pack.quantity <= 0:
                await sender_pack.delete()
            else:
                await sender_pack.save()

            receiver_pack, created = await PlayerPack.get_or_create(
                player=receiver, pack=pack
            )
            if not created:
                receiver_pack.quantity += quantity
                await receiver_pack.save()

            await interaction.followup.send(
                f"✅ You gave {quantity}x {pack.name} to {user.mention}.",
                ephemeral=True,
            )

        except Exception as e:
            log.error(f"Error in packs_give command: {e}")
            await interaction.followup.send(
                "An error occurred while giving the pack.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Packs(bot))
