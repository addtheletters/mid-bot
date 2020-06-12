# Commands.
from collections import namedtuple
from random import randint
from utils import reply
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
    await reply(msg, discord.utils.escape_markdown("¯\\_(ツ)_/¯"))

async def command_roll20(client, msg, intext):
    diceroll = randint(1, 20)
    await reply(msg, f"`d20 => {diceroll}`")

async def command_roll(client, msg, intext):
    try:
        roll_result = dice.roll(intext)
        await reply(msg, dice.format_roll_result(roll_result))
    except Error as err:
        await reply(msg, f"Sorry; encountered error during roll of `{intext}`.\n```{err}```")
