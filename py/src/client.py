# A bot client with some basic custom skills.
import typing
from config import *
from discord.ext import commands
from multiprocessing import Lock
from multiprocessing.managers import SyncManager

from utils import *

import cards
import cmds
import concurrent.futures
import discord
import logging
import os

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


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


# Bot client holding a pool of workers for running commands and a shared data manager.
class MidClient(commands.Bot):
    misc_commands = [cmds.echo, cmds.shrug, cmds.roll, cmds.eject]

    def __init__(self):
        commands.Bot.__init__(
            self,
            command_prefix=commands.when_mentioned_or(get_summon_prefix()),
            strip_after_prefix=True,
            intents=get_intents(),
            help_command=commands.DefaultHelpCommand(
                # display text for commands without a category
                no_category="Miscellaneous",
                # don't wrap pages as code blocks, allowing us to use markdown formatting
                paginator=commands.Paginator(prefix="", suffix=""),
            ),
        )
        self.executor = cmds.PebbleExecutor(MAX_COMMAND_WORKERS, COMMAND_TIMEOUT)
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
            # Since app commands cannot accept a >100 character description,
            # swap that field for the brief when we register hybrid commands.
            cmds.swap_hybrid_command_description(cmd)
            self.add_command(cmd)
        await self.add_cog(cmds.Cards(self))
