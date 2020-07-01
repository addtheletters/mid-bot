# Commands.
from collections import namedtuple
from config import *
from random import randint
from utils import escape, reply
import discord
import dice

Command = namedtuple("Command", ["keys", "func", "info", "detailed"])

async def command_help(client, msg, intext):
    if len(intext) < 1: # show command list
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
    else: # fetch detailed command help
        key = intext.split(" ")[0]
        try:
            cmd = client.commands[key]
            await reply(msg, cmd.detailed)
        except KeyError:
            await reply(msg, f"No help available for unknown command `{key}`.")

async def command_echo(client, msg, intext):
    if len(intext) == 0:
        await reply(msg, f"There is only silence.")
    else:
        await reply(msg, f"`{intext}`")

async def command_shruggie(client, msg, intext):    
    await reply(msg, escape("¯\\_(ツ)_/¯"))

async def command_roll(client, msg, intext):
    try:
        roll_result = dice.roll(intext)
        await reply(msg, dice.format_roll_results(roll_result))
    except Exception as err:
        print(f"Roll error: {err}")
        await reply(msg, f"Input not accepted.\n```{err}```")

# Add commands here. Commands need at least one key and a function to perform.
COMMAND_CONFIG = [
    Command(["help"], command_help,
        f"List available commands or show usage ({BOT_SUMMON_PREFIX}{DEFAULT_HELP_KEY} {DEFAULT_HELP_KEY}).",
f"""
__**help**__
Lists commands. Use a command by sending a message with the bot summon prefix (`{BOT_SUMMON_PREFIX}`) followed by the command keyword.
Multiple keywords may be associated with the same command and will be listed with it.
`{BOT_SUMMON_PREFIX}{DEFAULT_HELP_KEY} <command>` can be used to display detailed usage information about a particular command.
"""),
    Command(["echo", "repeat"], command_echo, "Repeat your message back.",
f"""
__**echo**__
Sends the contents of your message back to you.
The command keyword and bot prefix are excluded.
Content is wrapped in backquotes with the intention that Discord will display it as a code block; backquotes in your original message can easily break this.
"""),
    Command(["shrug"], command_shruggie, "Shruggie.",
"""
__**shrug**__
Displays a shruggie: ¯\\\\_(ツ)\\_/¯
That's all.
"""),
    Command(["roll"], command_roll, "Roll some dice.",
f"""
__**roll**__
Rolls a dice. 
The parser handles some of the usual dice notation (https://en.wikipedia.org/wiki/Dice_notation).
Here's what it can do. 

__Basic arithmetic.__ `+, -, *, /, ^ (power, not xor)`
    Use as you'd expect. `1+4`, `2*8`, `4^3^2`...
__Dice roll.__ `d`
    Use as `<N>d<S>`, which rolls `<N>` dice of size `<S>`, adding together the results.
    `<N>` and `<S>` must resolve to positive integers.
    `<N>` can be omitted; this will roll 1 dice.
    Example: `{BOT_SUMMON_PREFIX}roll 8d6`
__Keep/Drop.__ `kh` (keep high), `kl` (keep low), `dh` (drop high), `dl` (drop low).
    Use as `<diceroll>kh<N>` to keep the `<N>` highest dice from `<diceroll>`.
    `<diceroll>` must be some rolled dice (use of the `d` operator).
    `<N>` must resolve to a positive integer.
    Example: `{BOT_SUMMON_PREFIX}roll 4d6kh3`
__Semicolons__ act as dividers, allowing several independent rolls from one message.
    Example: `{BOT_SUMMON_PREFIX}roll 1d20+5; 2d6+5`
"""),
]
