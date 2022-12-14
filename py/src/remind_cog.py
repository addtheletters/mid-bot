# Cog for setting reminders
import logging
from datetime import datetime, timedelta

from cmds import swap_hybrid_command_description
import dateparser
from discord.ext import commands, tasks
from utils import *

log = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 15


class RemindEntry:
    def __init__(
        self,
        context: commands.Context | discord.abc.Messageable,
        message: str,
        time: datetime,
        targets: list[discord.User | discord.Member],
    ) -> None:
        self.context = context
        self.message = message
        self.time = time
        self.targets = targets

    def __repr__(self) -> str:
        return f"At {short_format_time(self.time)} for {','.join((u.name for u in self.targets))}: {self.message}"

    async def send(self):
        reminders = " ".join((usr.mention for usr in self.targets))
        decorated = reminders + "\nReminder: " + self.message
        if isinstance(self.context, commands.Context):
            await reply(self.context, decorated)
        else:
            await send_safe(self.context, decorated)

    def should_send(self):
        return self.time < (datetime.now() + timedelta(seconds=CHECK_INTERVAL_SECONDS))

    def get_targets(self):
        return self.targets

    def was_authored_by(self, user: discord.User | discord.Member) -> bool:
        return (
            isinstance(self.context, commands.Context) and self.context.author is user
        )

    def is_user_involved(self, user: discord.User | discord.Member) -> bool:
        return self.was_authored_by(user) or (user in self.get_targets())


def short_format_time(time: datetime):
    return f"{time:%a, %x, %H:%M}"


def contains_am_or_pm(timestr: str):
    return timestr.find("AM") > 0 or timestr.find("PM") > 0


class Reminder(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: commands.Bot = bot
        self.reminders: dict[int, RemindEntry] = {}
        self.next_id: int = 1

        swap_hybrid_command_description(self.remind)
        swap_hybrid_command_description(self.remlist)
        swap_hybrid_command_description(self.remcancel)
        self.reminder_loop.start()

    def cog_unload(self) -> None:
        self.reminder_loop.cancel()

    @tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
    async def reminder_loop(self):
        done = []
        for id, entry in self.reminders.items():
            if entry.should_send():
                await entry.send()
                done.append(id)
        for id in done:
            self.reminders.pop(id)

    @commands.hybrid_command(
        brief="Set a reminder",
        description=f"""
    __**remind**__
    Set a reminder. 
    The bot will mention you in a message within a minute of the set time, in the same channel the command was used.
    It will attempt to parse your requested time, allowing for requests like `{get_summon_prefix()}remind "in 30 minutes" check the oven`.
    If AM/PM is unspecified, it defaults to 24-hour clock interpretation, but will try to auto-adjust if the resulting time is in the past.
    """,
    )
    async def remind(self, ctx: commands.Context, time: str, *, text: str):
        parsed_time = dateparser.parse(time)
        detail_message = ""
        if parsed_time is None:
            await reply(ctx, f'Can\'t parse time "{time}".')
            return
        if parsed_time < (datetime.now() - timedelta(minutes=1)):
            if parsed_time.hour >= 12 or contains_am_or_pm(time):
                await reply(
                    ctx, f"Time ({short_format_time(parsed_time)}) is in the past!"
                )
                return
            parsed_time = parsed_time + timedelta(hours=12)
            detail_message = " (assuming 12-hour-clock PM time)"

        parsed_time.replace(second=0, microsecond=0)
        self.reminders[self.next_id] = RemindEntry(
            context=ctx, message=text, time=parsed_time, targets=[ctx.author]
        )
        self.next_id += 1
        await reply(
            ctx,
            f"Reminder #{self.next_id-1} set for {short_format_time(parsed_time)}.{detail_message}",
        )

    @remind.error
    async def remind_error(self, ctx: commands.Context, error):
        if ignorable_check_failure(error):
            return
        if isinstance(error, commands.errors.MissingRequiredArgument):
            await reply(ctx, f"Can't set reminder: {error}")

    @commands.hybrid_command(
        brief="Check your reminders",
        description=f"""
    __**remlist**__
    List pending reminders which will mention you.
    """,
    )
    async def remlist(self, ctx: commands.Context):
        to_join = []
        for id, entry in self.reminders.items():
            if entry.is_user_involved(ctx.author):
                to_join.append(f"#{id}: {entry}")
        if len(to_join) == 0:
            await reply(ctx, "You have no pending reminders.")
        else:
            await reply(ctx, "\n".join(to_join))

    @commands.hybrid_command(
        brief="Cancel a reminder",
        description=f"""
    __**remcancel**__
    Cancel a reminder.
    If you have only a single reminder set, will cancel that one when ID is omitted. 
    """,
    )
    async def remcancel(self, ctx: commands.Context, id: typing.Optional[int] = None):
        if id is not None:
            if id not in self.reminders:
                await reply(ctx, f"No reminder found with id #{id}.")
                return
            if not self.reminders[id].is_user_involved(ctx.author):
                await reply(ctx, "You aren't involved in this reminder.")
                return
            re = self.reminders.pop(id)
            await reply(ctx, f"Cancelled reminder: {re}")
        else:
            pending = []
            for id, entry in self.reminders.items():
                if entry.is_user_involved(ctx.author):
                    pending.append(id)
            if len(pending) == 0:
                await reply(ctx, "You have no pending reminders.")
                return
            if len(pending) > 1:
                await reply(
                    ctx, f"You have multiple pending reminders: #{','.join(pending)}"
                )
                return
            re = self.reminders.pop(pending[0])
            await reply(ctx, f"Cancelled reminder: {re}")
