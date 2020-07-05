# Commands.
from collections import namedtuple
from config import *
from random import randint
from utils import escape, codeblock
import asyncio
import cards
import discord
import dice
import logging

log = logging.getLogger(__name__)

Command = namedtuple("Command", ["keys", "func", "info", "detailed"])


def sub_help_notice(command):
    return f"See `{BOT_SUMMON_PREFIX}{DEFAULT_HELP_KEY} {command}`."


def command_help(intext, *args):
    if len(intext) < 1:  # show command list
        help_info = "Available commands:\n"
        for cmd in COMMAND_CONFIG:
            help_info += f"{cmd.keys}: {cmd.info}\n"
        return codeblock(help_info, big=True)
    else:  # fetch detailed command help
        key = intext.split(" ")[0]
        for cmd in COMMAND_CONFIG:
            if key in cmd.keys:
                return cmd.detailed
        return f"No help available for unknown command {codeblock(key)}."


def command_echo(intext, *args):
    if len(intext) == 0:
        return f"There is only silence."
    else:
        return f"{intext}"


def command_shruggie(intext, *args):
    return escape("¯\\_(ツ)_/¯")


def command_roll(intext, *args):
    try:
        roll_result = dice.roll(intext)
        return dice.format_roll_results(roll_result)
    except Exception as err:
        log.info(f"Roll error: {err}")
        return f"Input not accepted.\n{codeblock(err, big=True)}"


def command_holdem(intext, *args):
    if len(intext) == 0:
        return "A dry wind blows in from the west."
    try:
        intext = intext.split(" ")
        subargs = len(intext)
        subcommand = intext[0]
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
        return f"Unknown subcommand {codeblock(subcommand)}. {sub_help_notice('holdem')}"

    # apply deck changes
    data.set_card_deck(deck)
    # update card log
    data.add_card_log(f"{user}: {ret if subcommand != 'history' else 'viewed history.'}")
    return ret

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
This handles a subset of standard dice notation (https://en.wikipedia.org/wiki/Dice_notation).
Roughly in order of operator precedence:

__Dice roll__ `d`
    `<N>d<S>` to roll `<N>` dice of size `<S>`, adding the results. `<N>` omitted will roll 1 dice.
__Collective Comparison__ `?= ?> ?< ?>= ?<=`
    Filter for and count how many items from a collection succeed a comparison.
    `{BOT_SUMMON_PREFIX}roll 4d6?=5` for how many times 5 is rolled from 4 six-sided dice.
    `{BOT_SUMMON_PREFIX}roll repeat(3d6, 10)?>=4` for how many out of 10 rolls of 3d6 total to 4 or more.  
__Keep/Drop__ `kh` (keep high), `kl` (keep low), `dh` (drop high), `dl` (drop low)
    `<diceroll>kh<N>` keeps the `<N>` highest values from `<diceroll>`. `repeat` collections also work. 
    `{BOT_SUMMON_PREFIX}roll 4d6kh3` or `{BOT_SUMMON_PREFIX}roll repeat(3d6, 5)dl2`
__Explode__ `!`, also `!= !> !< !>= !<=`
    `<diceroll>!` A highest-possible roll explodes (triggers another roll, added to the total).
    A comparison added will explode on rolls that succeed.
    `{BOT_SUMMON_PREFIX}roll 10d4!`, `{BOT_SUMMON_PREFIX}roll 8d6!>4`
__Combinatorics__ `choose` or `C`
    `<n> C <k>` or `<n> choose <k>` to count choices.
__Arithmetic__ `+ - * / % ^`
    Use as you'd expect. `%` is remainder. `^` is power, not xor.
__Value Comparison__ `= > < >= <=`
    Check if a value succeeds a comparison. Evaluates to 1 if success, 0 if not.
    `{BOT_SUMMON_PREFIX}roll 1d20+5 >= 15`
__Functions__ `repeat() sqrt() fact()`
    `repeat(<expression>, <n>)`
    `sqrt(<x>)`
    `fact(<N>)` is N factorial (`!` is reserved for exploding dice).
__Parentheses__ `( )` for associativity and order of operations.
__Semicolons__ `;` divide your input, allowing several rolls from one message.
    `{BOT_SUMMON_PREFIX}roll 1d20+5; 2d6+5`
"""),
    Command(["holdem", "h"], command_holdem, "Deal out cards.",
            f"""
__**holdem**__
Throws out cards from a 52-card deck. (Direct-message the bot to receive cards in secret.)
The following subcommands are available:
__draw__ `{BOT_SUMMON_PREFIX}holdem draw <count>`
    Draw `<count>` cards from the deck.
__reset__ `{BOT_SUMMON_PREFIX}holdem reset`
    Reset the deck.
__shuffle__ `{BOT_SUMMON_PREFIX}holdem shuffle`
    Shuffle the remaining cards in the deck.
__inspect__ `{BOT_SUMMON_PREFIX}holdem inspect`
    Check the number of cards remaining in the deck, and peek at the top and bottom cards.
__history__ `{BOT_SUMMON_PREFIX}holdem history <count>`
    View `<count>` past actions performed using this command.
""")
]
