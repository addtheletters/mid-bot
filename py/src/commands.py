# Commands.
from collections import namedtuple
from random import randint
from utils import escape, reply
import discord
import dice

Command = namedtuple("Command", ["keys", "func", "info"])

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
    await reply(msg, escape("¯\\_(ツ)_/¯"))

async def command_roll(client, msg, intext):
    try:
        roll_result = dice.roll(intext)
        await reply(msg, dice.format_roll_results(roll_result))
    except Exception as err:
        print(f"Roll error: {err}")
        await reply(msg, f"Input not accepted.\n```{err}```")
