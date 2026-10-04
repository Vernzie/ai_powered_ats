import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, mock_open, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from job_application.models import Application, Criterion, Job, Requirement
from pipeline.models import Workflow
from screening import screen_application

from .models import ScreeningCriterionResult, ScreeningResult
from .views import _persist_screening_result


class ScreeningCriterionManagementTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='Password123!'
        )
        self.job = Job.objects.create(
            title='Senior Python Developer',
            description='Build backend services.',
            location='Remote',
            salary='120000.00',
            deadline=timezone.now() + timedelta(days=30),
        )

    def test_review_queue_includes_jobs_with_non_shortlisted_applications(self):
        self.client.force_login(self.admin)
        applied_application = Application.objects.create(
            job=self.job,
            applicant_name='Applied User',
            applicant_email='applied@example.com',
            resume='applied.pdf',
            cover_letter='applied-cover.pdf',
            status=Application.Status.RECEIVED,
        )
        screened_application = Application.objects.create(
            job=self.job,
            applicant_name='Screened User',
            applicant_email='screened@example.com',
            resume='screened.pdf',
            cover_letter='screened-cover.pdf',
            status=Application.Status.SCREENED,
        )
        ScreeningResult.objects.create(
            application=screened_application,
            overall_score=80,
            overall_comments='Meets the requirements.',
        )

        completed_job = Job.objects.create(
            title='Completed Job',
            description='All applications are processed.',
            location='Remote',
            salary='100000.00',
            deadline=timezone.now() + timedelta(days=30),
        )
        completed_screened_application = Application.objects.create(
            job=completed_job,
            applicant_name='Completed User',
            applicant_email='completed@example.com',
            resume='completed.pdf',
            cover_letter='completed-cover.pdf',
            status=Application.Status.SCREENED,
        )
        Application.objects.create(
            job=completed_job,
            applicant_name='Shortlisted User',
            applicant_email='shortlisted@example.com',
            resume='shortlisted.pdf',
            cover_letter='shortlisted-cover.pdf',
            status=Application.Status.SHORTLISTED,
        )
        ScreeningResult.objects.create(
            application=completed_screened_application,
            overall_score=92,
            overall_comments='Strong candidate.',
        )

        response = self.client.get(reverse('dashboard_review'))

        self.assertEqual(response.status_code, 200)
        listed_jobs = list(response.context['jobs'])
        recent_jobs = list(response.context['recent_jobs'])
        self.assertEqual(
            {job.pk for job in listed_jobs},
            {self.job.pk, completed_job.pk},
        )
        self.assertEqual(
            {job.pk: job.application_count for job in listed_jobs},
            {self.job.pk: 2, completed_job.pk: 1},
        )
        self.assertEqual(
            {job.pk for job in recent_jobs},
            {self.job.pk, completed_job.pk},
        )
        self.assertContains(response, 'Completed Job')
        self.assertContains(
            response,
            reverse('dashboard_review_results', args=[completed_job.pk]),
        )
        self.assertEqual(applied_application.status, Application.Status.RECEIVED)

    def test_admin_can_add_a_criterion_for_screening(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('dashboard_review_job', args=[self.job.pk]),
            {
                'action': 'add_criterion',
                'criterion_name': 'Python',
                'requirement_text': 'Strong Python and Django experience',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Criterion.objects.filter(job=self.job, name='Python').exists())
        self.assertTrue(
            Requirement.objects.filter(
                criterion__job=self.job,
                description='Strong Python and Django experience',
            ).exists()
        )

    def test_admin_can_edit_and_delete_a_criterion_for_screening(self):
        self.client.force_login(self.admin)
        criterion = Criterion.objects.create(job=self.job, name='Python')
        Requirement.objects.create(
            criterion=criterion,
            description='Strong Python experience',
            required=True,
        )

        edit_response = self.client.post(
            reverse('dashboard_job_screening', args=[self.job.pk]),
            {
                'action': 'edit_criterion',
                'criterion_id': criterion.pk,
                'criterion_name': 'Python + Django',
                'requirement_text': 'Strong Python experience\nExpert Django APIs',
            },
        )

        self.assertEqual(edit_response.status_code, 302)
        criterion.refresh_from_db()
        self.assertEqual(criterion.name, 'Python + Django')
        self.assertEqual(
            sorted(criterion.requirements.values_list('description', flat=True)),
            ['Expert Django APIs', 'Strong Python experience'],
        )

        delete_response = self.client.post(
            reverse('dashboard_job_screening', args=[self.job.pk]),
            {
                'action': 'delete_criterion',
                'criterion_id': criterion.pk,
            },
        )

        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(Criterion.objects.filter(pk=criterion.pk).exists())

    def test_ai_results_page_renders_score_filters_without_shortlisting_workflow(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('dashboard_job_screening_results', args=[self.job.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Filter by AI score')
        self.assertContains(response, 'data-score-filter="50"')
        self.assertContains(response, 'data-score-filter="70"')
        self.assertContains(response, 'data-score-filter="90"')
        self.assertNotContains(response, 'Shortlist all')

    def test_run_screening_includes_received_and_screened_applications(self):
        self.client.force_login(self.admin)
        criterion = Criterion.objects.create(job=self.job, name='Python')
        Requirement.objects.create(
            criterion=criterion,
            description='Strong Python skills',
            required=True,
        )

        applied_app = Application.objects.create(
            job=self.job,
            applicant_name='Applied User',
            applicant_email='applied@example.com',
            resume='resume.pdf',
            cover_letter='cover.pdf',
            status=Application.Status.RECEIVED,
        )
        already_screened = Application.objects.create(
            job=self.job,
            applicant_name='Screened User',
            applicant_email='screened@example.com',
            resume='resume2.pdf',
            cover_letter='cover2.pdf',
            status=Application.Status.SCREENED,
        )
        shortlisted = Application.objects.create(
            job=self.job,
            applicant_name='Shortlisted User',
            applicant_email='shortlisted@example.com',
            resume='resume3.pdf',
            cover_letter='cover3.pdf',
            status=Application.Status.SHORTLISTED,
        )

        def fake_screen_applications(job, application_ids=None):
            self.assertEqual(set(application_ids), {applied_app.pk, already_screened.pk})
            results = []
            for application_id in (applied_app.pk, already_screened.pk):
                results.append({
                    'application_id': application_id,
                    'file_id': 'abc',
                    'screening': {
                        'overall_score': 88,
                        'overall_comments': 'Strong fit',
                        'criteria': [{
                            'requirement_id': criterion.requirements.first().pk,
                            'assessment': 'meets',
                            'score': 88,
                            'evidence': 'Strong evidence',
                        }],
                    },
                })
            return results

        with patch('screening.screen_applications', side_effect=fake_screen_applications):
            response = self.client.post(
                reverse('dashboard_run_screening'),
                data='{"job_id": %s, "application_ids": [%s, %s, %s]}' % (
                    self.job.pk,
                    applied_app.pk,
                    already_screened.pk,
                    shortlisted.pk,
                ),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        applied_app.refresh_from_db()
        already_screened.refresh_from_db()
        shortlisted.refresh_from_db()
        self.assertEqual(applied_app.status, Application.Status.SCREENED)
        self.assertEqual(already_screened.status, Application.Status.SCREENED)
        self.assertEqual(shortlisted.status, Application.Status.SHORTLISTED)

    def test_dashboard_workspace_starts_unselected_and_job_route_selects_job(self):
        self.client.force_login(self.admin)
        active_job = Job.objects.create(
            title='Active Review Job',
            description='Needs review.',
            location='Remote',
            salary='95000.00',
            deadline=timezone.now() + timedelta(days=20),
            is_active=True,
        )
        inactive_job = Job.objects.create(
            title='Inactive Review Job',
            description='Not in focus.',
            location='Remote',
            salary='90000.00',
            deadline=timezone.now() + timedelta(days=10),
            is_active=False,
        )

        response = self.client.get(reverse('dashboard_workspace'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="workspace-data"')
        self.assertIsNone(response.context['workspace_data']['selected_job'])
        self.assertFalse(response.context['workspace_data']['collapse_job_list'])
        self.assertIn(active_job.pk, [job['id'] for job in response.context['workspace_data']['jobs']])
        self.assertNotIn(inactive_job.pk, [job['id'] for job in response.context['workspace_data']['jobs']])
        self.assertEqual(
            next(job['url'] for job in response.context['workspace_data']['jobs'] if job['id'] == active_job.pk),
            reverse('dashboard_workspace_job', kwargs={'job_id': active_job.pk}),
        )

        data_response = self.client.get(
            reverse('dashboard_workspace_job', kwargs={'job_id': active_job.pk}),
            {'format': 'json'},
        )
        self.assertEqual(data_response.status_code, 200)
        self.assertEqual(data_response.json()['selected_job']['id'], active_job.pk)

        detail_response = self.client.get(reverse('dashboard_workspace_job', kwargs={'job_id': active_job.pk}))
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.context['workspace_data']['selected_job']['id'], active_job.pk)
        self.assertTrue(detail_response.context['workspace_data']['collapse_job_list'])

        detail_response = self.client.get(reverse('dashboard_workspace_job', kwargs={'job_id': inactive_job.pk}))
        self.assertEqual(detail_response.status_code, 200)
        self.assertIsNone(detail_response.context['workspace_data']['selected_job'])
        self.assertTrue(detail_response.context['workspace_data']['collapse_job_list'])

    def test_workspace_has_four_requested_stages_and_counts_interviewed_applications(self):
        self.client.force_login(self.admin)
        job = Job.objects.create(
            title='Interview Pipeline Job',
            description='Hiring for interviews.',
            location='Remote',
            salary='95000.00',
            deadline=timezone.now() + timedelta(days=20),
            is_active=True,
        )
        Application.objects.create(
            job=job,
            applicant_name='Interview Candidate',
            applicant_email='interview@example.com',
            resume='resume.pdf',
            cover_letter='cover-letter.pdf',
            status=Application.Status.INTERVIEWED,
        )

        response = self.client.get(reverse('dashboard_workspace_job', kwargs={'job_id': job.pk}))

        self.assertEqual(response.status_code, 200)
        workspace_data = response.context['workspace_data']
        self.assertEqual(
            workspace_data['status_order'],
            ['RECEIVED', 'SCREENED', 'SHORTLISTED', 'INTERVIEWED'],
        )
        self.assertEqual(workspace_data['selected_job']['counts']['INTERVIEWED'], 1)
        self.assertIn(
            {'value': 'INTERVIEWED', 'label': 'Interviewed'},
            workspace_data['selected_job']['status_choices'],
        )

    def test_workspace_includes_job_criteria_and_candidate_ai_scores(self):
        self.client.force_login(self.admin)
        job = Job.objects.create(
            title='Criteria Workspace Job',
            description='Review candidates by criteria.',
            location='Remote',
            salary='95000.00',
            deadline=timezone.now() + timedelta(days=20),
        )
        criterion = Criterion.objects.create(job=job, name='Recruitment experience')
        requirement = Requirement.objects.create(
            criterion=criterion,
            description='Has experience managing recruitment processes.',
            required=True,
        )
        application = Application.objects.create(
            job=job,
            applicant_name='Criteria Candidate',
            applicant_email='criteria@example.com',
            resume='resume.pdf',
            cover_letter='cover-letter.pdf',
            status=Application.Status.SCREENED,
        )
        screening = ScreeningResult.objects.create(
            application=application,
            overall_score=82,
            overall_comments='Good recruitment experience.',
        )
        ScreeningCriterionResult.objects.create(
            screening=screening,
            requirement=requirement,
            assessment='meets',
            score=88,
            evidence='Managed end-to-end recruitment for multiple roles.',
        )

        response = self.client.get(
            reverse('dashboard_workspace_job', kwargs={'job_id': job.pk}),
            {'format': 'json'},
        )

        self.assertEqual(response.status_code, 200)
        selected_job = response.json()['selected_job']
        self.assertEqual(selected_job['criteria'][0]['name'], criterion.name)
        self.assertEqual(selected_job['criteria'][0]['requirements'][0]['id'], requirement.pk)
        candidate_result = selected_job['applications'][0]['criteria_results'][0]
        self.assertEqual(candidate_result['requirement_id'], requirement.pk)
        self.assertEqual(candidate_result['score'], 88)
        self.assertEqual(candidate_result['evidence'], 'Managed end-to-end recruitment for multiple roles.')

    def test_workspace_stage_navigation_updates_and_clears_shortlist_time(self):
        self.client.force_login(self.admin)
        job = Job.objects.create(
            title='Stage Navigation Job',
            description='Move candidates through stages.',
            location='Remote',
            salary='95000.00',
            deadline=timezone.now() + timedelta(days=20),
        )
        application = Application.objects.create(
            job=job,
            applicant_name='Stage Candidate',
            applicant_email='stage@example.com',
            resume='resume.pdf',
            cover_letter='cover-letter.pdf',
            status=Application.Status.SCREENED,
        )
        workspace_url = reverse('dashboard_workspace')

        forward_response = self.client.post(
            workspace_url,
            data=json.dumps({
                'action': 'move_application_status',
                'application_id': application.pk,
                'status': Application.Status.SHORTLISTED,
            }),
            content_type='application/json',
        )

        self.assertEqual(forward_response.status_code, 200)
        application.refresh_from_db()
        self.assertEqual(application.status, Application.Status.SHORTLISTED)
        self.assertIsNotNone(application.shortlisted_at)

        backward_response = self.client.post(
            workspace_url,
            data=json.dumps({
                'action': 'move_application_status',
                'application_id': application.pk,
                'status': Application.Status.SCREENED,
            }),
            content_type='application/json',
        )

        self.assertEqual(backward_response.status_code, 200)
        application.refresh_from_db()
        self.assertEqual(application.status, Application.Status.SCREENED)
        self.assertIsNone(application.shortlisted_at)

    def test_auto_screening_applies_the_job_threshold(self):
        workflow = Workflow.objects.create(name='Auto', slug='auto')
        job = Job.objects.create(
            title='Automated Threshold Job',
            description='Apply the saved AI threshold.',
            location='Remote',
            salary='95000.00',
            deadline=timezone.now() + timedelta(days=20),
            workflow=workflow,
            screening_threshold=80,
        )
        qualifying = Application.objects.create(
            job=job,
            applicant_name='Qualifying Candidate',
            applicant_email='qualifying@example.com',
            resume='qualifying.pdf',
            cover_letter='qualifying-cover.pdf',
        )
        below_threshold = Application.objects.create(
            job=job,
            applicant_name='Below Threshold Candidate',
            applicant_email='below@example.com',
            resume='below.pdf',
            cover_letter='below-cover.pdf',
        )

        for application, score in ((qualifying, 80), (below_threshold, 79)):
            _persist_screening_result(job, {
                'application_id': application.pk,
                'file_id': 'screening-file',
                'screening': {
                    'overall_score': score,
                    'overall_comments': 'Automated score result.',
                    'criteria': [],
                },
            })

        qualifying.refresh_from_db()
        below_threshold.refresh_from_db()
        self.assertEqual(qualifying.status, Application.Status.SHORTLISTED)
        self.assertEqual(below_threshold.status, Application.Status.SCREENED)

    def test_workspace_saves_workflow_and_only_keeps_threshold_for_auto(self):
        self.client.force_login(self.admin)
        auto_workflow = Workflow.objects.create(name='Auto', slug='auto')
        manual_workflow = Workflow.objects.create(name='Manual', slug='manual')
        job = Job.objects.create(
            title='Workflow Settings Job',
            description='Configure screening workflow.',
            location='Remote',
            salary='95000.00',
            deadline=timezone.now() + timedelta(days=20),
            workflow=manual_workflow,
        )
        url = reverse('dashboard_workspace')

        auto_response = self.client.post(
            url,
            data=json.dumps({
                'action': 'save_job_settings',
                'job_id': job.pk,
                'workflow_id': auto_workflow.pk,
                'screening_threshold': 83,
            }),
            content_type='application/json',
        )

        self.assertEqual(auto_response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.workflow_id, auto_workflow.pk)
        self.assertEqual(job.screening_threshold, 83)

        invalid_response = self.client.post(
            url,
            data=json.dumps({
                'action': 'save_job_settings',
                'job_id': job.pk,
                'workflow_id': auto_workflow.pk,
                'screening_threshold': 101,
            }),
            content_type='application/json',
        )
        self.assertEqual(invalid_response.status_code, 400)

        manual_response = self.client.post(
            url,
            data=json.dumps({
                'action': 'save_job_settings',
                'job_id': job.pk,
                'workflow_id': manual_workflow.pk,
                'screening_threshold': None,
            }),
            content_type='application/json',
        )

        self.assertEqual(manual_response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.workflow_id, manual_workflow.pk)
        self.assertIsNone(job.screening_threshold)

    def test_admin_job_detail_keeps_job_and_criteria_content(self):
        self.client.force_login(self.admin)
        criterion = Criterion.objects.create(job=self.job, name='Backend skills')
        Requirement.objects.create(
            criterion=criterion,
            description='Django experience',
            required=True,
        )

        response = self.client.get(reverse('admin_job_detail', args=[self.job.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.job.title)
        self.assertContains(response, 'Backend skills')
        self.assertContains(response, 'Django experience')
        self.assertNotContains(response, 'job-application-panel')

    def test_job_page_handles_applications_without_screening_results(self):
        self.client.force_login(self.admin)
        Application.objects.create(
            job=self.job,
            applicant_name='Unscreened Candidate',
            applicant_email='unscreened@example.com',
            resume='unscreened.pdf',
            cover_letter='unscreened-cover.pdf',
        )

        response = self.client.get(reverse('dashboard_job_page'), {'id': self.job.pk})

        self.assertEqual(response.status_code, 200)
        application_data = response.context['job_data']['applications'][0]
        self.assertIsNone(application_data['score'])
        self.assertEqual(application_data['result'], 'Waiting')

    def test_admin_job_detail_can_add_edit_and_delete_criteria(self):
        self.client.force_login(self.admin)
        detail_url = reverse('admin_job_detail', args=[self.job.pk])

        add_response = self.client.post(detail_url, {
            'action': 'add_criterion',
            'criterion_name': 'Backend skills',
            'requirement_text': 'Python\nDjango',
        })

        self.assertRedirects(add_response, detail_url)
        criterion = Criterion.objects.get(job=self.job, name='Backend skills')
        self.assertEqual(
            list(criterion.requirements.values_list('description', flat=True)),
            ['Django', 'Python'],
        )

        edit_response = self.client.post(detail_url, {
            'action': 'edit_criterion',
            'criterion_id': criterion.pk,
            'criterion_name': 'Platform skills',
            'requirement_text': 'Python\nFastAPI\nPostgreSQL',
        })

        self.assertRedirects(edit_response, detail_url)
        criterion.refresh_from_db()
        self.assertEqual(criterion.name, 'Platform skills')
        self.assertEqual(
            list(criterion.requirements.values_list('description', flat=True)),
            ['FastAPI', 'PostgreSQL', 'Python'],
        )

        delete_response = self.client.post(detail_url, {
            'action': 'delete_criterion',
            'criterion_id': criterion.pk,
        })

        self.assertRedirects(delete_response, detail_url)
        self.assertFalse(Criterion.objects.filter(pk=criterion.pk).exists())

    def test_screen_application_reviews_all_requirements_in_one_ai_call(self):
        criterion = Criterion.objects.create(job=self.job, name='Python')
        requirement = Requirement.objects.create(
            criterion=criterion,
            description='Strong Python skills',
            required=True,
        )
        communication_criterion = Criterion.objects.create(job=self.job, name='Communication')
        communication_requirement = Requirement.objects.create(
            criterion=communication_criterion,
            description='Communicates technical concepts clearly',
            required=False,
        )
        application = SimpleNamespace(
            id=321,
            job=self.job,
            resume=SimpleNamespace(path='/fake/resume.pdf'),
        )
        structured_response = SimpleNamespace(output_text=json.dumps({
            'overall_comments': 'Strong Python experience.',
            'criteria': [
                {
                    'requirement_id': requirement.pk,
                    'assessment': 'meets',
                    'score': 90,
                    'evidence': 'Eight years of Python and Django development.',
                },
                {
                    'requirement_id': communication_requirement.pk,
                    'assessment': 'partially_demonstrated',
                    'score': 70,
                    'evidence': 'Explains project work clearly in the resume.',
                },
            ],
        }))
        fake_client = SimpleNamespace(
            files=SimpleNamespace(create=Mock(side_effect=OSError('Upload unavailable'))),
            responses=SimpleNamespace(create=Mock(return_value=structured_response)),
        )

        with patch('screening._extract_resume_text', return_value='Python and Django experience.'), \
                patch('screening._get_client', return_value=fake_client), \
                patch('builtins.open', mock_open(read_data=b'resume')):
            result = screen_application(application, [requirement, communication_requirement])

        self.assertEqual(result['application_id'], application.id)
        self.assertEqual(result['screening']['overall_score'], 80)
        self.assertEqual(len(result['screening']['criteria']), 2)
        self.assertEqual(
            {item['requirement_id'] for item in result['screening']['criteria']},
            {requirement.pk, communication_requirement.pk},
        )
        self.assertEqual(fake_client.responses.create.call_count, 1)
        input_content = fake_client.responses.create.call_args.kwargs['input'][0]['content']
        self.assertIn('Strong Python skills', input_content[0]['text'])
        self.assertIn('RESUME TEXT', input_content[1]['text'])

    def test_single_application_screen_endpoint_rescreens_and_overwrites_existing_result(self):
        self.client.force_login(self.admin)
        auto_workflow = Workflow.objects.create(name='Auto Screening', slug='auto')
        self.job.workflow = auto_workflow
        self.job.screening_threshold = 80
        self.job.save(update_fields=['workflow', 'screening_threshold'])
        criterion = Criterion.objects.create(job=self.job, name='Python')
        requirement = Requirement.objects.create(
            criterion=criterion,
            description='Strong Python skills',
            required=True,
        )
        application = Application.objects.create(
            job=self.job,
            applicant_name='Single Screen Candidate',
            applicant_email='single-screen@example.com',
            resume='single-screen.pdf',
            cover_letter='single-screen-cover.pdf',
            status=Application.Status.SHORTLISTED,
        )
        previous_screening = ScreeningResult.objects.create(
            application=application,
            overall_score=70,
            overall_comments='Previous screening result.',
        )
        ScreeningCriterionResult.objects.create(
            screening=previous_screening,
            requirement=requirement,
            assessment='does not meet',
            score=50,
            evidence='Previous evidence.',
        )
        screening_result = {
            'application_id': application.pk,
            'file_id': 'single-screen-file',
            'screening': {
                'overall_score': 96,
                'overall_comments': 'Strong evidence for the role.',
                'criteria': [{
                    'requirement_id': requirement.pk,
                    'assessment': 'meets',
                    'score': 86,
                    'evidence': 'Several years of Python experience.',
                }],
            },
        }

        with patch.object(application.resume.storage, 'exists', return_value=True), \
            patch('application_screening.views._screen_application', return_value=screening_result) as mock_screen:
            response = self.client.post(
                reverse('dashboard_screen_application', kwargs={'application_id': application.pk}),
                data='{}',
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200, response.content)
        mock_screen.assert_called_once()
        self.assertEqual(mock_screen.call_args.args[0].pk, application.pk)
        self.assertEqual([item.pk for item in mock_screen.call_args.args[1]], [requirement.pk])
        response_data = response.json()
        self.assertEqual(response_data['application_id'], application.pk)
        self.assertEqual(response_data['score'], 96)
        self.assertEqual(response_data['criteria_results'][0]['requirement_id'], requirement.pk)
        self.assertEqual(response_data['criteria_results'][0]['score'], 86)
        application.refresh_from_db()
        self.assertEqual(application.status, Application.Status.SCREENED)
        saved_screening = ScreeningResult.objects.get(application=application)
        self.assertEqual(saved_screening.pk, previous_screening.pk)
        self.assertEqual(saved_screening.overall_score, 96)
        saved_criterion = ScreeningCriterionResult.objects.get(screening=saved_screening)
        self.assertEqual(saved_criterion.score, 86)
        self.assertEqual(saved_criterion.evidence, 'Several years of Python experience.')

    def test_single_application_screen_rejects_a_missing_resume_file(self):
        self.client.force_login(self.admin)
        application = Application.objects.create(
            job=self.job,
            applicant_name='Missing Resume Candidate',
            applicant_email='missing-resume@example.com',
            resume='missing-resume.pdf',
            cover_letter='missing-resume-cover.pdf',
            status=Application.Status.RECEIVED,
        )

        response = self.client.post(
            reverse('dashboard_screen_application', kwargs={'application_id': application.pk}),
            data='{}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Re-upload the resume', response.json()['error'])

    def test_streaming_screening_view_returns_ndjson_events(self):
        self.client.force_login(self.admin)
        criterion = Criterion.objects.create(job=self.job, name='Python')
        Requirement.objects.create(
            criterion=criterion,
            description='Strong Python skills',
            required=True,
        )
        application = Application.objects.create(
            job=self.job,
            applicant_name='Stream User',
            applicant_email='stream@example.com',
            resume='stream.pdf',
            cover_letter='stream-cover.pdf',
            status=Application.Status.RECEIVED,
        )

        def fake_stream(job, application_ids=None, max_workers=5):
            yield {'type': 'candidate_started', 'application_id': application.pk, 'applicant_name': application.applicant_name}
            yield {'type': 'all_done'}

        with patch('application_screening.views.stream_screening', side_effect=fake_stream):
            response = self.client.post(
                reverse('dashboard_screening_stream', args=[self.job.pk]),
                data=json.dumps({'application_ids': [application.pk]}),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/x-ndjson')
        body = b''.join(response.streaming_content).decode()
        self.assertIn('candidate_started', body)
        self.assertIn('all_done', body)
