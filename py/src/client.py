# A bot client with some basic custom skills.
import logging
import os
import shelve
from multiprocessing.managers import SyncManager
from typing import Optional

import cmds
import discord
from cards import CardsData
from config import *
from dice import MacroData
from discord.ext import commands, tasks
from utils import *

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class DataManager(SyncManager):
    def __init__(self):
        SyncManager.__init__(self)


# Interface for periodically shelving some data
class Storage:
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.fields = {}
        self.load()

    def load(self):
        try:
            with shelve.open(self.filename) as db:
                self.fields = {}
                for key in db.keys():
                    self.fields[key] = db[key]
            return False
        except OSError as e:
            log.error(f"Failed to load from storage.", e, exc_info=True)
            return True

    def save(self):
        try:
            with shelve.open(self.filename) as db:
                for key in self.fields.keys():
                    db[key] = self.fields[key]
            log.info("Saved bot data to local storage.")
            return False
        except OSError as e:
            log.error(f"Failed to save data to storage.", e, exc_info=True)
            return True

    def set(self, key: str, data):
        self.fields[key] = data

    def get(self, key: str):
        return self.fields[key]


class MidHelpCommand(commands.DefaultHelpCommand):
    CODEBLOCK_START = "```"
    CODEBLOCK_END = "```" + INVISIBLE_SPACE

    def __init__(self) -> None:
        self.codeblock_resolved = True
        commands.DefaultHelpCommand.__init__(
            self,
            # display text for commands without a category
            no_category="Miscellaneous",
            # don't wrap entire pages as code blocks, allowing us to use markdown formatting
            paginator=commands.Paginator(prefix="", suffix=""),
        )

    async def send_pages(self) -> None:
        if not self.codeblock_resolved:
            self.end_codeblock()

        destination = self.get_destination()
        embed = discord.Embed(title="Help")
        embed.description = ""
        for page in self.paginator.pages:
            embed.description += page
        await destination.send(embed=embed)

    def start_codeblock(self) -> None:
        self.codeblock_resolved = False
        if len(self.paginator._current_page) > 0:
            if self.paginator._current_page[-1] == MidHelpCommand.CODEBLOCK_END:
                # merge adjacent code blocks
                self.paginator._current_page.pop(-1)
                return
            elif self.paginator._current_page[-1] == MidHelpCommand.CODEBLOCK_START:
                return
        self.paginator.add_line(MidHelpCommand.CODEBLOCK_START)

    def end_codeblock(self) -> None:
        self.codeblock_resolved = True
        if len(self.paginator._current_page) > 0:
            if self.paginator._current_page[-1] == MidHelpCommand.CODEBLOCK_END:
                return
            elif self.paginator._current_page[-1] == MidHelpCommand.CODEBLOCK_START:
                # don't leave an empty code block
                self.paginator._current_page.pop(-1)
                return
        self.paginator.add_line(MidHelpCommand.CODEBLOCK_END)

    def add_indented_commands(
        self, commands, /, *, heading: str, max_size: Optional[int] = None
    ) -> None:
        self.start_codeblock()
        super().add_indented_commands(commands, heading=heading, max_size=max_size)
        self.end_codeblock()

    def add_command_arguments(self, command: commands.Command, /) -> None:
        self.start_codeblock()
        super().add_command_arguments(command)
        self.end_codeblock()


@discord.app_commands.command(name="help", description="Shows help")
async def help_app_command(interaction: discord.Interaction, command: Optional[str]):
    bot: MidClient = interaction.client  # type: ignore
    if bot.help_command is None:
        log.error("Missing help command.")
        return
    await interaction.response.defer()
    ctx = await commands.Context.from_interaction(interaction)
    sentinel = bot.help_command.context
    bot.help_command.context = ctx
    await bot.help_command.command_callback(
        ctx,
        command=command,
    )
    bot.help_command.context = sentinel
    await interaction.followup.send("Here's your help!")


# Bot client holding a pool of workers for running commands and a shared data manager.
class MidClient(commands.Bot):
    managed_types: dict = {"CardsData": CardsData, "MacroData": MacroData}

    def __init__(self, misc_commands, misc_cogs):
        commands.Bot.__init__(
            self,
            command_prefix=commands.when_mentioned_or(get_summon_prefix()),
            strip_after_prefix=True,
            intents=get_intents(),
            help_command=MidHelpCommand(),
        )
        self.description = config.BOT_DESCRIPTION

        self.misc_commands = misc_commands
        self.misc_cogs = misc_cogs

        self.executor = cmds.PebbleExecutor(MAX_COMMAND_WORKERS, COMMAND_TIMEOUT)
        self.sync_manager = None
        self.storage = Storage(LOCAL_STORAGE_FILENAME)

    def get_sync_manager(self) -> DataManager:
        if self.sync_manager is None:
            raise RuntimeError("Missing sync manager for MidClient bot.")
        return self.sync_manager

    def get_executor(self) -> cmds.PebbleExecutor:
        return self.executor

    def get_storage(self) -> Storage:
        return self.storage

    @tasks.loop(seconds=STORAGE_SAVE_INTERVAL)
    async def save_storage(self):
        self.get_storage().save()

    async def setup_hook(self) -> None:
        await super().setup_hook()
        await self.register_commands()
        log.info("Commands in tree:")
        for cmd in self.tree.walk_commands():
            log.info(f"{cmd.name}")

        TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")
        if TEST_GUILD_ID != None:
            log.info(
                f"Got test guild id: {TEST_GUILD_ID}; will sync app commands to test guild"
            )
            TEST_GUILD = (
                discord.Object(id=int(TEST_GUILD_ID)) if TEST_GUILD_ID else None
            )
            self.tree.copy_global_to(guild=TEST_GUILD)  # type: ignore
            await self.tree.sync(guild=TEST_GUILD)
        else:
            log.warn(
                f"No test guild id; only syncing tree to global. May take time for commands to appear."
            )
            await self.tree.sync()
        return

    # Override, near-identical to discord.Client.start().
    # Set up manager and tear down upon exit.
    # Clean up executor workers upon completion.
    async def start(self, token: str, *, reconnect: bool = True) -> None:
        self.setup_manager()

        await self.login(token)
        await self.connect(reconnect=reconnect)

        self.shutdown_manager()

    def setup_manager(self):
        if self.sync_manager != None:
            log.info("Sync manager already started.")
            return
        for key, type in MidClient.managed_types.items():
            log.info(f"managing data type {key}: {type}")
            DataManager.register(key, type)
        self.sync_manager = DataManager()
        self.sync_manager.start()
        log.info("Sync manager started.")
        self.save_storage.start()  # also start periodic save-to-disk task

    def shutdown_manager(self):
        self.executor.shutdown(False)
        if self.sync_manager != None:
            self.sync_manager.shutdown()
        log.info("Sync manager shut down.")
        self.save_storage.cancel()  # stop periodic save-to-disk task
        self.get_storage().save()

    async def on_ready(self):
        log.info(
            f"{self.user} is now connected to Discord in guilds:"
            + f"{[(g.name, g.id) for g in self.guilds]}"
        )

    async def on_command_error(self, ctx: commands.Context, exception, /) -> None:
        if ignorable_check_failure(exception):
            return
        return await super().on_command_error(ctx, exception)

    async def register_commands(self):
        self.tree.add_command(help_app_command)

        for cmd in self.misc_commands:
            cmds.swap_hybrid_command_description(cmd)
            self.add_command(cmd)
        for cog in self.misc_cogs:
            await self.add_cog(cog(self))
