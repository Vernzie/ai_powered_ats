from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('job_application', '0013_application_shortlisted_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='application',
            name='status',
            field=models.CharField(
                choices=[
                    ('RECEIVED', 'Received'),
                    ('SCREENED', 'Screened'),
                    ('SHORTLISTED', 'Shortlisted'),
                    ('INTERVIEWED', 'Interviewed'),
                    ('REJECTED', 'Rejected'),
                ],
                default='RECEIVED',
                max_length=20,
            ),
        ),
    ]