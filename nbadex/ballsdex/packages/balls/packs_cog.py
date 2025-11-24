"""Packs shop with autocomplete for Discord bot"""
import discord
import random
from discord import app_commands
from discord.ext import commands
from ballsdex.core.models import Player, Ball, BallInstance
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
    @app_commands.describe(
        sorting="Sort by: name, cost (default: name)",
        reverse="Reverse sort order",
    )
    async def list(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        sorting: str = "name",
        reverse: bool = False,
    ):
        """List all available packs"""
        await interaction.response.defer()
        try:
            packs = await get_enabled_packs()
            if not packs:
                await interaction.followup.send("No packs available!")
                return

            # Sort packs
            if sorting == "cost":
                packs = sorted(packs, key=lambda p: p["cost"], reverse=reverse)
            else:  # default: name
                packs = sorted(packs, key=lambda p: p["name"], reverse=reverse)

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
    @app_commands.describe(
        pack="The pack to buy",
        amount="Number of packs to buy (default: 1)",
    )
    @app_commands.autocomplete(pack=pack_autocomplete)
    async def buy(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        pack: str,
        amount: int = 1,
    ):
        """Buy a pack"""
        await interaction.response.defer(ephemeral=True)
        try:
            if amount <= 0:
                await interaction.followup.send("Amount must be at least 1!", ephemeral=True)
                return

            pack_id = int(pack)
            pack_data = await get_pack_by_id(pack_id)
            
            if not pack_data:
                await interaction.followup.send("Pack not found!", ephemeral=True)
                return

            player, _ = await Player.get_or_create(discord_id=interaction.user.id)
            total_cost = pack_data["cost"] * amount

            if player.coins < total_cost:
                await interaction.followup.send(
                    f"You don't have enough points to buy {amount} pack(s), you need {total_cost - player.coins} more points.",
                    ephemeral=True,
                )
                return

            player.coins -= total_cost
            await player.save()

            await log_transaction(
                interaction.user.id,
                -total_cost,
                f"Pack purchase: {amount}x {pack_data['name']}",
            )

            embed = discord.Embed(
                title="✅ Pack Purchased!",
                description=f"You have successfully bought {amount}x {pack_data['emoji']} **{pack_data['name']}** pack(s)!",
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
        amount="Number of packs to give (default: 1)",
    )
    @app_commands.autocomplete(pack=pack_autocomplete)
    async def give(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        user: discord.User,
        pack: str,
        amount: int = 1,
    ):
        """Give a pack to another player"""
        await interaction.response.defer(ephemeral=True)
        try:
            if amount <= 0:
                await interaction.followup.send("Amount must be at least 1!", ephemeral=True)
                return

            pack_id = int(pack)
            pack_data = await get_pack_by_id(pack_id)
            
            if not pack_data:
                await interaction.followup.send("Pack not found!", ephemeral=True)
                return

            await interaction.followup.send(f"Pack gifting {amount}x packs coming soon!", ephemeral=True)
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

            # Get player
            player, _ = await Player.get_or_create(discord_id=interaction.user.id)
            
            # Draw an NBA from the pack based on rarity
            ball_instance = await draw_ball_from_pack(pack_id, player)
            if not ball_instance:
                await interaction.followup.send(
                    f"Pack contains no available NBAs!", ephemeral=True
                )
                return
            
            # Award coins for opening the pack
            await award_coins_from_reward(interaction.user.id, "pack_open", pack_data["name"])
            
            # Get ball name for message
            ball_name = ball_instance.ball.country
            emoji = interaction.client.get_emoji(ball_instance.ball.emoji_id)
            
            embed = discord.Embed(
                title="🎉 Pack Opened!",
                description=f"You found: {emoji} **{ball_name}**!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Stats",
                value=f"HP: {ball_instance.hp} | ATK: {ball_instance.attack}",
                inline=False
            )
            embed.add_field(
                name="Bonus",
                value=f"💰 Coins awarded for opening pack!",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        except ValueError:
            await interaction.followup.send("Invalid pack!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)


# Helper functions
async def get_enabled_packs():
    """Get all enabled packs from the database"""
    try:
        import psycopg
        from ballsdex.core.models import Tortoise
        
        # Use the same connection as Tortoise ORM
        db = Tortoise.get_connection("default")
        
        # Query packs directly from the database
        query = "SELECT id, name, cost, description, emoji FROM pack WHERE enabled = true ORDER BY name"
        result = await db.execute_query(query)
        
        packs = []
        for row in result:
            packs.append({
                "id": row[0],
                "name": row[1],
                "cost": row[2],
                "description": row[3],
                "emoji": row[4],
            })
        return packs
    except Exception as e:
        print(f"Error fetching packs: {e}")
        import traceback
        traceback.print_exc()
        return []


async def get_pack_by_id(pack_id: int):
    """Get a pack by ID"""
    try:
        from ballsdex.core.models import Tortoise
        
        db = Tortoise.get_connection("default")
        query = "SELECT id, name, cost, description, emoji FROM pack WHERE id = %s AND enabled = true"
        result = await db.execute_query(query, [pack_id])
        
        if result:
            row = result[0]
            return {
                "id": row[0],
                "name": row[1],
                "cost": row[2],
                "description": row[3],
                "emoji": row[4],
            }
        return None
    except Exception as e:
        print(f"Error fetching pack: {e}")
        import traceback
        traceback.print_exc()
        return None


async def get_user_pack_count(discord_id: int, pack_id: int):
    """Get count of packs owned by user"""
    try:
        from ballsdex.core.models import Tortoise
        
        db = Tortoise.get_connection("default")
        query = """
            SELECT COUNT(*) FROM player_pack pp
            JOIN player p ON pp.player_id = p.id
            WHERE p.discord_id = %s AND pp.pack_id = %s
        """
        result = await db.execute_query(query, [discord_id, pack_id])
        return result[0][0] if result else 0
    except Exception as e:
        print(f"Error counting packs: {e}")
        return 0


async def get_user_packs(discord_id: int):
    """Get all packs owned by user"""
    try:
        from ballsdex.core.models import Tortoise
        
        db = Tortoise.get_connection("default")
        query = """
            SELECT pa.name, pa.cost, COUNT(pp.id) as count
            FROM player_pack pp
            JOIN pack pa ON pp.pack_id = pa.id
            JOIN player p ON pp.player_id = p.id
            WHERE p.discord_id = %s
            GROUP BY pa.id, pa.name, pa.cost
        """
        result = await db.execute_query(query, [discord_id])
        
        packs = []
        for row in result:
            packs.append({
                "name": row[0],
                "cost": row[1],
                "count": row[2],
                "emoji": "📦",
            })
        return packs
    except Exception as e:
        print(f"Error fetching user packs: {e}")
        import traceback
        traceback.print_exc()
        return []


async def log_transaction(discord_id: int, amount: int, reason: str):
    """Log a coin transaction"""
    try:
        from ballsdex.core.models import Tortoise
        
        db = Tortoise.get_connection("default")
        # First get the player ID
        player_query = "SELECT id FROM player WHERE discord_id = %s"
        player_result = await db.execute_query(player_query, [discord_id])
        
        if not player_result:
            print(f"Player not found for discord_id {discord_id}")
            return
        
        player_id = player_result[0][0]
        
        # Then insert the transaction
        insert_query = """
            INSERT INTO cointransaction (player_id, amount, reason)
            VALUES (%s, %s, %s)
        """
        await db.execute_query(insert_query, [player_id, amount, reason])
    except Exception as e:
        print(f"Error logging transaction: {e}")
        import traceback
        traceback.print_exc()


async def get_coin_reward(reward_name: str) -> int:
    """Get coin reward amount from database"""
    try:
        from bd_models.models import CoinReward

        def fetch_reward():
            reward = CoinReward.objects.get(name=reward_name)
            return reward.base_coins

        return await sync_to_async(fetch_reward)()
    except Exception as e:
        print(f"Error fetching reward '{reward_name}': {e}")
        return 0


async def award_coins_from_reward(discord_id: int, reward_name: str, context: str = ""):
    """Award coins to player based on CoinReward and log transaction"""
    try:
        from bd_models.models import Player as DjangoPlayer
        
        # Get reward amount from database
        coin_amount = await get_coin_reward(reward_name)
        if coin_amount <= 0:
            return
        
        # Update player coins in Tortoise
        player, _ = await Player.get_or_create(discord_id=discord_id)
        player.coins += coin_amount
        await player.save(update_fields=("coins",))
        
        # Log transaction
        reason = f"{reward_name}: {context}" if context else reward_name
        await log_transaction(discord_id, coin_amount, reason)
        
    except Exception as e:
        print(f"Error awarding coins: {e}")


async def get_pack_contents(pack_id: int):
    """Get all NBAs in a pack with their rarity"""
    try:
        from bd_models.models import PackContent

        def fetch_contents():
            contents = list(
                PackContent.objects.filter(pack_id=pack_id).values("ball_id", "rarity")
            )
            return contents

        return await sync_to_async(fetch_contents)()
    except Exception as e:
        print(f"Error fetching pack contents: {e}")
        return []


async def draw_ball_from_pack(pack_id: int, player: Player) -> BallInstance | None:
    """Draw a random NBA from pack based on rarity and create BallInstance"""
    try:
        # Get pack contents
        contents = await get_pack_contents(pack_id)
        if not contents:
            return None
        
        # Weight-based random selection based on rarity
        ball_ids = [c["ball_id"] for c in contents]
        weights = [c["rarity"] for c in contents]
        
        selected_ball_id = random.choices(ball_ids, weights=weights, k=1)[0]
        
        # Get the Ball model
        ball = await Ball.get(id=selected_ball_id)
        
        # Create BallInstance for the player
        ball_instance = await BallInstance.create(
            player=player,
            ball=ball,
            hp=ball.health,
            attack=ball.attack,
        )
        
        return ball_instance
    except Exception as e:
        print(f"Error drawing ball from pack: {e}")
        return None


async def setup(bot: "BallsDexBot"):
    await bot.add_cog(PacksCommands(bot))
