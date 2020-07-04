# Utility functions.
import discord
import logging
from config import MAX_MESSAGE_LENGTH, INVISIBLE_SPACE

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
    if len(payload) > MAX_MESSAGE_LENGTH:
        cutoff = len(payload) - MAX_MESSAGE_LENGTH
        payload = payload[:MAX_MESSAGE_LENGTH]\
            + f" ... (full message too long to send, truncated {cutoff} characters.)"
    await msg.channel.send(payload)


# Enclose `text` in a backticked codeblock.
# Places zero-width spaces next to internal backtick characters to avoid
# breaking out.
def codeblock(text, big=False):
    inner = str(text).replace('`', '`' + INVISIBLE_SPACE)
    if inner[0] == "`":
        inner = INVISIBLE_SPACE + inner
    if big:
        return f"```{inner}```"
    return f"`{inner}`"
