# A bot with some basic custom skills.
from collections import namedtuple
from dotenv import load_dotenv
from random import randint
import discord
import os

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

BOT_SUMMON_PREFIX = "~"
DEFAULT_HELP_KEY = "help"

def print_message(msg):
    print(f"({msg.id}) {msg.created_at.isoformat(timespec='milliseconds')} [{msg.channel}] <{msg.author}> {msg.content}")

# Send `text` in response to `msg`.
async def reply(msg, text):
    await msg.channel.send(f"{msg.author.mention} {text}")

async def command_help(client, msg, intext):
    shown = set()
    help_info = "```Available commands:\n"
    for key in client.commands.keys():
        if key in shown:
            continue
        cmd = client.commands[key]
        help_info += f"{cmd.keys}: {cmd.info}\n"
        for altkey in cmd.keys:
            shown.add(altkey)
    help_info += "```"
    await reply(msg, help_info)

async def command_echo(client, msg, intext):
    if len(intext) == 0:
        await reply(msg, f"There is only silence.")
    else:
        await reply(msg, f"`{intext}`")

async def command_shruggie(client, msg, intext):    
    await reply(msg, discord.utils.escape_markdown("¯\\_(ツ)_/¯"))

async def command_roll20(client, msg, intext):
    diceroll = randint(1, 20)
    await reply(msg, f"`d20 => {diceroll}`")

Command = namedtuple("Command", ["keys", "func", "info"])
# Add commands here. Commands need at least one key and a function to perform.
COMMAND_CONFIG = [
    Command([DEFAULT_HELP_KEY], command_help, "List available commands."),
    Command(["echo", "repeat"], command_echo, "Repeat your message back."),
    Command(["shrug"], command_shruggie, "Shruggie."),
    Command(["roll20"], command_roll20, "Roll a d20."),
]

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
        print(f"Processing message {msg.id}.")
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
                await reply(msg, f"The bot hears you. See `{BOT_SUMMON_PREFIX}{DEFAULT_HELP_KEY}`.")
                return
            command = tokens[0]
            intext = intext[len(command)+1:].strip() # trim off command text

            if command in self.commands.keys():
                await self.commands[command].func(self, msg, intext)
            else:
                await reply(msg, f"Unrecognized command `{command}`. See `{BOT_SUMMON_PREFIX}{DEFAULT_HELP_KEY}`.")

client = MidClient()
client.run(TOKEN)
