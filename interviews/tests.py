import json
import tempfile
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

import questions
from interviews.models import InterviewQuestion
from job_application.models import Application, Job


class QuestionGenerationTests(TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_directory.cleanup)
        media_settings = override_settings(MEDIA_ROOT=self.media_directory.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)
        self.user = get_user_model().objects.create_user(username='question-test-user')
        self.job = Job.objects.create(
            title='Junior Developer',
            description='Build and maintain software.',
            location='Remote',
            salary='80000.00',
            deadline=timezone.now() + timedelta(days=10),
        )
        self.application = Application.objects.create(
            job=self.job,
            user=self.user,
            applicant_name='Question Test Candidate',
            applicant_email='question-test@example.com',
            resume=SimpleUploadedFile('resume.pdf', b'%PDF-1.4 test resume', content_type='application/pdf'),
            cover_letter=SimpleUploadedFile('cover.pdf', b'%PDF-1.4 test cover', content_type='application/pdf'),
            status=Application.Status.INTERVIEWED,
        )
        self.generated_questions = [{
            'question': 'Describe a Python project.',
            'question_type': InterviewQuestion.QuestionType.SPECIFIC,
            'weight': 3,
            'expected_answer': 'Explains design choices and testing.',
        }]
        self.fake_client = Mock()
        self.fake_client.files.create.return_value = SimpleNamespace(id='file-test-123')
        self.fake_client.responses.create.return_value = SimpleNamespace(
            output_text=json.dumps({'questions': self.generated_questions}),
        )

    def test_main_returns_validated_question_dictionaries_and_attaches_resume_file(self):
        with patch.object(questions, 'get_client', return_value=self.fake_client):
            result = questions.main(
                'Role: Junior Developer',
                'Create one practical question.',
                question_count=1,
                resume_file_id='file-test-123',
            )

        self.assertEqual(result, self.generated_questions)
        request_content = self.fake_client.responses.create.call_args.kwargs['input'][0]['content']
        self.assertEqual(request_content[1], {'type': 'input_file', 'file_id': 'file-test-123'})

    def test_main_returns_requested_count_when_model_generates_extra_questions(self):
        extra_questions = self.generated_questions * 3
        self.fake_client.responses.create.return_value = SimpleNamespace(
            output_text=json.dumps({'questions': extra_questions}),
        )
        with patch.object(questions, 'get_client', return_value=self.fake_client):
            result = questions.main('Role: Junior Developer', 'Generate questions.', question_count=1)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['question'], self.generated_questions[0]['question'])

    def test_resume_upload_uses_openai_files_api(self):
        with patch.object(questions, 'get_client', return_value=self.fake_client):
            file_id = questions.upload_application_resume(self.application.pk)

        self.assertEqual(file_id, 'file-test-123')
        self.assertEqual(self.fake_client.files.create.call_args.kwargs['purpose'], 'user_data')
        uploaded_file = self.fake_client.files.create.call_args.kwargs['file']
        self.assertIsInstance(uploaded_file, tuple)
        self.assertEqual(uploaded_file[0], 'resume.pdf')
        self.assertEqual(uploaded_file[1], b'%PDF-1.4 test resume')

    def test_generate_and_save_persists_validated_questions(self):
        with patch.object(questions, 'get_client', return_value=self.fake_client):
            saved_questions = questions.generate_and_save_for_application(
                self.application.pk,
                'Role: Junior Developer',
                'Generate a practical interview question.',
                question_count=1,
            )

        self.assertEqual(len(saved_questions), 1)
        self.assertEqual(saved_questions[0]['application_id'], self.application.pk)
        self.assertEqual(saved_questions[0]['question'], 'Describe a Python project.')
        saved_question = InterviewQuestion.objects.get(pk=saved_questions[0]['id'])
        self.assertEqual(saved_question.expected_answer, 'Explains design choices and testing.')

    def test_save_rejects_invalid_question_before_writing(self):
        invalid_questions = [{
            'question': 'Incomplete question',
            'question_type': 'UNSUPPORTED',
            'weight': 2,
            'expected_answer': '',
        }]

        with self.assertRaises(ValueError):
            questions.save_interview_questions(self.application.pk, invalid_questions)

        self.assertFalse(InterviewQuestion.objects.filter(application=self.application).exists())
