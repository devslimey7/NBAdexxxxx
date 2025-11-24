"""Packs shop with interactive UI for Discord bot"""
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View, select
from ballsdex.core.models import Player
from ballsdex.settings import settings
from asgiref.sync import sync_to_async

if False:
    from ballsdex.core.bot import BallsDexBot


class PackSelectView(View):
    """Interactive pack selection view"""

    def __init__(self, interaction: discord.Interaction, packs: list, action: str = "buy"):
        super().__init__(timeout=60)
        self.interaction = interaction
        self.packs = packs
        self.action = action
        self.selected_pack = None
        self._update_options()

    @select(placeholder="Choose a pack...", min_values=1, max_values=1)
    async def pack_select(self, interaction: discord.Interaction["BallsDexBot"], select: Select):
        """Select a pack"""
        await interaction.response.defer(ephemeral=True)
        pack_id = int(select.values[0])
        self.selected_pack = next((p for p in self.packs if p["id"] == pack_id), None)

        if not self.selected_pack:
            await interaction.followup.send("Pack not found!", ephemeral=True)
            return

        if self.action == "buy":
            await self.handle_buy(interaction)
        elif self.action == "give":
            await self.handle_give(interaction)
        elif self.action == "open":
            await self.handle_open(interaction)

        self.stop()

    def _update_options(self):
        """Update select options from packs"""
        options = []
        for pack in self.packs:
            emoji = pack.get("emoji", "📦")
            options.append(
                discord.SelectOption(
                    label=pack["name"],
                    description=f"{emoji} • {pack['cost']} coins",
                    value=str(pack["id"]),
                )
            )
        if options:
            self.pack_select.options = options

    async def handle_buy(self, interaction: discord.Interaction["BallsDexBot"]):
        """Handle pack purchase"""
        try:
            player, _ = await Player.get_or_create(discord_id=interaction.user.id)

            if player.coins < self.selected_pack["cost"]:
                await interaction.followup.send(
                    f"Not enough coins! You have {player.coins:,} but need {self.selected_pack['cost']:,}.",
                    ephemeral=True,
                )
                return

            player.coins -= self.selected_pack["cost"]
            await player.save()

            # Log transaction
            await log_transaction(
                interaction.user.id,
                -self.selected_pack["cost"],
                f"Pack purchase: {self.selected_pack['name']}",
            )

            embed = discord.Embed(
                title="✅ Pack Purchased",
                description=f"You bought **{self.selected_pack['name']}**!\nCost: {self.selected_pack['cost']:,} coins",
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    async def handle_give(self, interaction: discord.Interaction["BallsDexBot"]):
        """Handle pack gifting"""
        await interaction.followup.send("Pack gifting coming soon!", ephemeral=True)

    async def handle_open(self, interaction: discord.Interaction["BallsDexBot"]):
        """Handle pack opening"""
        await interaction.followup.send("Pack opening coming soon!", ephemeral=True)


class PacksCommands(commands.Cog):
    """Pack shop commands"""

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot

    # ===== PACKS GROUP =====
    packs = app_commands.Group(name="packs", description="Pack shop")

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
                emoji = pack.get("emoji", "📦")
                embed.add_field(
                    name=f"{emoji} {pack['name']}",
                    value=f"**{pack['cost']} coins**\n{pack['description'] or 'No description'}",
                    inline=False,
                )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"Error loading packs: {e}", ephemeral=True)

    @packs.command(description="Buy a pack with coins")
    async def buy(self, interaction: discord.Interaction["BallsDexBot"]):
        """Buy a pack"""
        await interaction.response.defer(ephemeral=True)
        try:
            packs = await get_enabled_packs()
            if not packs:
                await interaction.followup.send("No packs available!", ephemeral=True)
                return

            view = PackSelectView(interaction, packs, action="buy")
            await interaction.followup.send(
                "Select a pack to buy:", view=view, ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @packs.command(description="View your pack inventory")
    async def inventory(self, interaction: discord.Interaction["BallsDexBot"]):
        """View your pack inventory"""
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.followup.send("Pack inventory coming soon!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @packs.command(description="Give a pack to another player")
    @app_commands.describe(user="User to give pack to")
    async def give(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        user: discord.User,
    ):
        """Give a pack to another player"""
        await interaction.response.defer(ephemeral=True)
        try:
            packs = await get_enabled_packs()
            if not packs:
                await interaction.followup.send("No packs available!", ephemeral=True)
                return

            view = PackSelectView(interaction, packs, action="give")
            await interaction.followup.send(
                f"Select a pack to give to {user.mention}:", view=view, ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @packs.command(description="Open a pack from your inventory")
    async def open(self, interaction: discord.Interaction["BallsDexBot"]):
        """Open a pack"""
        await interaction.response.defer(ephemeral=True)
        try:
            packs = await get_enabled_packs()
            if not packs:
                await interaction.followup.send("No packs available!", ephemeral=True)
                return

            view = PackSelectView(interaction, packs, action="open")
            await interaction.followup.send(
                "Select a pack to open:", view=view, ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)


# Helper functions for database operations
async def get_enabled_packs():
    """Get all enabled packs from the database"""
    try:
        from bd_models.models import Pack

        def fetch_packs():
            return list(
                Pack.objects.filter(enabled=True).values(
                    "id", "name", "cost", "description"
                )
            )

        packs = await sync_to_async(fetch_packs)()
        return packs
    except Exception as e:
        print(f"Error fetching packs: {e}")
        return []


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
    await bot.add_cog(PacksCommands(bot))
