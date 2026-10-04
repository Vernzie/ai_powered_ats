import json
from functools import wraps

import openai
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Exists, Max, OuterRef, Q
from django.http import Http404, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from job_application.models import Application, Criterion, Job, Requirement
from users.models import UserProfile

from .models import ScreeningCriterionResult, ScreeningResult
from .services import persist_screening_result as _persist_screening_result

try:
    from screening import screen_application as _screen_application
    from screening import stream_screening as _stream_screening
except ImportError:
    _screen_application = None
    _stream_screening = None


def stream_screening(job_obj, application_ids=None, max_workers=5):
    if _stream_screening is not None:
        return _stream_screening(job_obj, application_ids=application_ids, max_workers=max_workers)
    return []


def _is_admin(user):
    if user.is_superuser:
        return True
    profile = UserProfile.objects.filter(user=user).first()
    return profile is not None and profile.role == UserProfile.Role.ADMIN


def admin_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not _is_admin(request.user):
            raise Http404
        return view(request, *args, **kwargs)

    return wrapped


@admin_required
def screen_applications(request):
    has_reviewable_application = Application.objects.filter(
        job_id=OuterRef('pk'),
    ).exclude(status=Application.Status.SHORTLISTED)
    jobs = (
        Job.objects
        .annotate(
            application_count=Count(
                'applications',
                filter=~Q(applications__status=Application.Status.SHORTLISTED),
                distinct=True,
            ),
            has_reviewable_application=Exists(has_reviewable_application),
        )
        .filter(has_reviewable_application=True)
        .order_by('-posted_date')
    )
    recent_jobs = (
        Job.objects
        .filter(applications__screening_result__isnull=False)
        .annotate(
            latest_screened_at=Max('applications__screening_result__created_at'),
            application_count=Count('applications', distinct=True),
        )
        .order_by('-latest_screened_at')
        .distinct()
    )
    return render(request, 'dashboard/screening/index.html', {
        'jobs': jobs,
        'recent_jobs': recent_jobs,
    })


@admin_required
def job_screening(request, job_id):
    job = get_object_or_404(
        Job.objects.prefetch_related('criteria__requirements'),
        pk=job_id,
    )

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_criterion':
            criterion_name = (request.POST.get('criterion_name') or '').strip()
            requirement_text = (request.POST.get('requirement_text') or '').strip()

            if criterion_name:
                criterion, _ = Criterion.objects.get_or_create(job=job, name=criterion_name)
                if requirement_text:
                    Requirement.objects.create(
                        criterion=criterion,
                        description=requirement_text,
                        required=True,
                    )

            return redirect('dashboard_review_job', job_id=job.pk)

        if action == 'update_application_status':
            application = get_object_or_404(
                Application,
                pk=request.POST.get('application_id'),
                job=job,
            )
            status = request.POST.get('status')
            if status in Application.Status.values:
                application.status = status
                application.save(update_fields=['status'])
                messages.success(request, 'Application status updated.')
            else:
                messages.error(request, 'Choose a valid application status.')
            return redirect('dashboard_review_job', job_id=job.pk)

        if action == 'edit_criterion':
            criterion_id = request.POST.get('criterion_id')
            criterion = get_object_or_404(Criterion, pk=criterion_id, job=job)
            criterion_name = (request.POST.get('criterion_name') or '').strip()
            requirement_text = (request.POST.get('requirement_text') or '').strip()

            if criterion_name:
                criterion.name = criterion_name
                criterion.save()

            requirement_lines = [
                line.strip()
                for line in requirement_text.splitlines()
                if line.strip()
            ]

            existing_requirements = list(criterion.requirements.all())
            for index, requirement in enumerate(existing_requirements):
                if index < len(requirement_lines):
                    requirement.description = requirement_lines[index]
                    requirement.save()
                else:
                    requirement.delete()

            for description in requirement_lines[len(existing_requirements):]:
                Requirement.objects.create(
                    criterion=criterion,
                    description=description,
                    required=True,
                )

            return redirect('dashboard_review_job', job_id=job.pk)

        if action == 'delete_criterion':
            criterion_id = request.POST.get('criterion_id')
            criterion = get_object_or_404(Criterion, pk=criterion_id, job=job)
            criterion.delete()
            return redirect('dashboard_review_job', job_id=job.pk)

    applications = Application.objects.filter(
        job=job,
    ).exclude(
        status__in=(
            Application.Status.SHORTLISTED,
            Application.Status.INTERVIEWED,
        ),
    ).select_related('user').prefetch_related('screening_result').order_by('-applied_date')
    recent_screenings = ScreeningResult.objects.filter(
        application__job=job
    ).select_related('application').order_by('-created_at')[:10]
    selected_application = applications.filter(
        pk=request.GET.get('application')
    ).first() or applications.first()
    return render(request, 'dashboard/screening/job.html', {
        'job': job,
        'applications': applications,
        'selected_application': selected_application,
        'recent_screenings': recent_screenings,
        'status_choices': Application.Status.choices,
    })


@admin_required
def job_screening_results(request, job_id):
    job = get_object_or_404(
        Job.objects.prefetch_related('criteria__requirements'),
        pk=job_id,
    )

    applications = Application.objects.filter(job=job).order_by('-applied_date')
    screened_results = []
    for application in applications:
        try:
            screening = application.screening_result
        except ScreeningResult.DoesNotExist:
            screened_results.append({
                'application_id': application.pk,
                'applicant_name': application.applicant_name,
                'overall_score': None,
                'overall_comments': None,
                'criteria': [],
                'status': application.status,
                'pending': application.status == Application.Status.RECEIVED,
            })
            continue

        screened_results.append({
            'application_id': application.pk,
            'applicant_name': application.applicant_name,
            'overall_score': screening.overall_score,
            'overall_comments': screening.overall_comments,
            'criteria': [
                {
                    'requirement_id': item.requirement_id,
                    'assessment': item.assessment,
                    'score': item.score,
                    'evidence': item.evidence,
                }
                for item in screening.criteria.select_related('requirement').all()
            ],
            'status': application.status,
            'pending': False,
        })

    return render(request, 'dashboard/screening/screen_results.html', {
        'job': job,
        'screened_results': json.dumps(screened_results),
        'total_screened': len(screened_results),
    })


@admin_required
def job_screening_results_data(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    applications = Application.objects.filter(job=job).order_by('-applied_date')
    screened_results = []
    for application in applications:
        try:
            screening = application.screening_result
        except ScreeningResult.DoesNotExist:
            screened_results.append({
                'application_id': application.pk,
                'applicant_name': application.applicant_name,
                'overall_score': None,
                'overall_comments': None,
                'criteria': [],
                'status': application.status,
                'pending': application.status == Application.Status.RECEIVED,
            })
            continue

        screened_results.append({
            'application_id': application.pk,
            'applicant_name': application.applicant_name,
            'overall_score': screening.overall_score,
            'overall_comments': screening.overall_comments,
            'criteria': [
                {
                    'requirement_id': item.requirement_id,
                    'assessment': item.assessment,
                    'score': item.score,
                    'evidence': item.evidence,
                }
                for item in screening.criteria.select_related('requirement').all()
            ],
            'status': application.status,
            'pending': False,
        })

    return JsonResponse({'results': screened_results})


@admin_required
def application_screening_result(request, job_id, application_id):
    application = get_object_or_404(
        Application.objects.select_related('screening_result'),
        pk=application_id,
        job_id=job_id,
    )
    try:
        screening = application.screening_result
    except ScreeningResult.DoesNotExist:
        return JsonResponse({'screening': None})
    criteria = screening.criteria.select_related('requirement').all()
    return JsonResponse({
        'screening': {
            'overall_score': screening.overall_score,
            'overall_comments': screening.overall_comments,
            'criteria': [
                {
                    'requirement_id': item.requirement_id,
                    'requirement': item.requirement.description,
                    'assessment': item.assessment,
                    'score': item.score,
                    'evidence': item.evidence,
                }
                for item in criteria
            ],
        }
    })


@admin_required
@require_POST
def screen_application(request, application_id):
    application = get_object_or_404(
        Application.objects.select_related('job__workflow'),
        pk=application_id,
    )
    if application.status not in (
        Application.Status.RECEIVED,
        Application.Status.SCREENED,
        Application.Status.SHORTLISTED,
        Application.Status.REJECTED,
    ):
        return JsonResponse({'error': 'Only received, screened, or rejected applications can be screened.'}, status=409)
    if not application.resume or not application.resume.storage.exists(application.resume.name):
        return JsonResponse({'error': 'The resume file is missing. Re-upload the resume before screening this application.'}, status=400)

    requirements = list(
        Requirement.objects.filter(criterion__job=application.job)
        .select_related('criterion')
        .order_by('id')
    )
    if not requirements:
        return JsonResponse({'error': 'Add at least one criterion requirement before screening.'}, status=400)
    if _screen_application is None:
        return JsonResponse({'error': 'The AI screening service is unavailable.'}, status=503)

    try:
        result = _screen_application(application, requirements)
        if request.GET.get('preview') == '1':
            return JsonResponse({
                'application_id': application.pk,
                'applicant_name': application.applicant_name,
                'score': result['screening']['overall_score'],
                'screening_comments': result['screening']['overall_comments'],
                'criteria_results': result['screening']['criteria'],
                'file_id': result.get('file_id'),
            })
        with transaction.atomic():
            _persist_screening_result(
                application.job,
                result,
                reviewed_by=request.user,
                review_method=ScreeningResult.ReviewMethod.AI,
                status=Application.Status.SCREENED,
            )
    except RuntimeError as error:
        return JsonResponse({'error': str(error)}, status=503)
    except (KeyError, OSError, TypeError, ValueError, openai.APIError) as error:
        return JsonResponse({'error': str(error)}, status=502)

    application.refresh_from_db()
    return JsonResponse({
        'application_id': application.pk,
        'applicant_name': application.applicant_name,
        'status': application.status,
        'status_label': application.get_status_display(),
        'score': result['screening']['overall_score'],
        'screening_comments': result['screening']['overall_comments'],
        'criteria_results': result['screening']['criteria'],
    })


@admin_required
@require_POST
def stream_screening_job(request, job_id):
    try:
        payload = json.loads(request.body or '{}')
        application_ids = [int(value) for value in payload.get('application_ids', [])]
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'Invalid screening request.'}, status=400)

    job = get_object_or_404(Job, pk=job_id)
    if not Requirement.objects.filter(criterion__job=job).exists():
        return JsonResponse({'error': 'Add at least one criterion and requirement before screening.'}, status=400)

    valid_ids = set(
        Application.objects.filter(
            job=job,
            status__in=(
                Application.Status.RECEIVED,
                Application.Status.SCREENED,
                Application.Status.REJECTED,
            ),
            id__in=application_ids,
        ).values_list('id', flat=True)
    )
    if not valid_ids:
        return JsonResponse({'results': []})

    def event_stream():
        try:
            for event in stream_screening(job, application_ids=valid_ids):
                event_type = event.get('type')
                if event_type == 'candidate_done':
                    result = event.get('result')
                    if result:
                        with transaction.atomic():
                            payload_result = _persist_screening_result(
                                job,
                                result,
                                reviewed_by=request.user,
                                review_method=ScreeningResult.ReviewMethod.AI,
                            )
                        yield json.dumps({'type': 'candidate_done', 'application_id': result['application_id'], 'result': payload_result}) + '\n'
                        continue
                if event_type == 'all_done':
                    yield json.dumps({'type': 'all_done', 'results': []}) + '\n'
                    continue
                yield json.dumps(event) + '\n'
        except (KeyError, OSError, TypeError, ValueError, openai.APIError) as error:
            yield json.dumps({'type': 'error', 'error': str(error)}) + '\n'

    return StreamingHttpResponse(event_stream(), content_type='application/x-ndjson')


@admin_required
@require_POST
def run_screening(request):
    try:
        payload = json.loads(request.body or '{}')
        job_id = payload.get('job_id')
        application_ids = [int(value) for value in payload.get('application_ids', [])]
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'Invalid screening request.'}, status=400)

    job = get_object_or_404(Job, pk=job_id)
    if not Requirement.objects.filter(criterion__job=job).exists():
        return JsonResponse({'error': 'Add at least one criterion and requirement before screening.'}, status=400)

    valid_ids = set(
        Application.objects.filter(
            job=job,
            status__in=(
                Application.Status.RECEIVED,
                Application.Status.SCREENED,
                Application.Status.REJECTED,
            ),
            id__in=application_ids,
        ).values_list('id', flat=True)
    )
    if not valid_ids:
        return JsonResponse({'results': []})

    try:
        from screening import screen_applications as run_screening_for_job
        results = run_screening_for_job(job, application_ids=valid_ids)
    except (KeyError, OSError, TypeError, ValueError, openai.APIError) as error:
        return JsonResponse({'error': str(error)}, status=502)

    response_results = []
    with transaction.atomic():
        for result in results:
            response_results.append(_persist_screening_result(
                job,
                result,
                reviewed_by=request.user,
                review_method=ScreeningResult.ReviewMethod.AI,
            ))

    return JsonResponse({'results': response_results})