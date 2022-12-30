# Commands for fetching random images from external APIs.
# The name comes from its inspiration, a bot known as Böngo Cat.
import logging

import aiohttp
import discord
from discord.ext import commands
from utils import *

log = logging.getLogger(__name__)


RANDOM_CAT_ENDPOINT = "https://aws.random.cat/meow"
RANDOM_DUCK_ENDPOINT = "https://random-d.uk/api/v2/random"
RANDOM_FOX_ENDPOINT = "https://randomfox.ca/floof/"
DOG_CEO_ENDPOINT = "https://dog.ceo/api/breeds/image/random"
BUNNIES_IO_ENDPOINT = "https://api.bunnies.io/v2/loop/random/?media=gif"
SHIBE_ONLINE_ENDPOINT = "https://shibe.online/api/shibes?count=1"
SRA_PREFIX = "https://some-random-api.ml/"
SRA_BIRD_ENDPOINT = SRA_PREFIX + "animal/bird"

SRA_ANIMALS = [
    "bird",
    "cat",
    "dog",
    "fox",
    "kangaroo",
    "koala",
    "panda",
    "raccoon",
    "red_panda",
]


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


# Returns json as dict, raises ConnectionError if unsuccessful.
async def request_json(endpoint: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(endpoint) as response:
            json = await response.json()
            if bad_status(response.status):
                raise ConnectionError(f"API request failed ({response.status}): {json}")
            return json


async def fetch_random_cat(title: str) -> discord.Embed:
    re_json = await request_json(RANDOM_CAT_ENDPOINT)
    return image_embed(title=title, img_url=re_json["file"])


async def fetch_random_duck(title: str) -> discord.Embed:
    re_json = await request_json(RANDOM_DUCK_ENDPOINT)
    return image_embed(title=title, img_url=re_json["url"])


async def fetch_random_fox(title: str) -> discord.Embed:
    re_json = await request_json(RANDOM_FOX_ENDPOINT)
    return image_embed(title=title, img_url=re_json["image"], link=re_json["link"])


async def fetch_dog_ceo(title: str) -> discord.Embed:
    re_json = await request_json(DOG_CEO_ENDPOINT)
    return image_embed(title=title, img_url=re_json["message"])


async def fetch_bunnies_io(title: str) -> discord.Embed:
    re_json = await request_json(BUNNIES_IO_ENDPOINT)
    return image_embed(title=title, img_url=re_json["media"]["gif"])


async def fetch_shibe_online(title: str) -> discord.Embed:
    re_json = await request_json(SHIBE_ONLINE_ENDPOINT)
    return image_embed(title=title, img_url=re_json[0])


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
    embed = await fetch_random_cat("Cat.")
    await reply(ctx, embed=embed)


@bongo.command()
async def duck(ctx: commands.Context):
    embed = await fetch_random_duck("Quack.")
    await reply(ctx, embed=embed)


@bongo.command()
async def fox(ctx: commands.Context):
    embed = await fetch_random_fox("fox")
    await reply(ctx, embed=embed)


@bongo.command()
async def dog(ctx: commands.Context):
    embed = await fetch_dog_ceo("Dog...")
    await reply(ctx, embed=embed)


@bongo.command()
async def bunny(ctx: commands.Context):
    embed = await fetch_bunnies_io("bun")
    await reply(ctx, embed=embed)


@bongo.command()
async def shibe(ctx: commands.Context):
    embed = await fetch_shibe_online("shibe is a meme word for shiba inu")
    await reply(ctx, embed=embed)


@bongo.command()
async def bird(ctx: commands.Context):
    embed = await fetch_some_random("Bird!", SRA_BIRD_ENDPOINT)
    await reply(ctx, embed=embed)


@bongo.command()
async def sranimal(ctx: commands.Context, animal: str):
    if animal not in SRA_ANIMALS:
        await reply(ctx, "Sorry, the API doesn't have that animal.")
        return
    embed = await fetch_some_random(
        f"Some Random API: {animal}", SRA_PREFIX + "animal/" + animal
    )
    await reply(ctx, embed=embed)


@sranimal.autocomplete("animal")
async def sranimal_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    return [
        discord.app_commands.Choice(name=animal, value=animal)
        for animal in SRA_ANIMALS
        if current.lower() in animal.lower()
    ]
