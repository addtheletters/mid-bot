import logging
import os

import openai
from dotenv import load_dotenv

log = logging.getLogger(__name__)


def list_models():
    models = openai.Model.list()
    print(models)

if __name__ == "__main__":
    # openai library should already grab this from the environment
    def load_openai_key():
        load_dotenv()
        env_api_key = os.getenv("OPENAI_API_KEY")
        if env_api_key:
            openai.api_key = env_api_key
        else:
            log.warning("OpenAI API key not found!")

    load_openai_key()


    previous = ""
    while True:
        intext = input()
        if len(intext) == 0:
            intext = previous
        completion = openai.Completion.create(model="text-davinci-003", prompt=intext)
        previous = completion.choices[0].text
        print(previous)  # type: ignore

