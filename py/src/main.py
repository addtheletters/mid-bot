# Run the bot client.
from client import MidClient
from dotenv import load_dotenv
import logging
import os

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Apply environment variables from a `.env` file, if present.
load_dotenv()
# Get the discord token from the environment.
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN == None:
    log.error("Discord token is missing!")

if __name__ == "__main__":
    log.info("Starting bot...")
    client = MidClient()
    client.run(TOKEN)
    log.info("Bot stopped running.")
else:
    log.info("Bot was not started.")
