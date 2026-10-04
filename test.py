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

API_KEY = "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"
client = openai.OpenAI(api_key=API_KEY)


response = client.responses.create(
    model="gpt-4.1-mini",
    input="Hello, world!",
)

print(response.output_text)