import os
import time
from datetime import timedelta
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE', '_core.settings')
import django
django.setup()
from django.utils import timezone
from job_application.models import Job, Criterion, Requirement, Application
from screening import stream_screening
job = Job.objects.create(title='Test Job', description='desc', location='Remote', salary='123', deadline=timezone.now()+timedelta(days=7))
criterion = Criterion.objects.create(job=job, name='Python')
Requirement.objects.create(criterion=criterion, description='Strong Python skills', required=True)
path = Path('tmp_test_resume.pdf')
path.write_bytes(b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF')
app = Application.objects.create(job=job, applicant_name='Test User', applicant_email='x@y.com', resume='tmp_test_resume.pdf', cover_letter='tmp_cover.pdf', status=Application.Status.RECEIVED)
start = time.time(); count = 0
for event in stream_screening(job, application_ids=[app.id]):
    print(event.get('type'), event)
    count += 1
    if count >= 6:
        break
    if time.time() - start > 90:
        print('TIMEOUT')
        break
print('done count', count, 'elapsed', time.time()-start)
