# A bot with some basic custom skills.
from commands import *
from config import *
from dotenv import load_dotenv
from utils import reply, print_message
import discord
import os

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

def help_notice():
    return f"See `{BOT_SUMMON_PREFIX}{DEFAULT_HELP_KEY}`."

class MidClient(discord.Client):
    def __init__(self):
        discord.Client.__init__(self)
        self.commands = {}
        for cmd in COMMAND_CONFIG:
            for key in cmd.keys:
                if key in self.commands.keys():
                    print(f"Key {key} is overloaded. Fix the command configuration.")
                self.commands[key] = cmd

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
                await self.commands[command].func(self, msg, intext)
            else:
                await reply(msg, f"Unrecognized command `{command}`. {help_notice()}")

if __name__ == "__main__":
    client = MidClient()
    client.run(TOKEN)
