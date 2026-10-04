from django.conf import settings
from django.db import migrations


AI_REVIEWER_USERNAME = 'ai-screening'
AI_REVIEWER_EMAIL = 'ai-screening@system.invalid'


def create_ai_reviewer(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split('.')
    User = apps.get_model(app_label, model_name)
    ScreeningResult = apps.get_model('application_screening', 'ScreeningResult')
    database = schema_editor.connection.alias

    user_fields = {field.name for field in User._meta.get_fields()}
    defaults = {}
    if 'email' in user_fields:
        defaults['email'] = AI_REVIEWER_EMAIL
    if 'first_name' in user_fields:
        defaults['first_name'] = 'AI'
    if 'last_name' in user_fields:
        defaults['last_name'] = 'Screening'
    if 'is_active' in user_fields:
        defaults['is_active'] = False
    if 'is_staff' in user_fields:
        defaults['is_staff'] = False
    if 'is_superuser' in user_fields:
        defaults['is_superuser'] = False
    if 'password' in user_fields:
        defaults['password'] = '!'

    ai_reviewer, _ = User.objects.using(database).get_or_create(
        username=AI_REVIEWER_USERNAME,
        defaults=defaults,
    )
    ScreeningResult.objects.using(database).filter(
        review_method='AI',
        reviewed_by__isnull=True,
    ).update(reviewed_by_id=ai_reviewer.pk)


def clear_ai_reviewer_links(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split('.')
    User = apps.get_model(app_label, model_name)
    ScreeningResult = apps.get_model('application_screening', 'ScreeningResult')
    database = schema_editor.connection.alias
    ai_reviewer = User.objects.using(database).filter(username=AI_REVIEWER_USERNAME).first()
    if ai_reviewer:
        ScreeningResult.objects.using(database).filter(
            review_method='AI',
            reviewed_by_id=ai_reviewer.pk,
        ).update(reviewed_by_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ('application_screening', '0003_screeningresult_review_method_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(create_ai_reviewer, clear_ai_reviewer_links),
    ]
