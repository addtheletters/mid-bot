# Utility functions.
import logging
import os
import typing

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


def is_slash_command(ctx: commands.Context) -> bool:
    return ctx.interaction != None


# Send a message to a context or messageable, truncating if it would exceed length limits.
async def send_safe(
    ctx: commands.Context | discord.abc.Messageable, text: str | None = None, **kwargs
):
    payload = text
    if payload and len(payload) > config.MAX_MESSAGE_LENGTH:
        cutoff = len(payload) - config.MAX_MESSAGE_LENGTH
        payload = (
            payload[: config.MAX_MESSAGE_LENGTH]
            + f" ... (message too long, truncated {cutoff} characters.)"
        )
    if isinstance(ctx, commands.Context):
        # Send as followup if deferred interaction
        if ctx.interaction and ctx.interaction.response.is_done():
            if payload is None:
                payload = ""
            return await ctx.interaction.followup.send(payload, **kwargs)
        return await ctx.reply(payload, **kwargs)
    else:
        return await ctx.send(payload, **kwargs)


# Send `text` as a reply in the given context `ctx`.
# Set `mention` to true to include an @ mention. Behavior if unset is to mention if not a slash command.
async def reply(
    ctx: commands.Context | discord.abc.Messageable,
    text: str | None = None,
    mention: typing.Optional[bool] = None,
    **kwargs,
):
    payload = text
    if text and isinstance(ctx, commands.Context):
        payload = f"{(ctx.author.mention + ' ') if mention else ''}{text}"
    return await send_safe(ctx=ctx, text=payload, **kwargs)


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
    SUMMON_PREFIX = os.getenv("SUMMON_PREFIX")
    if SUMMON_PREFIX is not None:
        return SUMMON_PREFIX
    return config.DEFAULT_SUMMON_PREFIX


# Get a help message string displaying how to input the `help` command.
def get_help_notice(cmd=None):
    command_section = f" {cmd}" if cmd != None else ""
    return f"See `{get_summon_prefix()}{config.DEFAULT_HELP_KEY}{command_section}`."


# Helper check for deafen having no response.
def ignorable_check_failure(exception):
    if isinstance(exception, commands.CheckFailure):
        log.warn(exception)
        return True
    return False


# Create an embed featuring a linked image.
def image_embed(
    title: str, img_url: str, link: str | None = None, footer_text: str | None = None
) -> discord.Embed:
    return (
        discord.Embed(title=title, url=link if link else img_url)
        .set_image(url=img_url)
        .set_footer(text=footer_text)
    )
