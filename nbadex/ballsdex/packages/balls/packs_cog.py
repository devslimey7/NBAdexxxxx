import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ballsdex.core.models import Pack, Player, PlayerPack

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("ballsdex.packages.packs")


class Packs(commands.Cog):
    """Pack shop and management"""

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot

    packs = app_commands.Group(name="packs", description="Pack management")

    @packs.command(name="list")
    @app_commands.describe(sorting="Sort by: alphabetical, price, or reward")
    async def packs_list(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        sorting: str | None = None,
    ):
        """View all available packs"""
        await interaction.response.defer()
        
        try:
            packs = await Pack.all()
            if not packs:
                await interaction.followup.send("No packs available.")
                return

            if sorting == "alphabetical":
                packs = sorted(packs, key=lambda p: p.name)
            elif sorting == "price":
                packs = sorted(packs, key=lambda p: p.cost)
            elif sorting == "reward":
                packs = sorted(packs, key=lambda p: p.open_reward)

            player, _ = await Player.get_or_create(discord_id=interaction.user.id)
            player_packs = await PlayerPack.filter(player=player).all()
            ownership = {pp.pack_id: pp.count for pp in player_packs}

            embed = discord.Embed(title="Pack Shop", color=discord.Color.blue())
            for i, pack in enumerate(packs, 1):
                owned = ownership.get(pack.id, 0)
                emoji = pack.emoji or "📦"
                embed.add_field(
                    name=f"{i}. {emoji} {pack.name}",
                    value=f"{pack.description}\nCost: {pack.cost} 💰 (You own {owned})",
                    inline=False,
                )
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            log.error(f"Error in packs list: {e}")
            await interaction.followup.send("Error listing packs.", ephemeral=True)

    @packs.command(name="buy")
    @app_commands.describe(pack="Pack to buy", amount="How many (default 1)")
    async def packs_buy(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        pack: str,
        amount: int = 1,
    ):
        """Buy a pack"""
        await interaction.response.defer()

        try:
            player, _ = await Player.get_or_create(discord_id=interaction.user.id)
            pack_obj = await Pack.filter(name__icontains=pack).first()
            
            if not pack_obj:
                await interaction.followup.send("Pack not found.", ephemeral=True)
                return

            total_cost = pack_obj.cost * amount
            if player.coins < total_cost:
                await interaction.followup.send(
                    f"❌ Not enough coins! Need {total_cost}, have {player.coins}.",
                    ephemeral=True,
                )
                return

            player.coins -= total_cost
            await player.save()

            player_pack, created = await PlayerPack.get_or_create(player=player, pack=pack_obj)
            if not created:
                player_pack.count += amount
                await player_pack.save()
            else:
                player_pack.count = amount
                await player_pack.save()

            emoji = pack_obj.emoji or "📦"
            await interaction.followup.send(
                f"✅ Bought {amount}x {emoji} **{pack_obj.name}**!\n"
                f"Spent {total_cost} coins. Balance: {player.coins}"
            )
        except Exception as e:
            log.error(f"Error in packs buy: {e}")
            await interaction.followup.send("Error buying pack.", ephemeral=True)

    @packs.command(name="inventory")
    async def packs_inventory(self, interaction: discord.Interaction["BallsDexBot"]):
        """View your owned packs"""
        await interaction.response.defer()

        try:
            player, _ = await Player.get_or_create(discord_id=interaction.user.id)
            player_packs = await PlayerPack.filter(player=player).prefetch_related("pack").all()

            if not player_packs:
                await interaction.followup.send("You don't own any packs.")
                return

            embed = discord.Embed(title="Your Pack Inventory", color=discord.Color.green())
            for pp in player_packs:
                emoji = pp.pack.emoji or "📦"
                embed.add_field(
                    name=f"{emoji} {pp.pack.name}",
                    value=f"**{pp.count}** owned",
                    inline=True,
                )

            await interaction.followup.send(embed=embed)
        except Exception as e:
            log.error(f"Error in packs inventory: {e}")
            await interaction.followup.send("Error viewing inventory.", ephemeral=True)

    @packs.command(name="open")
    @app_commands.describe(pack="Pack to open")
    async def packs_open(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        pack: str,
    ):
        """Open a pack you own"""
        await interaction.response.defer()

        try:
            player, _ = await Player.get_or_create(discord_id=interaction.user.id)
            pack_obj = await Pack.filter(name__icontains=pack).first()
            
            if not pack_obj:
                await interaction.followup.send("Pack not found.", ephemeral=True)
                return

            player_pack = await PlayerPack.filter(player=player, pack=pack_obj).first()
            if not player_pack or player_pack.count < 1:
                await interaction.followup.send("❌ You don't own this pack!", ephemeral=True)
                return

            player_pack.count -= 1
            if player_pack.count == 0:
                await player_pack.delete()
            else:
                await player_pack.save()

            emoji = pack_obj.emoji or "📦"
            await interaction.followup.send(
                f"🎉 Opened {emoji} **{pack_obj.name}**!\nCheck pack description for rewards!"
            )
        except Exception as e:
            log.error(f"Error in packs open: {e}")
            await interaction.followup.send("Error opening pack.", ephemeral=True)

    @packs.command(name="give")
    @app_commands.describe(user="User to give to", pack="Pack to give", amount="Amount (default 1)")
    async def packs_give(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        user: discord.User,
        pack: str,
        amount: int = 1,
    ):
        """Give pack to another user"""
        await interaction.response.defer()

        try:
            from_player, _ = await Player.get_or_create(discord_id=interaction.user.id)
            to_player, _ = await Player.get_or_create(discord_id=user.id)
            pack_obj = await Pack.filter(name__icontains=pack).first()
            
            if not pack_obj:
                await interaction.followup.send("Pack not found.", ephemeral=True)
                return

            from_pack = await PlayerPack.filter(player=from_player, pack=pack_obj).first()
            if not from_pack or from_pack.count < amount:
                await interaction.followup.send(f"❌ You don't have {amount}x of this pack!", ephemeral=True)
                return

            from_pack.count -= amount
            if from_pack.count == 0:
                await from_pack.delete()
            else:
                await from_pack.save()

            to_pack, created = await PlayerPack.get_or_create(player=to_player, pack=pack_obj)
            if not created:
                to_pack.count += amount
                await to_pack.save()

            emoji = pack_obj.emoji or "📦"
            await interaction.followup.send(f"✅ Gave {amount}x {emoji} **{pack_obj.name}** to {user.mention}!")
        except Exception as e:
            log.error(f"Error in packs give: {e}")
            await interaction.followup.send("Error giving pack.", ephemeral=True)


async def setup(bot: "BallsDexBot"):
    await bot.add_cog(Packs(bot))
