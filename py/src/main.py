# Run the bot client.
import logging
import os

import cmds
from bongo import bongo
from client import MidClient
from cogs.artificial_cog import Intelligence
from cogs.cards_cog import Cards
from cogs.deafen_cog import Deafener
from cogs.dice_cog import DiceRoller
from cogs.maintenance_cog import Maintenance
from cogs.remind_cog import Reminder
from dotenv import load_dotenv

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Apply environment variables from a `.env` file, if present.
load_dotenv()
# Get the discord token from the environment.
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if DISCORD_TOKEN == None:
    log.error("Discord token is missing! Set the DISCORD_TOKEN environment variable.")
    exit()

if __name__ == "__main__":
    log.info("Starting bot...")
    client = MidClient(
        misc_commands=[cmds.echo, cmds.shrug, cmds.eject, bongo],
        misc_cogs=[Intelligence, Cards, Deafener, DiceRoller, Maintenance, Reminder],
    )
    client.run(DISCORD_TOKEN)
    log.info("Bot stopped running.")
