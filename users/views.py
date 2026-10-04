from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django import forms
from django.shortcuts import redirect, render

from .models import UserProfile


def get_user_redirect(user):
	if not user.is_authenticated:
		return 'home'

	if user.is_superuser:
		UserProfile.objects.get_or_create(
			user=user,
			defaults={'role': UserProfile.Role.ADMIN},
		)
		return 'dashboard'

	profile = UserProfile.objects.filter(user=user).first()
	if profile and profile.role == UserProfile.Role.ADMIN:
		return 'dashboard'

	return 'home'


class RegistrationForm(UserCreationForm):
	first_name = forms.CharField(required=True)
	last_name = forms.CharField(required=True)
	email = forms.EmailField(required=True)

	class Meta:
		model = User
		fields = ('first_name', 'last_name', 'username', 'email', 'password1', 'password2')


def login_view(request):
	form = AuthenticationForm(request, data=request.POST or None)
	if request.method == 'POST' and form.is_valid():
		user = form.get_user()
		login(request, user)
		return redirect(get_user_redirect(user))

	return render(request, 'users/login.html', {'form': form})


def register_view(request):
	form = RegistrationForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		user = form.save()
		UserProfile.objects.get_or_create(user=user, defaults={'role': UserProfile.Role.APPLICANT})
		login(request, user)
		return redirect(get_user_redirect(user))

	return render(request, 'users/register.html', {'form': form})


def logout_view(request):
	logout(request)
	return redirect('home')
