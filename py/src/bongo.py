# Commands for fetching random images from external APIs.
# The name comes from its inspiration, a bot known as Böngo Cat.
import logging
from typing import Tuple

import aiohttp
import discord
from discord.ext import commands
from utils import *

log = logging.getLogger(__name__)


RANDOM_CAT_ENDPOINT = "https://aws.random.cat/meow"
SRA_PREFIX = "https://some-random-api.ml/"
SRA_BIRD_ENDPOINT = SRA_PREFIX + "animal/bird"


def image_embed(
    title: str, img_url: str, link: str | None = None, footer_text: str | None = None
) -> discord.Embed:
    return (
        discord.Embed(title=title, url=link if link else img_url)
        .set_image(url=img_url)
        .set_footer(text=footer_text)
    )


def bad_status(status: int):
    return status < 200 or status > 299


# Returns json as dict, raises ConnectionError if unsuccessful
async def request_json(endpoint: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(endpoint) as response:
            json = await response.json()
            if bad_status(response.status):
                raise ConnectionError(f"API request failed ({response.status}): {json}")
            return json


async def fetch_api_file(title: str, endpoint: str) -> discord.Embed:
    re_json = await request_json(endpoint)
    return image_embed(title=title, img_url=re_json["file"])


async def fetch_some_random(title: str, endpoint: str) -> discord.Embed:
    re_json = await request_json(endpoint)
    return image_embed(
        title=title, img_url=re_json["image"], footer_text=re_json["fact"]
    )


@commands.hybrid_group(
    aliases=["b"],
    brief="Fetch random images",
    description=f"""
__**bongo**__
Produce random images from certain categories by calling various APIs.
""",
)
async def bongo(ctx):
    await reply(ctx, get_help_notice("bongo"))


@bongo.command()
async def cat(ctx: commands.Context):
    embed = await fetch_api_file("Cat.", RANDOM_CAT_ENDPOINT)
    await reply(ctx, embed=embed)


@bongo.command()
async def bird(ctx: commands.Context):
    embed = await fetch_some_random("Bird!", SRA_BIRD_ENDPOINT)
    await reply(ctx, embed=embed)


@bongo.command()
async def sra(ctx: commands.Context, path: str):
    embed = await fetch_some_random("Some Random API", SRA_PREFIX + path)
    await reply(ctx, embed=embed)
