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

REMIND_BUTTON_ID_ADD = "reminder_view:me_too"
REMIND_BUTTON_ID_REMOVE = "reminder_view:remove_me"

DEFAULT_TIMEZONE = ZoneInfo(config.DEFAULT_TIMEZONE_NAME)


class RemindEntry:
    def __init__(
        self,
        text: str,
        time: datetime,
        context: commands.Context,
        targets: list[discord.User | discord.Member],
        reply: discord.Message | None = None,
    ) -> None:
        self.text: str = text
        self.time: datetime = time
        self.target_ids: list[int] = [t.id for t in targets]
        self.author_id: int = context.author.id
        self.channel_id: int = context.channel.id
        self.request_id: int = context.message.id
        if context.interaction:
            self.interaction: bool = True
        else:
            self.interaction: bool = False
        self.response_id: int | None = reply.id if reply else None

        # cache-like discord models; these won't change once fetched but aren't persisted in storage.
        self._request: discord.Message | discord.PartialMessage | None = context.message
        self._context: commands.Context | None = context

    def __repr__(self) -> str:
        return f"Reminder at {short_format_time(self.time)} for {','.join(str(tid) for tid in self.target_ids)}: {self.text}"

    def __getstate__(self):
        # Exclude deep discord objects from pickling
        state = self.__dict__.copy()
        if "_request" in state:
            state["_request"] = None
        if "_context" in state:
            state["_context"] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        if "_request" not in state:
            log.info("Restoring request none state")
            self._request = None
        if "_context" not in state:
            log.info("Restoring context none state")
            self._context = None

    async def describe(self, bot: commands.Bot) -> str:
        targets = (u.name for u in await self.get_targets(bot))
        return f"At {short_format_time(self.time)} for {','.join(targets)}: {self.text}"

    def get_request(self, bot: commands.Bot) -> discord.PartialMessage:
        if self._request is None:
            self._request = discord.PartialMessage(
                channel=bot.get_partial_messageable(self.channel_id), id=self.request_id
            )
        return self._request

    async def get_context(self, bot: commands.Bot) -> commands.Context:
        if self._context is None:
            c = bot.get_partial_messageable(self.channel_id)
            if c is None:
                c = await bot.fetch_channel(self.channel_id)
            if not isinstance(c, discord.abc.Messageable):
                raise RuntimeError(
                    f"Failed to get context (reminder is not in a text channel). {self}"
                )
            m = None
            if self.interaction:
                if self.response_id:
                    m = await c.fetch_message(self.response_id)
                else:
                    raise RuntimeError(
                        f"Can't find message corresponding to reminder interaction. {self}"
                    )
            else:
                m = await c.fetch_message(self.request_id)
            self._context = await bot.get_context(m)
        return self._context

    async def get_targets(self, bot: commands.Bot) -> list[discord.User]:
        users = []
        for tid in self.target_ids:
            u = bot.get_user(tid)
            if u is None:
                try:
                    u = await bot.fetch_user(tid)
                except (discord.NotFound, discord.HTTPException):
                    log.error("Failed to fetch user object for target id.")
            users.append(u)
        return users

    def get_response(self, bot: commands.Bot) -> discord.PartialMessage | None:
        if self.response_id is None:
            return None
        return discord.PartialMessage(
            channel=bot.get_partial_messageable(self.channel_id), id=self.response_id
        )

    async def send(self, bot: commands.Bot):
        log.info(f"Reminder firing: {self}")
        mentions = await self.target_mentions(bot)
        decorated = mentions + "\nReminder: " + self.text
        ctx = bot.get_partial_messageable(self.channel_id)
        try:
            ctx = await self.get_context(bot)
        except RuntimeError:
            log.error(
                "Missing context for reminder notice. Attempting to reply in channel."
            )
        await reply(ctx, decorated)

    def should_send(self):
        return self.time < (
            datetime.now(tz=self.time.tzinfo)
            + timedelta(seconds=CHECK_INTERVAL_SECONDS)
        )

    async def target_mentions(self, bot: commands.Bot):
        return " ".join((usr.mention for usr in await self.get_targets(bot)))

    def was_authored_by(self, user: discord.User | discord.Member) -> bool:
        return self.author_id is user.id

    def is_user_involved(self, user: discord.User | discord.Member) -> bool:
        return self.was_authored_by(user) or (user.id in self.target_ids)

    def delta_from_creation(self, bot: commands.Bot) -> timedelta:
        return self.time - self.get_request(bot).created_at.replace(microsecond=0)


def short_format_time(time: datetime):
    return f"{time:%a, %x, %H:%M %Z}"


def contains_am_or_pm(timestr: str):
    timestr = timestr.upper()
    return timestr.find("AM") >= 0 or timestr.find("PM") >= 0


def too_far_in_past(time: datetime):
    return time < (
        datetime.now(tz=time.tzinfo) - timedelta(seconds=CHECK_INTERVAL_SECONDS)
    )


def _get_button_id_add(entry_id: int):
    return REMIND_BUTTON_ID_ADD + ":" + str(entry_id)


def _get_button_id_remove(entry_id: int):
    return REMIND_BUTTON_ID_REMOVE + ":" + str(entry_id)


class Reminder(BaseCog):

    REMINDER_STORAGE_KEY = "remind"
    REMINDER_COUNTER_STORAGE_KEY = "remind_count"

    def __init__(self, bot) -> None:
        super().__init__(bot)
        self.reminders: dict[int, RemindEntry] = {}
        self.next_id: int = 1

        swap_hybrid_command_description(self.remind)
        swap_hybrid_command_description(self.remlist)
        swap_hybrid_command_description(self.remcancel)

    def cog_load(self) -> None:
        self.load_stored_reminders()

        for id in self.reminders.keys():
            self.bot.add_view(ReminderView(self, id))

        self.reminder_loop.start()

    def cog_unload(self) -> None:
        self.reminder_loop.cancel()

    @tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
    async def reminder_loop(self):
        done = []
        for id, entry in self.reminders.items():
            if entry.should_send():
                await entry.send(self.bot)
                response = entry.get_response(self.bot)
                if response:
                    await response.edit(
                        content=self.reminder_set_message(id), view=None
                    )
                done.append(id)
        for id in done:
            self.cancel(id)

    @reminder_loop.before_loop
    async def bot_wait_reminder_loop(self):
        await self.bot.wait_until_ready()

    def load_stored_reminders(self):
        try:
            self.reminders = self.bot.get_storage().get(Reminder.REMINDER_STORAGE_KEY)
            self.next_id = self.bot.get_storage().get(
                Reminder.REMINDER_COUNTER_STORAGE_KEY
            )
        except KeyError as e:
            log.error(f"No reminder data found in storage.", e)

    def update_storage(self):
        self.bot.get_storage().set(Reminder.REMINDER_STORAGE_KEY, self.reminders)
        self.bot.get_storage().set(Reminder.REMINDER_COUNTER_STORAGE_KEY, self.next_id)

    def add_to_reminder(
        self, entry_id: int, user: discord.User | discord.Member
    ) -> None:
        if entry_id not in self.reminders:
            raise ValueError(f"The specified reminder isn't valid (#{entry_id}).")
        if user.id in self.reminders[entry_id].target_ids:
            raise ValueError(f"Already included in the reminder.")
        self.reminders[entry_id].target_ids.append(user.id)

    def remove_from_reminder(
        self, entry_id: int, user: discord.User | discord.Member
    ) -> None:
        if entry_id not in self.reminders:
            raise ValueError(f"The specified reminder isn't valid (#{entry_id}).")
        self.reminders[entry_id].target_ids.remove(user.id)

    def reminder_set_message(self, entry_id: int):
        if entry_id not in self.reminders:
            return f"Reminder #{entry_id} not found."
        entry = self.reminders[entry_id]
        return f"Reminder #{entry_id} set for {short_format_time(entry.time)}. (in {entry.delta_from_creation(self.bot)})"

    def _add_reminder(self, entry_id: int, entry: RemindEntry):
        self.reminders[entry_id] = entry
        self.update_storage()

    def cancel(self, entry_id: int):
        cancelled = self.reminders.pop(entry_id)
        self.update_storage()
        return cancelled

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

    @commands.hybrid_command(
        aliases=["rem"],
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
                    too_far_in_past(closer_time)
                    and closer_time.hour < 12
                    and not contains_am_or_pm(time)
                ):
                    closer_time = closer_time + timedelta(hours=12)
                    detail_message = f" (assuming 12-hour-clock PM time)"

        # if ambiguous, use least-far time still in the future
        if (
            time_ambiguous
            and closer_time is not None
            and not too_far_in_past(closer_time)
            and closer_time < parsed_time
        ):
            parsed_time = closer_time
            detail_message += f" (assuming today rather than tomorrow)"

        # fail if more than 1 minute in the past
        if too_far_in_past(parsed_time):
            await reply(
                ctx,
                f"Time ({short_format_time(parsed_time)}) is in the past!"
                + detail_message,
            )
            return

        log.info(f"setting reminder for time: {short_format_time(parsed_time)}")
        parsed_time = parsed_time.replace(microsecond=0)
        entry = RemindEntry(
            text=text, time=parsed_time, context=ctx, targets=[ctx.author]
        )
        self._add_reminder(entry_id, entry)
        response = await reply(
            ctx,
            f"{self.reminder_set_message(entry_id)}{detail_message}",
            view=ReminderView(self, entry_id),
        )
        if response:
            entry.response_id = response.id

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
                to_join.append(f"#{id}: {await entry.describe(self.bot)}")
        if len(to_join) == 0:
            await reply(ctx, "You have no pending reminders.")
        else:
            await reply(ctx, "\n".join(to_join))

    @commands.hybrid_command(
        brief="Cancel a reminder",
        description=f"""
    __**remcancel**__
    Cancel a reminder.
    If you have only a single reminder set, this will cancel it when ID is omitted.
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
            await reply(ctx, f"Cancelled reminder: {await re.describe(self.bot)}")
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
            response = re.get_response(self.bot)
            if response:
                await response.edit(content="Reminder cancelled.", view=None)
            await reply(ctx, f"Cancelled reminder: {await re.describe(self.bot)}")


class ReminderMeTooButton(discord.ui.Button):
    def __init__(self, cog: Reminder, entry_id: int, parent: discord.ui.View):
        self.rcog = cog
        self.entry_id = entry_id
        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=REMIND_BUTTON_TEXT_ADD,
            custom_id=_get_button_id_add(entry_id),
        )

    async def callback(self, interaction: discord.Interaction):
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
            + await self.rcog.reminders[self.entry_id].target_mentions(self.rcog.bot)
        )
        await interaction.response.edit_message(content=content)


class ReminderRemoveMeButton(discord.ui.Button):
    def __init__(self, cog: Reminder, entry_id: int, parent: discord.ui.View):
        self.rcog = cog
        self.entry_id = entry_id
        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=REMIND_BUTTON_TEXT_REMOVE,
            custom_id=_get_button_id_remove(entry_id),
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            self.rcog.remove_from_reminder(
                entry_id=self.entry_id, user=interaction.user
            )
        except ValueError as err:
            await interaction.response.send_message(
                f"Sorry, can't remove you: {err}", ephemeral=True
            )
            return

        if len(self.rcog.reminders[self.entry_id].target_ids) == 0:
            # cancel the reminder if there are no targets remaining
            self.rcog.cancel(self.entry_id)
            await interaction.response.edit_message(
                content="Reminder cancelled (nobody to remind).", view=None
            )
            return

        content = (
            self.rcog.reminder_set_message(self.entry_id)
            + " "
            + await self.rcog.reminders[self.entry_id].target_mentions(self.rcog.bot)
        )
        await interaction.response.edit_message(content=content)


class ReminderView(discord.ui.View):
    def __init__(self, cog: Reminder, entry_id: int):
        self.rcog = cog
        self.entry_id = entry_id
        super().__init__(timeout=None)
        self.add_item(ReminderMeTooButton(cog, entry_id, self))
        self.add_item(ReminderRemoveMeButton(cog, entry_id, self))
