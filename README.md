# Codebase Research Agent

A Django + DRF take-home project for asking natural-language questions about GitHub repositories. Users submit a repository URL and a question; an LLM agent explores the cloned codebase with tools and persists sessions, tool calls, and findings.

## Setup

Clone the project:

```bash
git clone <repo-url>
cd <repo-directory>
```

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/Scripts/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create local environment variables:

```bash
cp .env.example .env
```

Run migrations:

```bash
python manage.py migrate
```

Start the development server:

```bash
python manage.py runserver
```

## Example Request

The API is added in a later phase. The intended request shape is:

```bash
curl -X POST http://127.0.0.1:8000/api/sessions/ \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/example/project",
    "question": "Where is authentication handled?"
  }'
```
