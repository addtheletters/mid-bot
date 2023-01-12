# OpenAI API interfacing.
import logging
import os

import openai
from dotenv import load_dotenv

log = logging.getLogger(__name__)


def load_openai_key():
    # openai library may already grab this from the environment
    if openai.api_key is not None:
        log.info("OpenAI API key is already loaded.")
        return
    load_dotenv()
    env_api_key = os.getenv("OPENAI_API_KEY")
    if env_api_key:
        openai.api_key = env_api_key
        log.info("Loaded OpenAI API key.")
    else:
        log.warning("OpenAI API key not found!")


def list_model_ids() -> list[str]:
    models = openai.Model.list()
    return [model.id for model in models["data"]]  # type: ignore


if __name__ == "__main__":
    load_openai_key()
    print(list_model_ids())

    bonus_params = {"max_tokens": 400, "temperature": 0.8}
    previous = ""
    while True:
        intext = input()
        if len(intext) == 0:
            intext = previous

        completion = openai.Completion.create(
            model="text-davinci-003", prompt=intext, **bonus_params
        )
        previous = completion.choices[0].text  # type: ignore
        print(previous)  # type: ignore
