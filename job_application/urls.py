from django.urls import path

from . import views


urlpatterns = [
    path('', views.home, name='home'),
    path('home/job/<int:pk>/', views.job_detail, name='job_detail'),
    path('home/job/<int:pk>/apply/', views.apply_job, name='apply_job'),
]