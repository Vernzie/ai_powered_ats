from django.core.validators import MinValueValidator
from django.db import models

from job_application.models import Application


class InterviewQuestion(models.Model):
    class QuestionType(models.TextChoices):
        GENERAL = 'GENERAL', 'General'
        SPECIFIC = 'SPECIFIC', 'Specific'

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='interview_questions',
    )
    question = models.TextField()
    expected_answer = models.TextField(blank=True)
    question_type = models.CharField(
        max_length=8,
        choices=QuestionType.choices,
        default=QuestionType.GENERAL,
    )
    weight = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )

    def __str__(self):
        return f'{self.application.applicant_name}: {self.question[:80]}'


class InterviewAnswer(models.Model):
    question = models.ForeignKey(
        InterviewQuestion,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    answer = models.TextField()

    def __str__(self):
        return f'Answer to interview question {self.question_id}'