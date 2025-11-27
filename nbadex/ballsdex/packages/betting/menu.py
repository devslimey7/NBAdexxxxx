from typing import TYPE_CHECKING

import discord
from discord.ui import Button, View, button

from ballsdex.core.utils.buttons import ConfirmChoiceView

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


class BetView(View):
    """Interactive view for managing active bets"""
    
    def __init__(self, bet_data: dict, cog):
        super().__init__(timeout=1800)  # 30 min timeout
        self.bet_data = bet_data
        self.cog = cog
    
    async def interaction_check(self, interaction: discord.Interaction["BallsDexBot"]) -> bool:
        """Check if user is part of the bet"""
        if interaction.user.id not in (
            self.bet_data["player1"].discord_id,
            self.bet_data["player2"].discord_id,
        ):
            await interaction.response.send_message(
                "You are not allowed to interact with this bet.", ephemeral=True
            )
            return False
        return True
    
    @button(label="View Bet", emoji="👀", style=discord.ButtonStyle.primary)
    async def view_bet(self, interaction: discord.Interaction["BallsDexBot"], button: Button):
        """View current bet stakes"""
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        if interaction.user.id == self.bet_data["player1"].discord_id:
            stakes = self.bet_data["player1_stakes"]
            opponent = self.bet_data["player2"].discord_id
        else:
            stakes = self.bet_data["player2_stakes"]
            opponent = self.bet_data["player1"].discord_id
        
        embed = discord.Embed(
            title="Your Bet Stakes",
            color=discord.Color.blue(),
        )
        
        if stakes:
            lines = [f"• {stake.ball.country}" for stake in stakes]
            embed.description = "\n".join(lines)
        else:
            embed.description = "No NBAs added yet"
        
        embed.add_field(name="Opponent", value=f"<@{opponent}>", inline=False)
        embed.set_footer(text=f"Total: {len(stakes)} NBAs")
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @button(label="Clear Stakes", emoji="🗑️", style=discord.ButtonStyle.secondary)
    async def clear_stakes(self, interaction: discord.Interaction["BallsDexBot"], button: Button):
        """Clear your bet stakes"""
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        view = ConfirmChoiceView(
            interaction,
            accept_message="Clearing your stakes...",
            cancel_message="This request has been cancelled.",
        )
        await interaction.followup.send(
            "Are you sure you want to clear your stakes?", view=view, ephemeral=True
        )
        await view.wait()
        if not view.value:
            return
        
        if interaction.user.id == self.bet_data["player1"].discord_id:
            self.bet_data["player1_stakes"].clear()
        else:
            self.bet_data["player2_stakes"].clear()
        
        await interaction.followup.send("Stakes cleared.", ephemeral=True)
    
    @button(label="Cancel Bet", emoji="❌", style=discord.ButtonStyle.danger)
    async def cancel_bet(self, interaction: discord.Interaction["BallsDexBot"], button: Button):
        """Cancel the bet"""
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        view = ConfirmChoiceView(
            interaction,
            accept_message="Cancelling bet...",
            cancel_message="This request has been cancelled.",
        )
        await interaction.followup.send(
            "Are you sure you want to cancel this bet?", view=view, ephemeral=True
        )
        await view.wait()
        if not view.value:
            return
        
        # Remove from active bets
        bet_key = None
        for key in list(self.cog.active_bets.keys()):
            if interaction.user.id in key:
                bet_key = key
                break
        
        if bet_key:
            del self.cog.active_bets[bet_key]
        
        await interaction.followup.send("Bet cancelled.", ephemeral=True)
        self.stop()
