from typing import TYPE_CHECKING

import discord

from ballsdex.core.utils import menus
from ballsdex.core.utils.paginator import Pages
from ballsdex.packages.betting.betting_user import BettingUser

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


def _get_prefix_emote(bettor: BettingUser) -> str:
    if bettor.cancelled:
        return "\N{NO ENTRY SIGN}"
    elif bettor.accepted:
        return "\N{WHITE HEAVY CHECK MARK}"
    elif bettor.locked:
        return "\N{LOCK}"
    else:
        return ""


def _get_bettor_name(bettor: BettingUser) -> str:
    return f"{_get_prefix_emote(bettor)} {bettor.user.name}"


def _build_list_of_strings(bettor: BettingUser, bot: "BallsDexBot", short: bool = False) -> list[str]:
    proposal: list[str] = [""]
    i = 0

    for nba in bettor.proposal:
        cb_text = nba.description(short=short, include_emoji=True, bot=bot, is_trade=True)
        if bettor.locked:
            text = f"- *{cb_text}*\n"
        else:
            text = f"- {cb_text}\n"
        if bettor.cancelled:
            text = f"~~{text}~~"

        if len(text) + len(proposal[i]) > 950:
            i += 1
            proposal.append("")
        proposal[i] += text

    if not proposal[0]:
        proposal[0] = "*Empty*"

    return proposal


def fill_bet_embed_fields(
    embed: discord.Embed,
    bot: "BallsDexBot",
    bettor1: BettingUser,
    bettor2: BettingUser,
    compact: bool = False,
):
    """Fill the fields of an embed with the NBAs part of a bet."""
    embed.clear_fields()

    compact1 = _build_list_of_strings(bettor1, bot, short=compact)
    compact2 = _build_list_of_strings(bettor2, bot, short=compact)

    embed.add_field(
        name=_get_bettor_name(bettor1),
        value=compact1[0],
        inline=True,
    )
    embed.add_field(
        name=_get_bettor_name(bettor2),
        value=compact2[0],
        inline=True,
    )

    for field_value in compact1[1:] + compact2[1:]:
        embed.add_field(name="\u200b", value=field_value, inline=False)
