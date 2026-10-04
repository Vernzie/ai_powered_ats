"""Configuration for the AI assistant experiment."""

# Progress note:
# The OpenAI connection, terminal prompt loop, HR instructions, job listing tool,
# and create_new_job tool are working. Tool results are serialized and formatted
# by a second model response. The next step is to continue improving conversational
# context and add any remaining HR tools tomorrow.

import json
import os
import re
from datetime import datetime
from venv import create

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "_core.settings")

import django

django.setup()

from openai import OpenAI
from django.utils import timezone

from job_application.models import Application, Job


JOB_DETAILS_CLEANUP_INSTRUCTIONS = (
    "Before calling create_new_job, clean and map the user's wording to the exact fields: "
    "map Job title/title to title, Full Job Description/description to description, "
    "Job Location/location to location, salary including currency words to a numeric amount, "
    "and Application deadline/deadline to YYYY-MM-DD HH:MM. "
    "Convert natural dates such as '30 September 2026' to '2026-09-30 23:59'. "
    "Do not invent missing values; ask the user for them."
)


# Conversation configuration
MAX_RECENT_CHATS = 5
API_KEY = os.environ.get("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing from the environment or .env file.")

ASSISTANT_INSTRUCTIONS = (
    "You are a helpful assistant for the HR application. "
    "You may respond with your own knowledge about HR recruitment. "
    "When the user asks a specific question about this site, including jobs or applications, "
    "use the available tools instead of guessing. "
    "When the user asks how to create a job, explain the required fields first: title, "
    "description, location, salary, and deadline. Ask for missing fields before creating the job. "
    "Only call create_new_job when all required details are available. "
    f"{JOB_DETAILS_CLEANUP_INSTRUCTIONS}"
)

pre_text = ASSISTANT_INSTRUCTIONS

TOOL_RESULT_INSTRUCTIONS = (
    f"{pre_text} "
    "A tool has been invoked and returned structured data. "
    "Use that data to answer the user's original question clearly and neatly. "
    "Do not show raw JSON, internal tool names, function-call metadata, or technical implementation details. "
    "For job lists, state the total count and present each job with its title, description, location, salary, and deadline. "
    "For job creation guidance, clearly list the required fields and ask the user for any missing values. "
    "If a job was created, confirm the title and database ID."
)

JOB_CREATION_GUIDE = (
    "To create a job, provide these fields:\n"
    "1. Title\n"
    "2. Description\n"
    "3. Location\n"
    "4. Salary\n"
    "5. Deadline in YYYY-MM-DD HH:MM format"
)




# GUI configuration
WINDOW_TITLE = "HR AI Assistant"
WINDOW_SIZE = "700x560"
WINDOW_BACKGROUND = "#f5f1e8"
WINDOW_TEXT_COLOR = "#17222b"
WINDOW_MUTED_COLOR = "#66737b"
WINDOW_ACCENT_COLOR = "#e76445"
WINDOW_ACCENT_DARK_COLOR = "#b8422a"
WINDOW_SURFACE_COLOR = "#fffdf8"




def get_available_jobs():
    """Return every field for jobs whose deadline has not passed."""
    jobs = Job.objects.filter(deadline__gte=timezone.now()).order_by("deadline")
    result = [
        {
            "id": job.id,
            "title": job.title,
            "description": job.description,
            "location": job.location,
            "salary": str(job.salary),
            "posted_date": job.posted_date.isoformat(),
            "deadline": job.deadline.isoformat(),
        }
        for job in jobs
    ]
    return result


def create_new_job(title=None, description=None, location=None, salary=None, deadline=None):
    """Create a job or return the fields still needed to create one."""
    values = {
        "title": title,
        "description": description,
        "location": location,
        "salary": salary,
        "deadline": deadline,
    }
    missing_fields = [field for field, value in values.items() if value in (None, "")]
    if missing_fields:
        return {
            "created": False,
            "missing_fields": missing_fields,
            "guide": JOB_CREATION_GUIDE,
        }

    try:
        salary_value = float(re.sub(r"[^0-9.]", "", str(salary)))
        deadline_formats = (
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d %B %Y",
            "%d %B %Y %H:%M",
            "%d %b %Y",
            "%d %b %Y %H:%M",
        )
        deadline_value = None
        for deadline_format in deadline_formats:
            try:
                deadline_value = datetime.strptime(str(deadline).strip(), deadline_format)
                if deadline_format in {"%Y-%m-%d", "%d %B %Y", "%d %b %Y"}:
                    deadline_value = deadline_value.replace(hour=23, minute=59)
                deadline_value = timezone.make_aware(deadline_value)
                break
            except ValueError:
                continue
        if deadline_value is None:
            raise ValueError
    except (TypeError, ValueError):
        return {
            "created": False,
            "missing_fields": [],
            "guide": "Salary must be a number and deadline must use YYYY-MM-DD HH:MM format.",
        }

    job = Job.objects.create(
        title=title,
        description=description,
        location=location,
        salary=salary_value,
        deadline=deadline_value,
    )
    return {
        "created": True,
        "job_id": job.pk,
        "title": job.title,
    }


tools = [
    {
        "type": "function",
        "name": "get_available_jobs",
        "description": "Return all fields for currently available jobs, including title, description, location, salary, posted date, and deadline.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "create_new_job",
        "description": "Create a new HR job. If fields are missing, return the required-field guide instead of creating a partial job.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Job title."},
                "description": {"type": "string", "description": "Full job description."},
                "location": {"type": "string", "description": "Job location or remote status."},
                "salary": {"type": "string", "description": "Salary amount, for example 85000."},
                "deadline": {"type": "string", "description": "Application deadline in YYYY-MM-DD HH:MM format."},
            },
            "required": [],
            "additionalProperties": False,
        },
    },

]

def ask_ai(prompt):
    """Send a prompt, execute requested local tools, and return the final text response."""
    client = OpenAI(api_key=API_KEY)
    response = client.responses.create(
        model="gpt-4.1-mini",
        instructions=pre_text,
        input=prompt,
        tools=tools,
    )

    tool_outputs = []
    response_input = list(response.output)
    for item in response.output:
        if item.type != "function_call":
            continue

        if item.name == "get_available_jobs":
            result = get_available_jobs()
        elif item.name == "create_new_job":
            arguments = json.loads(item.arguments or "{}")
            result = create_new_job(**arguments)
        else:
            raise ValueError(f"Unknown function requested: {item.name}")

        tool_output = {
            "type": "function_call_output",
            "call_id": item.call_id,
            "output": json.dumps(result, default=str),
        }
        tool_outputs.append(tool_output)

    if tool_outputs:
        response = client.responses.create(
            model="gpt-4.1-mini",
            instructions=TOOL_RESULT_INSTRUCTIONS,
            input=response_input + tool_outputs,
            tools=tools,
        )

    return response.output_text


def main():
    print("HR AI assistant ready. Type 'exit' to quit.")

    while True:
        try:
            prompt = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if prompt.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        if not prompt:
            continue

        try:
            print(f"AI: {ask_ai(prompt)}")
        except Exception as error:
            print(f"AI request failed: {error}")

if __name__ == "__main__":
    main()
