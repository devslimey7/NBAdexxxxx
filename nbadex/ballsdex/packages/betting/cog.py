import asyncio
import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Optional, cast

import discord
from cachetools import TTLCache
from discord import app_commands
from discord.ext import commands
from discord.utils import MISSING
from tortoise.expressions import Q

from ballsdex.core.models import BallInstance, Player, Bet as BetModel, BetStake, BetHistory
from ballsdex.core.utils.buttons import ConfirmChoiceView
from ballsdex.core.utils.paginator import Pages
from ballsdex.core.utils.sorting import FilteringChoices, SortingChoices, filter_balls, sort_balls
from ballsdex.core.utils.transformers import (
    BallEnabledTransform,
    BallInstanceTransform,
    SpecialEnabledTransform,
)
from ballsdex.settings import settings

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("ballsdex.packages.betting")

BETTING_GUILD_ID = 1440962506796433519
BETTING_CHANNEL_ID = 1443544409684836382


def betting_channel_check(interaction: discord.Interaction) -> bool:
    """Check if user is in betting channel"""
    return interaction.guild_id == BETTING_GUILD_ID and interaction.channel_id == BETTING_CHANNEL_ID


@app_commands.guild_only()
class Bet(commands.GroupCog):
    """
    Bet NBAs with other players.
    """

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot
        self.active_bets: TTLCache[tuple[int, int], dict] = TTLCache(maxsize=999999, ttl=1800)

    @app_commands.command()
    @app_commands.check(betting_channel_check)
    async def begin(self, interaction: discord.Interaction["BallsDexBot"], user: discord.User):
        """
        Begin a bet with the chosen user.

        Parameters
        ----------
        user: discord.User
            The user you want to bet with
        """
        if user.bot:
            await interaction.response.send_message("You cannot bet with bots.", ephemeral=True)
            return
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "You cannot bet with yourself.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            player1, _ = await Player.get_or_create(discord_id=interaction.user.id)
            player2, _ = await Player.get_or_create(discord_id=user.id)
        except Exception as e:
            await interaction.followup.send(f"Error creating players: {str(e)}", ephemeral=True)
            return

        bet_key = (interaction.user.id, user.id)
        if bet_key in self.active_bets:
            await interaction.followup.send(
                "You already have an active bet with this user!", ephemeral=True
            )
            return

        # Create bet record
        try:
            bet = await BetModel.create(
                player1=player1,
                player2=player2,
            )
            self.active_bets[bet_key] = {
                "bet_id": bet.id,
                "player1": player1,
                "player2": player2,
                "player1_stakes": [],
                "player2_stakes": [],
                "player1_locked": False,
                "player2_locked": False,
            }
            await interaction.followup.send(
                f"Bet started with {user.mention}! Use `/bet add` to add NBAs.", ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"Error creating bet: {str(e)}", ephemeral=True)
            log.error(f"Error creating bet: {e}", exc_info=True)

    @app_commands.command()
    @app_commands.check(betting_channel_check)
    async def add(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        nba: BallInstanceTransform,
        special: SpecialEnabledTransform | None = None,
    ):
        """
        Add an NBA to your bet.

        Parameters
        ----------
        nba: BallInstance
            The NBA you want to add to your bet
        special: Special
            Filter the results of autocompletion to a special event. Ignored afterwards.
        """
        if not nba:
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        bet_key = (interaction.user.id,)
        active_bet = None
        for key, bet_data in self.active_bets.items():
            if interaction.user.id in key:
                active_bet = bet_data
                break

        if not active_bet:
            await interaction.followup.send("You do not have an active bet.", ephemeral=True)
            return

        if nba.favorite:
            view = ConfirmChoiceView(
                interaction,
                accept_message="NBA added.",
                cancel_message="This request has been cancelled.",
            )
            await interaction.followup.send(
                "This NBA is a favorite, are you sure you want to bet it?",
                view=view,
                ephemeral=True,
            )
            await view.wait()
            if not view.value:
                return

        try:
            # Create bet stake
            stake = await BetStake.create(
                bet_id=active_bet["bet_id"],
                player=active_bet["player1"] if interaction.user.id == active_bet["player1"].discord_id else active_bet["player2"],
                ballinstance=nba,
            )
            if interaction.user.id == active_bet["player1"].discord_id:
                active_bet["player1_stakes"].append(stake)
            else:
                active_bet["player2_stakes"].append(stake)
            await interaction.followup.send(f"{nba.ball.country} added to bet.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error adding NBA to bet: {str(e)}", ephemeral=True)
            log.error(f"Error adding NBA to bet: {e}", exc_info=True)

    @app_commands.command()
    @app_commands.check(betting_channel_check)
    async def remove(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        nba: BallInstanceTransform,
        special: SpecialEnabledTransform | None = None,
    ):
        """
        Remove an NBA from your bet.

        Parameters
        ----------
        nba: BallInstance
            The NBA you want to remove from your bet
        special: Special
            Filter the results of autocompletion to a special event. Ignored afterwards.
        """
        if not nba:
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        active_bet = None
        for key, bet_data in self.active_bets.items():
            if interaction.user.id in key:
                active_bet = bet_data
                break

        if not active_bet:
            await interaction.followup.send("You do not have an active bet.", ephemeral=True)
            return

        try:
            stakes = (
                active_bet["player1_stakes"]
                if interaction.user.id == active_bet["player1"].discord_id
                else active_bet["player2_stakes"]
            )
            for stake in stakes:
                if stake.ballinstance.id == nba.id:
                    stakes.remove(stake)
                    await stake.delete()
                    await interaction.followup.send("NBA removed from bet.", ephemeral=True)
                    return
            await interaction.followup.send("NBA not found in your bet.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error removing NBA from bet: {str(e)}", ephemeral=True)
            log.error(f"Error removing NBA from bet: {e}", exc_info=True)

    @app_commands.command()
    @app_commands.check(betting_channel_check)
    async def view(self, interaction: discord.Interaction["BallsDexBot"]):
        """
        View your current bet stakes.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        active_bet = None
        for key, bet_data in self.active_bets.items():
            if interaction.user.id in key:
                active_bet = bet_data
                break

        if not active_bet:
            await interaction.followup.send("You do not have an active bet.", ephemeral=True)
            return

        try:
            stakes = (
                active_bet["player1_stakes"]
                if interaction.user.id == active_bet["player1"].discord_id
                else active_bet["player2_stakes"]
            )

            if not stakes:
                await interaction.followup.send("You have no NBAs in your bet.", ephemeral=True)
                return

            embed = discord.Embed(
                title="Your Bet Stakes",
                color=discord.Color.blue(),
            )

            nba_list = []
            for stake in stakes:
                nba_list.append(f"• {stake.ballinstance.ball.country}")

            embed.description = "\n".join(nba_list)
            embed.set_footer(text=f"Total: {len(stakes)} NBAs")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error viewing bet: {str(e)}", ephemeral=True)
            log.error(f"Error viewing bet: {e}", exc_info=True)

    @app_commands.command()
    @app_commands.check(betting_channel_check)
    async def cancel(self, interaction: discord.Interaction["BallsDexBot"]):
        """
        Cancel your active bet.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        active_bet = None
        bet_key = None
        for key, bet_data in self.active_bets.items():
            if interaction.user.id in key:
                active_bet = bet_data
                bet_key = key
                break

        if not active_bet:
            await interaction.followup.send("You do not have an active bet.", ephemeral=True)
            return

        try:
            # Delete all stakes and create history
            await BetHistory.create(
                bet_id=active_bet["bet_id"],
                status="cancelled",
                cancelled_by=interaction.user.id,
            )

            for stake in active_bet["player1_stakes"] + active_bet["player2_stakes"]:
                await stake.delete()

            del self.active_bets[bet_key]
            await interaction.followup.send("Bet cancelled.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error cancelling bet: {str(e)}", ephemeral=True)
            log.error(f"Error cancelling bet: {e}", exc_info=True)

    bulk = app_commands.Group(name="bulk", description="Bulk betting commands")

    @bulk.command(name="add")
    @app_commands.check(betting_channel_check)
    async def bulk_add(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        nba: BallEnabledTransform | None = None,
        sort: SortingChoices | None = None,
        special: SpecialEnabledTransform | None = None,
        filter: FilteringChoices | None = None,
    ):
        """
        Bulk add NBAs to your bet with filtering options.

        Parameters
        ----------
        nba: Ball
            The NBA you would like to filter the results to
        sort: SortingChoices
            Choose how NBAs are sorted
        special: Special
            Filter the results to a special event
        filter: FilteringChoices
            Filter the results to a specific filter
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        active_bet = None
        for key, bet_data in self.active_bets.items():
            if interaction.user.id in key:
                active_bet = bet_data
                break

        if not active_bet:
            await interaction.followup.send("You do not have an active bet.", ephemeral=True)
            return

        try:
            query = BallInstance.filter(player__discord_id=interaction.user.id)
            if nba:
                query = query.filter(ball=nba)
            if special:
                query = query.filter(special=special)
            if sort:
                query = sort_balls(sort, query)
            if filter:
                query = filter_balls(filter, query, interaction.guild_id)

            nbas = await query.all()
            if not nbas:
                await interaction.followup.send(
                    f"No NBAs found matching your criteria.", ephemeral=True
                )
                return

            # Create stakes for all matching NBAs
            created_count = 0
            for nba_instance in nbas:
                try:
                    stake = await BetStake.create(
                        bet_id=active_bet["bet_id"],
                        player=active_bet["player1"] if interaction.user.id == active_bet["player1"].discord_id else active_bet["player2"],
                        ball_instance=nba_instance,
                    )
                    if interaction.user.id == active_bet["player1"].discord_id:
                        active_bet["player1_stakes"].append(stake)
                    else:
                        active_bet["player2_stakes"].append(stake)
                    created_count += 1
                except Exception:
                    # Skip duplicates
                    continue

            await interaction.followup.send(
                f"Added {created_count} NBAs to your bet.", ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"Error adding NBAs: {str(e)}", ephemeral=True)
            log.error(f"Error bulk adding NBAs: {e}", exc_info=True)

    @app_commands.command()
    @app_commands.check(betting_channel_check)
    async def history(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        days: int | None = None,
    ):
        """
        View your betting history.

        Parameters
        ----------
        days: int
            Number of days of history to show (default: 7)
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        if not days:
            days = 7

        try:
            query = BetHistory.filter(
                Q(bet__player1__discord_id=interaction.user.id)
                | Q(bet__player2__discord_id=interaction.user.id)
            )

            if days > 0:
                from datetime import datetime, timedelta
                cutoff = discord.utils.utcnow() - timedelta(days=days)
                query = query.filter(created_at__gte=cutoff)

            history = await query.all()

            if not history:
                await interaction.followup.send("No betting history found.", ephemeral=True)
                return

            embed = discord.Embed(
                title="Your Betting History",
                color=discord.Color.blue(),
            )

            history_list = []
            for bet_hist in history[:25]:  # Limit to 25 for embed
                history_list.append(f"• {bet_hist.status.upper()} - {bet_hist.created_at}")

            embed.description = "\n".join(history_list)
            embed.set_footer(text=f"Total: {len(history)} bets")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error retrieving history: {str(e)}", ephemeral=True)
            log.error(f"Error retrieving history: {e}", exc_info=True)


async def setup(bot: "BallsDexBot"):
    await bot.add_cog(Bet(bot))
