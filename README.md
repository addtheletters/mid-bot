# mid-bot

mid-bot is a barebones discord bot that can roll dice and shrug profusely.

New published releases are automatically deployed to an OCP instance by a Github workflow.

Run the bot locally:
- Install the dependencies listed in `requirements.txt`. (`pip install -r requirements.txt`)
- Set environment variable `DISCORD_TOKEN` to your bot API token. A `.env` file with the line `DISCORD_TOKEN=your.token.here` will work.
- Run `./run_bot.sh`.

This bot relies on:
- [python3](https://www.python.org/)
- [discord.py](https://discordpy.readthedocs.io/en/latest/)
- [python-dotenv](https://saurabh-kumar.com/python-dotenv/)
- [Pebble](https://pypi.org/project/Pebble/)
- [dateparser](https://dateparser.readthedocs.io/en/latest/)
- [aiohttp](https://docs.aiohttp.org/en/stable/)
- [OpenAI](https://github.com/openai/openai-python)
