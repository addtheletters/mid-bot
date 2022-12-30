# Miscellaneous commands and subprocess command-running infrastructure.
import asyncio
import concurrent.futures
import functools
import logging
import typing

import dice
import discord
from config import COMMAND_TIMEOUT
from discord.ext import commands
from pebble import ProcessPool
from utils import *

log = logging.getLogger(__name__)

# Wrapper for ProcessPool to allow use with asyncio run_in_executor
class PebbleExecutor(concurrent.futures.Executor):
    def __init__(self, max_workers, timeout=None):
        self.pool = ProcessPool(max_workers=max_workers)
        self.timeout = timeout

    def submit(self, fn, *args, **kwargs):
        return self.pool.schedule(fn, args=args, timeout=self.timeout)  # type: ignore

    def map(self, func, *iterables, timeout=None, chunksize=1):
        raise NotImplementedError("This wrapper does not support `map`.")

    def shutdown(self, wait=True):
        if wait:
            log.info("Closing workers...")
            self.pool.close()
        else:
            log.info("Stopping workers...")
            self.pool.stop()
        self.pool.join()
        log.info("Workers joined.")


# Since app commands cannot accept a >100 character description,
# swap that field for the brief when we register hybrid commands.
def swap_hybrid_command_description(hybrid: commands.HybridCommand):
    if not hybrid.app_command or not hybrid.brief:
        raise RuntimeError(
            f"Tried to swap missing description/brief on hybrid command {hybrid}"
        )
    hybrid.app_command.description = hybrid.brief


async def as_subprocess_command(
    ctx: commands.Context, func: typing.Callable[..., typing.Any], *args, **kwargs
) -> typing.Any:
    loop: asyncio.AbstractEventLoop = ctx.bot.loop
    executor: PebbleExecutor = ctx.bot.get_executor()
    cmd_future = loop.run_in_executor(
        executor, functools.partial(func, *args, **kwargs)
    )

    if not ctx.command:
        raise RuntimeError(f"Missing command for context {ctx}")

    output = f"Executing {ctx.command.name}: {ctx.kwargs}..."
    log.info(output)
    try:
        async with ctx.typing():
            output = await asyncio.wait_for(cmd_future, timeout=COMMAND_TIMEOUT)
    except Exception as err:
        cmd_future.cancel()
        output = (
            f"Command {ctx.command.name} with args {ctx.kwargs} raised error: {err}"
        )
        log.info(output)
        raise
    return output


@commands.hybrid_command(
    aliases=["repeat"],
    brief="Repeat your message back",
    description=f"""
__**echo**__
Sends the contents of your message back to you.
The command keyword and bot prefix are excluded.
""",
)
@commands.cooldown(1, 1, commands.BucketType.user)
async def echo(
    ctx: commands.Context,
    *,
    msg: str = commands.parameter(description="The message you want repeated"),
):
    await reply(ctx, msg)


@echo.error
async def echo_error(ctx: commands.Context, error):
    if ignorable_check_failure(error):
        return
    if isinstance(error, commands.errors.MissingRequiredArgument):
        await reply(ctx, f"There is only silence.")
        return
    raise error


@commands.hybrid_command(
    brief="Get a Shruggie",
    description=f"""
__**shrug**__
Displays a shruggie: ¯\\_(ツ)_/¯""",
)
async def shrug(ctx: commands.Context):
    await reply(ctx, escape("¯\\_(ツ)_/¯"))


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
    ctx: commands.Context,
    *,
    formula: str = commands.parameter(description="The dice roll formula to evaluate"),
):
    output = await as_subprocess_command(ctx, _roll, formula)
    await reply(ctx, output)


@roll.error
async def roll_error(ctx: commands.Context, error):
    if ignorable_check_failure(error):
        return
    await reply(ctx, f"{error}")


def _roll(formula: str) -> str:
    output = "No result."
    try:
        roll_result = dice.roll(formula)
        output = dice.format_roll_results(roll_result)
    except Exception as err:
        log.info(f"Roll error. {err}")
        output = f"Roll error.\n{codeblock(err, big=True)}"
    return output


@commands.hybrid_command(aliases=["rs"], brief="Save a roll macro")
async def rollsave(ctx: commands.Context, name: str, contents: str):
    dice.GLOBAL_MACROS.add_macro(name=name, contents=contents)
    await reply(ctx, f"Saved macro: {name} = {contents}")


@rollsave.error
async def rollsave_error(ctx: commands.Context, error):
    if ignorable_check_failure(error):
        return
    if isinstance(error, ValueError):
        await reply(ctx, f"Error saving macro: {error}")
    raise error


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
    await reply(ctx, message)


@eject.error
async def eject_error(ctx: commands.Context, error):
    if ignorable_check_failure(error):
        return
    if isinstance(error, commands.errors.MemberNotFound):
        await reply(ctx, f"Sorry, I don't know who {error.argument} is.")
        return
    raise error
