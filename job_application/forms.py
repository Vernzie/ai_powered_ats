from django import forms

from .models import Application


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['applicant_email', 'resume', 'cover_letter']
        widgets = {
            'applicant_email': forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
            'resume': forms.ClearableFileInput(attrs={'accept': '.pdf,.doc,.docx'}),
            'cover_letter': forms.ClearableFileInput(attrs={'accept': '.pdf,.doc,.docx'}),
        }