# Cog for card deck related commands.
import logging
import typing

import cards
from cmds import as_subprocess_command, swap_hybrid_command_description
from cogs.base_cog import BaseCog
from discord.ext import commands
from utils import *

log = logging.getLogger(__name__)


class Cards(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.data: cards.CardsData = bot.get_sync_manager().CardsData()  # type: ignore
        swap_hybrid_command_description(self.deck)

    def add_history_log(self, ctx: commands.Context, reply: str) -> str:
        card_log = f"{ctx.author.name} [{ctx.command.name}]: {reply if ctx.command.name != 'history' else 'viewed history.'}"  # type: ignore
        self.data.add_card_log(card_log)
        return card_log

    async def as_card_operation(
        self, ctx: commands.Context, card_op: typing.Callable[..., str], *args, **kwargs
    ):
        output = await as_subprocess_command(ctx, card_op, self.data, *args, **kwargs)
        self.add_history_log(ctx, output)
        await reply(ctx, output)

    @commands.hybrid_group(
        aliases=["d"],
        brief="Deal with cards",
        description=f"""
    __**deck**__
    Throws out cards from a 52-card deck. (Direct-message the bot to receive cards in secret.)
    The following subcommands are available:
    __draw__ `{get_summon_prefix()}deck draw <count>`
        Draw `<count>` cards from the deck.
    __reset__ `{get_summon_prefix()}deck reset`
        Reset the deck.
    __shuffle__ `{get_summon_prefix()}deck shuffle`
        Shuffle the remaining cards in the deck.
    __inspect__ `{get_summon_prefix()}deck inspect`
        Check the number of cards remaining in the deck, and peek at the top and bottom cards.
    __history__ `{get_summon_prefix()}deck history <count>`
        View `<count>` past actions performed using this command.
    """,
    )
    async def deck(self, ctx):
        await reply(ctx, get_help_notice("deck"))

    @deck.command()
    async def draw(
        self,
        ctx: commands.Context,
        count: int = commands.parameter(
            description="How many cards to draw", default=1
        ),
    ):
        await self.as_card_operation(ctx, _draw, count)

    @deck.command()
    async def reset(self, ctx: commands.Context):
        await self.as_card_operation(ctx, _reset)

    @deck.command()
    async def shuffle(self, ctx: commands.Context):
        await self.as_card_operation(ctx, _shuffle)

    @deck.command()
    async def inspect(self, ctx: commands.Context):
        await self.as_card_operation(ctx, _inspect)

    @deck.command()
    async def history(
        self,
        ctx: commands.Context,
        count: int = commands.parameter(
            description="How many past actions to display", default=5
        ),
    ):
        await self.as_card_operation(ctx, _history, count)


def _draw(card_data: cards.CardsData, count: int) -> str:
    cdeck = card_data.get_card_deck()
    drawn = cards.draw(cdeck, count)
    card_data.set_card_deck(cdeck)
    return str(drawn)


def _reset(card_data: cards.CardsData) -> str:
    cdeck = cards.shuffle(cards.build_deck_52())
    card_data.set_card_deck(cdeck)
    return "Deck reset and shuffled."


def _shuffle(card_data: cards.CardsData) -> str:
    cdeck = cards.shuffle(card_data.get_card_deck())
    card_data.set_card_deck(cdeck)
    return "Deck shuffled."


def _inspect(card_data: cards.CardsData) -> str:
    cdeck = card_data.get_card_deck()
    top = cdeck[len(cdeck) - 1] if len(cdeck) > 0 else None
    bot = cdeck[0] if len(cdeck) > 0 else None
    return f"{len(cdeck)} cards in deck. Top card is {top}. Bottom card is {bot}."


def _history(card_data: cards.CardsData, count: int) -> str:
    history = card_data.get_card_logs()
    numbered = [f"{i+1}: {history[i]}" for i in range(len(history))][-count:]
    output = "\n".join(numbered)
    if len(numbered) < count:
        output = "> start of history.\n" + output
    return output
