from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from job_application.models import Application, Requirement

from .models import ScreeningCriterionResult, ScreeningResult

AI_REVIEWER_USERNAME = 'ai-screening'


def persist_screening_result(
    job,
    result,
    *,
    reviewed_by=None,
    review_method=ScreeningResult.ReviewMethod.AI,
    status=None,
):
    screening_data = result['screening']
    if review_method == ScreeningResult.ReviewMethod.AI:
        reviewed_by = get_user_model().objects.get(username=AI_REVIEWER_USERNAME)
    application = get_object_or_404(Application, pk=result['application_id'], job=job)
    requirement_map = {
        requirement.id: requirement
        for requirement in Requirement.objects.filter(criterion__job=job)
    }
    screening_result, _ = ScreeningResult.objects.update_or_create(
        application=application,
        defaults={
            'file_id': result.get('file_id'),
            'overall_score': screening_data['overall_score'],
            'overall_comments': screening_data['overall_comments'],
            'review_method': review_method,
            'reviewed_by': reviewed_by,
        },
    )
    ScreeningCriterionResult.objects.filter(screening=screening_result).delete()
    for criterion_result in screening_data['criteria']:
        requirement = requirement_map.get(criterion_result['requirement_id'])
        if requirement:
            ScreeningCriterionResult.objects.create(
                screening=screening_result,
                requirement=requirement,
                assessment=criterion_result['assessment'],
                score=criterion_result['score'],
                evidence=criterion_result.get('evidence', ''),
            )

    if status is None:
        if job.workflow and job.workflow.slug.lower() == 'auto':
            threshold = job.screening_threshold if job.screening_threshold is not None else 70
            status = (
                Application.Status.SHORTLISTED
                if screening_data['overall_score'] >= threshold
                else Application.Status.SCREENED
            )
        else:
            status = Application.Status.SCREENED
    application.status = status
    application.save(update_fields=['status'])
    return {
        'application_id': application.id,
        'applicant_name': application.applicant_name,
        'overall_score': screening_data['overall_score'],
        'overall_comments': screening_data['overall_comments'],
        'criteria': screening_data['criteria'],
    }
