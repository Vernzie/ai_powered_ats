from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import UserProfile


class RegistrationFlowTests(TestCase):
	def test_registration_creates_an_applicant_profile_and_signs_user_in(self):
		response = self.client.post(reverse('register'), {
			'first_name': 'Avery',
			'last_name': 'Applicant',
			'username': 'avery_applicant',
			'email': 'avery@example.com',
			'password1': 'Zp7!aV9#kQ2mLx',
			'password2': 'Zp7!aV9#kQ2mLx',
		})

		self.assertRedirects(response, reverse('home'))
		user = get_user_model().objects.get(username='avery_applicant')
		self.assertEqual(user.profile.role, UserProfile.Role.APPLICANT)
		self.assertTrue(response.wsgi_request.user.is_authenticated)
