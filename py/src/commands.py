# Commands.
from collections import namedtuple
from config import *
from random import randint
from utils import escape, codeblock
import asyncio
import discord
import dice

Command = namedtuple("Command", ["keys", "func", "info", "detailed"])

def command_help(intext):
    if len(intext) < 1: # show command list
        help_info = "Available commands:\n"
        for cmd in COMMAND_CONFIG:
            help_info += f"{cmd.keys}: {cmd.info}\n"
        return codeblock(help_info, big=True)
    else: # fetch detailed command help
        key = intext.split(" ")[0]
        for cmd in COMMAND_CONFIG:
            if key in cmd.keys:
                return cmd.detailed    
        return f"No help available for unknown command {codeblock(key)}."

def command_echo(intext):
    if len(intext) == 0:
        return f"There is only silence."
    else:
        return f"{intext}"

def command_shruggie(intext):
    return escape("¯\\_(ツ)_/¯")

def command_roll(intext):
    try:
        roll_result = dice.roll(intext)
        return dice.format_roll_results(roll_result)
    except Exception as err:
        print(f"Roll error: {err}")
        return f"Input not accepted.\n{codeblock(err, big=True)}"

# Add commands here. Commands need at least one key and a function to perform.
# A command function can return a string which will be sent as a response.
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
"""),
    Command(["shrug"], command_shruggie, "Shruggie.",
"""
__**shrug**__
Displays a shruggie: ¯\\\\_(ツ)\\_/¯
That's all.
"""),
    Command(["roll", "r"], command_roll, "Roll some dice.",
f"""
__**roll**__
Rolls some dice and does some math.
This handles a basic subset of standard dice notation (https://en.wikipedia.org/wiki/Dice_notation).
Here's what it can do.

__Basic arithmetic__ `+ - * / ^ (power, not xor)`
    Use as you'd expect. `1+4`, `2*8`, `4^3^2`...
__Dice roll__ `d`
    Use as `<N>d<S>`, which rolls `<N>` dice of size `<S>`, adding together the results.
    `<N>` and `<S>` must resolve to positive integers.
    `<N>` can be omitted; this will roll 1 dice.
    Example: `{BOT_SUMMON_PREFIX}roll 8d6`
__Keep/Drop__ `kh` (keep high), `kl` (keep low), `dh` (drop high), `dl` (drop low)
    Use as `<diceroll>kh<N>` to keep the `<N>` highest dice from `<diceroll>`.
    `<diceroll>` must be some rolled dice (use of the `d` operator).
    `<N>` must resolve to a positive integer.
    Example: `{BOT_SUMMON_PREFIX}roll 4d6kh3`
__Parentheses__ `( )` enforce associativity and order of operations.
    Example: `{BOT_SUMMON_PREFIX}roll 3d((2+23)/5)`
__Semicolons__ `;` act as dividers, allowing several independent rolls from one message.
    Example: `{BOT_SUMMON_PREFIX}roll 1d20+5; 2d6+5`
"""),
]
