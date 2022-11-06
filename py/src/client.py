# A bot client with some basic custom skills.
from typing import Sequence
from cmds import *
from config import *
from discord.ext import commands
from multiprocessing import Lock
from multiprocessing.managers import SyncManager
from pebble import ProcessPool
from utils import *
import asyncio
import cards
import concurrent.futures
import discord
import logging
import os

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Wrapper for ProcessPool to allow use with asyncio run_in_executor
class PebbleExecutor(concurrent.futures.Executor):
    def __init__(self, max_workers, timeout=None):
        self.pool = ProcessPool(max_workers=max_workers)
        self.timeout = timeout

    def submit(self, fn, *args, **kwargs):
        return self.pool.schedule(fn, args=args, timeout=self.timeout)

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


# Internal data held by the client, synced to workers via a manager process.
class ClientData:
    def __init__(self):
        self.card_deck = cards.shuffle(cards.build_deck_52())
        self.card_logs = []

    def get_card_deck(self):
        return self.card_deck

    def set_card_deck(self, deck):
        self.card_deck = deck

    def get_card_logs(self):
        return self.card_logs

    def clear_card_logs(self):
        self.card_logs = []

    def add_card_log(self, message):
        self.card_logs.append(message)


class DataManager(SyncManager):
    def __init__(self):
        SyncManager.__init__(self)


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
    ctx, *, msg: str = commands.parameter(description="The message you want repeated")
):
    await ctx.send(msg)


@echo.error
async def echo_error(ctx, error):
    if isinstance(error, commands.errors.MissingRequiredArgument):
        await ctx.send(f"There is only silence.")


@commands.hybrid_command(
    brief="Get a Shruggie",
    description=f"""
__**shrug**__
Displays a shruggie: ¯\\_(ツ)_/¯""",
)
async def shrug(ctx):
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
    ctx,
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


class Cards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = ClientData()
        swap_hybrid_command_description(self.cards)

    def update_data(
        self, ctx: commands.Context, reply: str, new_deck: Sequence[cards.Card]
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
    async def draw(self, ctx: commands.Context, count: int = 1):
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
    async def history(self, ctx: commands.Context, count: int = 1):
        history = self.data.get_card_logs()
        numbered = [f"{i+1}: {history[i]}" for i in range(len(history))][-count:]
        reply = "\n".join(numbered)
        if len(numbered) < count:
            reply = "> start of history.\n" + reply
        self.update_data(ctx, reply, self.data.get_card_deck())
        await ctx.send(reply)


# Bot client holding a pool of workers which are used to execute commands.
class MidClient(commands.Bot):
    def __init__(self):
        commands.Bot.__init__(
            self,
            command_prefix=get_summon_prefix(),
            intents=get_intents(),
            help_command=commands.DefaultHelpCommand(
                # display text for commands without a category
                no_category="Miscellaneous",
                # don't wrap pages as code blocks, allowing us to use markdown formatting
                paginator=commands.Paginator(prefix="", suffix=""),
            ),
        )
        self.executor = PebbleExecutor(MAX_COMMAND_WORKERS, COMMAND_TIMEOUT)
        self.sync_manager = None
        self.data = None

    async def setup_hook(self) -> None:
        await super().setup_hook()
        await self.register_commands()
        log.info("Commands in tree:")
        for cmd in self.tree.walk_commands():
            log.info(f"{cmd.name}")

        TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")
        if TEST_GUILD_ID != None:
            log.info(f"Got test guild id: {TEST_GUILD_ID}; will sync app commands")
            TEST_GUILD = (
                discord.Object(id=int(TEST_GUILD_ID)) if TEST_GUILD_ID else None
            )
            self.tree.copy_global_to(guild=TEST_GUILD)
            await self.tree.sync(guild=TEST_GUILD)
        else:
            log.warn(f"No test guild id; not syncing app commands")
        return

    # Override, near-identical to discord.Client.start().
    # Set up manager and tear down upon exit.
    # Clean up executor workers upon completion.
    async def start(self, token: str, *, reconnect: bool = True) -> None:
        self.setup_manager()

        await self.login(token)
        await self.connect(reconnect=reconnect)

        self.executor.shutdown(False)
        if self.sync_manager != None:
            self.sync_manager.shutdown()

    def setup_manager(self):
        if self.sync_manager != None:
            log.info("Sync manager already started.")
            return
        DataManager.register("Data", ClientData)
        self.sync_manager = DataManager()
        self.sync_manager.start()
        log.info("Sync manager started.")
        self.data = self.sync_manager.Data()

    async def on_ready(self):
        log.info(
            f"{self.user} is now connected to Discord in guilds:"
            + f"{[(g.name, g.id) for g in self.guilds]}"
        )

    async def register_commands(self):
        swap_hybrid_command_description(echo)
        swap_hybrid_command_description(shrug)
        swap_hybrid_command_description(roll)
        self.add_command(echo)
        self.add_command(shrug)
        self.add_command(roll)
        await self.add_cog(Cards(self))
