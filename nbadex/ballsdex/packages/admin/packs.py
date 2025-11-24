from typing import TYPE_CHECKING

import discord
from discord import app_commands
from tortoise.exceptions import DoesNotExist

from ballsdex.core.models import Pack, Player, PlayerPack

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


class Packs(app_commands.Group):
    """Admin pack management commands"""

    @app_commands.command()
    async def add(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        user: discord.User,
        pack: str,
        amount: int = 1,
    ):
        """Add packs to a user"""
        await interaction.response.defer()
        
        try:
            player, _ = await Player.get_or_create(discord_id=user.id)
            pack_obj = await Pack.filter(name__icontains=pack).first()
            
            if not pack_obj:
                await interaction.followup.send("Pack not found.", ephemeral=True)
                return
            
            player_pack, created = await PlayerPack.get_or_create(
                player=player, pack=pack_obj
            )
            if not created:
                player_pack.count += amount
                await player_pack.save()
            
            await interaction.followup.send(
                f"✅ Added {amount}x **{pack_obj.name}** to {user.mention}"
            )
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @app_commands.command()
    async def remove(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        user: discord.User,
        pack: str,
        amount: int = 1,
    ):
        """Remove packs from a user"""
        await interaction.response.defer()
        
        try:
            player = await Player.get(discord_id=user.id)
            pack_obj = await Pack.filter(name__icontains=pack).first()
            
            if not pack_obj:
                await interaction.followup.send("Pack not found.", ephemeral=True)
                return
            
            player_pack = await PlayerPack.filter(player=player, pack=pack_obj).first()
            if not player_pack:
                await interaction.followup.send(
                    f"{user.mention} doesn't own this pack.", ephemeral=True
                )
                return
            
            if player_pack.count <= amount:
                await player_pack.delete()
                await interaction.followup.send(
                    f"✅ Removed all **{pack_obj.name}** from {user.mention}"
                )
            else:
                player_pack.count -= amount
                await player_pack.save()
                await interaction.followup.send(
                    f"✅ Removed {amount}x **{pack_obj.name}** from {user.mention}"
                )
        except DoesNotExist:
            await interaction.followup.send("Player not found.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)
