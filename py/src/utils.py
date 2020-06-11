# Utility functions
import discord

# Log message contents
def print_message(msg):
    print(f"({msg.id}) {msg.created_at.isoformat(timespec='milliseconds')} [{msg.channel}] <{msg.author}> {msg.content}")

# Send `text` in response to `msg`.
async def reply(msg, text):
    await msg.channel.send(f"{msg.author.mention} {text}")
