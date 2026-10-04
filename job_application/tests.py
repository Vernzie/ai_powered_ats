import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Application, Job


class JobApplicationFlowTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username='avery_applicant',
			email='avery@example.com',
			password='test-password',
			first_name='Avery',
			last_name='Applicant',
		)
		self.job = Job.objects.create(
			title='Product Designer',
			description='Design useful products.',
			location='Remote',
			salary='95000.00',
			deadline=timezone.now() + timedelta(days=30),
		)

	def test_applying_persists_application_and_uploaded_documents(self):
		self.client.force_login(self.user)
		with tempfile.TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				response = self.client.post(
					reverse('apply_job', args=[self.job.pk]),
					{
						'applicant_email': self.user.email,
						'resume': SimpleUploadedFile('resume.pdf', b'resume contents', content_type='application/pdf'),
						'cover_letter': SimpleUploadedFile('cover-letter.pdf', b'letter contents', content_type='application/pdf'),
					},
				)

		self.assertRedirects(response, reverse('job_detail', args=[self.job.pk]))
		application = Application.objects.get(job=self.job, user=self.user)
		self.assertEqual(application.applicant_name, 'Avery Applicant')
		self.assertEqual(application.applicant_email, self.user.email)
		self.assertTrue(application.resume.name.endswith('resume.pdf'))
		self.assertTrue(application.cover_letter.name.endswith('cover-letter.pdf'))
