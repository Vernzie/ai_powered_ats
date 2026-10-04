from django.urls import path

from .views import (
    application_review,
    application_review_resume,
    application_shortlist,
    add_shortlisted_to_interviews,
    interviewed_applications,
    prepare_interview,
    create_interview_question,
    interview_question_detail,
    generate_interview_questions_for_application,
    dashboard_workspace,
)


urlpatterns = [
    path('', dashboard_workspace, name='dashboard_workspace'),
    path('<int:job_id>/review/', application_review, name='workspace_application_review'),
    path(
        '<int:job_id>/review/<int:application_id>/resume/',
        application_review_resume,
        name='workspace_application_review_resume',
    ),
    path('<int:job_id>/shortlist/', application_shortlist, name='workspace_application_shortlist'),
    path('<int:job_id>/interviews/', interviewed_applications, name='workspace_interviewed_applications'),
    path('<int:job_id>/interviews/<int:application_id>/prepare/', prepare_interview, name='workspace_prepare_interview'),
    path('<int:job_id>/interviews/<int:application_id>/questions/', create_interview_question, name='workspace_interview_question_create'),
    path('<int:job_id>/interviews/<int:application_id>/questions/generate/', generate_interview_questions_for_application, name='workspace_generate_interview_questions'),
    path('<int:job_id>/interviews/<int:application_id>/questions/<int:question_id>/', interview_question_detail, name='workspace_interview_question_detail'),
    path('<int:job_id>/interviews/add/', add_shortlisted_to_interviews, name='workspace_add_shortlisted_to_interviews'),
    path('<int:job_id>/', dashboard_workspace, name='dashboard_workspace_job'),
]