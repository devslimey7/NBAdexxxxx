"""Packs shop with autocomplete for Discord bot"""
import discord
from discord import app_commands
from discord.ext import commands
from ballsdex.core.models import Player
from ballsdex.settings import settings
from asgiref.sync import sync_to_async

if False:
    from ballsdex.core.bot import BallsDexBot


async def pack_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Autocomplete for pack names"""
    packs = await get_enabled_packs()
    matches = [
        p for p in packs if current.lower() in p["name"].lower()
    ]
    return [
        app_commands.Choice(name=f"{p['name']} • {p['cost']} points", value=str(p["id"]))
        for p in matches[:25]
    ]


class PacksCommands(commands.Cog):
    """Pack shop commands"""

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot

    # ===== PACKS GROUP =====
    packs = app_commands.Group(name="packs", description="Pack shop")

    @packs.command(description="List all packs")
    async def list(self, interaction: discord.Interaction["BallsDexBot"]):
        """List all available packs"""
        await interaction.response.defer()
        try:
            packs = await get_enabled_packs()
            if not packs:
                await interaction.followup.send("No packs available!")
                return

            embed = discord.Embed(title="📦 Available Packs", color=discord.Color.blue())
            for pack in packs:
                # Count how many user owns
                owned_count = await get_user_pack_count(interaction.user.id, pack["id"])
                embed.add_field(
                    name=f"{pack['emoji']} {pack['name']}, {pack['cost']} points 💰 (You own {owned_count})",
                    value="",
                    inline=False,
                )

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @packs.command(description="Buy a pack with coins")
    @app_commands.describe(pack="The pack to buy")
    @app_commands.autocomplete(pack=pack_autocomplete)
    async def buy(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        pack: str,
    ):
        """Buy a pack"""
        await interaction.response.defer(ephemeral=True)
        try:
            pack_id = int(pack)
            pack_data = await get_pack_by_id(pack_id)
            
            if not pack_data:
                await interaction.followup.send("Pack not found!", ephemeral=True)
                return

            player, _ = await Player.get_or_create(discord_id=interaction.user.id)

            if player.coins < pack_data["cost"]:
                await interaction.followup.send(
                    f"You don't have enough points to buy 1 pack, you need {pack_data['cost'] - player.coins} more points.",
                    ephemeral=True,
                )
                return

            player.coins -= pack_data["cost"]
            await player.save()

            await log_transaction(
                interaction.user.id,
                -pack_data["cost"],
                f"Pack purchase: {pack_data['name']}",
            )

            embed = discord.Embed(
                title="✅ Pack Purchased!",
                description=f"You have successfully bought 1x {pack_data['emoji']} **{pack_data['name']}** pack!",
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.followup.send("Invalid pack!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @packs.command(description="View your pack inventory")
    async def inventory(self, interaction: discord.Interaction["BallsDexBot"]):
        """View your pack inventory"""
        await interaction.response.defer(ephemeral=True)
        try:
            packs = await get_user_packs(interaction.user.id)
            if not packs:
                await interaction.followup.send("You don't own any packs!", ephemeral=True)
                return

            embed = discord.Embed(title="🎁 Your Pack Inventory", color=discord.Color.gold())
            for pack in packs:
                embed.add_field(
                    name=f"{pack['emoji']} {pack['name']} 🎁 ({pack['count']} owned)",
                    value=f"Value of each pack: {pack['cost']} points 💰",
                    inline=False,
                )
            embed.description = "To buy a pack, use `/packs buy`"
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @packs.command(description="Give a pack to another player")
    @app_commands.describe(
        user="The user to give the pack to",
        pack="The pack to give",
    )
    @app_commands.autocomplete(pack=pack_autocomplete)
    async def give(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        user: discord.User,
        pack: str,
    ):
        """Give a pack to another player"""
        await interaction.response.defer(ephemeral=True)
        try:
            pack_id = int(pack)
            pack_data = await get_pack_by_id(pack_id)
            
            if not pack_data:
                await interaction.followup.send("Pack not found!", ephemeral=True)
                return

            await interaction.followup.send("Pack gifting coming soon!", ephemeral=True)
        except ValueError:
            await interaction.followup.send("Invalid pack!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @packs.command(description="Open a pack from your inventory")
    @app_commands.describe(
        pack="The pack to open",
        ephemeral="Whether to show only to you",
    )
    @app_commands.autocomplete(pack=pack_autocomplete)
    async def open(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        pack: str,
        ephemeral: bool = True,
    ):
        """Open a pack"""
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            pack_id = int(pack)
            pack_data = await get_pack_by_id(pack_id)
            
            if not pack_data:
                await interaction.followup.send("Pack not found!", ephemeral=True)
                return

            await interaction.followup.send("Pack opening coming soon!", ephemeral=ephemeral)
        except ValueError:
            await interaction.followup.send("Invalid pack!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)


# Helper functions
async def get_enabled_packs():
    """Get all enabled packs from the database"""
    try:
        from bd_models.models import Pack

        def fetch_packs():
            return list(
                Pack.objects.filter(enabled=True).values("id", "name", "cost", "description")
            )

        packs = await sync_to_async(fetch_packs)()
        # Add default emoji
        for pack in packs:
            pack["emoji"] = "📦"
        return packs
    except Exception as e:
        print(f"Error fetching packs: {e}")
        return []


async def get_pack_by_id(pack_id: int):
    """Get a pack by ID"""
    try:
        from bd_models.models import Pack

        def fetch_pack():
            pack = Pack.objects.get(id=pack_id, enabled=True)
            return {
                "id": pack.id,
                "name": pack.name,
                "cost": pack.cost,
                "emoji": "📦",
                "description": pack.description,
            }

        return await sync_to_async(fetch_pack)()
    except Exception as e:
        print(f"Error fetching pack: {e}")
        return None


async def get_user_pack_count(discord_id: int, pack_id: int):
    """Get count of packs owned by user"""
    try:
        from bd_models.models import PlayerPack

        def count_packs():
            from bd_models.models import Player as DjangoPlayer
            try:
                player = DjangoPlayer.objects.get(discord_id=discord_id)
                count = PlayerPack.objects.filter(player=player, pack_id=pack_id).count()
                return count
            except:
                return 0

        return await sync_to_async(count_packs)()
    except Exception:
        return 0


async def get_user_packs(discord_id: int):
    """Get all packs owned by user"""
    try:
        from bd_models.models import PlayerPack, Player as DjangoPlayer
        from django.db.models import Count

        def fetch_user_packs():
            try:
                player = DjangoPlayer.objects.get(discord_id=discord_id)
                packs = (
                    PlayerPack.objects.filter(player=player)
                    .values("pack__name", "pack__cost")
                    .annotate(count=Count("id"))
                )
                result = []
                for p in packs:
                    result.append(
                        {
                            "name": p["pack__name"],
                            "cost": p["pack__cost"],
                            "count": p["count"],
                            "emoji": "📦",
                        }
                    )
                return result
            except:
                return []

        return await sync_to_async(fetch_user_packs)()
    except Exception as e:
        print(f"Error fetching user packs: {e}")
        return []


async def log_transaction(discord_id: int, amount: int, reason: str):
    """Log a coin transaction"""
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
    await bot.add_cog(PacksCommands(bot))
