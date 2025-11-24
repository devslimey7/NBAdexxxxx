from typing import TYPE_CHECKING

from ballsdex.packages.balls.cog import Balls
from ballsdex.packages.balls.economy_commands import EconomyCommands

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


async def setup(bot: "BallsDexBot"):
    await bot.add_cog(Balls(bot))
    await bot.add_cog(EconomyCommands(bot))
