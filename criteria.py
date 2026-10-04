import os

import openai
from dotenv import load_dotenv

load_dotenv()


API_KEY = os.environ.get("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing from the environment or .env file.")
client = openai.OpenAI(api_key=API_KEY)


response = client.responses.create(
    model="gpt-4.1-mini",
    input="Hello, world!",
)

print(response.output_text)