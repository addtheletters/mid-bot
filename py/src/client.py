# A bot client with some basic custom skills.
from commands import *
from config import *
from multiprocessing import Lock
from multiprocessing.managers import SyncManager
from pebble import ProcessPool
from utils import reply, log_message
import asyncio
import cards
import concurrent.futures
import discord
import logging

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def help_notice():
    return f"See `{BOT_SUMMON_PREFIX}{DEFAULT_HELP_KEY}`."


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
            log.info("Ending workers...")
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
class MidClient(discord.Client):

    def __init__(self, channel_whitelist=None):
        discord.Client.__init__(self)
        self.executor = PebbleExecutor(
            MAX_COMMAND_WORKERS,
            COMMAND_TIMEOUT)
        self.sync_manager = None
        self.data = None
        self.channel_whitelist = channel_whitelist
        self.commands = {}
        self.register_commands()

    # Override, near-identical to discord.Client.run().
    # Set up manager and tear down upon exit.
    # Prevent main loop from exiting on subprocess SIGINT/SIGTERM.
    # Clean up executor workers upon completion.
    def run(self, *args, **kwargs):
        self.setup_manager()

        loop = self.loop
        async def runner():
            try:
                await self.start(*args, **kwargs)
            finally:
                await self.close()

        def stop_loop_on_completion(f):
            loop.stop()

        future = asyncio.ensure_future(runner(), loop=loop)
        future.add_done_callback(stop_loop_on_completion)
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            log.info("Received signal to terminate bot and event loop.")
        finally:
            future.remove_done_callback(stop_loop_on_completion)
            log.info("Cleaning up tasks.")
            discord.client._cleanup_loop(loop)

        if not future.cancelled():
            return future.result()
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

    def register_commands(self):
        for cmd in COMMAND_CONFIG:
            for key in cmd.keys:
                self.register_command(key, cmd)

    def register_command(self, key, cmd):
        if key in self.commands.keys():
            log.warning(f"Key {codeblock(key)} is overloaded. Fix the command configuration.")
        self.commands[key] = cmd
        if key not in cmd.keys:
            cmd.keys.append(key)

    async def execute_command(self, command_key, msg, intext):
        cmd_future = self.loop.run_in_executor(self.executor,
                                               self.commands[command_key].func,
                                               intext, self.data, f"{msg.author}")
        try:
            response = await asyncio.wait_for(cmd_future,
                                              timeout=COMMAND_TIMEOUT)
            return response
        except concurrent.futures.TimeoutError:
            log.info(f"Command {command_key} timed out on input: {intext}.")
            cmd_future.cancel()
            raise
        except Exception as err:
            log.info(f"Command execution raised error: {err}")
            cmd_future.cancel()
            raise

    async def on_ready(self):
        log.info(f"{self.user} is now connected to Discord in guilds:"
                 + f"{[g.name for g in self.guilds]}")

    async def on_message(self, msg):
        if (self.should_process_message(msg)):
            log_message(msg)
            await self.process_message(msg)

    def is_whitelisted(self, msg):
        if self.channel_whitelist == None:
            return True
        return msg.channel.id in self.channel_whitelist

    def should_process_message(self, msg):
        # don't reply to self
        if msg.author == self.user:
            return False
        # ignore if not whitelisted
        if not self.is_whitelisted(msg):
            return False
        # ignore empty messages
        if msg.content == None or len(msg.content) < 1:
            return False
        # allow bot-mentions to be processed to inform users about the prefix
        if self.user in msg.mentions:
            return True
        # check for bot prefix
        return msg.content.startswith(BOT_SUMMON_PREFIX)

    async def process_message(self, msg):
        if msg.channel == None:
            log.info("Missing channel, can't reply.")
            return

        async with msg.channel.typing():
            command = None
            # message without prefix sent to bot
            if not msg.content.startswith(BOT_SUMMON_PREFIX):
                if "hello" in msg.content.lower() or "hi" in msg.content.lower():
                    await reply(msg, f"Hi there! 🙂")
                    return
                summon_text = BOT_SUMMON_PREFIX + "<command>"
                await reply(msg, f"Summon me using: {codeblock(summon_text)}")
                return

            intext = msg.content[len(BOT_SUMMON_PREFIX):].strip().replace(INVISIBLE_SPACE, "")
            tokens = intext.split()
            if len(tokens) < 1:  # nothing following the prefix
                await reply(msg, f"The bot hears you. {help_notice()}")
                return
            command = tokens[0]
            intext = intext[len(command) + 1:].strip()  # trim off command text

            if command in self.commands.keys():
                try:
                    command_response = await self.execute_command(command, msg, intext)
                    if command_response != None and len(command_response) > 0:
                        await reply(msg, command_response)
                    return
                except concurrent.futures.TimeoutError:
                    full_command = command + " " + intext
                    await reply(msg, f"Command execution timed out for {codeblock(full_command)}.")
            else:
                await reply(msg, f"Unrecognized command {codeblock(command)}. {help_notice()}")
