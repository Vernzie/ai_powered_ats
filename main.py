import os

import openai
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "_core.settings")

import django

django.setup()

from openai import OpenAI
from django.utils import timezone

from job_application.models import Application, Job, Requirement, Criterion

API_KEY = "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"
client = openai.OpenAI(api_key=API_KEY)
from screening import screen_applications
# ============================================================
# GET JOB
# ============================================================

jobs = Job.objects.all()

hr_job = jobs.last()

results = screen_applications(hr_job)
from pprint import pprint

for result in results:
    pprint(result)
    

