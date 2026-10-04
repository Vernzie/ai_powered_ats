
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Job(models.Model):
    workflow = models.ForeignKey(
        'pipeline.Workflow',
        on_delete=models.SET_NULL,
        related_name='jobs',
        null=True,
        blank=True,
    )
    screening_threshold = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    title = models.CharField(max_length=100)
    description = models.TextField()

    location = models.CharField(max_length=100)

    salary = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    posted_date = models.DateTimeField(auto_now_add=True)
    deadline = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'main_app_job'

    def __str__(self):
        return self.title


class Criterion(models.Model):
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='criteria',
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=150)

    class Meta:
        db_table = 'main_app_criterion'
        ordering = ('name',)
        verbose_name = 'Criterion'
        verbose_name_plural = 'Criteria'

    def __str__(self):
        if self.job is None:
            return self.name
        return f"{self.job.title} - {self.name}"


class Requirement(models.Model):
    criterion = models.ForeignKey(
        Criterion,
        on_delete=models.CASCADE,
        related_name='requirements'
    )

    description = models.TextField()

    required = models.BooleanField(default=True)

    class Meta:
        db_table = 'main_app_requirement'
        ordering = ('description',)

    def __str__(self):
        return f"{self.criterion.name} - {self.description}"


class Application(models.Model):
    class Status(models.TextChoices):
        RECEIVED = 'RECEIVED', 'Received'
        SCREENED = 'SCREENED', 'Screened'
        SHORTLISTED = 'SHORTLISTED', 'Shortlisted'
        INTERVIEWED = 'INTERVIEWED', 'Interviewed'
        REJECTED = 'REJECTED', 'Rejected'

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='applications'
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='job_applications',
        null=True,
        blank=True,
    )

    applicant_name = models.CharField(max_length=100)

    applicant_email = models.EmailField()

    resume = models.FileField(
        upload_to='resumes/',
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'doc', 'docx']
            )
        ],
    )

    cover_letter = models.FileField(
        upload_to='cover_letters/',
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'doc', 'docx']
            )
        ],
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RECEIVED,
    )

    applied_date = models.DateTimeField(auto_now_add=True)
    shortlisted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'main_app_application'

    def save(self, *args, **kwargs):
        status_changed = self._state.adding
        if self._state.adding:
            if self.status == self.Status.SHORTLISTED and self.shortlisted_at is None:
                self.shortlisted_at = timezone.now()
        else:
            previous_status = type(self).objects.filter(pk=self.pk).values_list('status', flat=True).first()
            status_changed = previous_status != self.status
            if status_changed:
                self.shortlisted_at = (
                    timezone.now()
                    if self.status == self.Status.SHORTLISTED
                    else None
                )

        update_fields = kwargs.get('update_fields')
        if status_changed and update_fields is not None and 'status' in update_fields:
            kwargs['update_fields'] = set(update_fields) | {'shortlisted_at'}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.applicant_name} - {self.job.title}"

