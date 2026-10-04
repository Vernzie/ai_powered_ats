import json
import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "_core.settings")

import django
import openai
from pypdf import PdfReader

django.setup()

from job_application.models import Application, Criterion, Job, Requirement

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise RuntimeError('Set OPENAI_API_KEY before running AI screening.')
        _client = openai.OpenAI(api_key=api_key)
    return _client


def _get_requirements(job_obj):
    return list(
        Requirement.objects.filter(criterion__job=job_obj)
        .select_related('criterion')
        .order_by('id')
    )


def _build_requirement_schema():
    return {
        'type': 'object',
        'properties': {
            'requirement_id': {'type': 'integer'},
            'assessment': {'type': 'string', 'enum': ['meets', 'does_not_meet', 'partially_demonstrated', 'not_demonstrated']},
            'score': {'type': 'integer', 'minimum': 0, 'maximum': 100},
            'evidence': {'type': 'string'},
        },
        'required': ['requirement_id', 'assessment', 'score', 'evidence'],
        'additionalProperties': False,
    }


def _build_application_schema():
    return {
        'type': 'object',
        'properties': {
            'overall_comments': {'type': 'string'},
            'criteria': {
                'type': 'array',
                'items': _build_requirement_schema(),
            },
        },
        'required': ['overall_comments', 'criteria'],
        'additionalProperties': False,
    }


def _extract_resume_text(resume_path):
    try:
        file_path = Path(resume_path)
        if not file_path.exists():
            return ''

        try:
            reader = PdfReader(str(file_path))
            pages = []
            for page in reader.pages:
                text = page.extract_text() or ''
                if text:
                    pages.append(text)
            combined = '\n'.join(pages).strip()
            if combined:
                return combined[:20000]
        except Exception:
            pass

        raw = file_path.read_bytes()
        try:
            return raw.decode('utf-8', errors='strict')[:20000].strip()
        except UnicodeDecodeError:
            return raw.decode('latin-1', errors='ignore')[:20000].strip()
    except OSError:
        return ''


def screen_application(application, requirements=None):
    if not application.resume:
        raise ValueError('This application does not have a resume to screen.')

    requirements = list(requirements if requirements is not None else _get_requirements(application.job))
    if not requirements:
        raise ValueError('Add at least one criterion requirement before screening.')

    resume_path = application.resume.path
    resume_text = _extract_resume_text(resume_path)
    uploaded_file = None
    upload_error = None
    try:
        with open(resume_path, 'rb') as resume_file:
            uploaded_file = _get_client().files.create(file=resume_file, purpose='user_data')
    except (OSError, openai.APIError) as error:
        upload_error = error

    if uploaded_file is None and not resume_text:
        raise RuntimeError('The resume could not be read or uploaded for screening.') from upload_error

    requirements_payload = [
        {
            'requirement_id': requirement.id,
            'criterion': requirement.criterion.name,
            'description': requirement.description,
            'required': requirement.required,
        }
        for requirement in requirements
    ]
    content = [{
        'type': 'input_text',
        'text': 'Evaluate this resume against every requirement below. Return each requirement_id exactly once.\n\n'
                f"JOB CRITERIA AND REQUIREMENTS:\n{json.dumps(requirements_payload, ensure_ascii=False)}",
    }]
    if uploaded_file:
        content.append({'type': 'input_file', 'file_id': uploaded_file.id})
    else:
        content.append({'type': 'input_text', 'text': f"RESUME TEXT:\n{resume_text[:20000]}"})

    response = _get_client().responses.create(
        model='gpt-4.1-mini',
        instructions="""
You are an evidence-grounded HR screening assistant. Review one candidate resume against all supplied job requirements in a single pass.

Rules:
1. Assess every supplied requirement exactly once and use its exact requirement_id.
2. Only use evidence present in the resume. Do not infer missing experience or qualifications.
3. Score each requirement from 0 to 100. Use meets, does_not_meet, partially_demonstrated, or not_demonstrated as the assessment.
4. Provide concise resume evidence for each assessment; state when evidence is absent.
5. Return concise overall_comments and the structured criteria array only.
""",
        input=[{'role': 'user', 'content': content}],
        text={
            'format': {
                'type': 'json_schema',
                'name': 'application_screening',
                'strict': True,
                'schema': _build_application_schema(),
            }
        },
    )

    payload = json.loads(response.output_text)
    criteria = payload.get('criteria')
    expected_ids = [requirement.id for requirement in requirements]
    returned_ids = [result.get('requirement_id') for result in criteria or []]
    if len(returned_ids) != len(expected_ids) or set(returned_ids) != set(expected_ids):
        raise ValueError('AI screening returned missing or duplicate requirement results.')

    scores = [max(0, min(100, int(result.get('score', 0)))) for result in criteria]
    overall_score = int(sum(scores) / len(scores)) if scores else 0
    overall_comments = str(payload.get('overall_comments') or '').strip()

    return {
        'application_id': application.id,
        'file_id': uploaded_file.id if uploaded_file else None,
        'screening': {
            'criteria': criteria,
            'overall_score': overall_score,
            'overall_comments': overall_comments,
        },
    }


def stream_screening(job_obj, application_ids=None, max_workers=5):
    max_workers = max(1, int(max_workers))
    applications = Application.objects.filter(job=job_obj)
    if application_ids is not None:
        applications = applications.filter(id__in=application_ids)
    applications = list(applications.order_by('id'))
    requirements = _get_requirements(job_obj)

    if not applications:
        yield {'type': 'all_done', 'results': []}
        return

    if not requirements:
        yield {'type': 'error', 'error': 'Add at least one criterion and requirement before screening.'}
        yield {'type': 'all_done', 'results': []}
        return

    for application in applications:
        yield {'type': 'candidate_started', 'application_id': application.id, 'applicant_name': application.applicant_name}

        try:
            final_result = screen_application(application, requirements)
            yield {'type': 'candidate_done', 'application_id': application.id, 'result': final_result}
        except Exception as exc:  # pragma: no cover - surfaced to the stream endpoint in the response
            yield {'type': 'error', 'application_id': application.id, 'error': str(exc)}

    yield {'type': 'all_done', 'results': []}


def screen_applications(job_obj, application_ids=None):
    results = []
    for event in stream_screening(job_obj, application_ids=application_ids):
        if event.get('type') == 'candidate_done':
            results.append(event['result'])
    return results