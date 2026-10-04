import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from job_application.models import Application, Criterion, Job, Requirement
from pipeline.models import Workflow


class JobSetupFlowTests(TestCase):
	def setUp(self):
		self.admin = get_user_model().objects.create_superuser(
			username='admin',
			email='admin@example.com',
			password='test-password',
		)
		self.client.force_login(self.admin)

	def test_jobs_list_payload_links_to_each_job_workspace(self):
		job = Job.objects.create(
			title='Workspace Jobs List',
			description='Review candidates in the workspace.',
			location='Remote',
			salary='90000.00',
			deadline=timezone.now() + timedelta(days=20),
		)

		response = self.client.get(reverse('dashboard_jobs'))

		self.assertEqual(response.status_code, 200)
		job_data = next(item for item in response.context['jobs_data']['jobs'] if item['id'] == job.pk)
		self.assertEqual(
			job_data['workspaceUrl'],
			reverse('dashboard_workspace_job', kwargs={'job_id': job.pk}),
		)

	def test_dashboard_sidebar_counts_match_database_records(self):
		job = Job.objects.create(
			title='Sidebar Count Job',
			description='Count applications for the sidebar.',
			location='Remote',
			salary='90000.00',
			deadline=timezone.now() + timedelta(days=20),
		)
		Application.objects.create(
			job=job,
			applicant_name='Received Candidate',
			applicant_email='received-sidebar@example.com',
			resume='received-sidebar.pdf',
			cover_letter='received-sidebar-cover.pdf',
			status=Application.Status.RECEIVED,
		)
		Application.objects.create(
			job=job,
			applicant_name='Interview Prep Candidate',
			applicant_email='interview-sidebar@example.com',
			resume='interview-sidebar.pdf',
			cover_letter='interview-sidebar-cover.pdf',
			status=Application.Status.INTERVIEWED,
		)

		response = self.client.get(reverse('dashboard'))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['sidebar_counts'], {
			'jobs': Job.objects.count(),
			'applications': Application.objects.count(),
			'interviews': 0,
		})
		self.assertContains(response, 'id="sidebar-counts"')

	def test_dashboard_lists_fully_automated_jobs_shortlisted_today(self):
		workflow = Workflow.objects.create(name='Fully Automated', slug='auto')
		job = Job.objects.create(
			title='Data Engineer',
			description='Build data systems.',
			location='Remote',
			salary='100000.00',
			deadline=timezone.now() + timedelta(days=30),
			workflow=workflow,
		)
		Application.objects.create(
			job=job,
			applicant_name='Shortlisted Candidate',
			applicant_email='candidate@example.com',
			resume='resume.pdf',
			cover_letter='cover-letter.pdf',
		)
		application = Application.objects.get(applicant_email='candidate@example.com')
		application.status = Application.Status.SHORTLISTED
		application.save(update_fields=['status'])
		self.assertIsNotNone(application.shortlisted_at)

		response = self.client.get(reverse('dashboard'))

		self.assertEqual(response.status_code, 200)
		results = response.context['dashboard_data']['automatedResults']
		self.assertEqual(len(results), 1)
		self.assertEqual(results[0]['title'], job.title)
		self.assertEqual(results[0]['newApplicationCount'], 0)
		self.assertEqual(results[0]['shortlistedTodayCount'], 1)
		self.assertEqual(results[0]['jobUrl'], f"{reverse('dashboard_job_page')}?id={job.pk}")
		self.assertEqual(
			results[0]['workspaceUrl'],
		reverse('dashboard_workspace_job', kwargs={'job_id': job.pk}),
		)

	def test_dashboard_shows_automated_jobs_with_new_applications(self):
		workflow = Workflow.objects.create(name='Fully Automated', slug='auto')
		job = Job.objects.create(
			title='Data Engineer',
			description='Build data systems.',
			location='Remote',
			salary='100000.00',
			deadline=timezone.now() + timedelta(days=30),
			workflow=workflow,
		)
		Application.objects.create(
			job=job,
			applicant_name='New Candidate',
			applicant_email='new-candidate@example.com',
			resume='resume.pdf',
			cover_letter='cover-letter.pdf',
		)

		response = self.client.get(reverse('dashboard'))

		self.assertEqual(response.status_code, 200)
		results = response.context['dashboard_data']['automatedResults']
		self.assertEqual(len(results), 1)
		self.assertEqual(results[0]['newApplicationCount'], 1)
		self.assertEqual(results[0]['shortlistedTodayCount'], 0)
		self.assertEqual(
			results[0]['workspaceUrl'],
			reverse('dashboard_workspace_job', kwargs={'job_id': job.pk}),
		)

	def test_admin_can_create_a_job_with_criteria_and_requirements(self):
		workflow = Workflow.objects.create(name='Auto', slug='auto')
		url = reverse('job_create')
		page_response = self.client.get(url)
		self.assertEqual(page_response.status_code, 200)
		self.assertEqual(page_response.context['atlas_page'], 'job-create')
		self.assertContains(page_response, 'id="job-creation-data"')

		draft_response = self.client.post(
			url,
			data=json.dumps({
				'action': 'save_job_details',
				'title': 'Backend Engineer',
				'description': 'Build backend systems.',
				'location': 'Remote',
				'salary': '120000.00',
				'deadline': (timezone.now() + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M'),
			}),
			content_type='application/json',
		)
		self.assertEqual(draft_response.status_code, 200, draft_response.content)
		job_id = draft_response.json()['job_id']
		job = Job.objects.get(pk=job_id)
		self.assertFalse(job.is_active)

		publish_response = self.client.post(
			url,
			data=json.dumps({
				'action': 'publish_job',
				'job_id': job_id,
				'workflow_id': workflow.pk,
				'screening_threshold': 82,
				'criteria': [
					{
						'name': 'Backend experience',
						'requirements': [
							{'description': 'Django experience', 'required': True},
							{'description': 'API design experience', 'required': False},
						],
					},
					{
						'name': 'Communication',
						'requirements': [
							{'description': 'Explains technical work clearly', 'required': True},
						],
					},
				],
			}),
			content_type='application/json',
		)

		self.assertEqual(publish_response.status_code, 200, publish_response.content)
		self.assertEqual(publish_response.json()['redirect_url'], reverse('dashboard_jobs'))
		job.refresh_from_db()
		self.assertTrue(job.is_active)
		self.assertEqual(job.workflow_id, workflow.pk)
		self.assertEqual(job.screening_threshold, 82)
		self.assertEqual(
			list(job.criteria.order_by('name').values_list('name', flat=True)),
			['Backend experience', 'Communication'],
		)
		self.assertEqual(
			list(Requirement.objects.filter(criterion__job=job, criterion__name='Backend experience').order_by('description').values_list('description', flat=True)),
			['API design experience', 'Django experience'],
		)

	def test_job_detail_data_links_to_that_jobs_workspace(self):
		job = Job.objects.create(
			title='Workspace Link Job',
			description='Use its dedicated review workspace.',
			location='Remote',
			salary='90000.00',
			deadline=timezone.now() + timedelta(days=20),
		)
		application = Application.objects.create(
			job=job,
			applicant_name='Workspace Candidate',
			applicant_email='workspace@example.com',
			resume='resume.pdf',
			cover_letter='cover-letter.pdf',
		)

		response = self.client.get(reverse('dashboard_job_page'), {'id': job.pk})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			response.context['job_data']['workspaceUrl'],
			reverse('dashboard_workspace_job', kwargs={'job_id': job.pk}),
		)
		self.assertEqual(
			response.context['job_data']['applications'][0]['detailUrl'],
			f"{reverse('dashboard_application_page')}?id={application.pk}",
		)

	def test_admin_can_update_and_delete_applications(self):
		job = Job.objects.create(
			title='Product Designer',
			description='Design useful products.',
			location='Remote',
			salary='95000.00',
			deadline=timezone.now() + timedelta(days=30),
		)
		application = Application.objects.create(
			job=job,
			applicant_name='Avery Applicant',
			applicant_email='avery@example.com',
			resume='resume.pdf',
			cover_letter='cover-letter.pdf',
		)

		overview_response = self.client.get(reverse('dashboard_overview'))
		applications_response = self.client.get(reverse('dashboard_applications'))

		self.assertEqual(overview_response.status_code, 200)
		self.assertContains(overview_response, 'Overview')
		self.assertContains(overview_response, 'AI screening')
		self.assertEqual(applications_response.status_code, 200)
		self.assertContains(applications_response, 'Avery Applicant')
		self.assertContains(applications_response, job.title)
		application_data = applications_response.context['applications_data']['applications'][0]
		self.assertIsNone(application_data['score'])
		self.assertEqual(application_data['result'], 'Waiting')
		self.assertEqual(
			application_data['workspaceUrl'],
			f"{reverse('dashboard_workspace_job', kwargs={'job_id': job.pk})}?status=RECEIVED&application={application.pk}",
		)

		update_response = self.client.post(reverse('dashboard_applications'), {
			'action': 'update',
			'application_id': application.pk,
			'applicant_name': 'Avery Updated',
			'applicant_email': 'avery.updated@example.com',
			'status': Application.Status.SCREENED,
		})

		self.assertRedirects(update_response, reverse('dashboard_applications'))
		application.refresh_from_db()
		self.assertEqual(application.applicant_name, 'Avery Updated')
		self.assertEqual(application.applicant_email, 'avery.updated@example.com')
		self.assertEqual(application.status, Application.Status.SCREENED)

		delete_response = self.client.post(reverse('dashboard_applications'), {
			'action': 'delete',
			'application_id': application.pk,
		})

		self.assertRedirects(delete_response, reverse('dashboard_applications'))
		self.assertFalse(Application.objects.filter(pk=application.pk).exists())
