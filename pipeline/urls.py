from django.urls import path

from .views import workflow_index

urlpatterns = [
    path('', workflow_index, name='workflow_index'),
]
