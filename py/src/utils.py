# Utility functions.
import logging

import config
import discord
from discord.ext import commands

log = logging.getLogger(__name__)


# Escape discord formatting
def escape(text):
    return discord.utils.escape_markdown(text)


# Log message contents
def log_message(msg):
    log.info(
        f"({msg.id}) "
        + f"{msg.created_at.isoformat(timespec='milliseconds')} "
        + f"[{msg.channel}] <{msg.author}> {msg.content}"
    )


# Send `text` as a reply in the given context `ctx`.
# Set `mention` to true to include an @ mention.
async def reply(ctx: commands.Context, text: str, mention: bool = False):
    payload = f"{ctx.author.mention if mention else ''}{text}"
    if len(payload) > config.MAX_MESSAGE_LENGTH:
        cutoff = len(payload) - config.MAX_MESSAGE_LENGTH
        payload = (
            payload[: config.MAX_MESSAGE_LENGTH]
            + f" ... (message too long, truncated {cutoff} characters.)"
        )
    await ctx.send(payload)


# Enclose `text` in a backticked codeblock.
# Places zero-width spaces next to internal backtick characters to avoid
# breaking out.
def codeblock(text, big=False):
    inner = str(text).replace("`", "`" + config.INVISIBLE_SPACE)
    if inner[0] == "`":
        inner = config.INVISIBLE_SPACE + inner
    if big:
        return f"```{inner}```"
    return f"`{inner}`"


# Get the intents flags required for MidClient.
def get_intents():
    intents = discord.Intents.default()
    intents.message_content = True
    return intents


# Get the prefix string that the bot will recognize for a given guild ID.
# Currently the default is used across all guilds.
def get_summon_prefix(guild_id=None):
    return config.DEFAULT_SUMMON_PREFIX


# Get a help message string displaying how to input the `help` command.
def get_help_notice(cmd=None):
    command_section = f" {cmd}" if cmd != None else ""
    return f"See `{get_summon_prefix()}{config.DEFAULT_HELP_KEY}{command_section}`."
