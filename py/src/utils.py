# Utility functions.
import discord

import config
import logging


log = logging.getLogger(__name__)


# Escape discord formatting
def escape(text):
    return discord.utils.escape_markdown(text)


# Log message contents
def log_message(msg):
    log.info(f"({msg.id}) " +
             f"{msg.created_at.isoformat(timespec='milliseconds')} " +
             f"[{msg.channel}] <{msg.author}> {msg.content}")


# Send `text` in response to `msg`.
async def reply(msg, text):
    payload = f"{msg.author.mention} {text}"
    if len(payload) > config.MAX_MESSAGE_LENGTH:
        cutoff = len(payload) - config.MAX_MESSAGE_LENGTH
        payload = payload[:config.MAX_MESSAGE_LENGTH]\
            + f" ... (message too long, truncated {cutoff} characters.)"
    await msg.channel.send(payload)


# Enclose `text` in a backticked codeblock.
# Places zero-width spaces next to internal backtick characters to avoid
# breaking out.
def codeblock(text, big=False):
    inner = str(text).replace('`', '`' + config.INVISIBLE_SPACE)
    if inner[0] == "`":
        inner = config.INVISIBLE_SPACE + inner
    if big:
        return f"```{inner}```"
    return f"`{inner}`"


# Get the prefix string that the bot will recognize for a given guild ID.
# Currently the default is used across all guilds.
def get_summon_prefix(guild_id=None):
    return config.DEFAULT_SUMMON_PREFIX


# Get a help message string displaying how to input the `help` command.
def get_help_notice():
    return f"See `{get_summon_prefix()}{config.DEFAULT_HELP_KEY}`."
