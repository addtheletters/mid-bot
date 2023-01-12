# Cog for interfacing with AI tools
import logging

import artificial
import discord
import openai
from cmds import swap_hybrid_command_description
from discord.ext import commands
from utils import *

log = logging.getLogger(__name__)

OAI_DEFAULT_MODEL = "text-davinci-003"
OAI_DEFAULT_MAX_TOKENS = 300
OAI_DEFAULT_TEMPERATURE = 0.7

IMAGE_GEN_TITLE = "DALL-E"
OAI_DEFAULT_IMAGE_SIZE = "512x512"


class Intelligence(commands.Cog):
    def __init__(self, bot) -> None:
        swap_hybrid_command_description(self.complete)
        swap_hybrid_command_description(self.genimage)
        swap_hybrid_command_description(self.parameters)
        artificial.load_openai_key()
        self.completion_params = {
            "model": OAI_DEFAULT_MODEL,
            "max_tokens": OAI_DEFAULT_MAX_TOKENS,
            "temperature": OAI_DEFAULT_TEMPERATURE,
        }
        self.genimage_params = {
            "size": OAI_DEFAULT_IMAGE_SIZE,
        }

    @commands.hybrid_command(
        aliases=["gentext"],
        brief="Generate text from a prompt",
        description=f"""
    __**complete**__
    Generates text following a prompt. Uses the OpenAI API completion endpoint (GPT-3).
    Use {get_summon_prefix()}parameters to check the configuration.
    """,
    )
    async def complete(self, ctx: commands.Context, prompt: str):
        async with ctx.typing():
            response = openai.Completion.create(prompt=prompt, **self.completion_params)
        text: str = response.choices[0].text  # type: ignore
        await reply(ctx, prompt + "\n" + codeblock(text, big=True))

    @commands.hybrid_command(
        brief="Generate an image from a prompt",
        description=f"""
    __**genimage**__
    Generates an image based on a text prompt. Uses the OpenAI API image endpoint (DALL-E).
    Use {get_summon_prefix()}parameters to check the configuration.
    """,
    )
    async def genimage(self, ctx: commands.Context, prompt: str):
        async with ctx.typing():
            response = openai.Image.create(prompt=prompt, **self.genimage_params)
        result_url: str = response.data[0].url  # type: ignore
        await reply(
            ctx,
            embed=image_embed(
                title=IMAGE_GEN_TITLE, img_url=result_url, footer_text=prompt
            ),
        )

    @commands.hybrid_command(
        brief="View AI generation parameters",
        description=f"""
    __**parameters**__
    Show the parameters used by the AI generator commands.""",
    )
    async def parameters(self, ctx: commands.Context):
        output = (
            "Completion: "
            + str(self.completion_params)
            + "\n\nImage Generation: "
            + str(self.genimage_params)
        )
        output = codeblock(output, big=True)
        await reply(ctx, output)
