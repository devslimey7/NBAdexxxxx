import logging
import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

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
from ballsdex.core.utils.paginator import Pages
from ballsdex.core.utils.transformers import BallInstanceTransform, BallEnabledTransform, SpecialEnabledTransform
from ballsdex.settings import settings

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("ballsdex.packages.coins")


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
        self.stop()

    @discord.ui.button(emoji="✖", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()


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
    async def balance(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        """
        Check your coins balance or another user's balance.

        Parameters
        ----------
        user: discord.User
            The user whose balance to check (optional)
        """
        target = user or interaction.user
        player, _ = await Player.get_or_create(discord_id=target.id)
        
        embed = discord.Embed(
            title="Coins Balance",
            description=f"{target.mention} has **{player.coins:,}** coins",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

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
        
        async with in_transaction():
            player = await Player.get(discord_id=interaction.user.id)
            await countryball.refresh_from_db()
            
            if countryball.player_id != player.pk:
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

    @app_commands.command()
    async def bulk_sell(
        self,
        interaction: discord.Interaction,
        countryball: Optional[BallEnabledTransform] = None,
        special: Optional[SpecialEnabledTransform] = None,
        sort: Optional[SortingChoices] = None,
    ):
        """
        Bulk sell multiple NBAs for coins.

        Parameters
        ----------
        countryball: Ball
            Filter by specific NBA type (optional)
        special: Special
            Filter by special event (optional)
        sort: SortingChoices
            Sort order for selection (optional)
        """
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
        
        total_value = 0
        for inst in instances:
            value = inst.countryball.quicksell_value
            if inst.specialcard:
                value = int(value * 1.5)
            total_value += value
        
        filter_text = ""
        if countryball:
            filter_text += f" {countryball.country}"
        if special:
            filter_text += f" ({special.name})"
        
        embed = discord.Embed(
            title="Confirm Bulk Quicksell",
            description=(
                f"Are you sure you want to sell **{len(instances)}**{filter_text} "
                f"{settings.plural_collectible_name} for a total of **{total_value:,}** coins?\n\n"
                f"This action cannot be undone!"
            ),
            color=discord.Color.orange()
        )
        
        view = ConfirmView(interaction.user)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        
        await view.wait()
        
        if view.value is None or not view.value:
            embed.description = "Bulk quicksell cancelled."
            embed.color = discord.Color.red()
            await interaction.edit_original_response(embed=embed, view=None)
            return
        
        async with in_transaction():
            await player.refresh_from_db()
            
            sold_count = 0
            for inst in instances:
                await inst.refresh_from_db()
                if inst.player_id == player.pk and not inst.deleted:
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
            special_text = f"\nEvent: {pack.special.name}" if pack.special else "\nEvent: Any"
            limit_text = f"\nDaily Limit: {pack.daily_limit}" if pack.daily_limit > 0 else ""
            
            embed.add_field(
                name=f"{emoji}{pack.name}",
                value=(
                    f"Price: **{pack.price:,}** coins\n"
                    f"Rarity Range: {pack.min_rarity} - {pack.max_rarity}"
                    f"{special_text}{limit_text}"
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
        
        if amount > pack.quantity:
            await interaction.response.send_message(
                f"You only have **{pack.quantity}** of this pack!",
                ephemeral=True
            )
            return
        
        if amount > 10:
            await interaction.response.send_message(
                "You can only open up to 10 packs at a time!",
                ephemeral=True
            )
            return
        
        await pack.fetch_related("pack", "player")
        the_pack = pack.pack
        player = pack.player
        
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
        
        await interaction.response.defer()
        
        query = Ball.filter(
            enabled=True,
            rarity__gte=the_pack.min_rarity,
            rarity__lte=the_pack.max_rarity
        )
        
        available_balls = await query.all()
        
        if not available_balls:
            await interaction.followup.send(
                f"No {settings.plural_collectible_name} available in this pack's rarity range!",
                ephemeral=True
            )
            return
        
        total_rarity = sum(b.rarity for b in available_balls)
        
        results = []
        async with in_transaction():
            await pack.refresh_from_db()
            
            if pack.quantity < amount:
                await interaction.followup.send(
                    f"You no longer have enough packs!",
                    ephemeral=True
                )
                return
            
            pack.quantity -= amount
            await pack.save(update_fields=["quantity"])
            
            special_to_use = None
            if the_pack.special:
                special_to_use = the_pack.special
            
            for _ in range(amount):
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
                
                await PackOpenHistory.create(
                    player=player,
                    pack=the_pack,
                    ball_received=instance
                )
                
                results.append(instance)
        
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
        
        await interaction.followup.send(embed=embed)
