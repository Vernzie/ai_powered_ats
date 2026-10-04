import json
from datetime import datetime, time, timedelta
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from job_application.models import Application, Criterion, Job, Requirement
from pipeline.models import Workflow
from users.models import UserProfile

from .forms import ApplicationManagementForm, JobForm, RequirementForm, RequirementFormSet


ATLAS_ROUTE_NAMES = {
	'dashboard': 'dashboard',
	'workspace': 'dashboard_workspace',
	'jobs': 'dashboard_jobs',
	'review': 'dashboard_review',
	'job': 'dashboard_job_page',
	'applications': 'dashboard_applications',
	'application': 'dashboard_application_page',
	'interviews': 'dashboard_interviews',
	'workflows': 'dashboard_workflows',
	'settings': 'dashboard_settings',
}


def _is_admin(user):
	if user.is_superuser:
		return True
	profile = UserProfile.objects.filter(user=user).first()
	return profile is not None and profile.role == UserProfile.Role.ADMIN


def _application_screening_result(application):
	return getattr(application, 'screening_result', None)


def admin_required(view):
	@login_required
	@wraps(view)
	def wrapped(request, *args, **kwargs):
		if not _is_admin(request.user):
			raise Http404
		return view(request, *args, **kwargs)

	return wrapped


@admin_required
def dashboard(request):
	today_start = timezone.make_aware(
		datetime.combine(timezone.localdate(), time.min),
		timezone.get_current_timezone(),
	)
	tomorrow_start = today_start + timedelta(days=1)
	active_jobs = list(
		Job.objects.filter(is_active=True)
		.select_related('workflow')
		.annotate(
			application_count=Count('applications'),
			new_application_count=Count(
				'applications',
				filter=Q(applications__status=Application.Status.RECEIVED),
			),
			shortlisted_today_count=Count(
				'applications',
				filter=Q(
					applications__status=Application.Status.SHORTLISTED,
					applications__shortlisted_at__gte=today_start,
					applications__shortlisted_at__lt=tomorrow_start,
				),
			),
		)
		.order_by('-posted_date')
	)
	return _render_atlas(request, 'dashboard', {
		'dashboard_data': {
			'activeJobCount': len(active_jobs),
			'totalApplications': Application.objects.count(),
			'activeJobs': [
				{
					'id': job.pk,
					'title': job.title,
					'url': f"{reverse('dashboard_job_page')}?id={job.pk}",
					'location': job.location,
					'workflow': job.workflow.name if job.workflow else 'Unassigned',
					'applicationCount': job.application_count,
				}
				for job in active_jobs
			],
			'automatedResults': [
				{
					'id': job.pk,
					'title': job.title,
					'newApplicationCount': job.new_application_count,
					'shortlistedTodayCount': job.shortlisted_today_count,
					'jobUrl': f"{reverse('dashboard_job_page')}?id={job.pk}",
					'workspaceUrl': reverse('dashboard_workspace_job', kwargs={'job_id': job.pk}),
				}
				for job in active_jobs
				if job.workflow and job.workflow.slug.lower() == 'auto'
				and (job.shortlisted_today_count or job.new_application_count)
			],
		},
	})


def _atlas_context(page):
	application_counts = Application.objects.aggregate(
		total=Count('id'),
	)
	return {
		'atlas_page': page,
		'sidebar_counts': {
			'jobs': Job.objects.count(),
			'applications': application_counts['total'],
			'interviews': 0,
		},
		'atlas_paths': {
			name: reverse(route_name)
			for name, route_name in ATLAS_ROUTE_NAMES.items()
		},
	}


def _render_atlas(request, page, extra_context=None):
	context = _atlas_context(page)
	if extra_context:
		context.update(extra_context)
	return render(request, 'dashboard/atlas.html', context)


@admin_required
def dashboard_atlas_page(request, page):
	if page not in ATLAS_ROUTE_NAMES:
		raise Http404

	target = reverse(ATLAS_ROUTE_NAMES[page])
	query = request.META.get('QUERY_STRING')
	return redirect(f'{target}?{query}' if query else target)


@admin_required
def dashboard_workflow(request):
	jobs = Job.objects.select_related('workflow').order_by('-posted_date')
	context = {
		'auto_jobs': jobs.filter(workflow__slug='auto'),
		'manual_jobs': jobs.filter(workflow__slug='manual'),
	}
	return render(request, 'workflow/index.html', context)


@admin_required
def dashboard_overview(request):
	return render(request, 'dashboard/overview.html', {
		'total_jobs': Job.objects.count(),
		'total_applications': Application.objects.count(),
		'applied_applications': Application.objects.filter(status=Application.Status.RECEIVED).count(),
	})


@admin_required
def dashboard_jobs(request):
	jobs = list(
		Job.objects.select_related('workflow')
		.annotate(
			application_count=Count('applications'),
			screened_count=Count(
				'applications',
				filter=Q(applications__status__in=(
					Application.Status.SCREENED,
					Application.Status.SHORTLISTED,
					Application.Status.REJECTED,
				)),
			),
			shortlisted_count=Count(
				'applications',
				filter=Q(applications__status=Application.Status.SHORTLISTED),
			),
		)
		.order_by('-posted_date')
	)
	return _render_atlas(request, 'jobs', {
		'jobs_data': {
			'createUrl': reverse('job_create'),
			'workflows': sorted({job.workflow.name for job in jobs if job.workflow}),
			'jobs': [
				{
					'id': job.pk,
					'title': job.title,
					'location': job.location,
					'workflow': job.workflow.name if job.workflow else 'Unassigned',
					'applicationCount': job.application_count,
					'screenedCount': job.screened_count,
					'shortlistedCount': job.shortlisted_count,
					'interviewCount': None,
					'isActive': job.is_active,
					'detailUrl': f"{reverse('dashboard_job_page')}?id={job.pk}",
					'reviewUrl': reverse('dashboard_review_job', kwargs={'job_id': job.pk}),
					'workspaceUrl': reverse('dashboard_workspace_job', kwargs={'job_id': job.pk}),
				}
				for job in jobs
			],
		},
	})


@admin_required
def dashboard_job_page(request):
	job_id = request.GET.get('id')
	if not job_id or not job_id.isdecimal():
		raise Http404('A valid job ID is required.')

	job = get_object_or_404(
		Job.objects.select_related('workflow').annotate(
			application_count=Count('applications'),
			received_count=Count(
				'applications',
				filter=Q(applications__status=Application.Status.RECEIVED),
			),
			screened_count=Count(
				'applications',
				filter=Q(applications__status=Application.Status.SCREENED),
			),
			shortlisted_count=Count(
				'applications',
				filter=Q(applications__status=Application.Status.SHORTLISTED),
			),
			interviewed_count=Count(
				'applications',
				filter=Q(applications__status=Application.Status.INTERVIEWED),
			),
		),
		pk=int(job_id),
	)
	criteria = list(job.criteria.prefetch_related('requirements').all())
	applications = list(
		job.applications.select_related('screening_result')
		.prefetch_related('screening_result__criteria__requirement')
		.order_by('-applied_date')
	)
	status_labels = {
		Application.Status.RECEIVED: 'Submitted',
		Application.Status.SCREENED: 'Screening',
		Application.Status.SHORTLISTED: 'Shortlisted',
		Application.Status.INTERVIEWED: 'Interviewed',
		Application.Status.REJECTED: 'Rejected',
	}
	return _render_atlas(request, 'job', {
		'job_data': {
			'id': job.pk,
			'title': job.title,
			'workspaceUrl': reverse('dashboard_workspace_job', kwargs={'job_id': job.pk}),
			'description': job.description,
			'location': job.location,
			'workflow': job.workflow.name if job.workflow else 'Unassigned',
			'applicationCount': job.application_count,
			'pipelineCounts': {
				'received': job.received_count,
				'screened': job.screened_count,
				'shortlisted': job.shortlisted_count,
				'interviewed': job.interviewed_count,
			},
			'isActive': job.is_active,
			'criteria': [
				{
					'id': criterion.pk,
					'name': criterion.name,
					'requirements': [
						{
							'id': requirement.pk,
							'name': requirement.description,
							'required': requirement.required,
						}
						for requirement in criterion.requirements.all()
					],
				}
				for criterion in criteria
			],
			'applications': [
				{
					'id': application.pk,
					'name': application.applicant_name,
					'email': application.applicant_email,
					'status': application.status,
					'statusLabel': status_labels.get(application.status, application.get_status_display()),
					'score': (
						_application_screening_result(application).overall_score
						if _application_screening_result(application) else None
					),
					'result': (
						'Waiting'
						if not _application_screening_result(application)
						else 'Passed'
						if application.status == Application.Status.SHORTLISTED
						else 'Failed'
						if application.status == Application.Status.REJECTED
						else 'Screened'
					),
					'detailUrl': f"{reverse('dashboard_application_page')}?id={application.pk}",
					'criteriaResults': [
						{
							'requirementId': result.requirement_id,
							'assessment': result.assessment,
							'score': result.score,
							'evidence': result.evidence,
						}
						for result in application.screening_result.criteria.all()
					] if _application_screening_result(application) else [],
				}
				for application in applications
			],
		},
	})


@admin_required
def dashboard_application_page(request):
	application_id = request.GET.get('id')
	if not application_id or not application_id.isdecimal():
		raise Http404('A valid application ID is required.')

	application = get_object_or_404(
		Application.objects.select_related('job__workflow', 'screening_result')
		.prefetch_related('screening_result__criteria__requirement__criterion'),
		pk=int(application_id),
	)
	screening = getattr(application, 'screening_result', None)
	status_labels = {
		Application.Status.RECEIVED: 'Submitted',
		Application.Status.SCREENED: 'Screening',
		Application.Status.SHORTLISTED: 'Shortlisted',
		Application.Status.INTERVIEWED: 'Interviewed',
		Application.Status.REJECTED: 'Rejected',
	}
	status_label = status_labels.get(application.status, application.get_status_display())
	result_label = (
		'Waiting'
		if screening is None
		else 'Passed'
		if application.status == Application.Status.SHORTLISTED
		else 'Failed'
		if application.status == Application.Status.REJECTED
		else 'Screened'
	)
	return _render_atlas(request, 'application', {
		'application_data': {
			'id': application.pk,
			'name': application.applicant_name,
			'email': application.applicant_email,
			'jobTitle': application.job.title,
			'jobUrl': f"{reverse('dashboard_job_page')}?id={application.job_id}",
			'reviewUrl': f"{reverse('dashboard_review_job', kwargs={'job_id': application.job_id})}?application={application.pk}",
			'status': application.status,
			'statusLabel': status_label,
			'statusChoices': [
				{'value': value, 'label': status_labels.get(value, label)}
				for value, label in Application.Status.choices
			],
			'result': result_label,
			'workflow': application.job.workflow.name if application.job.workflow else 'Unassigned',
			'submitted': timezone.localtime(application.applied_date).strftime('%d %b %Y').lstrip('0'),
			'resumeName': application.resume.name if application.resume else None,
			'coverLetterName': application.cover_letter.name if application.cover_letter else None,
			'score': screening.overall_score if screening else None,
			'screeningComments': screening.overall_comments if screening else None,
			'screenedAt': (
				timezone.localtime(screening.created_at).strftime('%d %b %Y %H:%M')
				if screening else None
			),
			'criteria': [
				{
					'criterion': item.requirement.criterion.name,
					'requirement': item.requirement.description,
					'assessment': item.assessment,
					'score': item.score,
					'evidence': item.evidence,
				}
				for item in screening.criteria.select_related('requirement__criterion').all()
			] if screening else [],
		},
	})


@admin_required
def dashboard_interviews(request):
	return _render_atlas(request, 'interviews')


@admin_required
def dashboard_workflows(request):
	return _render_atlas(request, 'workflows')


@admin_required
def dashboard_settings(request):
	return _render_atlas(request, 'settings')


@admin_required
def dashboard_applications(request):
	if request.method == 'POST':
		application = get_object_or_404(Application, pk=request.POST.get('application_id'))
		action = request.POST.get('action')
		if action == 'delete':
			application.delete()
			messages.success(request, 'Application deleted.')
		elif action == 'update':
			form = ApplicationManagementForm(request.POST, instance=application)
			if form.is_valid():
				form.save()
				messages.success(request, 'Application updated.')
			else:
				messages.error(request, 'Application was not updated. Check the applicant name and email.')
		return redirect('dashboard_applications')

	applications = list(
		Application.objects.select_related(
			'job__workflow',
			'screening_result',
		).order_by('-applied_date')
	)
	status_labels = {
		Application.Status.RECEIVED: 'Submitted',
		Application.Status.SCREENED: 'Screening',
		Application.Status.SHORTLISTED: 'Shortlisted',
		Application.Status.INTERVIEWED: 'Interviewed',
		Application.Status.REJECTED: 'Rejected',
	}
	return _render_atlas(request, 'applications', {
		'applications_data': {
			'statuses': [
				{'value': value, 'label': label}
				for value, label in status_labels.items()
			],
			'jobs': [
				{'id': job.pk, 'title': job.title}
				for job in Job.objects.order_by('title')
			],
			'applications': [
				{
					'id': application.pk,
					'name': application.applicant_name,
					'email': application.applicant_email,
					'jobId': application.job_id,
					'jobTitle': application.job.title,
					'status': application.status,
					'statusLabel': status_labels.get(application.status, application.status),
					'score': (
						_application_screening_result(application).overall_score
						if _application_screening_result(application) else None
					),
					'result': (
						'Waiting'
						if not _application_screening_result(application)
						else 'Passed'
						if application.status == Application.Status.SHORTLISTED
						else 'Failed'
						if application.status == Application.Status.REJECTED
						else 'Screened'
					),
					'workflow': application.job.workflow.name if application.job.workflow else 'Unassigned',
					'submitted': timezone.localtime(application.applied_date).strftime('%d %b %Y').lstrip('0'),
					'jobUrl': f"{reverse('dashboard_job_page')}?id={application.job_id}",
					'detailUrl': f"{reverse('dashboard_application_page')}?id={application.pk}",
					'workspaceUrl': (
						f"{reverse('dashboard_workspace_job', kwargs={'job_id': application.job_id})}"
						f"?status={application.status}&application={application.pk}"
					),
				}
				for application in applications
			],
		},
	})


@admin_required
def admin_job_detail(request, pk):
	job = get_object_or_404(Job, pk=pk)
	if request.method == 'POST':
		action = request.POST.get('action')

		if action == 'add_criterion':
			criterion_name = (request.POST.get('criterion_name') or '').strip()
			requirement_lines = [
				line.strip()
				for line in (request.POST.get('requirement_text') or '').splitlines()
				if line.strip()
			]
			if criterion_name:
				criterion, _ = Criterion.objects.get_or_create(job=job, name=criterion_name)
				Requirement.objects.bulk_create([
					Requirement(criterion=criterion, description=line, required=True)
					for line in requirement_lines
				])
			return redirect('admin_job_detail', pk=job.pk)

		if action == 'edit_criterion':
			criterion = get_object_or_404(
				Criterion,
				pk=request.POST.get('criterion_id'),
				job=job,
			)
			criterion_name = (request.POST.get('criterion_name') or '').strip()
			if criterion_name:
				criterion.name = criterion_name
				criterion.save()

			requirement_lines = [
				line.strip()
				for line in (request.POST.get('requirement_text') or '').splitlines()
				if line.strip()
			]
			existing_requirements = list(criterion.requirements.all())
			for index, requirement in enumerate(existing_requirements):
				if index < len(requirement_lines):
					requirement.description = requirement_lines[index]
					requirement.save()
				else:
					requirement.delete()
			Requirement.objects.bulk_create([
				Requirement(criterion=criterion, description=line, required=True)
				for line in requirement_lines[len(existing_requirements):]
			])
			return redirect('admin_job_detail', pk=job.pk)

		if action == 'delete_criterion':
			criterion = get_object_or_404(
				Criterion,
				pk=request.POST.get('criterion_id'),
				job=job,
			)
			criterion.delete()
			return redirect('admin_job_detail', pk=job.pk)

	criteria = job.criteria.prefetch_related('requirements').all()
	return render(request, 'dashboard/jobs/detail.html', {
		'job': job,
		'criteria': criteria,
	})


@admin_required
def job_create(request):
	if request.method == 'POST':
		try:
			payload = json.loads(request.body or '{}')
		except (TypeError, ValueError):
			return JsonResponse({'error': 'Invalid job creation request.'}, status=400)
		if not isinstance(payload, dict):
			return JsonResponse({'error': 'Invalid job creation request.'}, status=400)

		action = payload.get('action')
		if action == 'save_job_details':
			job_id = request.session.get('job_creation_id')
			instance = Job.objects.filter(pk=job_id, is_active=False).first() if job_id else None
			form = JobForm(payload, instance=instance)
			if not form.is_valid():
				return JsonResponse({'errors': form.errors.get_json_data()}, status=400)
			job = form.save(commit=False)
			job.is_active = False
			job.workflow = None
			job.screening_threshold = None
			job.save()
			request.session['job_creation_id'] = job.pk
			return JsonResponse({'ok': True, 'job_id': job.pk})

		if action == 'publish_job':
			job_id = payload.get('job_id')
			if not job_id or str(job_id) != str(request.session.get('job_creation_id')):
				return JsonResponse({'error': 'Your job draft could not be found. Return to the first step and try again.'}, status=400)
			job = Job.objects.filter(pk=job_id, is_active=False).first()
			if job is None:
				return JsonResponse({'error': 'Your job draft could not be found. Return to the first step and try again.'}, status=400)

			workflow = Workflow.objects.filter(
				pk=payload.get('workflow_id'),
				slug__in=('auto', 'manual'),
			).first()
			if workflow is None:
				return JsonResponse({'error': 'Choose Fully Automated or Semi Automated.'}, status=400)
			threshold = None
			if workflow.slug == 'auto':
				try:
					threshold = int(payload.get('screening_threshold'))
				except (TypeError, ValueError):
					return JsonResponse({'error': 'Enter an AI threshold from 0 to 100.'}, status=400)
				if isinstance(payload.get('screening_threshold'), bool) or not 0 <= threshold <= 100:
					return JsonResponse({'error': 'Enter an AI threshold from 0 to 100.'}, status=400)

			criteria_payload = payload.get('criteria')
			if not isinstance(criteria_payload, list) or not criteria_payload:
				return JsonResponse({'error': 'Add at least one criterion and requirement before publishing.'}, status=400)
			normalized_criteria = []
			for criterion in criteria_payload:
				if not isinstance(criterion, dict):
					return JsonResponse({'error': 'Each criterion must have a name and requirements.'}, status=400)
				name = str(criterion.get('name') or '').strip()
				requirements = criterion.get('requirements')
				if not name or not isinstance(requirements, list) or not requirements:
					return JsonResponse({'error': 'Every criterion needs a name and at least one requirement.'}, status=400)
				normalized_requirements = []
				for requirement in requirements:
					if not isinstance(requirement, dict):
						return JsonResponse({'error': 'Enter a requirement for every row.'}, status=400)
					description = str(requirement.get('description') or '').strip()
					if not description:
						return JsonResponse({'error': 'Requirements cannot be empty.'}, status=400)
					normalized_requirements.append({
						'description': description,
						'required': bool(requirement.get('required', True)),
					})
				normalized_criteria.append({'name': name, 'requirements': normalized_requirements})

			with transaction.atomic():
				job.workflow = workflow
				job.screening_threshold = threshold
				job.is_active = True
				job.save(update_fields=['workflow', 'screening_threshold', 'is_active'])
				for criterion_data in normalized_criteria:
					criterion = Criterion.objects.create(job=job, name=criterion_data['name'])
					Requirement.objects.bulk_create([
						Requirement(
							criterion=criterion,
							description=requirement_data['description'],
							required=requirement_data['required'],
						)
						for requirement_data in criterion_data['requirements']
					])
			request.session.pop('job_creation_id', None)
			return JsonResponse({'ok': True, 'redirect_url': reverse('dashboard_jobs')})

		return JsonResponse({'error': 'Unsupported job creation action.'}, status=400)

	draft = Job.objects.filter(
		pk=request.session.get('job_creation_id'),
		is_active=False,
	).first()
	return _render_atlas(request, 'job-create', {
		'job_creation_data': {
			'workflows': list(
				Workflow.objects.filter(slug__in=('auto', 'manual'))
				.order_by('name')
				.values('id', 'name', 'slug')
			),
			'draft': {
				'id': draft.pk,
				'title': draft.title,
				'description': draft.description,
				'location': draft.location,
				'salary': str(draft.salary),
				'deadline': timezone.localtime(draft.deadline).strftime('%Y-%m-%dT%H:%M'),
			} if draft else None,
		},
	})


@admin_required
def job_review(request):
	job_id = request.session.get('job_wizard_id')
	if not job_id:
		return redirect('job_create')
	job = get_object_or_404(Job, pk=job_id)
	criterion = get_object_or_404(Criterion, pk=request.session.get('job_criterion_id'), job=job)
	form = RequirementForm(request.POST or None)
	if request.method == 'POST':
		action = request.POST.get('action')
		if action == 'add_requirement' and form.is_valid():
			requirement = form.save(commit=False)
			requirement.criterion = criterion
			requirement.save()
			return redirect('job_review')
		if action == 'publish':
			request.session.pop('job_wizard_id', None)
			request.session.pop('job_criterion_id', None)
			messages.success(request, f'Your job, {job.title}, has been published.')
			return redirect('dashboard_jobs')
	return render(request, 'dashboard/jobs/review.html', {
		'job': job,
		'criterion': criterion,
		'criteria': [criterion],
		'requirement_form': form,
	})


@admin_required
@require_POST
def add_job_requirement(request):
	job_id = request.session.get('job_wizard_id')
	criterion_id = request.session.get('job_criterion_id')
	if not job_id or not criterion_id:
		return JsonResponse({'error': 'The job review session has expired.'}, status=400)
	criterion = get_object_or_404(Criterion, pk=criterion_id, job_id=job_id)
	form = RequirementForm(request.POST)
	if not form.is_valid():
		return JsonResponse({'errors': form.errors.get_json_data()}, status=400)
	requirement = form.save(commit=False)
	requirement.criterion = criterion
	requirement.save()
	return JsonResponse({
		'description': requirement.description,
		'required': requirement.required,
	})


@admin_required
def job_update(request, pk):
	job = get_object_or_404(Job, pk=pk)
	form = JobForm(request.POST or None, instance=job)
	requirement_formset = RequirementFormSet(request.POST or None, prefix='requirements')
	if request.method == 'POST' and form.is_valid() and requirement_formset.is_valid():
		with transaction.atomic():
			form.save()
			criterion = job.criteria.first()
			if criterion is None:
				criterion = Criterion.objects.create(job=job, name='Job Requirements')
			for requirement_form in requirement_formset:
				if requirement_form.cleaned_data:
					requirement = requirement_form.save(commit=False)
					requirement.criterion = criterion
					requirement.save()
		request.session['job_wizard_id'] = job.pk
		request.session['job_criterion_id'] = criterion.pk
		return redirect('job_review')
	return render(request, 'dashboard/jobs/form.html', {
		'form': form,
		'editing_job': job,
		'requirement_formset': requirement_formset,
		'existing_requirements': Requirement.objects.filter(
			criterion__job=job,
		).select_related('criterion'),
	})


@admin_required
@require_POST
def requirement_delete(request, job_pk, pk):
	requirement = get_object_or_404(
		Requirement,
		pk=pk,
		criterion__job_id=job_pk,
	)
	requirement.delete()
	return redirect('job_update', pk=job_pk)


@admin_required
@require_POST
def job_delete(request, pk):
	job = get_object_or_404(Job, pk=pk)
	job.delete()
	return redirect('dashboard')
