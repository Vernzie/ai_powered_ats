from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('job_application', '0014_application_interviewed_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='screening_threshold',
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[MinValueValidator(0), MaxValueValidator(100)],
            ),
        ),
    ]