from django.conf import settings
from django.db import models

from job_application.models import Application, Requirement


class ScreeningResult(models.Model):
    class ReviewMethod(models.TextChoices):
        AI = 'AI', 'AI-assisted'
        MANUAL = 'MANUAL', 'Manual'

    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        related_name="screening_result"
    )

    file_id = models.CharField(max_length=255, blank=True, null=True)
    overall_score = models.PositiveIntegerField()
    overall_comments = models.TextField()
    review_method = models.CharField(
        max_length=10,
        choices=ReviewMethod.choices,
        default=ReviewMethod.AI,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='screening_results',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)


class ScreeningCriterionResult(models.Model):
    screening = models.ForeignKey(
        ScreeningResult,
        on_delete=models.CASCADE,
        related_name='criteria'
    )

    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE
    )

    assessment = models.CharField(max_length=50)
    score = models.PositiveIntegerField()
    evidence = models.TextField()