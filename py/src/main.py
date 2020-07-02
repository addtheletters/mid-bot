# A bot with some basic custom skills.
from commands import *
from config import *
from dotenv import load_dotenv
from pebble import ProcessPool
from utils import reply, log_message
import asyncio
import concurrent.futures
import discord
import logging
import os

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

def help_notice():
    return f"See `{BOT_SUMMON_PREFIX}{DEFAULT_HELP_KEY}`."

# Wrapper for ProcessPool to allow use with asyncio run_in_executor
class PebbleExecutor(concurrent.futures.Executor):
    def __init__(self, max_workers, timeout=None):
        self.pool = ProcessPool(max_workers=MAX_COMMAND_WORKERS)
        self.timeout = timeout

    def submit(self, fn, *args, **kwargs):
        return self.pool.schedule(fn, args=args, timeout=self.timeout)

    def map(self, func, *iterables, timeout=None, chunksize=1):
        return NotImplementedError("This wrapper does not yet support `map`.")

    def shutdown(self, wait=True):
        if wait:
            log.info("Closing workers...")
            self.pool.close()
        else:
            log.info("Ending workers...")
            self.pool.stop()
        self.pool.join()
        log.info("Workers joined.")

class MidClient(discord.Client):
    def __init__(self):
        discord.Client.__init__(self)
        self.executor = PebbleExecutor(
            MAX_COMMAND_WORKERS,
            COMMAND_TIMEOUT)

        self.commands = {}
        for cmd in COMMAND_CONFIG:
            for key in cmd.keys:
                self.register_command(key, cmd)

    # Override. Functionally near-identical to discord.Client.
    # Prevent main loop from exiting on subprocess SIGINT/SIGTERM.
    # Clean up executor workers upon completion.
    def run(self, *args, **kwargs):
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

    def register_command(self, key, cmd):
        if key in self.commands.keys():
            log.warning(f"Key {key} is overloaded. Fix the command configuration.")
        self.commands[key] = cmd
        if key not in cmd.keys:
            cmd.keys.append(key)

    async def execute_command(self, command_key, msg, intext):
        cmd_future = self.loop.run_in_executor(self.executor, self.commands[command_key].func, intext)
        try:
            response = await asyncio.wait_for(cmd_future, timeout=COMMAND_TIMEOUT)
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
        log.info(f"{self.user} is now connected to Discord in guilds: {[g.name for g in self.guilds]}")

    async def on_message(self, msg):
        if (self.should_process_message(msg)):
            log_message(msg)
            await self.process_message(msg)

    def should_process_message(self, msg):
        # don't reply to self
        if msg.author == self.user:
            return False
        # ignore empty messages
        if msg.content == None or len(msg.content) < 1:
            return False
        # allow bot-mentions to be processed to inform users about the prefix 
        return msg.content.startswith(BOT_SUMMON_PREFIX) or self.user in msg.mentions

    async def process_message(self, msg):
        if msg.channel == None:
            log.info("Missing channel, can't reply.")
            return

        async with msg.channel.typing():
            command = None
            # message without prefix sent to bot
            if not msg.content.startswith(BOT_SUMMON_PREFIX):
                await reply(msg, f"Summon me using: `{BOT_SUMMON_PREFIX}<your request here>`")
                return

            intext = msg.content[len(BOT_SUMMON_PREFIX):].strip()
            tokens = intext.split()
            if len(tokens) < 1: # nothing following the prefix
                await reply(msg, f"The bot hears you. {help_notice()}")
                return
            command = tokens[0]
            intext = intext[len(command)+1:].strip() # trim off command text

            if command in self.commands.keys():
                try:
                    command_response = await self.execute_command(command, msg, intext)
                    if command_response != None and len(command_response) > 0:
                        await reply(msg, command_response)
                    return
                except concurrent.futures.TimeoutError:
                    await reply(msg, f"Command execution timed out for `{command} {intext}`.")
            else:
                await reply(msg, f"Unrecognized command `{command}`. {help_notice()}")

if __name__ == "__main__":
    client = MidClient()
    client.run(TOKEN)
