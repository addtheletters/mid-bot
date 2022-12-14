# Cog for deafening the bot
import logging
from datetime import datetime, timedelta

from cmds import swap_hybrid_command_description
from discord.ext import commands
from utils import *

log = logging.getLogger(__name__)

DEFAULT_DEAFEN_SECONDS = 60
MAX_DEAFEN_SECONDS = 300
UNDEAFEN_CMD_NAME = "undeafen"


class Deafener(commands.Cog):
    def __init__(self, bot) -> None:
        self.time_for_undeafen: datetime | None = None
        swap_hybrid_command_description(self.deafen)
        swap_hybrid_command_description(self.undeafen)

    # auto-registered as a global check upon cog added
    def bot_check(self, ctx: commands.Context):
        if self.time_for_undeafen is None:
            return True

        if ctx.command and (ctx.command.name == UNDEAFEN_CMD_NAME):
            return True

        msg_time = ctx.message.created_at
        if msg_time < self.time_for_undeafen:
            return False
        else:
            self.time_for_undeafen = None
            return True

    @commands.hybrid_command(brief="Make the bot temporarily unresponsive")
    async def deafen(
        self,
        ctx: commands.Context,
        seconds: int = commands.parameter(
            description="How many seconds to deafen for. Max 300.",
            default=DEFAULT_DEAFEN_SECONDS,
        ),
    ):
        if seconds < 0:
            raise ValueError(f"Can't deafen for negative time ({seconds})")
        display_time = f"{seconds} sec."
        if seconds > MAX_DEAFEN_SECONDS:
            seconds = MAX_DEAFEN_SECONDS
            display_time = f"{seconds} sec (capped at maximum)."

        msg_time = ctx.message.created_at
        self.time_for_undeafen = msg_time + timedelta(seconds=seconds)

        await reply(ctx, "Deafening bot for " + display_time)

    @commands.hybrid_command(brief="Allow the bot to hear again")
    async def undeafen(self, ctx: commands.Context):
        status = "The bot can hear you now."
        if self.time_for_undeafen is None:
            status = "The bot could already hear you."
        self.time_for_undeafen = None
        await reply(ctx, status)
