# Cog for dice roller commands
import logging

import dice
from cmds import as_subprocess_command, swap_hybrid_command_description
from discord.ext import commands
from utils import *

log = logging.getLogger(__name__)


def _roll(formula: str, macro_data: dice.MacroData) -> str:
    output = "No result."
    try:
        roll_result = dice.roll(formula, macro_data=macro_data)
        output = dice.format_roll_results(roll_result)
    except Exception as err:
        log.info(f"Roll error. {err}")
        output = f"Roll error.\n{codeblock(err, big=True)}"
    return output


class DiceRoller(commands.Cog):
    def __init__(self, bot) -> None:
        self.macro_data: dice.MacroData = bot.get_sync_manager().MacroData()
        self.add_default_macros()
        swap_hybrid_command_description(self.roll)
        swap_hybrid_command_description(self.macros)

    def add_default_macros(self):
        self.macro_data.add_macro("stats", "repeat(4d6kh3, 6)")
        self.macro_data.add_macro("double", "{$stats, $stats}")
        self.macro_data.add_macro("fireball", "8d6[fire damage]")

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
        output = await as_subprocess_command(ctx, _roll, formula, self.macro_data)
        await reply(ctx, output)

    @roll.error
    async def roll_error(self, ctx: commands.Context, error):
        if ignorable_check_failure(error):
            return
        await reply(ctx, f"{error}")

    @commands.hybrid_group(
        aliases=["m"],
        brief="Modify dice roll macros",
        description=f"""
    __**macros**__
    Assign names to dice roll formulas, saving them as macros.
    When `$name` appears in a `{get_summon_prefix()}roll` input, it'll be replaced by the macro contents before evaluation.
    Use these subcommands to modify dice roll macros.
    """,
    )
    async def macros(self, ctx: commands.Context):
        await reply(ctx, get_help_notice("macros"))

    @macros.command(aliases=["s", "set"], brief="Save a roll macro")
    async def save(self, ctx: commands.Context, name: str, contents: str):
        old = None
        try:
            old = self.macro_data.add_macro(name=name, contents=contents)
        except ValueError as err:
            await reply(ctx, f"Error saving macro: `{err}`")
            return
        if old is not None:
            await reply(ctx, f"Overwrote macro: `{name} = {old} ⇒ {contents}`")
        else:
            await reply(ctx, f"Saved macro: `{name} = {contents}`")

    @macros.command(aliases=["d", "del"], brief="Delete a roll macro")
    async def delete(self, ctx: commands.Context, name: str):
        try:
            contents = self.macro_data.delete_macro(name=name)
            await reply(ctx, f"Deleted macro: `{name} = {contents}`")
        except ValueError as err:
            await reply(ctx, f"Error deleting macro: `{err}`")
            return

    @macros.command(aliases=["l", "ls"], brief="List all macros")
    async def list(self, ctx: commands.Context):
        mlist = [
            f"{name} = {contents}"
            for name, contents in self.macro_data.get_all_macros().items()
        ]
        output = f"{len(mlist)} macro(s) available: \n" + codeblock(
            "\n".join(mlist), big=True
        )
        await reply(ctx, text=output)
