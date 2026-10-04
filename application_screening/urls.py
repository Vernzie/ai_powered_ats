from django.urls import path

from . import views


urlpatterns = [
    path('', views.screen_applications, name='screen_applications'),
    path('job/<int:job_id>/', views.job_screening, name='job_screening'),
    path('job/<int:job_id>/application/<int:application_id>/', views.application_screening_result, name='application_screening_result'),
    path('run/', views.run_screening, name='run_screening'),
]