# Base class for mid-bot cogs
import logging

from client import MidClient
from discord.ext import commands

log = logging.getLogger(__name__)


class BaseCog(commands.Cog):
    def __init__(self, bot: MidClient) -> None:
        self.bot = bot
