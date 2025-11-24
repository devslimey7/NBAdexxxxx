from typing import TYPE_CHECKING

from ballsdex.packages.balls.cog import Balls
from ballsdex.packages.balls.economy_commands import EconomyCommands
from ballsdex.packages.balls.packs_cog import PacksCommands

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


async def setup(bot: "BallsDexBot"):
    await bot.add_cog(Balls(bot))
    await bot.add_cog(EconomyCommands(bot))
    await bot.add_cog(PacksCommands(bot))
