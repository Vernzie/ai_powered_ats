import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "_core.settings")

import django
import openai

django.setup()

from job_application.models import Application, Criterion, Job, Requirement

API_KEY = os.environ.get("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing from the environment or .env file.")
client = openai.OpenAI(api_key=API_KEY)


response = client.responses.create(
    model="gpt-4.1-mini",
    input="Hello, world!",
)

print(response.output_text)