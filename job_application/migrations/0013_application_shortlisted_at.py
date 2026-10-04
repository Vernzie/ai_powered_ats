from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('job_application', '0012_job_is_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='application',
            name='shortlisted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]