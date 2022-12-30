# Cog for dice roller commands
import logging

import dice
from cmds import as_subprocess_command, swap_hybrid_command_description
from discord.ext import commands
from utils import *

log = logging.getLogger(__name__)


def _roll(formula: str) -> str:
    output = "No result."
    try:
        roll_result = dice.roll(formula)
        output = dice.format_roll_results(roll_result)
    except Exception as err:
        log.info(f"Roll error. {err}")
        output = f"Roll error.\n{codeblock(err, big=True)}"
    return output


class DiceRoller(commands.Cog):
    def __init__(self, bot) -> None:
        swap_hybrid_command_description(self.roll)
        swap_hybrid_command_description(self.rollsave)

    @commands.hybrid_command(
        aliases=["r"],
        brief="Roll some dice",
        description=f"""
    __**roll**__
    Rolls some dice and does some math.
    See: (https://en.wikipedia.org/wiki/Dice_notation).
    Roughly in order of precedence:

    __Dice roll__ `d`
        `<N>d<S>` to roll N dice of size S. N omitted will roll 1 dice.
        `F` for FATE/Fudge. `c` for coin: heads is 1, tails is 0.
    __Counting__ `?`
        Filter and count how many items succeed.
        `{get_summon_prefix()}roll 4d6?=5` for how many times 5 is rolled from 4 six-sided dice. 
    __Keep/Drop__ `k`, `p`
        `<set>kh<N>` keeps the N highest values. `<set>k@<i>` to single out an index. 
        `{get_summon_prefix()}roll 4d6kh3` or `{get_summon_prefix()}roll repeat(3d6, 5)pl2`
    __Reroll__ `r` (reroll once), `rr` (reroll recursive)
        Reroll, replacing the original with the new.
        `{get_summon_prefix()}roll 8d6rl1` to reroll the lowest d6 out of the 8.
        `{get_summon_prefix()}roll 2d6rr<3` to keep rerolling any d6 that is less than 3.
    __Explode__ `!` (explode), `!o` (explode once)
        `<diceroll>!` Max rolls trigger another roll. Can also explode on comparison.
        `{get_summon_prefix()}roll 10d4!`, `{get_summon_prefix()}roll 8d6!>4`
        `{get_summon_prefix()}roll 3d8!o=3`
    __Combinatorics__  `permute` or `P`, `choose` or `C`
        `<n> P <k>` or `<n> permute <k>`.
        `<n> C <k>` or `<n> choose <k>`.
    __Label__ `[ ]`, `#`
        Label preceding expressions. # to comment out what follows.
    __Arithmetic__ `+ - * / // % ^`
        `//` is integer division. `%` is remainder. `^` is power, not xor.
    __Comparison__ `= > < >= <= ~=`
        `{get_summon_prefix()}roll 1d20+5 >= 15`
    __Functions__ `agg() fact() repeat() sqrt() floor() ceil()`
        `agg(<set>, <operator>)` to use the operator on each item.
            Valid operators are: `+ - * / % ^`. Dice rolls are already aggregated using `+`.
            Try `{get_summon_prefix()}roll agg(3d8, *)` or `{get_summon_prefix()}roll agg(repeat(3d6+2, 4), +)`
        `fact(<N>)` is N factorial (`!` reserved for explode).
        `repeat(<expr>, <n>)` repeats the expr, producing a n-size set.
    __Parentheses__ `( )` for associativity and order of operations.
    __Braces__ `{{ }}` around comma-separated items for literal sets.
    __Semicolons__ `;` for many rolls at once.
        `{get_summon_prefix()}roll 1d20+5; 2d6+5`
    """,
    )
    async def roll(
        self,
        ctx: commands.Context,
        *,
        formula: str = commands.parameter(
            description="The dice roll formula to evaluate"
        ),
    ):
        output = await as_subprocess_command(ctx, _roll, formula)
        await reply(ctx, output)

    @roll.error
    async def roll_error(self, ctx: commands.Context, error):
        if ignorable_check_failure(error):
            return
        await reply(ctx, f"{error}")

    @commands.hybrid_command(aliases=["rs"], brief="Save a roll macro")
    async def rollsave(self, ctx: commands.Context, name: str, contents: str):
        dice.GLOBAL_MACROS.add_macro(name=name, contents=contents)
        await reply(ctx, f"Saved macro: {name} = {contents}")

    @rollsave.error
    async def rollsave_error(self, ctx: commands.Context, error):
        if ignorable_check_failure(error):
            return
        if isinstance(error, ValueError):
            await reply(ctx, f"Error saving macro: {error}")
        raise error
