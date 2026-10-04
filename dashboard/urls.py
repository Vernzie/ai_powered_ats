from django.urls import include, path

from application_screening.views import (
    application_screening_result,
    job_screening,
    job_screening_results,
    job_screening_results_data,
    run_screening,
    screen_applications,
	screen_application,
    stream_screening_job,
)

from . import views


urlpatterns = [
	path('workspace/', include('workspace.urls')),
	path('', views.dashboard, name='dashboard'),
	path('atlas/<str:page>/', views.dashboard_atlas_page, name='dashboard_atlas_page'),
	path('overview/', views.dashboard_overview, name='dashboard_overview'),
	path('application/<int:application_id>/screen/', screen_application, name='dashboard_screen_application'),
	path('jobs/', views.dashboard_jobs, name='dashboard_jobs'),
	path('applications/', views.dashboard_applications, name='dashboard_applications'),
	path('job/', views.dashboard_job_page, name='dashboard_job_page'),
	path('application/', views.dashboard_application_page, name='dashboard_application_page'),
	path('interviews/', views.dashboard_interviews, name='dashboard_interviews'),
	path('workflows/', views.dashboard_workflows, name='dashboard_workflows'),
	path('settings/', views.dashboard_settings, name='dashboard_settings'),
	path('review/', screen_applications, name='dashboard_review'),
	path('review/job/<int:job_id>/', job_screening, name='dashboard_review_job'),
	path('review/job/<int:job_id>/results/', job_screening_results, name='dashboard_review_results'),
	path('review/job/<int:job_id>/results/data/', job_screening_results_data, name='dashboard_review_results_data'),
	path('review/job/<int:job_id>/stream/', stream_screening_job, name='dashboard_review_stream'),
	path('review/job/<int:job_id>/application/<int:application_id>/', application_screening_result, name='dashboard_review_application_result'),
	path('review/run/', run_screening, name='dashboard_review_run'),
	path('workflow/', views.dashboard_workflow, name='dashboard_workflow'),
	path('screening/', screen_applications, name='dashboard_screening'),
	path('screening/job/<int:job_id>/', job_screening, name='dashboard_job_screening'),
	path('screening/job/<int:job_id>/results/', job_screening_results, name='dashboard_job_screening_results'),
	path('screening/job/<int:job_id>/results/data/', job_screening_results_data, name='dashboard_job_screening_results_data'),
	path('screening/job/<int:job_id>/stream/', stream_screening_job, name='dashboard_screening_stream'),
	path('screening/job/<int:job_id>/application/<int:application_id>/', application_screening_result, name='dashboard_application_screening_result'),
	path('screening/run/', run_screening, name='dashboard_run_screening'),
	path('job/new/', views.job_create, name='job_create'),
	path('job/new/review/', views.job_review, name='job_review'),
	path('job/new/requirements/add/', views.add_job_requirement, name='add_job_requirement'),
	path('job/<int:pk>/', views.admin_job_detail, name='admin_job_detail'),
	path('job/<int:pk>/edit/', views.job_update, name='job_update'),
	path('job/<int:job_pk>/requirement/<int:pk>/delete/', views.requirement_delete, name='requirement_delete'),
	path('job/<int:pk>/delete/', views.job_delete, name='job_delete'),
]
