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

def sub_help_notice(command):
    return f"See `{get_summon_prefix()}{DEFAULT_HELP_KEY} {command}`."

def command_roll(intext, *args):
    try:
        roll_result = dice.roll(intext)
        return dice.format_roll_results(roll_result)
    except Exception as err:
        log.info(f"Roll error: {err}")
        return f"Input not accepted.\n{codeblock(err, big=True)}"


def command_cards(intext, *args):
    if len(intext) == 0:
        return "A dry wind blows in from the west."
    intext = intext.split(" ")
    subargs = len(intext)
    subcommand = intext[0]
    try:
        # fetch deck from manager. TODO: lock here?
        data = args[0]
        deck = data.get_card_deck()
        user = args[1]
    except Exception as err:
        raise RuntimeError("Can't find cards (data manager failed?)") from err

    ret = None
    if subcommand == "draw":
        count = 1
        if subargs > 1:
            count = int(intext[1])
        drawn = cards.draw(deck, count)
        ret = f"{drawn}"
    elif subcommand == "reset":
        deck = cards.shuffle(cards.build_deck_52())
        ret = "Deck reset and shuffled."
    elif subcommand == "shuffle":
        deck = cards.shuffle(deck)
        ret = f"Deck shuffled."
    elif subcommand == "inspect":
        top = deck[len(deck) - 1] if len(deck) > 0 else None
        bot = deck[0] if len(deck) > 0 else None
        ret = f"{len(deck)} cards in deck. Top card is {top}. Bottom card is {bot}."
    elif subcommand == "history":
        count = 1
        if subargs > 1:
            count = int(intext[1])
        history = data.get_card_logs()
        numbered = [f"{i+1}: {history[i]}" for i in range(len(history))][-count:]
        ret = '\n'.join(numbered)
        if len(numbered) < count:
            ret = "> start of history.\n" + ret
    else:
        return f"Unknown subcommand {codeblock(subcommand)}. {sub_help_notice('cards')}"

    # apply deck changes
    data.set_card_deck(deck)
    # update card log
    data.add_card_log(f"{user}: {ret if subcommand != 'history' else 'viewed history.'}")
    return ret


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
    Command(["cards", "c"], command_cards, "Deal out cards.",
            f"""
__**cards**__
Throws out cards from a 52-card deck. (Direct-message the bot to receive cards in secret.)
The following subcommands are available:
__draw__ `{get_summon_prefix()}cards draw <count>`
    Draw `<count>` cards from the deck.
__reset__ `{get_summon_prefix()}cards reset`
    Reset the deck.
__shuffle__ `{get_summon_prefix()}cards shuffle`
    Shuffle the remaining cards in the deck.
__inspect__ `{get_summon_prefix()}cards inspect`
    Check the number of cards remaining in the deck, and peek at the top and bottom cards.
__history__ `{get_summon_prefix()}cards history <count>`
    View `<count>` past actions performed using this command.
"""),
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
