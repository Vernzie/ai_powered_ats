import json
import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from application_screening.models import ScreeningCriterionResult, ScreeningResult
from interviews.models import InterviewQuestion
from job_application.models import Application, Criterion, Job, Requirement


class ApplicationReviewTests(TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_directory.cleanup)
        media_settings = override_settings(MEDIA_ROOT=self.media_directory.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)

        self.reviewer = User.objects.create_superuser(
            username='reviewer',
            email='reviewer@example.com',
            password='test-password',
        )
        self.client.force_login(self.reviewer)
        self.job = Job.objects.create(
            title='Review Job',
            description='A job used to test candidate review.',
            location='Remote',
            salary='90000.00',
            deadline=timezone.now() + timedelta(days=20),
        )
        self.criterion = Criterion.objects.create(job=self.job, name='Technical Skills')
        self.requirement_python = Requirement.objects.create(
            criterion=self.criterion,
            description='Python development experience',
            required=True,
        )
        self.requirement_api = Requirement.objects.create(
            criterion=self.criterion,
            description='API development experience',
            required=True,
        )
        self.application = Application.objects.create(
            job=self.job,
            applicant_name='Candidate Review',
            applicant_email='candidate@example.com',
            resume=SimpleUploadedFile('resume.pdf', b'%PDF-1.4 resume content', content_type='application/pdf'),
            cover_letter=SimpleUploadedFile('cover.pdf', b'%PDF-1.4 cover content', content_type='application/pdf'),
        )
        self.review_url = reverse('workspace_application_review', kwargs={'job_id': self.job.pk})

    def _review_payload(self, review_method='MANUAL'):
        return {
            'application_id': str(self.application.pk),
            'review_method': review_method,
            'score_%s' % self.requirement_python.pk: '80',
            'assessment_%s' % self.requirement_python.pk: 'meets',
            'evidence_%s' % self.requirement_python.pk: 'Built Python services.',
            'score_%s' % self.requirement_api.pk: '60',
            'assessment_%s' % self.requirement_api.pk: 'partially_demonstrated',
            'evidence_%s' % self.requirement_api.pk: 'Described API work in a project.',
            'overall_comments': 'Relevant experience with some gaps.',
        }

    def test_review_page_loads_resume_and_job_requirements(self):
        ScreeningResult.objects.create(
            application=self.application,
            overall_score=85,
            overall_comments='Strong evidence across requirements.',
            review_method=ScreeningResult.ReviewMethod.MANUAL,
            reviewed_by=self.reviewer,
        )
        response = self.client.get(self.review_url, {'application': self.application.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'application-review-form')
        self.assertContains(response, self.requirement_python.description)
        self.assertContains(response, self.requirement_api.description)
        self.assertContains(response, 'Use AI to fill scores')
        self.assertContains(response, 'Overall score:')
        self.assertContains(response, '<strong id="review-overall-score-value">85</strong>')
        self.assertContains(
            response,
            'data-ai-url="%s"' % reverse(
                'dashboard_screen_application',
                kwargs={'application_id': self.application.pk},
            ),
        )
        self.assertNotContains(response, 'preview=1')
        self.assertContains(response, 'data-screened-url=')
        self.assertContains(response, 'Send to screened')
        self.assertContains(response, '<object class="resume-frame"')
        self.assertNotContains(response, 'Open resume</a>')
        self.assertContains(response, 'class="shell sidebar-collapsed"')
        self.assertContains(response, 'aria-expanded="false"')

        resume_response = self.client.get(reverse(
            'workspace_application_review_resume',
            kwargs={'job_id': self.job.pk, 'application_id': self.application.pk},
        ))
        self.assertEqual(resume_response.status_code, 200)
        self.assertEqual(resume_response['Content-Type'], 'application/pdf')
        self.assertIn('inline', resume_response.get('Content-Disposition', ''))
        self.assertEqual(resume_response.get('X-Frame-Options'), 'SAMEORIGIN')
        try:
            self.assertIn(b'resume content', b''.join(resume_response.streaming_content))
        finally:
            resume_response.close()

    def test_incomplete_manual_review_does_not_save_or_advance_application(self):
        payload = self._review_payload()
        payload.pop('score_%s' % self.requirement_api.pk)
        response = self.client.post(
            '%s?application=%s' % (self.review_url, self.application.pk),
            payload,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ScreeningResult.objects.filter(application=self.application).exists())
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.RECEIVED)

    def test_manual_review_saves_all_scores_and_reviewer_then_marks_screened(self):
        response = self.client.post(
            '%s?application=%s' % (self.review_url, self.application.pk),
            self._review_payload(),
        )

        self.assertEqual(response.status_code, 302)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.SCREENED)
        screening = ScreeningResult.objects.get(application=self.application)
        self.assertEqual(screening.overall_score, 70)
        self.assertEqual(screening.review_method, ScreeningResult.ReviewMethod.MANUAL)
        self.assertEqual(screening.reviewed_by, self.reviewer)
        saved_results = {
            result.requirement_id: result
            for result in ScreeningCriterionResult.objects.filter(screening=screening)
        }
        self.assertEqual(saved_results[self.requirement_python.pk].score, 80)
        self.assertEqual(saved_results[self.requirement_python.pk].evidence, 'Built Python services.')
        self.assertEqual(saved_results[self.requirement_api.pk].score, 60)

    def test_ai_preview_does_not_save_scores_or_change_status(self):
        ai_result = {
            'application_id': self.application.pk,
            'file_id': 'ai-file-id',
            'screening': {
                'overall_score': 85,
                'overall_comments': 'Strong evidence across requirements.',
                'criteria': [
                    {
                        'requirement_id': self.requirement_python.pk,
                        'assessment': 'meets',
                        'score': 90,
                        'evidence': 'Resume describes Python delivery.',
                    },
                    {
                        'requirement_id': self.requirement_api.pk,
                        'assessment': 'partially_demonstrated',
                        'score': 80,
                        'evidence': 'Resume mentions API integration.',
                    },
                ],
            },
        }
        with patch('application_screening.views._screen_application', return_value=ai_result):
            response = self.client.post(
                reverse('dashboard_screen_application', kwargs={'application_id': self.application.pk}) + '?preview=1',
                data='{}',
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['criteria_results']), 2)
        self.assertEqual(response.json()['file_id'], 'ai-file-id')
        self.assertFalse(ScreeningResult.objects.filter(application=self.application).exists())
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.RECEIVED)

    def test_ai_assisted_review_saves_as_ai_only_after_submit(self):
        response = self.client.post(
            '%s?application=%s' % (self.review_url, self.application.pk),
            self._review_payload(review_method='AI'),
        )

        self.assertEqual(response.status_code, 302)
        screening = ScreeningResult.objects.get(application=self.application)
        self.assertEqual(screening.review_method, ScreeningResult.ReviewMethod.AI)
        self.assertEqual(screening.reviewed_by.username, 'ai-screening')
        review_page = self.client.get(self.review_url, {'application': self.application.pk})
        self.assertContains(review_page, 'Previously screened/reviewed by <strong>AI</strong>')

    def test_shortlist_page_shows_title_for_screened_application_only(self):
        self.application.status = Application.Status.SCREENED
        self.application.save(update_fields=['status'])
        shortlist_url = reverse('workspace_application_shortlist', kwargs={'job_id': self.job.pk})

        response = self.client.get(shortlist_url, {'application': self.application.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<h1>Shortlisting</h1>')
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.SCREENED)

        self.application.status = Application.Status.RECEIVED
        self.application.save(update_fields=['status'])
        invalid_response = self.client.get(shortlist_url, {'application': self.application.pk})
        self.assertEqual(invalid_response.status_code, 404)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.RECEIVED)

    def test_shortlist_page_lists_screened_candidates_and_scores(self):
        self.application.status = Application.Status.SCREENED
        self.application.save(update_fields=['status'])
        screening = ScreeningResult.objects.create(
            application=self.application,
            overall_score=78,
            overall_comments='Good evidence across the main requirements.',
            review_method=ScreeningResult.ReviewMethod.MANUAL,
            reviewed_by=self.reviewer,
        )
        ScreeningCriterionResult.objects.create(
            screening=screening,
            requirement=self.requirement_python,
            assessment='meets',
            score=82,
            evidence='Built Python services.',
        )
        unselected_screened = Application.objects.create(
            job=self.job,
            applicant_name='Unselected Screened Candidate',
            applicant_email='unselected@example.com',
            resume='resumes/unselected.pdf',
            cover_letter='cover_letters/unselected.pdf',
            status=Application.Status.SCREENED,
        )
        shortlist_url = reverse('workspace_application_shortlist', kwargs={'job_id': self.job.pk})

        response = self.client.get(shortlist_url, {'application': self.application.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['shortlist_data']['selected_application_id'],
            self.application.pk,
        )
        self.assertEqual(response.context['shortlist_data']['applications'][0]['score'], 78)
        self.assertEqual(
            response.context['shortlist_data']['applications'][0]['criteria_results'][0]['score'],
            82,
        )
        self.assertEqual(response.context['screened_count'], 1)
        self.assertEqual(
            [item['id'] for item in response.context['shortlist_data']['applications']],
            [self.application.pk],
        )
        self.assertContains(response, 'data-selected-application-id="%s"' % self.application.pk)
        unselected_screened.refresh_from_db()
        self.assertEqual(unselected_screened.status, Application.Status.SCREENED)

    def test_add_to_shortlisted_moves_only_selected_screened_applications(self):
        second_screened = Application.objects.create(
            job=self.job,
            applicant_name='Second Screened Candidate',
            applicant_email='second@example.com',
            resume=SimpleUploadedFile('second-resume.pdf', b'%PDF-1.4 resume', content_type='application/pdf'),
            cover_letter=SimpleUploadedFile('second-cover.pdf', b'%PDF-1.4 cover', content_type='application/pdf'),
            status=Application.Status.SCREENED,
        )
        self.application.status = Application.Status.SCREENED
        self.application.save(update_fields=['status'])
        received = Application.objects.create(
            job=self.job,
            applicant_name='Received Candidate',
            applicant_email='received@example.com',
            resume=SimpleUploadedFile('received-resume.pdf', b'%PDF-1.4 resume', content_type='application/pdf'),
            cover_letter=SimpleUploadedFile('received-cover.pdf', b'%PDF-1.4 cover', content_type='application/pdf'),
            status=Application.Status.RECEIVED,
        )
        shortlist_url = reverse('workspace_application_shortlist', kwargs={'job_id': self.job.pk})

        page_response = self.client.get(
            shortlist_url,
            [('application', str(self.application.pk)), ('application', str(second_screened.pk))],
        )
        self.assertEqual(page_response.status_code, 200)
        self.assertEqual(page_response.context['screened_count'], 2)
        self.assertEqual(
            {item['id'] for item in page_response.context['shortlist_data']['applications']},
            {self.application.pk, second_screened.pk},
        )

        response = self.client.post(
            shortlist_url,
            {'application_ids': [self.application.pk, second_screened.pk]},
        )

        self.assertEqual(response.status_code, 302)
        self.application.refresh_from_db()
        second_screened.refresh_from_db()
        received.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.SHORTLISTED)
        self.assertEqual(second_screened.status, Application.Status.SHORTLISTED)
        self.assertEqual(received.status, Application.Status.RECEIVED)
        self.assertIsNotNone(self.application.shortlisted_at)
        self.assertIsNotNone(second_screened.shortlisted_at)

    def test_json_shortlist_action_updates_all_submitted_screened_ids(self):
        self.application.status = Application.Status.SCREENED
        self.application.save(update_fields=['status'])
        second_screened = Application.objects.create(
            job=self.job,
            applicant_name='Second Screened Candidate',
            applicant_email='second@example.com',
            resume=SimpleUploadedFile('second-resume.pdf', b'%PDF-1.4 resume', content_type='application/pdf'),
            cover_letter=SimpleUploadedFile('second-cover.pdf', b'%PDF-1.4 cover', content_type='application/pdf'),
            status=Application.Status.SCREENED,
        )

        response = self.client.post(
            reverse('workspace_application_shortlist', kwargs={'job_id': self.job.pk}),
            {'application_ids': [self.application.pk, second_screened.pk]},
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], Application.Status.SHORTLISTED)
        self.assertEqual(response.json()['shortlisted_count'], 2)
        self.application.refresh_from_db()
        second_screened.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.SHORTLISTED)
        self.assertEqual(second_screened.status, Application.Status.SHORTLISTED)

    def test_bulk_interview_action_moves_only_job_shortlisted_applications(self):
        self.application.status = Application.Status.SHORTLISTED
        self.application.save(update_fields=['status'])
        second_shortlisted = Application.objects.create(
            job=self.job,
            applicant_name='Second Shortlisted Candidate',
            applicant_email='second-shortlisted@example.com',
            resume=SimpleUploadedFile('second-resume.pdf', b'%PDF-1.4 resume', content_type='application/pdf'),
            cover_letter=SimpleUploadedFile('second-cover.pdf', b'%PDF-1.4 cover', content_type='application/pdf'),
            status=Application.Status.SHORTLISTED,
        )

        response = self.client.post(
            reverse('workspace_add_shortlisted_to_interviews', kwargs={'job_id': self.job.pk}),
            {'application_ids': [self.application.pk, second_shortlisted.pk]},
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], Application.Status.INTERVIEWED)
        self.assertEqual(response.json()['interviewed_count'], 2)
        self.application.refresh_from_db()
        second_shortlisted.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.INTERVIEWED)
        self.assertEqual(second_shortlisted.status, Application.Status.INTERVIEWED)

    def test_interviewed_applications_page_lists_only_interviewed_status(self):
        self.application.status = Application.Status.INTERVIEWED
        self.application.save(update_fields=['status'])
        shortlisted = Application.objects.create(
            job=self.job,
            applicant_name='Still Shortlisted Candidate',
            applicant_email='shortlisted@example.com',
            resume=SimpleUploadedFile('shortlisted-resume.pdf', b'%PDF-1.4 resume', content_type='application/pdf'),
            cover_letter=SimpleUploadedFile('shortlisted-cover.pdf', b'%PDF-1.4 cover', content_type='application/pdf'),
            status=Application.Status.SHORTLISTED,
        )

        response = self.client.get(
            reverse('workspace_interviewed_applications', kwargs={'job_id': self.job.pk}),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['interviewed_count'], 1)
        self.assertContains(response, self.application.applicant_name)
        self.assertContains(response, self.application.applicant_email)
        self.assertContains(response, 'Interviewed')
        self.assertNotContains(response, shortlisted.applicant_name)

        workspace_response = self.client.get(
            reverse('dashboard_workspace_job', kwargs={'job_id': self.job.pk}),
            {'format': 'json'},
        )
        self.assertEqual(workspace_response.status_code, 200)
        self.assertEqual(
            workspace_response.json()['selected_job']['interviewed_applications_url'],
            reverse('workspace_interviewed_applications', kwargs={'job_id': self.job.pk}),
        )
        workspace_page = self.client.get(
            reverse('dashboard_workspace_job', kwargs={'job_id': self.job.pk}),
        )
        self.assertEqual(workspace_page.status_code, 200)
        self.assertEqual(
            workspace_page.context['workspace_data']['status_labels'][Application.Status.INTERVIEWED],
            'Interview Prep',
        )

    def test_interview_preparation_page_shows_resume_and_question_editor(self):
        self.application.status = Application.Status.INTERVIEWED
        self.application.save(update_fields=['status'])
        second_interviewed = Application.objects.create(
            job=self.job,
            applicant_name='Second Interview Candidate',
            applicant_email='second-interview@example.com',
            resume='second-interview-resume.pdf',
            cover_letter='second-interview-cover.pdf',
            status=Application.Status.INTERVIEWED,
        )
        Application.objects.create(
            job=self.job,
            applicant_name='Shortlisted Candidate',
            applicant_email='shortlisted@example.com',
            resume='shortlisted-resume.pdf',
            cover_letter='shortlisted-cover.pdf',
            status=Application.Status.SHORTLISTED,
        )
        InterviewQuestion.objects.create(
            application=self.application,
            question='Existing saved question.',
            expected_answer='Use a concrete example.',
            question_type=InterviewQuestion.QuestionType.GENERAL,
            weight=2,
        )

        response = self.client.get(
            reverse(
                'workspace_prepare_interview',
                kwargs={'job_id': self.job.pk, 'application_id': self.application.pk},
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'resume-frame')
        self.assertContains(response, 'Interview questions')
        self.assertContains(response, 'data-create-question-url=')
        self.assertContains(response, 'data-generate-questions-url=')
        self.assertContains(response, 'interview-question-data')
        self.assertContains(response, 'Existing saved question.')
        self.assertContains(response, 'Use a concrete example.')
        self.assertContains(response, 'id="interview-ai-prompt"')
        self.assertContains(response, 'id="interview-ai-question-count"')
        self.assertContains(response, 'Generate questions')
        self.assertContains(response, 'a difficult Python bug')
        self.assertContains(response, 'id="interview-application-select"')
        self.assertContains(response, second_interviewed.applicant_name)
        self.assertContains(response, '1 question')
        self.assertContains(response, '0 questions')
        self.assertNotContains(response, 'shortlisted@example.com')
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.assertIn('csrftoken', response.cookies)
        workspace_response = self.client.get(
            reverse('dashboard_workspace_job', kwargs={'job_id': self.job.pk}),
            {'format': 'json'},
        )
        self.assertEqual(workspace_response.status_code, 200)
        workspace_applications = workspace_response.json()['selected_job']['applications']
        current_application = next(
            item for item in workspace_applications
            if item['id'] == self.application.pk
        )
        self.assertEqual(
            current_application['interview_question_count'],
            1,
        )

    def test_interview_question_create_edit_delete_are_application_scoped(self):
        self.application.status = Application.Status.INTERVIEWED
        self.application.save(update_fields=['status'])
        create_url = reverse(
            'workspace_interview_question_create',
            kwargs={'job_id': self.job.pk, 'application_id': self.application.pk},
        )
        payload = {
            'question': 'Describe a challenging project.',
            'expected_answer': 'Explain the challenge, action, and outcome.',
            'question_type': InterviewQuestion.QuestionType.SPECIFIC,
            'weight': 3,
        }

        create_response = self.client.post(
            create_url,
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(create_response.status_code, 201)
        saved_question = InterviewQuestion.objects.get(pk=create_response.json()['id'])
        self.assertEqual(saved_question.application, self.application)
        self.assertEqual(saved_question.question, payload['question'])
        self.assertEqual(saved_question.expected_answer, payload['expected_answer'])
        self.assertEqual(saved_question.question_type, InterviewQuestion.QuestionType.SPECIFIC)
        self.assertEqual(saved_question.weight, 3)

        detail_url = reverse(
            'workspace_interview_question_detail',
            kwargs={
                'job_id': self.job.pk,
                'application_id': self.application.pk,
                'question_id': saved_question.pk,
            },
        )
        update_response = self.client.patch(
            detail_url,
            data=json.dumps({
                'question': 'Tell us about that project.',
                'expected_answer': 'Describe the results and lessons learned.',
                'question_type': InterviewQuestion.QuestionType.GENERAL,
                'weight': 2,
            }),
            content_type='application/json',
        )
        self.assertEqual(update_response.status_code, 200)
        saved_question.refresh_from_db()
        self.assertEqual(saved_question.question, 'Tell us about that project.')
        self.assertEqual(saved_question.expected_answer, 'Describe the results and lessons learned.')
        self.assertEqual(saved_question.question_type, InterviewQuestion.QuestionType.GENERAL)
        self.assertEqual(saved_question.weight, 2)

        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(InterviewQuestion.objects.filter(pk=saved_question.pk).exists())

    def test_ai_generation_view_saves_questions_before_returning_them(self):
        self.application.status = Application.Status.INTERVIEWED
        self.application.save(update_fields=['status'])
        generated_questions = [{
            'question': 'Describe a Python project.',
            'expected_answer': 'Explains the design and outcome.',
            'question_type': InterviewQuestion.QuestionType.SPECIFIC,
            'weight': 3,
        }]
        generate_url = reverse(
            'workspace_generate_interview_questions',
            kwargs={'job_id': self.job.pk, 'application_id': self.application.pk},
        )
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.reviewer)
        page_response = csrf_client.get(
            reverse(
                'workspace_prepare_interview',
                kwargs={'job_id': self.job.pk, 'application_id': self.application.pk},
            ),
        )
        csrf_token = page_response.cookies['csrftoken'].value

        with patch('workspace.views.upload_application_resume', return_value='resume-file-id') as upload_resume, \
            patch('workspace.views.generate_interview_questions', return_value=generated_questions) as generate:
            response = csrf_client.post(
                generate_url,
                data=json.dumps({'prompt': 'Ask about Python projects.', 'question_count': 1}),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token,
            )

        self.assertEqual(response.status_code, 200, response.content)
        upload_resume.assert_called_once_with(self.application.pk)
        generate.assert_called_once()
        self.assertEqual(generate.call_args.kwargs['question_count'], 1)
        self.assertEqual(generate.call_args.kwargs['resume_file_id'], 'resume-file-id')
        saved_question = InterviewQuestion.objects.get(application=self.application)
        self.assertEqual(response.json()['questions'][0]['id'], saved_question.pk)
        self.assertEqual(response.json()['questions'][0]['question'], saved_question.question)

    def test_interview_preparation_page_rejects_application_not_interviewed(self):
        response = self.client.get(
            reverse(
                'workspace_prepare_interview',
                kwargs={'job_id': self.job.pk, 'application_id': self.application.pk},
            ),
        )

        self.assertEqual(response.status_code, 404)
