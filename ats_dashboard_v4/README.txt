ATLAS ATS MULTI-PAGE PROTOTYPE

Open index.html.

Pages:
index.html             Dashboard
jobs.html              All jobs
job.html?id=1          Individual job / job control center
applications.html      Global applications
applications.html?job=1 Applications filtered to a job
application.html?id=101 Individual application
interviews.html        Interview manager
workflows.html         Workflow configuration
settings.html          System settings

The local demo uses query parameters so it works by opening index.html directly.

TARGET DJANGO ROUTES
--------------------
In the real Django application, the same navigation concepts can map to:

/                       dashboard
/jobs/                  jobs list
/jobs/<int:id>/         individual job
/jobs/<int:id>/applications/
/applications/          global applications
/applications/<int:id>/ individual application
/interviews/
/workflows/
/settings/

The prototype intentionally keeps the URL/resource relationship visible:
Job pages own their applications and workflow.
Application pages link back to their job.
Workflow changes are job-level.
Application status/history is application-level.

The JavaScript currently uses mock data only. Replace the mock actions with Django forms,
views, POST endpoints or fetch() calls when wiring the backend.
