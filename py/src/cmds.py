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
