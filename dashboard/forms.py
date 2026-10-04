from django import forms
from django.forms import formset_factory

from job_application.models import Application, Job, Requirement


class JobForm(forms.ModelForm):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields['deadline'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M']

	class Meta:
		model = Job
		fields = ('title', 'description', 'location', 'salary', 'deadline')
		widgets = {
			'deadline': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
		}


class RequirementForm(forms.ModelForm):
	class Meta:
		model = Requirement
		fields = ('description', 'required')
		widgets = {
			'description': forms.TextInput(attrs={'placeholder': 'e.g. Python experience'}),
		}


class ApplicationManagementForm(forms.ModelForm):
	class Meta:
		model = Application
		fields = ('applicant_name', 'applicant_email', 'status')


RequirementFormSet = formset_factory(
	RequirementForm,
	extra=1,
	can_delete=False,
)
