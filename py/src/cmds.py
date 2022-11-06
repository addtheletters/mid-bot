# Commands.
from collections import namedtuple
from config import *
from random import randint
from utils import *

import asyncio
import cards
import discord
import dice
import logging

log = logging.getLogger(__name__)

Command = namedtuple("Command", ["keys", "func", "info", "detailed"])


def command_eject(intext, *args):
    intext = intext.strip().split(" ")
    target = "No one"
    action = "was ejected."
    remaining = "　　。　  　.  　"
    if len(intext) > 0:
        if len(intext[0].strip()) > 0:
            target = intext[0]
    if len(intext) > 1:
        if intext[1].lower() in ("bad", "impostor", "yes", "sus"):
            action = "was an Impostor."
        elif intext[1].lower() in ("good", "innocent", "no", "clear"):
            action = "was not an Impostor."
        else:
            target += " " + intext[1]
    if len(intext) > 2:
        try:
            remaining = str(int(intext[2])) + " Impostor(s) remain."
        except ValueError:
            for i in range(2, len(intext)):
                target += " " + intext[i]
    guy = " "
    if target != "No one":
        guy = "ඞ"

    message = f"""
    . 　　　。　　　　•　 　ﾟ　　。 　　.

　　　.　　　 　.　　　　　。　　 。　. 　

    .　　 。　　　　 {guy}    . 　　 • 　　　•

　　 ﾟ   . 　 {target} {action}　 。　.

　　  '　　  {remaining}   　 • 　　 。

　　ﾟ　　　.　　　.     　　　　.　       。"""
    return message


# Add commands here. Commands need at least one key and a function to perform.
# A command function can return a string which will be sent as a response.
COMMAND_CONFIG = [
    Command(["eject", "kill"], command_eject, "Eject an impostor.",
        f"""
__**eject**__
Choose someone sus and eject them.
`{get_summon_prefix()}eject <target> <badness> <remaining>`
If no __target__ is specified, no one is ejected.
__badness__ can be good, bad, impostor, innocent, yes, or no.
If impostors remain, supply a integer for __remaining__.
The parsing is dumb and just splits on whitespace. Anything not matching expected values for badness / remaining is added on to the target.
""")
]
