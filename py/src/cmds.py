# Commands.
from collections import namedtuple
import typing
from config import *
from random import randint
from utils import *

import asyncio
import cards
import discord
from discord.ext import commands
import dice
import logging

log = logging.getLogger(__name__)

# Since app commands cannot accept a >100 character description, swap that field for the brief.
def swap_hybrid_command_description(hybrid: commands.HybridCommand):
    hybrid.app_command.description = hybrid.brief


@commands.hybrid_command(
    aliases=["repeat"],
    brief="Repeat your message back",
    description=f"""
__**echo**__
Sends the contents of your message back to you.
The command keyword and bot prefix are excluded.
""",
)
async def echo(
    ctx: commands.Context,
    *,
    msg: str = commands.parameter(description="The message you want repeated"),
):
    await ctx.send(msg)


@echo.error
async def echo_error(ctx: commands.Context, error):
    if isinstance(error, commands.errors.MissingRequiredArgument):
        await ctx.send(f"There is only silence.")


@commands.hybrid_command(
    brief="Get a Shruggie",
    description=f"""
__**shrug**__
Displays a shruggie: ¯\\_(ツ)_/¯""",
)
async def shrug(ctx: commands.Context):
    await ctx.send(escape("¯\\_(ツ)_/¯"))


@commands.hybrid_command(
    aliases=["r"],
    brief="Roll some dice",
    description=f"""
__**roll**__
Rolls some dice and does some math.
This handles a subset of standard dice notation (https://en.wikipedia.org/wiki/Dice_notation).
Roughly in order of precedence:

__Dice roll__ `d`
    `<N>d<S>` to roll N dice of size S, evaluated by adding the results. This produces a collection. N omitted will roll 1 dice. 
__Collective Comparison__ `?= ?> ?< ?>= ?<= ?~=`
    Filter for and count how many items from a collection succeed a comparison.
    `{get_summon_prefix()}roll 4d6?=5` for how many times 5 is rolled from 4 six-sided dice. 
__Keep/Drop__ `kh` (keep high), `kl` (keep low), `dh` (drop high), `dl` (drop low)
    `<collection>kh<N>` keeps the N highest values from the collection.
    `{get_summon_prefix()}roll 4d6kh3` or `{get_summon_prefix()}roll repeat(3d6, 5)dl2`
__Explode__ `!`, also `!= !> !< !>= !<= !~=`
    `<diceroll>!` Highest-possible rolls explode (triggers another roll).
    With comparison, will explode on rolls that succeed.
    `{get_summon_prefix()}roll 10d4!`, `{get_summon_prefix()}roll 8d6!>4`
__Combinatorics__ `choose` or `C`
    `<n> C <k>` or `<n> choose <k>` to count choices.
__Arithmetic__ `+ - * / % ^`
    Use as you'd expect. `%` is remainder. `^` is power, not xor.
__Value Comparison__ `= > < >= <= ~=`
    Evaluates to 1 if success, 0 if not. `{get_summon_prefix()}roll 1d20+5 >= 15`
__Functions__ `agg() fact() repeat() sqrt()`
    `agg(<collection>, <operator>)` to aggregate the collection using the operator.
        Valid operators are: `+ - * / % ^`. Dice rolls are already aggregated using `+`.
        Try `{get_summon_prefix()}roll agg(3d8, *)` or `{get_summon_prefix()}roll agg(repeat(3d6+2, 4), +)`
    `fact(<N>)` is N factorial (`!` is reserved for exploding dice).
    `repeat(<expression>, <n>)` repeats the evaluation, producing a n-size collection.
    `sqrt(<x>)` square root of x.
__Parentheses__ `( )` for associativity and order of operations.
__Semicolons__ `;` for several rolls in one message.
    `{get_summon_prefix()}roll 1d20+5; 2d6+5`
""",
)
async def roll(
    ctx: commands.Context,
    *,
    formula: str = commands.parameter(description="The dice roll formula to evaluate"),
):
    # TODO subprocess compute for the dice roll output
    output = "No result."
    try:
        roll_result = dice.roll(formula)
        output = dice.format_roll_results(roll_result)
    except Exception as err:
        log.info(f"Roll error. {err}")
        output = f"Roll error.\n{codeblock(err, big=True)}"
    await ctx.send(output)


@roll.error
async def roll_error(ctx: commands.Context, error):
    if isinstance(error, commands.errors.HybridCommandError):
        await ctx.send(f"{error}")


@commands.hybrid_command(
    aliases=["kill"],
    brief="Eject an impostor",
    description=f"""
__**eject**__
Choose someone sus and eject them.
`{get_summon_prefix()}eject <target> <imposter> <remaining>`
Supply __imposter__ if you know whether they were an imposter.
If impostors remain, supply a integer for __remaining__.
""",
)
async def eject(
    ctx: commands.Context,
    target: discord.Member = commands.parameter(description="The person to eject"),
    imposter: typing.Optional[bool] = commands.parameter(
        description="Whether the person was an imposter", default=None
    ),
    remaining: typing.Optional[int] = commands.parameter(
        description="How many imposters remain", default=None
    ),
):
    guy = "ඞ"
    action = "was ejected."
    if imposter == True:
        action = "was an Impostor."
    elif imposter == False:
        action = "was not an Impostor."
    remaincount = "　　。　  　.  　"
    if remaining is not None:
        remaincount = f"{remaining} Impostor(s) remain."
    message = f"""
    . 　　　。　　　　•　 　ﾟ　　。 　　.

　　　.　　　 　.　　　　　。　　 。　. 　

    .　　 。　　　　 {guy}    . 　　 • 　　　•

　　 ﾟ   . 　 {target} {action}　 。　.

　　  '　　  {remaincount}   　 • 　　 。

　　ﾟ　　　.　　　.     　　　　.　       。"""
    await ctx.send(message)


@eject.error
async def eject_error(ctx: commands.Context, error):
    if isinstance(error, commands.errors.MemberNotFound):
        await ctx.send(f"Sorry, I don't know who {error.argument} is.")


class Cards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = bot.get_client_data()
        swap_hybrid_command_description(self.cards)

    def update_data(
        self, ctx: commands.Context, reply: str, new_deck: typing.Sequence[cards.Card]
    ):
        # apply deck changes
        self.data.set_card_deck(new_deck)
        # update card log
        self.data.add_card_log(
            f"{ctx.author.name} [{ctx.command.name}]: {reply if ctx.command.name != 'history' else 'viewed history.'}"
        )

    @commands.hybrid_group(
        aliases=["c"],
        brief="Deal with cards",
        description=f"""
    __**cards**__
    Throws out cards from a 52-card deck. (Direct-message the bot to receive cards in secret.)
    The following subcommands are available:
    __draw__ `{get_summon_prefix()}cards draw <count>`
        Draw `<count>` cards from the deck.
    __reset__ `{get_summon_prefix()}cards reset`
        Reset the deck.
    __shuffle__ `{get_summon_prefix()}cards shuffle`
        Shuffle the remaining cards in the deck.
    __inspect__ `{get_summon_prefix()}cards inspect`
        Check the number of cards remaining in the deck, and peek at the top and bottom cards.
    __history__ `{get_summon_prefix()}cards history <count>`
        View `<count>` past actions performed using this command.
    """,
    )
    async def cards(self, ctx):
        await ctx.send(get_help_notice("cards"))

    @cards.command()
    async def draw(
        self,
        ctx: commands.Context,
        count: int = commands.parameter(
            description="How many cards to draw", default=1
        ),
    ):
        deck = self.data.get_card_deck()
        reply = f"{cards.draw(deck, count)}"
        self.update_data(ctx, reply, deck)
        await ctx.send(reply)

    @cards.command()
    async def reset(self, ctx: commands.Context):
        deck = cards.shuffle(cards.build_deck_52())
        reply = "Deck reset and shuffled."
        self.update_data(ctx, reply, deck)
        await ctx.send(reply)

    @cards.command()
    async def shuffle(self, ctx: commands.Context):
        deck = cards.shuffle(self.data.get_card_deck())
        reply = "Deck shuffled."
        self.update_data(ctx, reply, deck)
        await ctx.send(reply)

    @cards.command()
    async def inspect(self, ctx: commands.Context):
        deck = self.data.get_card_deck()
        top = deck[len(deck) - 1] if len(deck) > 0 else None
        bot = deck[0] if len(deck) > 0 else None
        reply = f"{len(deck)} cards in deck. Top card is {top}. Bottom card is {bot}."
        self.update_data(ctx, reply, deck)
        await ctx.send(reply)

    @cards.command()
    async def history(
        self,
        ctx: commands.Context,
        count: int = commands.parameter(
            description="How many past actions to display", default=5
        ),
    ):
        history = self.data.get_card_logs()
        numbered = [f"{i+1}: {history[i]}" for i in range(len(history))][-count:]
        reply = "\n".join(numbered)
        if len(numbered) < count:
            reply = "> start of history.\n" + reply
        self.update_data(ctx, reply, self.data.get_card_deck())
        await ctx.send(reply)
