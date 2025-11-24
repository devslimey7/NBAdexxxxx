from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


async def setup(bot: "BallsDexBot"):
    from ballsdex.packages.balls.cog import Balls
    from ballsdex.packages.balls.packs_cog import Packs
    
    await bot.add_cog(Balls(bot))
    await bot.add_cog(Packs(bot))
