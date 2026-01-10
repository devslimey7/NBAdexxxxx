import logging
import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional, List, Set

import discord
from discord import app_commands
from discord.ext import commands
from tortoise import timezone
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from ballsdex.core.models import (
    Ball,
    BallInstance,
    Pack,
    PackOpenHistory,
    Player,
    PlayerPack,
    Special,
    balls as balls_cache,
    specials as specials_cache,
)
from ballsdex.core.utils import menus
from ballsdex.core.utils.paginator import Pages
from ballsdex.core.utils.transformers import BallInstanceTransform, BallEnabledTransform, SpecialEnabledTransform
from ballsdex.settings import settings

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("ballsdex.packages.coins")

_active_operations: Set[int] = set()


class ConfirmView(discord.ui.View):
    def __init__(self, user: discord.User | discord.Member, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.user = user
        self.value: Optional[bool] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your confirmation!", ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="✔", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(emoji="✖", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.defer()
        self.stop()


class BulkSellSource(menus.ListPageSource):
    def __init__(self, entries: List[BallInstance], bot: "BallsDexBot"):
        super().__init__(entries, per_page=25)
        self.bot = bot

    async def format_page(self, menu, instances: List[BallInstance]):
        return True


class BulkSellSelect(discord.ui.Select):
    def __init__(self, instances: List[BallInstance], selected: Set[int], bot: "BallsDexBot"):
        self.instances = instances
        self.selected = selected
        self.bot = bot
        options = self._build_options()
        super().__init__(
            placeholder="Select NBAs to sell...",
            min_values=0,
            max_values=min(25, len(options)),
            options=options,
        )

    def _build_options(self) -> List[discord.SelectOption]:
        options = []
        for inst in self.instances[:25]:
            ball = inst.countryball
            value = ball.quicksell_value
            if inst.specialcard:
                value = int(value * 1.5)
            attack = "{:+}".format(inst.attack_bonus)
            health = "{:+}".format(inst.health_bonus)
            special_text = f" ({inst.specialcard.name})" if inst.specialcard else ""
            emoji = self.bot.get_emoji(ball.emoji_id)
            options.append(discord.SelectOption(
                label=f"#{inst.pk:0X} {ball.country}{special_text}",
                description=f"{attack}%/{health}% - {value:,} coins",
                value=str(inst.pk),
                default=inst.pk in self.selected,
                emoji=emoji,
            ))
        return options

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        current_page_pks = {inst.pk for inst in self.instances[:25]}
        self.selected -= current_page_pks
        for val in self.values:
            self.selected.add(int(val))
        self.view.update_footer()


class BulkSellView(Pages):
    def __init__(
        self,
        interaction: discord.Interaction,
        instances: List[BallInstance],
        bot: "BallsDexBot",
    ):
        self.all_instances = instances
        self.bot = bot
        self.selected: Set[int] = set()
        self.confirmed = False
        source = BulkSellSource(instances, bot)
        super().__init__(source, interaction=interaction)
        self.select_menu: Optional[BulkSellSelect] = None
        self.update_select_menu()
        self.add_item(self.confirm_button)
        self.add_item(self.select_all_button)
        self.add_item(self.cancel_button)

    def update_select_menu(self):
        if self.select_menu:
            self.remove_item(self.select_menu)
        start = self.current_page * 25
        end = start + 25
        page_instances = self.all_instances[start:end]
        if page_instances:
            self.select_menu = BulkSellSelect(page_instances, self.selected, self.bot)
            self.add_item(self.select_menu)

    def update_footer(self):
        pass

    async def show_page(self, interaction: discord.Interaction, page_number: int):
        self.current_page = page_number
        self.update_select_menu()
        await self._update_view(interaction)

    async def _update_view(self, interaction: discord.Interaction):
        total_value = 0
        for inst in self.all_instances:
            if inst.pk in self.selected:
                value = inst.countryball.quicksell_value
                if inst.specialcard:
                    value = int(value * 1.5)
                total_value += value
        
        embed = discord.Embed(
            title="Bulk Sell NBAs",
            description=(
                f"Select NBAs to sell. Page {self.current_page + 1}/{self.source.get_max_pages()}\n\n"
                f"**Selected: {len(self.selected)}** NBAs for **{total_value:,}** coins\n"
                f"Use the dropdown to select, then click Confirm."
            ),
            color=discord.Color.gold()
        )
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Confirm Sale", style=discord.ButtonStyle.success, row=2)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected:
            await interaction.response.send_message("No NBAs selected!", ephemeral=True)
            return
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Select All", style=discord.ButtonStyle.secondary, row=2)
    async def select_all_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        for inst in self.all_instances:
            self.selected.add(inst.pk)
        self.update_select_menu()
        await self._update_view(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=2)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        self.stop()
        await interaction.response.defer()


class PackTransform(app_commands.Transformer):
    async def transform(self, interaction: discord.Interaction, value: str) -> Pack:
        try:
            pack = await Pack.get(id=int(value))
        except Exception:
            pack = await Pack.filter(name__icontains=value).first()
        if not pack:
            raise app_commands.TransformerError(value, type(value), self)
        return pack

    async def autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        try:
            packs = await Pack.filter(enabled=True).order_by("price")
            choices = []
            for pack in packs:
                if current.lower() in pack.name.lower():
                    emoji = pack.emoji + " " if pack.emoji else ""
                    choices.append(app_commands.Choice(
                        name=f"{emoji}{pack.name} - {pack.price:,} coins",
                        value=str(pack.id)
                    ))
            return choices[:25]
        except Exception:
            return []


class OwnedPackTransform(app_commands.Transformer):
    async def transform(self, interaction: discord.Interaction, value: str) -> PlayerPack:
        player, _ = await Player.get_or_create(discord_id=interaction.user.id)
        try:
            player_pack = await PlayerPack.get(id=int(value), player=player)
        except Exception:
            player_pack = await PlayerPack.filter(
                player=player, pack__name__icontains=value, quantity__gt=0
            ).first()
        if not player_pack or player_pack.quantity <= 0:
            raise app_commands.TransformerError(value, type(value), self)
        return player_pack

    async def autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        try:
            player, _ = await Player.get_or_create(discord_id=interaction.user.id)
            player_packs = await PlayerPack.filter(player=player, quantity__gt=0).prefetch_related("pack")
            choices = []
            for pp in player_packs:
                if current.lower() in pp.pack.name.lower():
                    emoji = pp.pack.emoji + " " if pp.pack.emoji else ""
                    choices.append(app_commands.Choice(
                        name=f"{emoji}{pp.pack.name} x{pp.quantity}",
                        value=str(pp.id)
                    ))
            return choices[:25]
        except Exception:
            return []


class SortingChoices(discord.Enum):
    alphabetical = "ball__country"
    rarity_desc = "-ball__rarity"
    rarity_asc = "ball__rarity"
    health = "-health_bonus"
    attack = "-attack_bonus"
    quicksell = "-ball__quicksell_value"


class Coins(commands.GroupCog, group_name="coins"):
    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot

    @app_commands.command()
    async def balance(self, interaction: discord.Interaction):
        """
        Check your coins balance.
        """
        player, _ = await Player.get_or_create(discord_id=interaction.user.id)
        
        embed = discord.Embed(
            title="Coins Balance",
            description=f"You have **{player.coins:,}** coins",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command()
    async def give(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        amount: int,
    ):
        """
        Give coins to another user.

        Parameters
        ----------
        user: discord.User
            The user you want to give coins to
        amount: int
            Number of coins to give
        """
        if user.id == interaction.user.id:
            await interaction.response.send_message("You cannot give coins to yourself!", ephemeral=True)
            return
        
        if user.bot:
            await interaction.response.send_message("You cannot give coins to bots!", ephemeral=True)
            return
        
        if amount < 1:
            await interaction.response.send_message("Amount must be at least 1!", ephemeral=True)
            return
        
        if interaction.user.id in _active_operations:
            await interaction.response.send_message("You have another operation in progress!", ephemeral=True)
            return
        
        _active_operations.add(interaction.user.id)
        try:
            async with in_transaction():
                player = await Player.get_or_none(discord_id=interaction.user.id)
                if not player:
                    player = await Player.create(discord_id=interaction.user.id)
                
                if player.coins < amount:
                    await interaction.response.send_message(
                        f"You don't have enough coins! You have **{player.coins:,}** coins.",
                        ephemeral=True
                    )
                    return
                
                recipient, _ = await Player.get_or_create(discord_id=user.id)
                
                player.coins -= amount
                recipient.coins += amount
                await player.save(update_fields=["coins"])
                await recipient.save(update_fields=["coins"])
            
            await interaction.response.send_message(
                f"You gave **{amount:,}** coins to {user.mention}!\n"
                f"Your new balance: **{player.coins:,}** coins",
                ephemeral=True
            )
        finally:
            _active_operations.discard(interaction.user.id)

    @app_commands.command()
    async def sell(
        self,
        interaction: discord.Interaction,
        countryball: BallInstanceTransform,
    ):
        """
        Sell an NBA for coins (quicksell).

        Parameters
        ----------
        countryball: BallInstance
            The NBA you want to sell
        """
        if countryball.favorite:
            await interaction.response.send_message(
                f"You cannot sell a favorited {settings.collectible_name}!",
                ephemeral=True
            )
            return

        if not countryball.is_tradeable:
            await interaction.response.send_message(
                f"This {settings.collectible_name} cannot be sold!",
                ephemeral=True
            )
            return

        if interaction.user.id in _active_operations:
            await interaction.response.send_message("You have another operation in progress!", ephemeral=True)
            return

        ball = countryball.countryball
        sell_value = ball.quicksell_value
        
        bonus_multiplier = 1.0
        if countryball.specialcard:
            bonus_multiplier = 1.5
        
        final_value = int(sell_value * bonus_multiplier)
        
        attack = "{:+}".format(countryball.attack_bonus)
        health = "{:+}".format(countryball.health_bonus)
        special_text = f" ({countryball.specialcard.name})" if countryball.specialcard else ""
        
        embed = discord.Embed(
            title="Confirm Quicksell",
            description=(
                f"Are you sure you want to sell **#{countryball.pk:0X} {ball.country}{special_text}** "
                f"({attack}%/{health}%) for **{final_value:,}** coins?"
            ),
            color=discord.Color.orange()
        )
        
        view = ConfirmView(interaction.user)
        await interaction.response.send_message(embed=embed, view=view)
        
        await view.wait()
        
        if view.value is None:
            embed.description = "Quicksell timed out."
            embed.color = discord.Color.greyple()
            await interaction.edit_original_response(embed=embed, view=None)
            return
        
        if not view.value:
            embed.description = "Quicksell cancelled."
            embed.color = discord.Color.red()
            await interaction.edit_original_response(embed=embed, view=None)
            return
        
        _active_operations.add(interaction.user.id)
        try:
            async with in_transaction():
                player = await Player.get(discord_id=interaction.user.id)
                await countryball.refresh_from_db()
                
                if countryball.player_id != player.pk or countryball.deleted:
                    embed.description = f"You no longer own this {settings.collectible_name}!"
                    embed.color = discord.Color.red()
                    await interaction.edit_original_response(embed=embed, view=None)
                    return
                
                countryball.deleted = True
                await countryball.save(update_fields=["deleted"])
                
                player.coins += final_value
                await player.save(update_fields=["coins"])
            
            embed.title = "Quicksell Complete!"
            embed.description = (
                f"You sold **#{countryball.pk:0X} {ball.country}{special_text}** for **{final_value:,}** coins!\n"
                f"New balance: **{player.coins:,}** coins"
            )
            embed.color = discord.Color.green()
            await interaction.edit_original_response(embed=embed, view=None)
        finally:
            _active_operations.discard(interaction.user.id)

    @app_commands.command()
    async def bulk_sell(
        self,
        interaction: discord.Interaction,
        countryball: Optional[BallEnabledTransform] = None,
        special: Optional[SpecialEnabledTransform] = None,
        sort: Optional[SortingChoices] = None,
    ):
        """
        Bulk sell multiple NBAs for coins with selection.

        Parameters
        ----------
        countryball: Ball
            Filter by specific NBA type (optional)
        special: Special
            Filter by special event (optional)
        sort: SortingChoices
            Sort order for selection (optional)
        """
        if interaction.user.id in _active_operations:
            await interaction.response.send_message("You have another operation in progress!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        player, _ = await Player.get_or_create(discord_id=interaction.user.id)
        
        query = BallInstance.filter(player=player, favorite=False, tradeable=True, deleted=False)
        
        if countryball:
            query = query.filter(ball=countryball)
        if special:
            query = query.filter(special=special)
        
        order = sort.value if sort else "-ball__quicksell_value"
        instances = await query.order_by(order).prefetch_related("ball", "special")
        
        if not instances:
            await interaction.followup.send(
                f"No sellable {settings.plural_collectible_name} found matching your filters!",
                ephemeral=True
            )
            return
        
        view = BulkSellView(interaction, list(instances), self.bot)
        
        total_value = sum(
            int(inst.countryball.quicksell_value * (1.5 if inst.specialcard else 1))
            for inst in instances
        )
        
        embed = discord.Embed(
            title="Bulk Sell NBAs",
            description=(
                f"Select NBAs to sell. Page 1/{view.source.get_max_pages()}\n\n"
                f"**Selected: 0** NBAs for **0** coins\n"
                f"Use the dropdown to select, then click Confirm.\n\n"
                f"*Total available: {len(instances)} NBAs worth {total_value:,} coins*"
            ),
            color=discord.Color.gold()
        )
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        
        await view.wait()
        
        if not view.confirmed or not view.selected:
            embed.description = "Bulk sell cancelled."
            embed.color = discord.Color.red()
            await interaction.edit_original_response(embed=embed, view=None)
            return
        
        _active_operations.add(interaction.user.id)
        try:
            selected_pks = view.selected
            total_value = 0
            sold_count = 0
            
            async with in_transaction():
                await player.refresh_from_db()
                
                for inst in instances:
                    if inst.pk not in selected_pks:
                        continue
                    await inst.refresh_from_db()
                    if inst.player_id == player.pk and not inst.deleted and not inst.favorite:
                        value = inst.countryball.quicksell_value
                        if inst.specialcard:
                            value = int(value * 1.5)
                        total_value += value
                        inst.deleted = True
                        await inst.save(update_fields=["deleted"])
                        sold_count += 1
                
                player.coins += total_value
                await player.save(update_fields=["coins"])
            
            embed.title = "Bulk Quicksell Complete!"
            embed.description = (
                f"You sold **{sold_count}** {settings.plural_collectible_name} for **{total_value:,}** coins!\n"
                f"New balance: **{player.coins:,}** coins"
            )
            embed.color = discord.Color.green()
            await interaction.edit_original_response(embed=embed, view=None)
        finally:
            _active_operations.discard(interaction.user.id)


class Packs(commands.GroupCog, group_name="pack"):
    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot

    @app_commands.command()
    async def list(self, interaction: discord.Interaction):
        """
        View all available packs you can buy.
        """
        packs = await Pack.filter(enabled=True).order_by("price").prefetch_related("special")
        
        if not packs:
            await interaction.response.send_message(
                "No packs are currently available!",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="Available Packs",
            description=f"Here are the packs you can buy with coins:",
            color=discord.Color.blue()
        )
        
        for pack in packs:
            emoji = pack.emoji + " " if pack.emoji else ""
            description = pack.description if pack.description else "No description"
            limit_text = f"\nDaily Limit: {pack.daily_limit}" if pack.daily_limit > 0 else ""
            
            embed.add_field(
                name=f"{emoji}{pack.name}",
                value=(
                    f"Price: **{pack.price:,}** coins\n"
                    f"{description}{limit_text}"
                ),
                inline=True
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command()
    async def buy(
        self,
        interaction: discord.Interaction,
        pack: app_commands.Transform[Pack, PackTransform],
        amount: int = 1,
    ):
        """
        Buy packs with your coins.

        Parameters
        ----------
        pack: Pack
            The pack you want to buy
        amount: int
            Number of packs to buy (default: 1)
        """
        if amount < 1:
            await interaction.response.send_message("Amount must be at least 1!", ephemeral=True)
            return
        
        if amount > 100:
            await interaction.response.send_message("You can only buy up to 100 packs at a time!", ephemeral=True)
            return
        
        if interaction.user.id in _active_operations:
            await interaction.response.send_message("You have another operation in progress!", ephemeral=True)
            return
        
        total_cost = pack.price * amount
        
        player, _ = await Player.get_or_create(discord_id=interaction.user.id)
        
        if player.coins < total_cost:
            await interaction.response.send_message(
                f"You don't have enough coins! You need **{total_cost:,}** coins but only have **{player.coins:,}** coins.",
                ephemeral=True
            )
            return
        
        emoji = pack.emoji + " " if pack.emoji else ""
        
        embed = discord.Embed(
            title="Confirm Purchase",
            description=(
                f"Are you sure you want to buy **{amount}x {emoji}{pack.name}** "
                f"for **{total_cost:,}** coins?"
            ),
            color=discord.Color.blue()
        )
        
        view = ConfirmView(interaction.user)
        await interaction.response.send_message(embed=embed, view=view)
        
        await view.wait()
        
        if view.value is None:
            embed.description = "Purchase timed out."
            embed.color = discord.Color.greyple()
            await interaction.edit_original_response(embed=embed, view=None)
            return
        
        if not view.value:
            embed.description = "Purchase cancelled."
            embed.color = discord.Color.red()
            await interaction.edit_original_response(embed=embed, view=None)
            return
        
        _active_operations.add(interaction.user.id)
        try:
            async with in_transaction():
                await player.refresh_from_db()
                
                if player.coins < total_cost:
                    embed.description = "You no longer have enough coins!"
                    embed.color = discord.Color.red()
                    await interaction.edit_original_response(embed=embed, view=None)
                    return
                
                player.coins -= total_cost
                await player.save(update_fields=["coins"])
                
                player_pack, created = await PlayerPack.get_or_create(
                    player=player,
                    pack=pack,
                    defaults={"quantity": 0}
                )
                player_pack.quantity += amount
                await player_pack.save(update_fields=["quantity"])
            
            embed.title = "Purchase Complete!"
            embed.description = (
                f"You bought **{amount}x {emoji}{pack.name}**!\n"
                f"Coins spent: **{total_cost:,}**\n"
                f"New balance: **{player.coins:,}** coins\n"
                f"You now have **{player_pack.quantity}** of this pack."
            )
            embed.color = discord.Color.green()
            await interaction.edit_original_response(embed=embed, view=None)
        finally:
            _active_operations.discard(interaction.user.id)

    @app_commands.command()
    async def inventory(self, interaction: discord.Interaction):
        """
        View your owned packs.
        """
        player, _ = await Player.get_or_create(discord_id=interaction.user.id)
        player_packs = await PlayerPack.filter(player=player, quantity__gt=0).prefetch_related("pack")
        
        if not player_packs:
            await interaction.response.send_message(
                "You don't own any packs! Use `/pack buy` to purchase some.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="Your Packs",
            description="",
            color=discord.Color.gold()
        )
        
        for pp in player_packs:
            emoji = pp.pack.emoji + " " if pp.pack.emoji else ""
            embed.description += f"{emoji}**{pp.pack.name}**: {pp.quantity}\n"
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command()
    async def give(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        pack: app_commands.Transform[PlayerPack, OwnedPackTransform],
        amount: int = 1,
    ):
        """
        Give packs to another user.

        Parameters
        ----------
        user: discord.User
            The user you want to give packs to
        pack: PlayerPack
            The pack you want to give
        amount: int
            Number of packs to give (default: 1)
        """
        if user.id == interaction.user.id:
            await interaction.response.send_message("You cannot give packs to yourself!", ephemeral=True)
            return
        
        if user.bot:
            await interaction.response.send_message("You cannot give packs to bots!", ephemeral=True)
            return
        
        if amount < 1:
            await interaction.response.send_message("Amount must be at least 1!", ephemeral=True)
            return
        
        if amount > pack.quantity:
            await interaction.response.send_message(
                f"You only have **{pack.quantity}** of this pack!",
                ephemeral=True
            )
            return
        
        if interaction.user.id in _active_operations:
            await interaction.response.send_message("You have another operation in progress!", ephemeral=True)
            return
        
        await pack.fetch_related("pack", "player")
        the_pack = pack.pack
        
        _active_operations.add(interaction.user.id)
        try:
            async with in_transaction():
                await pack.refresh_from_db()
                
                if pack.quantity < amount:
                    await interaction.response.send_message(
                        f"You no longer have enough packs!",
                        ephemeral=True
                    )
                    return
                
                pack.quantity -= amount
                await pack.save(update_fields=["quantity"])
                
                recipient, _ = await Player.get_or_create(discord_id=user.id)
                
                recipient_pack = await PlayerPack.filter(player=recipient, pack=the_pack).first()
                if recipient_pack:
                    recipient_pack.quantity += amount
                    await recipient_pack.save(update_fields=["quantity"])
                else:
                    await PlayerPack.create(
                        player=recipient,
                        pack=the_pack,
                        quantity=amount
                    )
            
            emoji = the_pack.emoji + " " if the_pack.emoji else ""
            await interaction.response.send_message(
                f"You gave **{amount}x {emoji}{the_pack.name}** to {user.mention}!\n"
                f"You now have **{pack.quantity}** of this pack.",
                ephemeral=True
            )
        finally:
            _active_operations.discard(interaction.user.id)

    @app_commands.command()
    async def open(
        self,
        interaction: discord.Interaction,
        pack: app_commands.Transform[PlayerPack, OwnedPackTransform],
        amount: int = 1,
    ):
        """
        Open your owned packs to get NBAs.

        Parameters
        ----------
        pack: PlayerPack
            The pack you want to open
        amount: int
            Number of packs to open (default: 1)
        """
        if amount < 1:
            await interaction.response.send_message("Amount must be at least 1!", ephemeral=True)
            return
        
        if amount > 10:
            await interaction.response.send_message(
                "You can only open up to 10 packs at a time!",
                ephemeral=True
            )
            return
        
        if interaction.user.id in _active_operations:
            await interaction.response.send_message(
                "You have another pack operation in progress! Please wait.",
                ephemeral=True
            )
            return
        
        _active_operations.add(interaction.user.id)
        try:
            await pack.fetch_related("pack", "player")
            the_pack = pack.pack
            player = pack.player
            
            async with in_transaction():
                await pack.refresh_from_db()
                
                if pack.quantity < amount:
                    await interaction.response.send_message(
                        f"You only have **{pack.quantity}** of this pack!",
                        ephemeral=True
                    )
                    return
                
                if the_pack.daily_limit > 0:
                    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    opens_today = await PackOpenHistory.filter(
                        player=player,
                        pack=the_pack,
                        opened_at__gte=today_start
                    ).count()
                    
                    remaining = the_pack.daily_limit - opens_today
                    if remaining <= 0:
                        hours_until_reset = 24 - timezone.now().hour
                        await interaction.response.send_message(
                            f"You've reached the daily limit for opening **{the_pack.name}**!\n"
                            f"Your limit will reset in about {hours_until_reset} hours.",
                            ephemeral=True
                        )
                        return
                    
                    if amount > remaining:
                        await interaction.response.send_message(
                            f"You can only open **{remaining}** more of this pack today!",
                            ephemeral=True
                        )
                        return
                
                pack.quantity -= amount
                await pack.save(update_fields=["quantity"])
                
                query = Ball.filter(
                    enabled=True,
                    rarity__gte=the_pack.min_rarity,
                    rarity__lte=the_pack.max_rarity
                )
                
                available_balls = await query.all()
                
                if not available_balls:
                    pack.quantity += amount
                    await pack.save(update_fields=["quantity"])
                    await interaction.response.send_message(
                        f"No {settings.plural_collectible_name} available in this pack's rarity range!",
                        ephemeral=True
                    )
                    return
                
                total_rarity = sum(b.rarity for b in available_balls)
                
                results = []
                special_to_use = None
                if the_pack.special:
                    special_to_use = the_pack.special
                
                for _ in range(amount):
                    pack_cards = []
                    for _ in range(the_pack.cards_count):
                        roll = random.uniform(0, total_rarity)
                        cumulative = 0
                        selected_ball = available_balls[0]
                        
                        for ball in available_balls:
                            cumulative += ball.rarity
                            if roll <= cumulative:
                                selected_ball = ball
                                break
                        
                        attack_bonus = random.randint(-settings.max_attack_bonus, settings.max_attack_bonus)
                        health_bonus = random.randint(-settings.max_health_bonus, settings.max_health_bonus)
                        
                        instance = await BallInstance.create(
                            ball=selected_ball,
                            player=player,
                            attack_bonus=attack_bonus,
                            health_bonus=health_bonus,
                            special=special_to_use,
                            server_id=interaction.guild_id if interaction.guild else None,
                        )
                        pack_cards.append(instance)
                        results.append(instance)
                    
                    await PackOpenHistory.create(
                        player=player,
                        pack=the_pack,
                        ball_received=pack_cards[0] if pack_cards else None
                    )
            
            emoji = the_pack.emoji + " " if the_pack.emoji else ""
            
            if len(results) == 1:
                inst = results[0]
                ball = inst.countryball
                attack = "{:+}".format(inst.attack_bonus)
                health = "{:+}".format(inst.health_bonus)
                special_text = f" ({inst.specialcard.name})" if inst.specialcard else ""
                
                embed = discord.Embed(
                    title=f"{emoji}{the_pack.name}",
                    description=(
                        f"{interaction.user.mention} You packed **{ball.country}**!{special_text}\n"
                        f"(#{inst.pk:0X}, {attack}%/{health}%)"
                    ),
                    color=discord.Color.gold()
                )
                
                ball_emoji = self.bot.get_emoji(ball.emoji_id)
                if ball_emoji:
                    embed.set_thumbnail(url=ball_emoji.url)
            else:
                description = f"{interaction.user.mention} You opened **{amount}x {the_pack.name}**!\n\n"
                for inst in results:
                    ball = inst.countryball
                    attack = "{:+}".format(inst.attack_bonus)
                    health = "{:+}".format(inst.health_bonus)
                    special_text = f" ({inst.specialcard.name})" if inst.specialcard else ""
                    ball_emoji = self.bot.get_emoji(ball.emoji_id)
                    emoji_str = str(ball_emoji) + " " if ball_emoji else ""
                    description += f"{emoji_str}**{ball.country}**{special_text} (#{inst.pk:0X}, {attack}%/{health}%)\n"
                
                embed = discord.Embed(
                    title=f"{emoji}{the_pack.name} Results",
                    description=description,
                    color=discord.Color.gold()
                )
            
            await interaction.response.send_message(embed=embed)
        finally:
            _active_operations.discard(interaction.user.id)
