# A bot with some basic custom skills.
from commands import *
from config import *
from dotenv import load_dotenv
from utils import reply, print_message
import asyncio
import concurrent.futures
import discord
import os

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

def help_notice():
    return f"See `{BOT_SUMMON_PREFIX}{DEFAULT_HELP_KEY}`."

class MidClient(discord.Client):
    def __init__(self):
        discord.Client.__init__(self)
        self.executor = concurrent.futures.ProcessPoolExecutor(max_workers=MAX_COMMAND_WORKERS)

        self.commands = {}
        for cmd in COMMAND_CONFIG:
            for key in cmd.keys:
                self.register_command(key, cmd)

    def register_command(self, key, cmd):
        if key in self.commands.keys():
            print(f"Key {key} is overloaded. Fix the command configuration.")
        self.commands[key] = cmd
        if key not in cmd.keys:
            cmd.keys.append(key)

    async def execute_command(self, command_key, msg, intext):
        event_loop = asyncio.get_event_loop()
        cmd_future = event_loop.run_in_executor(self.executor, self.commands[command_key].func, intext)
        try:
            response = await asyncio.wait_for(cmd_future, timeout=COMMAND_TIMEOUT)
            return response
        except asyncio.TimeoutError:
            print(f"Command {command_key} timed out on input: {intext}. Resetting executor.")
            raise

    async def on_ready(self):
        print(f"{self.user} is now connected to Discord in guilds: {[g.name for g in self.guilds]}")

    async def on_message(self, msg):
        print_message(msg)
        if (self.should_process_message(msg)):
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
            print("Missing channel, can't reply.")
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
                    if len(command_response) > 0:
                        await reply(msg, command_response)
                    return
                except concurrent.futures.TimeoutError:
                    await reply(msg, f"Command execution timed out for `{command}`.")
            else:
                await reply(msg, f"Unrecognized command `{command}`. {help_notice()}")

if __name__ == "__main__":
    client = MidClient()
    client.run(TOKEN)
