from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ApplicationForm
from .models import Job


def home(request):
	jobs = Job.objects.order_by('-posted_date')
	return render(request, 'pages/home.html', {'jobs': jobs})


def job_detail(request, pk):
	job = get_object_or_404(
		Job.objects.prefetch_related('criteria__requirements'),
		pk=pk,
	)
	return render(request, 'pages/job_details.html', {
		'job': job,
		'criteria': job.criteria.all(),
	})


@login_required
def apply_job(request, pk):
	job = get_object_or_404(Job, pk=pk)

	if request.method == 'POST':
		form = ApplicationForm(request.POST, request.FILES)
		if form.is_valid():
			application = form.save(commit=False)
			application.job = job
			application.user = request.user
			application.applicant_name = request.user.get_full_name() or request.user.username
			application.save()
			return redirect('job_detail', pk=job.pk)
	else:
		form = ApplicationForm(initial={'applicant_email': request.user.email})

	return render(request, 'pages/apply_now.html', {'form': form, 'job': job})
