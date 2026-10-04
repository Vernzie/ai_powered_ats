"""AI interview-question generation and application question persistence helpers."""

import json
import os
from pathlib import Path

import django
from dotenv import load_dotenv
from django.db import transaction
from openai import APIError, OpenAI

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "_core.settings")
django.setup()

from interviews.models import InterviewQuestion
from job_application.models import Application

MODEL = "gpt-4.1-mini"
load_dotenv(Path(__file__).resolve().with_name(".env"))

_client = None

QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "question_type": {"type": "string", "enum": ["GENERAL", "SPECIFIC"]},
                    "weight": {"type": "integer", "minimum": 1, "maximum": 5},
                    "expected_answer": {"type": "string"},
                },
                "required": ["question", "question_type", "weight", "expected_answer"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}


def get_client():
    """Create the OpenAI client on first use so imports do not require credentials."""
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is missing from the environment or adjacent .env file.")
        _client = OpenAI(api_key=api_key)
    return _client


def upload_application_resume(application_id):
    """Upload an Interviewed application's resume and return its OpenAI file ID."""
    application = Application.objects.filter(
        pk=application_id,
        status=Application.Status.INTERVIEWED,
    ).first()
    if application is None:
        raise ValueError("The application does not exist or is not in the Interviewed stage.")
    if not application.resume or not application.resume.storage.exists(application.resume.name):
        raise ValueError("The application resume is missing.")

    try:
        with application.resume.open("rb") as resume_file:
            resume_bytes = resume_file.read()
        resume_upload = (Path(application.resume.name).name, resume_bytes)
        uploaded_file = get_client().files.create(file=resume_upload, purpose="user_data")
    except (OSError, APIError) as error:
        raise RuntimeError("The application resume could not be uploaded for question generation.") from error

    file_id = getattr(uploaded_file, "id", None)
    if not file_id:
        raise RuntimeError("The file upload did not return a file ID.")
    return file_id


def _validate_questions(questions, expected_count=None):
    if not isinstance(questions, list) or not questions:
        raise ValueError("The AI response must contain at least one question.")
    if expected_count is not None:
        if len(questions) < expected_count:
            raise ValueError(f"The AI returned {len(questions)} questions; expected at least {expected_count}.")
        questions = questions[:expected_count]

    validated = []
    for index, item in enumerate(questions, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Question {index} must be an object.")
        question = item.get("question")
        question_type = item.get("question_type")
        weight = item.get("weight")
        expected_answer = item.get("expected_answer", "")

        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"Question {index} is missing question text.")
        if question_type not in InterviewQuestion.QuestionType.values:
            raise ValueError(f"Question {index} has an invalid question type.")
        if isinstance(weight, bool) or not isinstance(weight, int) or not 1 <= weight <= 65535:
            raise ValueError(f"Question {index} weight must be an integer from 1 to 65535.")
        if not isinstance(expected_answer, str):
            raise ValueError(f"Question {index} expected_answer must be text.")

        validated.append({
            "question": question.strip(),
            "question_type": question_type,
            "weight": weight,
            "expected_answer": expected_answer.strip(),
        })
    return validated


def main(input_text, instructions, question_count=3, resume_file_id=None):
    """Ask the model for questions and return validated question dictionaries."""
    if not isinstance(input_text, str) or not input_text.strip():
        raise ValueError("Provide input text for interview-question generation.")
    if not isinstance(instructions, str) or not instructions.strip():
        raise ValueError("Provide instructions for interview-question generation.")
    if isinstance(question_count, bool) or not isinstance(question_count, int) or not 1 <= question_count <= 20:
        raise ValueError("question_count must be an integer from 1 to 20.")

    content = [{"type": "input_text", "text": input_text.strip()}]
    if resume_file_id:
        content.append({"type": "input_file", "file_id": resume_file_id})

    try:
        response = get_client().responses.create(
            model=MODEL,
            instructions=instructions.strip(),
            input=[{"role": "user", "content": content}],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "interview_questions",
                    "strict": True,
                    "schema": QUESTION_SCHEMA,
                }
            },
        )
        response_data = json.loads(response.output_text)
    except json.JSONDecodeError as error:
        raise ValueError("The AI response was not valid JSON.") from error
    except APIError as error:
        raise RuntimeError("The AI question-generation request failed.") from error

    if not isinstance(response_data, dict):
        raise ValueError("The AI response must be a JSON object.")
    return _validate_questions(response_data.get("questions"), expected_count=question_count)


def save_interview_questions(application_id, questions):
    """Validate and save a batch of questions for an Interviewed application."""
    validated_questions = _validate_questions(questions)
    application = Application.objects.filter(
        pk=application_id,
        status=Application.Status.INTERVIEWED,
    ).first()
    if application is None:
        raise ValueError("Questions can only be saved for an Interviewed application.")

    with transaction.atomic():
        saved_questions = [
            InterviewQuestion.objects.create(application=application, **question_data)
            for question_data in validated_questions
        ]
    return [
        {
            "id": question.pk,
            "application_id": question.application_id,
            "question": question.question,
            "question_type": question.question_type,
            "weight": question.weight,
            "expected_answer": question.expected_answer,
        }
        for question in saved_questions
    ]


def generate_and_save_for_application(application_id, input_text, instructions, question_count=3):
    """Upload an application's resume, generate questions, and save the validated result."""
    resume_file_id = upload_application_resume(application_id)
    questions = main(
        input_text,
        instructions,
        question_count=question_count,
        resume_file_id=resume_file_id,
    )
    return save_interview_questions(application_id, questions)


def run_sample():
    job_title = "Junior Software Developer"
    candidate_background = (
        "Recent IT graduate with academic Python projects, introductory Flask and React experience, "
        "and regular use of GitHub for version control."
    )
    prompt = f"Role: {job_title}\nCandidate background: {candidate_background}"
    instructions = (
        "Generate concise, fair interview questions grounded only in the supplied role and candidate background. "
        "Use GENERAL for broad behavioral questions and SPECIFIC for role- or experience-focused questions. "
        "Give each question an expected_answer rubric describing evidence a strong response should include. "
        "Assign an importance weight from 1 to 5. Do not invent candidate facts."
    )
    questions = main(prompt, instructions, question_count=3)
    print(json.dumps(questions, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run_sample()
