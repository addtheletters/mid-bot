# A bot for messing around.
import os

import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

DEFAULT_ACK_EMOJI = '🤖'

class ExperimentClient(discord.Client):
    def __init__(self):
        discord.Client.__init__(self)
        self.guild_emojis = []
        self.ack_emoji = DEFAULT_ACK_EMOJI

    async def on_ready(self):
        print(f'{self.user} is now connected to Discord.')
        print(client.guilds)
        self.guild_emojis = await client.guilds[0].fetch_emojis()
        if len(self.guild_emojis) > 0:
            self.ack_emoji = self.guild_emojis[0]
        print(f'Using ack emoji {self.ack_emoji}')

    async def on_typing(self, channel, user, when):
        print(f'{when}: <{user}> is typing in [{channel}]...')

    async def on_message(self, message):
        print(f'{message.created_at}: [{message.channel}] <{message.author}> {message.content}')
        await message.add_reaction(self.ack_emoji)

if __name__ == "__main__":
    client = ExperimentClient()
    client.run(TOKEN)
