from django.shortcuts import render

from job_application.models import Job


def workflow_index(request):
    jobs = Job.objects.select_related('workflow').order_by('-posted_date')
    return render(request, 'workflow/index.html', {
        'auto_jobs': jobs.filter(workflow__slug='auto'),
        'manual_jobs': jobs.filter(workflow__slug='manual'),
    })
