from typing import TYPE_CHECKING

import discord

from ballsdex.core.utils import menus
from ballsdex.core.utils.paginator import Pages

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


class BetStakesSource(menus.ListPageSource):
    """Pagination source for displaying bet stakes"""
    
    def __init__(self, stakes: list, player_name: str, bot: "BallsDexBot"):
        self.player_name = player_name
        self.bot = bot
        super().__init__(stakes, per_page=10)
    
    async def format_page(self, menu: Pages, page: list) -> discord.Embed:
        embed = discord.Embed(
            title=f"Bet Stakes - {self.player_name}",
            color=discord.Color.blue(),
        )
        
        lines = []
        for stake in page:
            lines.append(f"• {stake.ball.country}")
        
        embed.description = "\n".join(lines) if lines else "No NBAs in bet"
        embed.set_footer(text=f"Page {menu.current_page + 1}/{menu.source.get_max_pages()} | Total: {len(self.entries)} NBAs")
        return embed
