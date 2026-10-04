import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "_core.settings")

import django

django.setup()

from job_application.models import Job
from workflow1.utils import get_resume


def main():
    job = Job.objects.order_by("id").first()
    if not job:
        print("No jobs found in the database.")
        return

    application = job.applications.order_by("id").first()
    if not application:
        print(f"No applications found for job: {job.title}")
        return

    resume = get_resume(application)
    print(f"Job: {job.title}")
    print(f"Application ID: {application.id}")
    print(f"Applicant: {application.applicant_name}")

    if resume is None:
        print("No PDF resume found for this application.")
        return

    print(f"Resume file name: {resume.name}")
    print(f"Resume exists: {resume.storage.exists(resume.name)}")
    print(f"Resume URL: {getattr(resume, 'url', 'N/A')}")


if __name__ == "__main__":
    main()
