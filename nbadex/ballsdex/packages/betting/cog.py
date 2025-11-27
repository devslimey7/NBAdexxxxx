import discord
from discord import app_commands
from discord.ext import commands
from typing import TYPE_CHECKING
from datetime import datetime, timedelta

from ballsdex.core.models import Player, BallInstance, Bet, BetStake, BetHistory, Ball
from ballsdex.settings import settings

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

BETTING_GUILD_ID = 1440962506796433519
BETTING_CHANNEL_ID = 1443544409684836382


def betting_channel_check(interaction: discord.Interaction) -> bool:
    """Check if user is in betting channel"""
    if interaction.guild_id != BETTING_GUILD_ID or interaction.channel_id != BETTING_CHANNEL_ID:
        return False
    return True


async def nba_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[int]]:
    """Autocomplete for selecting NBAs from user's inventory"""
    try:
        player = await Player.get_or_none(discord_id=interaction.user.id)
        if not player:
            return []
        
        # Get user's NBAs
        nbas = await BallInstance.filter(player=player).prefetch_related("ball")
        
        # Filter by current input (search by ball name or instance ID)
        choices = []
        for nba in nbas:
            ball_name = nba.ball.name if nba.ball else "Unknown"
            label = f"{ball_name} (#{nba.id})"
            
            if current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label[:100], value=nba.id))
        
        return choices[:25]  # Discord limit
    except Exception:
        return []


class Betting(commands.GroupCog):
    """
    Bet NBAs with other players.
    """

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot
        self.active_bets: dict[int, dict] = {}

    @app_commands.command()
    @app_commands.guilds(discord.Object(id=BETTING_GUILD_ID))
    @app_commands.check(betting_channel_check)
    async def begin(self, interaction: discord.Interaction, user: discord.User):
        """Begin a bet with another user."""
        await interaction.response.defer(ephemeral=True)

        if user.id == interaction.user.id:
            await interaction.followup.send("You cannot bet with yourself!", ephemeral=True)
            return

        bet_key = (interaction.user.id, user.id)
        if bet_key in self.active_bets:
            await interaction.followup.send(
                "You already have an active bet with this user!", ephemeral=True
            )
            return

        try:
            p1 = await Player.get_or_create(discord_id=interaction.user.id)
            p2 = await Player.get_or_create(discord_id=user.id)
        except Exception as e:
            await interaction.followup.send(f"Error creating players: {str(e)}", ephemeral=True)
            return

        try:
            bet = await Bet.create(player1=p1[0], player2=p2[0])
            self.active_bets[bet_key] = {"bet_id": bet.id, "player1_nba_ids": set(), "player2_nba_ids": set()}

            embed = discord.Embed(
                title="Bet Started",
                description=f"Bet between {interaction.user.mention} and {user.mention}",
                color=discord.Color.blue(),
            )
            embed.add_field(name="Status", value="Awaiting stakes", inline=False)
            embed.add_field(name="Player 1 Stakes", value="None yet", inline=True)
            embed.add_field(name="Player 2 Stakes", value="None yet", inline=True)
            embed.set_footer(text=f"Bet ID: {bet.id}")

            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error creating bet: {str(e)}", ephemeral=True)

    @app_commands.command()
    @app_commands.guilds(discord.Object(id=BETTING_GUILD_ID))
    @app_commands.check(betting_channel_check)
    async def add(
        self,
        interaction: discord.Interaction,
        nba: int,
    ):
        """Add an NBA to your ongoing bet."""
        await interaction.response.defer(ephemeral=True)

        active_bet = None
        for key, val in self.active_bets.items():
            if interaction.user.id in key:
                active_bet = val
                break

        if not active_bet:
            await interaction.followup.send("You don't have an active bet.", ephemeral=True)
            return

        try:
            player = await Player.get(discord_id=interaction.user.id)
            bet = await Bet.get(id=active_bet["bet_id"])
        except Exception as e:
            await interaction.followup.send(f"Error retrieving bet: {str(e)}", ephemeral=True)
            return

        try:
            ball_instance = await BallInstance.get(id=nba, player=player)
            await BetStake.create(bet=bet, player=player, ballinstance=ball_instance)
            
            if bet.player1_id == player.id:
                active_bet["player1_nba_ids"].add(nba)
            else:
                active_bet["player2_nba_ids"].add(nba)
            
            embed = discord.Embed(
                title="NBA Added to Bet",
                description=f"Added NBA #{nba}",
                color=discord.Color.green(),
            )
            embed.set_footer(text=f"Bet ID: {bet.id}")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(
                f"Error adding NBA: {str(e)} - Make sure you own this NBA.", ephemeral=True
            )

    @app_commands.command()
    @app_commands.guilds(discord.Object(id=BETTING_GUILD_ID))
    @app_commands.check(betting_channel_check)
    async def remove(
        self,
        interaction: discord.Interaction,
        nba: int,
    ):
        """Remove an NBA from your stakes in the ongoing bet."""
        await interaction.response.defer(ephemeral=True)

        active_bet = None
        for key, val in self.active_bets.items():
            if interaction.user.id in key:
                active_bet = val
                break

        if not active_bet:
            await interaction.followup.send("You don't have an active bet.", ephemeral=True)
            return

        try:
            player = await Player.get(discord_id=interaction.user.id)
            bet = await Bet.get(id=active_bet["bet_id"])
        except Exception as e:
            await interaction.followup.send(f"Error retrieving bet: {str(e)}", ephemeral=True)
            return

        try:
            stake = await BetStake.get(bet=bet, ballinstance_id=nba, player=player)
            await stake.delete()

            if bet.player1_id == player.id:
                active_bet["player1_nba_ids"].discard(nba)
            else:
                active_bet["player2_nba_ids"].discard(nba)

            embed = discord.Embed(
                title="NBA Removed from Bet",
                description=f"Removed NBA #{nba}",
                color=discord.Color.orange(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(
                f"Error removing NBA: {str(e)}", ephemeral=True
            )

    @app_commands.command()
    @app_commands.guilds(discord.Object(id=BETTING_GUILD_ID))
    @app_commands.check(betting_channel_check)
    async def view(self, interaction: discord.Interaction):
        """View the NBAs added to an ongoing bet."""
        await interaction.response.defer(ephemeral=True)

        active_bet = None
        bet_key = None
        for key, val in self.active_bets.items():
            if interaction.user.id in key:
                active_bet = val
                bet_key = key
                break

        if not active_bet:
            await interaction.followup.send("You don't have an active bet.", ephemeral=True)
            return

        try:
            bet = await Bet.get(id=active_bet["bet_id"])
        except Exception as e:
            await interaction.followup.send(f"Error retrieving bet: {str(e)}", ephemeral=True)
            return

        p1_name = f"<@{bet.player1_id}>"
        p2_name = f"<@{bet.player2_id}>"

        p1_nbas = active_bet["player1_nba_ids"]
        p2_nbas = active_bet["player2_nba_ids"]

        embed = discord.Embed(
            title="Current Bet Stakes",
            description=f"Bet between {p1_name} and {p2_name}",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name=f"Player 1 Stakes ({len(p1_nbas)} NBAs)",
            value=f"{', '.join([f'#{x}' for x in p1_nbas]) if p1_nbas else 'No stakes'}",
            inline=False,
        )
        embed.add_field(
            name=f"Player 2 Stakes ({len(p2_nbas)} NBAs)",
            value=f"{', '.join([f'#{x}' for x in p2_nbas]) if p2_nbas else 'No stakes'}",
            inline=False,
        )
        embed.set_footer(text=f"Bet ID: {bet.id}")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command()
    @app_commands.guilds(discord.Object(id=BETTING_GUILD_ID))
    @app_commands.check(betting_channel_check)
    async def cancel(self, interaction: discord.Interaction):
        """Cancel the ongoing bet."""
        await interaction.response.defer(ephemeral=True)

        active_bet = None
        bet_key = None
        for key, val in self.active_bets.items():
            if interaction.user.id in key:
                active_bet = val
                bet_key = key
                break

        if not active_bet:
            await interaction.followup.send("You don't have an active bet.", ephemeral=True)
            return

        try:
            bet = await Bet.get(id=active_bet["bet_id"])
            stakes = await BetStake.filter(bet=bet)
            for stake in stakes:
                await stake.delete()
            await bet.delete()
            del self.active_bets[bet_key]

            embed = discord.Embed(
                title="Bet Cancelled",
                description="All stakes have been returned.",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error cancelling bet: {str(e)}", ephemeral=True)

    @app_commands.command()
    @app_commands.guilds(discord.Object(id=BETTING_GUILD_ID))
    @app_commands.check(betting_channel_check)
    async def bulk_add(
        self,
        interaction: discord.Interaction,
    ):
        """Bulk add NBAs to the ongoing bet from your inventory."""
        await interaction.response.defer(ephemeral=True)

        active_bet = None
        for key, val in self.active_bets.items():
            if interaction.user.id in key:
                active_bet = val
                break

        if not active_bet:
            await interaction.followup.send("You don't have an active bet.", ephemeral=True)
            return

        try:
            player = await Player.get(discord_id=interaction.user.id)
            bet = await Bet.get(id=active_bet["bet_id"])
        except Exception as e:
            await interaction.followup.send(f"Error retrieving bet: {str(e)}", ephemeral=True)
            return

        instances = await BallInstance.filter(player=player).limit(10)

        if not instances:
            await interaction.followup.send(
                "You have no NBAs to add.", ephemeral=True
            )
            return

        added_count = 0
        try:
            for instance in instances:
                existing = await BetStake.filter(
                    bet=bet, ballinstance=instance, player=player
                ).exists()
                if not existing:
                    await BetStake.create(bet=bet, player=player, ballinstance=instance)
                    if bet.player1_id == player.id:
                        active_bet["player1_nba_ids"].add(instance.id)
                    else:
                        active_bet["player2_nba_ids"].add(instance.id)
                    added_count += 1

            embed = discord.Embed(
                title="Bulk Added to Bet",
                description=f"Added {added_count} NBA(s) to your stakes",
                color=discord.Color.green(),
            )
            embed.set_footer(text=f"Bet ID: {bet.id}")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error bulk adding NBAs: {str(e)}", ephemeral=True)

    @app_commands.command()
    @app_commands.guilds(discord.Object(id=BETTING_GUILD_ID))
    @app_commands.check(betting_channel_check)
    async def history(
        self,
        interaction: discord.Interaction,
        days: int | None = None,
    ):
        """Retrieve bet history from last x days."""
        await interaction.response.defer(ephemeral=True)

        days = days or 7
        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            history_items = await BetHistory.filter(
                bet_date__gte=cutoff_date,
            ).filter(
                player1_id == interaction.user.id | player2_id == interaction.user.id
            ).order_by("-bet_date").limit(10)

            if not history_items:
                await interaction.followup.send(
                    f"No bet history found in the last {days} days.", ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"Betting History (Last {days} Days)",
                description=f"Found {len(history_items)} bets",
                color=discord.Color.gold(),
            )

            for item in history_items:
                status = "Cancelled" if item.cancelled else "Completed"
                winner = (
                    f"<@{item.winner_id}>"
                    if item.winner_id
                    else "Draw"
                )
                embed.add_field(
                    name=f"Bet vs <@{item.player2_id if item.player1_id == interaction.user.id else item.player1_id}>",
                    value=f"**Status:** {status}\n**Winner:** {winner}\n**Date:** <t:{int(item.bet_date.timestamp())}>",
                    inline=False,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error retrieving history: {str(e)}", ephemeral=True)
