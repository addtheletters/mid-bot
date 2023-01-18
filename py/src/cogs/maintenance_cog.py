# Cog for ensuring that bot data is stored before maintenance

from cmds import swap_hybrid_command_description
from config import STORAGE_SAVE_INTERVAL
from cogs.base_cog import BaseCog
from discord.ext import commands
from utils import reply


class Maintenance(BaseCog):
    def __init__(self, bot) -> None:
        super().__init__(bot)
        swap_hybrid_command_description(self.forcesave)

    @commands.hybrid_command(
        brief="Save the bot's persistent data",
        description=f"""
    __**forcesave**__
    Immediately save bot data to persistent storage.
    Normally, the bot does this automatically every {STORAGE_SAVE_INTERVAL} seconds.
    """,
    )
    async def forcesave(self, ctx: commands.Context):
        errored = self.bot.get_storage().save()
        if errored:
            await reply(ctx, "Encountered error while saving. Check the logs.")
            return
        else:
            await reply(ctx, "Succesfully stored data.")
