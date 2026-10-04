"""Create sample Applicant users and applications for the ATS demo."""

import os
from io import BytesIO

os.environ.setdefault('DJANGO_SETTINGS_MODULE', '_core.settings')

import django

django.setup()

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from job_application.models import Application, Job
from users.models import UserProfile


SAMPLE_APPLICANTS = [
	{
		'first_name': 'Mila', 'last_name': 'Kuman', 'years': 8,
		'degree': 'BSc Computer Science', 'python': 'Python, Django, Flask',
		'databases': 'PostgreSQL, MySQL', 'web': 'Django, React, REST APIs',
		'extras': 'Mentored five developers; led code reviews; Docker, CI/CD, AWS, automated testing, Agile/Scrum, Git, cybersecurity practices.',
	},
	{
		'first_name': 'Jonah', 'last_name': 'Wai', 'years': 6,
		'degree': 'Bachelor of Information Technology', 'python': 'Python, Django REST Framework',
		'databases': 'PostgreSQL, MySQL', 'web': 'Django, React, REST APIs',
		'extras': 'Conducted code reviews and mentored junior staff; Docker, CI/CD, cloud deployment, automated testing, Agile/Scrum, Git, application security.',
	},
	{
		'first_name': 'Lani', 'last_name': 'Toviri', 'years': 7,
		'degree': 'BEng Software Engineering', 'python': 'Python, Flask, Django',
		'databases': 'PostgreSQL, Oracle', 'web': 'Flask, React, REST APIs',
		'extras': 'Provided technical guidance to a small team; design patterns, Docker, CI/CD, Azure, automated testing, Scrum, Git, security reviews.',
	},
	{
		'first_name': 'Peter', 'last_name': 'Amoa', 'years': 5,
		'degree': 'BSc Information Technology', 'python': 'Python, Django',
		'databases': 'MySQL, PostgreSQL', 'web': 'Django, React, REST APIs',
		'extras': 'Reviewed pull requests and supported two junior developers; Docker, GitHub Actions, automated tests, Scrum, cloud fundamentals, secure coding.',
	},
	{
		'first_name': 'Ruth', 'last_name': 'Kila', 'years': 9,
		'degree': 'BSc Computer Science', 'python': 'Python, Django REST Framework',
		'databases': 'PostgreSQL, Oracle', 'web': 'Django, React, REST APIs',
		'extras': 'Technical lead and mentor; scalable architecture, Docker, CI/CD, AWS, automated testing, Agile/Scrum, GitHub, cybersecurity best practices.',
	},
	{
		'first_name': 'Eli', 'last_name': 'Namo', 'years': 6,
		'degree': 'Bachelor of Software Engineering', 'python': 'Python, Flask',
		'databases': 'PostgreSQL, MySQL', 'web': 'Flask, React, REST APIs',
		'extras': 'Led code reviews and mentored graduates; Docker, CI/CD, GCP, automated testing, Scrum, Git, secure API development.',
	},
	{
		'first_name': 'Sera', 'last_name': 'Malo', 'years': 3,
		'degree': 'BSc Information Technology', 'python': 'Python, Django',
		'databases': 'MySQL', 'web': 'Django, basic React',
		'extras': 'Contributed to team code reviews; Git and introductory automated testing. Seeking opportunities to grow into technical leadership.',
	},
	{
		'first_name': 'Daniel', 'last_name': 'Kopi', 'years': 4,
		'degree': 'Diploma in Web Development', 'python': 'Python basics',
		'databases': 'SQLite, MySQL', 'web': 'Flask, JavaScript',
		'extras': 'Built small web applications and collaborated with a development team; limited production experience with cloud and CI/CD.',
	},
	{
		'first_name': 'Ava', 'last_name': 'Bundi', 'years': 2,
		'degree': 'BSc Business Information Systems', 'python': 'Python coursework',
		'databases': 'MySQL coursework', 'web': 'HTML, CSS, introductory Django',
		'extras': 'Junior developer with academic team projects; introductory Git and manual testing. No professional mentoring experience yet.',
	},
	{
		'first_name': 'Noah', 'last_name': 'Sengi', 'years': 5,
		'degree': 'BSc Computer Science', 'python': 'Python, Django',
		'databases': 'PostgreSQL', 'web': 'Django, REST APIs',
		'extras': 'Strong individual contributor; supports peer reviews. Some automated testing and Git experience; limited React, Docker, and cloud experience.',
	},
]


def create_applicant_user(*, username, password=None, **user_fields):
	"""Create an authentication user and its Applicant profile."""
	user_model = get_user_model()
	user = user_model.objects.create_user(
		username=username,
		password=password,
		**user_fields,
	)
	UserProfile.objects.create(user=user, role=UserProfile.Role.APPLICANT)
	return user


def _make_resume_pdf(applicant):
	"""Build a small, clearly fictional PDF resume for a sample applicant."""
	buffer = BytesIO()
	pdf = canvas.Canvas(buffer, pagesize=A4)
	width, height = A4

	lines = [
		('SAMPLE RESUME - FICTIONAL CANDIDATE', 15),
		(f"{applicant['first_name']} {applicant['last_name']}", 13),
		(f"{applicant['first_name'].lower()}.{applicant['last_name'].lower()}@example.test", 10),
		('Senior Software Developer Applicant | Port Moresby, Papua New Guinea', 10),
		('', 10),
		('PROFILE', 11),
		(f"{applicant['years']} years of professional software development experience. Focused on reliable web applications, team collaboration, and maintainable software.", 10),
		('', 10),
		('EDUCATION', 11),
		(applicant['degree'], 10),
		('', 10),
		('TECHNICAL EXPERIENCE', 11),
		(f"Programming: {applicant['python']}", 10),
		(f"Web and APIs: {applicant['web']}", 10),
		(f"Databases: {applicant['databases']}", 10),
		(applicant['extras'], 10),
		('', 10),
		('SELECTED WORK', 11),
		('Designed and maintained web application features, integrated APIs, investigated defects, and collaborated with product and engineering teammates.', 10),
	]

	y = height - 55
	for value, font_size in lines:
		if not value:
			y -= 10
			continue
		pdf.setFont('Helvetica-Bold' if font_size >= 11 else 'Helvetica', font_size)
		# Simple word wrapping keeps the generated document readable.
		words = value.split()
		row = ''
		for word in words:
			candidate = f'{row} {word}'.strip()
			if pdf.stringWidth(candidate, pdf._fontname, font_size) > width - 100 and row:
				pdf.drawString(50, y, row)
				y -= font_size + 5
				row = word
			else:
				row = candidate
		if row:
			pdf.drawString(50, y, row)
			y -= font_size + 8
		if y < 60:
			pdf.showPage()
			y = height - 55
		pdf.setFont('Helvetica', 10)

	pdf.save()
	return buffer.getvalue()


@transaction.atomic
def create_sample_applications():
	"""Create ten sample applicants and applications for the named job."""
	jobs = Job.objects.filter(title__iexact='Senior Software Developer')
	if jobs.count() != 1:
		raise LookupError(
			f"Expected one 'Senior Software Developer' job, found {jobs.count()}."
		)
	job = jobs.get()
	user_model = get_user_model()
	created = []

	for applicant in SAMPLE_APPLICANTS:
		first_name = applicant['first_name']
		last_name = applicant['last_name']
		username = f"sample_{first_name.lower()}_{last_name.lower()}"
		email = f"{first_name.lower()}.{last_name.lower()}@example.test"
		user = user_model.objects.filter(username=username).first()
		if user is None:
			user = create_applicant_user(
				username=username,
				password='SampleApplicant2026!',
				first_name=first_name,
				last_name=last_name,
				email=email,
			)
		else:
			UserProfile.objects.get_or_create(
				user=user,
				defaults={'role': UserProfile.Role.APPLICANT},
			)

		application, was_created = Application.objects.get_or_create(
			job=job,
			user=user,
			defaults={
				'applicant_name': f'{first_name} {last_name}',
				'applicant_email': email,
				'resume': '',
				'cover_letter': '',
			},
		)
		if was_created:
			pdf_bytes = _make_resume_pdf(applicant)
			filename = f'{username}_resume.pdf'
			application.resume.save(filename, ContentFile(pdf_bytes), save=False)
			application.cover_letter.save(
				f'{username}_cover_letter.pdf', ContentFile(pdf_bytes), save=False
			)
			application.save()
		created.append((user, application, was_created))

	return job, created


def main():
	job, applications = create_sample_applications()
	new_count = sum(1 for _, _, was_created in applications if was_created)
	print(f'Job: {job.title} (ID {job.pk})')
	print(f'Applications created: {new_count}; sample applicants processed: {len(applications)}')
	for user, application, was_created in applications:
		state = 'created' if was_created else 'already existed'
		print(f'  {user.first_name} {user.last_name}: {application} ({state})')


if __name__ == '__main__':
	main()
