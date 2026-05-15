# Codebase Research Agent

A Django + DRF backend that answers natural-language questions about GitHub repositories. You POST a repo URL and a question; an LLM agent explores the cloned codebase with tools and persists every session, tool call, and finding to SQLite.

Built for the [CodeFusion AI](https://www.codefusionai.com) senior backend take-home.

## How it works

```text
POST /api/sessions/  →  clone repo  →  agent loop (tools + LLM)  →  JSON response
                              ↓
                         SQLite (sessions, tool_calls, findings)
```

1. **Clone** the repository into `repo_cache/` (shallow, depth=1).
2. **Agent** calls tools (`list_files`, `search_code`, `read_file`, etc.) in a loop.
3. **Persist** tool calls, findings, and the final answer.
4. **Return** the full session as JSON (sync request, up to ~60 seconds).

LLM providers are tried in order (`LLM_PROVIDER_ORDER`). If Groq hits a rate limit, OpenAI or Anthropic is used automatically when configured.

## Requirements

- Python 3.11+
- Git
- **At least one** LLM API key (Groq recommended — free tier)
- Optional: [ripgrep](https://github.com/BurntSushi/ripgrep) (`rg`) for faster code search

## Setup

```bash
git clone <your-repo-url>
cd <repo-directory>

python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
# .venv\Scripts\activate        # Windows CMD/PowerShell

pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` — set **at least one** provider key:

```env
LLM_PROVIDER_ORDER=groq,openai,anthropic

GROQ_API_KEY=gsk_...          # free tier at console.groq.com
GROQ_MODEL=llama-3.3-70b-versatile

OPENAI_API_KEY=sk-...         # optional fallback
OPENAI_MODEL=gpt-4o-mini

ANTHROPIC_API_KEY=sk-ant-...  # optional fallback
ANTHROPIC_MODEL=claude-3-5-haiku-20241022

REPO_CACHE_DIR=./repo_cache
```

```bash
python manage.py migrate
python manage.py runserver
```

## LLM providers

| Provider | Cost | Role | Notes |
|----------|------|------|--------|
| **Groq** | Free tier (daily token cap) | Default | Fast; uses OpenAI-compatible API |
| **OpenAI** | Paid | Fallback | Used when Groq fails or is unconfigured |
| **Anthropic** | Paid | Fallback | Claude Haiku; native Messages API |

- Order is controlled by `LLM_PROVIDER_ORDER` (comma-separated).
- Providers without an API key are skipped.
- The response `final_answer` includes which provider succeeded: `_(LLM provider: groq)_`.

## API (Postman / curl)

Base URL: `http://127.0.0.1:8000`

> **Tip:** In Postman, set request timeout to **120 seconds** — research runs synchronously.

### Start research

`POST /api/sessions/`

```json
{
  "repo_url": "https://github.com/pallets/click",
  "question": "Where is the main CLI entry point defined?"
}
```

Returns `201` with full session: `final_answer`, `tool_calls`, `findings`, token counts.

### Get session

`GET /api/sessions/<id>/`

Use the `id` from the POST response. Older failed sessions may exist from earlier runs.

### List sessions for a repository

`GET /api/repositories/<repo_id>/`

`repo_id` is the `repository_id` field from a session response.

### Errors

| Status | Meaning |
|--------|---------|
| `500` | No LLM API keys configured |
| `503` | All configured providers failed (e.g. Groq rate limit and no fallback keys) |

Response body includes `providers_tried` with per-provider error messages.

## Management commands

```bash
# Clone a repo without running the agent
python manage.py clone_repo https://github.com/pallets/click

# Remove failed sessions from broken early runs
python manage.py cleanup_failed_sessions

# Seed demo data (4 agent runs; uses API quota)
python manage.py seed_demo
```

## Django Admin

Admin is a web UI to **view** persisted data (not to start research).

```bash
python manage.py createsuperuser
python manage.py runserver
```

Open **http://127.0.0.1:8000/admin/**

| Section | Purpose |
|---------|---------|
| **Research sessions** | Click a session → see answer, tool calls, findings on one page |
| **Repositories** | Cloned repos and session counts |
| **Tool calls** | Global list of agent steps |
| **Findings** | File citations |

**Workflow for demos:** run `POST /api/sessions/` in Postman → note `id` → open that session in admin.

## Tests

```bash
python manage.py test
```

## Project layout

```text
coderesearch/       Django settings, URLs
repositories/       Repository model, clone service
research/           API, admin, management commands
agent/              Agent loop, tools, LLM provider chain
  providers/        Groq, OpenAI, Anthropic adapters
  tools/            Code exploration + DB tools
repo_cache/         Cloned repos (gitignored)
```

## Troubleshooting

**Groq `429` / rate limit** — Free tier is ~100k tokens/day. Use existing sessions via `GET` for demos, add `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` as fallback, or wait for daily reset.

**`503` all providers failed** — Check `.env` keys and `LLM_PROVIDER_ORDER`. Response lists `providers_tried`.

**Empty `findings`** — Citations are auto-extracted from `final_answer` when the model skips `save_finding`.

**Wrong session id** — Always use the `id` returned by your latest POST, not `1`.

## Design notes

See [DECISIONS.md](DECISIONS.md) for architecture, schema rationale, and trade-offs.
