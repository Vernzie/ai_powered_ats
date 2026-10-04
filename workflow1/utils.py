from application_screening.models import ScreeningCriterionResult, ScreeningResult
from job_application.models import Application, Criterion, Job, Requirement
from users.models import UserProfile

__all__ = [
    "Job",
    "Criterion",
    "Requirement",
    "Application",
    "UserProfile",
    "ScreeningResult",
    "ScreeningCriterionResult",
    "get_resume",
]


def get_resume(application_obj):
    """Return the submitted resume only when it is a PDF file."""
    if application_obj is None:
        return None

    resume = getattr(application_obj, "resume", None)
    if not resume:
        return None

    file_name = str(resume.name or "").lower()
    if file_name.endswith(".pdf"):
        return resume

    return None


