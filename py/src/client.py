# A bot client with some basic custom skills.
from config import *
from discord.ext import commands
from multiprocessing import Lock
from multiprocessing.managers import SyncManager
from pebble import ProcessPool
from utils import *

import cards
import cmds
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


# Bot client holding a pool of workers which are used to execute commands.
class MidClient(commands.Bot):
    misc_commands = [cmds.echo, cmds.shrug, cmds.roll, cmds.eject]

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

    def get_client_data(self):
        return self.data

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
        for cmd in MidClient.misc_commands:
            cmds.swap_hybrid_command_description(cmd)
            self.add_command(cmd)
        await self.add_cog(cmds.Cards(self))
