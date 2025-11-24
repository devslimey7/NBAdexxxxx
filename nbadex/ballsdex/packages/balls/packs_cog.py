"""Packs shop with paginated UI for Discord bot"""
import discord
from discord import app_commands
from discord.ext import commands
from ballsdex.core.models import Player
from ballsdex.core.utils.paginator import Pages
from ballsdex.core.utils.menus import ListPageSource
from ballsdex.settings import settings
from asgiref.sync import sync_to_async

if False:
    from ballsdex.core.bot import BallsDexBot


class PackPageSource(ListPageSource):
    """Page source for displaying packs"""

    def __init__(self, entries, cog):
        super().__init__(entries, per_page=5)
        self.cog = cog

    async def format_page(self, menu: Pages, entries):
        embed = discord.Embed(title="📦 Available Packs", color=discord.Color.blue())
        
        for pack in entries:
            embed.add_field(
                name=f"{pack['emoji']} {pack['name']}",
                value=f"**{pack['cost']} coins** - {pack['description'] or 'No description'}",
                inline=False,
            )

        maximum = self.get_max_pages()
        if maximum > 1:
            embed.set_footer(text=f"Page {menu.current_page + 1}/{maximum}")
        
        return embed


class PackSelectPages(Pages):
    """Paginated pack selector with confirmation"""

    def __init__(self, interaction: discord.Interaction["BallsDexBot"], packs: list, cog, action: str = "buy"):
        source = PackPageSource(packs, cog)
        super().__init__(source, interaction=interaction)
        self.packs = packs
        self.cog = cog
        self.action = action
        self.selected_pack = None

    async def on_pack_select(self, pack_id: int, interaction: discord.Interaction["BallsDexBot"]):
        """Called when a pack is selected"""
        self.selected_pack = next((p for p in self.packs if p["id"] == pack_id), None)
        
        if not self.selected_pack:
            await interaction.response.send_message("Pack not found!", ephemeral=True)
            return

        if self.action == "buy":
            await self.handle_buy(interaction)
        elif self.action == "give":
            await self.handle_give(interaction)
        elif self.action == "open":
            await self.handle_open(interaction)

    async def handle_buy(self, interaction: discord.Interaction["BallsDexBot"]):
        """Handle pack purchase with confirmation"""
        try:
            # Show confirmation
            view = discord.ui.View()
            
            async def confirm_callback(button_interaction: discord.Interaction):
                await button_interaction.response.defer(ephemeral=True)
                player, _ = await Player.get_or_create(discord_id=button_interaction.user.id)
                
                if player.coins < self.selected_pack["cost"]:
                    await button_interaction.followup.send(
                        f"Not enough coins! You have {player.coins:,} but need {self.selected_pack['cost']:,}.",
                        ephemeral=True,
                    )
                    return
                
                player.coins -= self.selected_pack["cost"]
                await player.save()
                
                await log_transaction(
                    button_interaction.user.id,
                    -self.selected_pack["cost"],
                    f"Pack purchase: {self.selected_pack['name']}",
                )
                
                embed = discord.Embed(
                    title="✅ Pack Purchased!",
                    description=f"You successfully bought 1x {self.selected_pack['emoji']} **{self.selected_pack['name']}** pack!",
                    color=discord.Color.green(),
                )
                await button_interaction.followup.send(embed=embed, ephemeral=True)
            
            async def cancel_callback(button_interaction: discord.Interaction):
                await button_interaction.response.defer(ephemeral=True)
                await button_interaction.followup.send("Purchase cancelled.", ephemeral=True)
            
            yes_button = discord.ui.Button(style=discord.ButtonStyle.success, label="✓ Yes", custom_id="pack_confirm_yes")
            no_button = discord.ui.Button(style=discord.ButtonStyle.danger, label="✗ No", custom_id="pack_confirm_no")
            
            yes_button.callback = confirm_callback
            no_button.callback = cancel_callback
            
            view.add_item(yes_button)
            view.add_item(no_button)
            
            embed = discord.Embed(
                title="Confirm Purchase",
                description=f"Are you sure you want to buy 1x {self.selected_pack['emoji']} **{self.selected_pack['name']}** pack for **{self.selected_pack['cost']} coins**?",
                color=discord.Color.blurple(),
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    async def handle_give(self, interaction: discord.Interaction["BallsDexBot"]):
        """Handle pack gifting"""
        await interaction.response.send_message("Pack gifting coming soon!", ephemeral=True)

    async def handle_open(self, interaction: discord.Interaction["BallsDexBot"]):
        """Handle pack opening"""
        await interaction.response.send_message("Pack opening coming soon!", ephemeral=True)


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

            source = PackPageSource(packs, self)
            pages = Pages(source=source, interaction=interaction)
            await pages.start()
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

            pages = PackSelectPages(interaction, packs, self, action="buy")
            await pages.start(content="**Select a pack to buy:**", ephemeral=True)
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

            pages = PackSelectPages(interaction, packs, self, action="give")
            await pages.start(content=f"**Select a pack to give to {user.mention}:**", ephemeral=True)
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

            pages = PackSelectPages(interaction, packs, self, action="open")
            await pages.start(content="**Select a pack to open:**", ephemeral=True)
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
        # Add default emoji to each pack
        for pack in packs:
            pack["emoji"] = "📦"
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
