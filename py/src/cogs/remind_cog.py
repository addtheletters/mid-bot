# Cog for setting reminders
import logging
import typing
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import config
import dateparser
import discord
from cmds import swap_hybrid_command_description
from cogs.base_cog import BaseCog
from discord.ext import commands, tasks
from utils import *

log = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 15

REMIND_BUTTON_TEXT_ADD = "Remind me too!"
REMIND_BUTTON_TEXT_REMOVE = "Don't remind me."
REMIND_TARGET_SEPARATOR = " ⇒ "

DEFAULT_TIMEZONE = ZoneInfo(config.DEFAULT_TIMEZONE_NAME)


class RemindEntry:
    def __init__(
        self,
        context: commands.Context,
        message: str,
        time: datetime,
        targets: list[discord.User | discord.Member],
        reply: discord.Message | None = None,
    ) -> None:
        self.context = context
        self.message = message
        self.time = time
        self.targets = targets
        self.reply = reply

    def __repr__(self) -> str:
        return f"At {short_format_time(self.time)} for {','.join((u.name for u in self.targets))}: {self.message}"

    async def send(self):
        reminders = self.target_mentions()
        decorated = reminders + "\nReminder: " + self.message
        if isinstance(self.context, commands.Context):
            await reply(self.context, decorated)
        else:
            await send_safe(self.context, decorated)

    def should_send(self):
        return self.time < (
            datetime.now(tz=self.time.tzinfo)
            + timedelta(seconds=CHECK_INTERVAL_SECONDS)
        )

    def get_targets(self):
        return self.targets

    def target_mentions(self):
        return " ".join((usr.mention for usr in self.targets))

    def was_authored_by(self, user: discord.User | discord.Member) -> bool:
        return (
            isinstance(self.context, commands.Context) and self.context.author is user
        )

    def is_user_involved(self, user: discord.User | discord.Member) -> bool:
        return self.was_authored_by(user) or (user in self.get_targets())

    def delta_from_creation(self) -> timedelta:
        return self.time - self.context.message.created_at.replace(microsecond=0)


def short_format_time(time: datetime):
    return f"{time:%a, %x, %H:%M %Z}"


def contains_am_or_pm(timestr: str):
    timestr = timestr.upper()
    return timestr.find("AM") >= 0 or timestr.find("PM") >= 0


class Reminder(BaseCog):
    def __init__(self, bot) -> None:
        super().__init__(bot)
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
                if entry.reply:
                    await entry.reply.edit(
                        content=self.reminder_set_message(id), view=None
                    )
                done.append(id)
        for id in done:
            self.cancel(id)

    def add_to_reminder(
        self, entry_id: int, user: discord.User | discord.Member
    ) -> None:
        if entry_id not in self.reminders:
            raise ValueError(f"The specified reminder isn't valid (#{entry_id}).")
        if user in self.reminders[entry_id].get_targets():
            raise ValueError(f"Already included in the reminder.")
        self.reminders[entry_id].targets.append(user)

    def remove_from_reminder(
        self, entry_id: int, user: discord.User | discord.Member
    ) -> None:
        if entry_id not in self.reminders:
            raise ValueError(f"The specified reminder isn't valid (#{entry_id}).")
        self.reminders[entry_id].targets.remove(user)

    def reminder_set_message(self, entry_id: int):
        if entry_id not in self.reminders:
            return f"Reminder #{entry_id} not found."
        entry = self.reminders[entry_id]
        return f"Reminder #{entry_id} set for {short_format_time(entry.time)}. (in {entry.delta_from_creation()})"

    def cancel(self, entry_id: int):
        return self.reminders.pop(entry_id)

    def build_parse_settings_future(self):
        return {
            "PREFER_DATES_FROM": "future",
            "PREFER_DAY_OF_MONTH": "first",
            "TIMEZONE": config.DEFAULT_TIMEZONE_NAME,
        }

    def build_parse_settings_current(self):
        return {
            "PREFER_DAY_OF_MONTH": "first",
            "TIMEZONE": config.DEFAULT_TIMEZONE_NAME,
        }

    def too_far_in_past(self, time: datetime):
        return time < (datetime.now(tz=time.tzinfo) - timedelta(minutes=1))

    @commands.hybrid_command(
        aliases=["rem"],
        brief="Set a reminder",
        description=f"""
    __**remind**__
    Set a reminder. 
    The bot will mention you in a message within a minute of the set time, in the same channel the command was used.
    It will attempt to parse your requested time, allowing for requests like `{get_summon_prefix()}remind "in 30 minutes" check the oven`.
    If AM/PM is unspecified, it defaults to 24-hour clock interpretation, but will try to auto-adjust if the resulting time is in the past.
    Reminders aren't yet saved to any persistent storage, and will be lost if the bot restarts, so don't rely on it for anything extremely important.
    """,
    )
    async def remind(self, ctx: commands.Context, time: str, *, text: str):
        entry_id = self.next_id
        self.next_id += 1

        parsed_time = None
        closer_time = None
        time_ambiguous: bool = False
        detail_message = ""
        async with ctx.typing():
            parsed_time = dateparser.parse(time, settings=self.build_parse_settings_future())  # type: ignore
            if parsed_time is None:
                await reply(ctx, f'Can\'t parse time "{time}".')
                return
            if parsed_time.tzinfo is None:
                parsed_time = parsed_time.replace(tzinfo=DEFAULT_TIMEZONE)
                detail_message += f" (assuming {parsed_time.tzname()} time zone)"

            # Check for date ambiguity
            closer_time = dateparser.parse(time, settings=self.build_parse_settings_current())  # type: ignore
            if closer_time and parsed_time != closer_time:
                time_ambiguous = True

                if closer_time.tzinfo is None:
                    closer_time = closer_time.replace(tzinfo=DEFAULT_TIMEZONE)
                # sensibly override AM/PM if it seems off (in the past)
                if (
                    self.too_far_in_past(closer_time)
                    and closer_time.hour < 12
                    and not contains_am_or_pm(time)
                ):
                    closer_time = closer_time + timedelta(hours=12)
                    detail_message = f" (assuming 12-hour-clock PM time)"

        # if ambiguous, use least-far time still in the future
        if (
            time_ambiguous
            and closer_time is not None
            and not self.too_far_in_past(closer_time)
            and closer_time < parsed_time
        ):
            parsed_time = closer_time
            detail_message += f" (assuming today rather than tomorrow)"

        # fail if more than 1 minute in the past
        if self.too_far_in_past(parsed_time):
            await reply(
                ctx,
                f"Time ({short_format_time(parsed_time)}) is in the past!"
                + detail_message,
            )
            return

        log.info(f"setting reminder for time: {short_format_time(parsed_time)}")
        parsed_time = parsed_time.replace(microsecond=0)
        self.reminders[entry_id] = RemindEntry(
            context=ctx, message=text, time=parsed_time, targets=[ctx.author]
        )
        self.reminders[entry_id].reply = await reply(
            ctx,
            f"{self.reminder_set_message(entry_id)}{detail_message}",
            view=ReminderView(self, entry_id),
        )

    @remind.error
    async def remind_error(self, ctx: commands.Context, error):
        if ignorable_check_failure(error):
            return
        if isinstance(error, commands.errors.MissingRequiredArgument):
            await reply(ctx, f"Can't set reminder: {error}")
            return
        raise error

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
            re = self.cancel(id)
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
                    ctx,
                    f"You have multiple pending reminders: #{','.join(( str(id) for id in pending ))}",
                )
                return
            re = self.cancel(pending[0])
            if re.reply:
                await re.reply.edit(content="Reminder cancelled.", view=None)
            await reply(ctx, f"Cancelled reminder: {re}")


class ReminderView(discord.ui.View):
    def __init__(self, cog: Reminder, entry_id: int):
        self.rcog = cog
        self.entry_id = entry_id
        super().__init__(timeout=None)

    @discord.ui.button(label=REMIND_BUTTON_TEXT_ADD, style=discord.ButtonStyle.blurple)
    async def me_too_pressed(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        try:
            self.rcog.add_to_reminder(entry_id=self.entry_id, user=interaction.user)
        except ValueError as err:
            await interaction.response.send_message(
                f"Sorry, can't add you: {err}", ephemeral=True
            )
            return

        content = (
            self.rcog.reminder_set_message(self.entry_id)
            + " "
            + self.rcog.reminders[self.entry_id].target_mentions()
        )
        await interaction.response.edit_message(content=content, view=self)

    @discord.ui.button(
        label=REMIND_BUTTON_TEXT_REMOVE, style=discord.ButtonStyle.blurple
    )
    async def remove_me_pressed(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        try:
            self.rcog.remove_from_reminder(
                entry_id=self.entry_id, user=interaction.user
            )
        except ValueError as err:
            await interaction.response.send_message(
                f"Sorry, can't remove you: {err}", ephemeral=True
            )
            return

        if len(self.rcog.reminders[self.entry_id].get_targets()) == 0:
            # cancel the reminder if there are no targets remaining
            self.rcog.cancel(self.entry_id)
            await interaction.response.edit_message(
                content="Reminder cancelled (nobody to remind).", view=None
            )
            return

        content = (
            self.rcog.reminder_set_message(self.entry_id)
            + " "
            + self.rcog.reminders[self.entry_id].target_mentions()
        )
        await interaction.response.edit_message(content=content, view=self)
