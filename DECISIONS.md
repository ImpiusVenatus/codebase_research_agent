# Design Decisions

## Architecture Overview

The system is a synchronous Django REST API backed by SQLite. A single `POST /api/sessions/` clones (or reuses) a GitHub repository, creates a `ResearchSession`, and runs `ResearchAgent` inline before returning JSON.

```text
Client → DRF view → RepositoryService (clone)
                 → ResearchAgent loop
                      ↔ ChainedLLMProvider (Groq → OpenAI → Anthropic)
                      ↔ tool_dispatcher → code_tools / db_tools
                 → ORM (ToolCall, Finding rows)
```

The agent package is **not** a Django app. It holds the loop, tools, and provider adapters so the research logic stays testable without HTTP.

**Provider chain:** Each LLM call goes through `ChainedLLMProvider`. On rate limits or connection errors, the next configured provider is tried. After the first success in a session, that provider is preferred for subsequent calls in the same run. Groq is default (free tier); OpenAI and Anthropic are optional fallbacks requiring their own API keys.

**Context management:** Tool outputs stored in the DB are full length; only truncated text (3,000 characters) is sent back to the model. `list_files` is capped at 80 paths. The agent has a hard limit of 15 tool calls and 60 seconds wall clock.

## Database Schema Rationale

| Model | Purpose |
|-------|---------|
| `Repository` | One row per GitHub URL; stores clone path and `last_indexed_at` for idempotent caching |
| `ResearchSession` | One user question + final answer + status + token usage |
| `ToolCall` | Append-only log of each tool invocation (audit trail for the video demo) |
| `Finding` | Structured citations the agent (or post-processing) saves for cross-session memory |

**Why normalize this way:** Repositories are shared across sessions. Tool calls and findings are heavy one-to-many children — separate tables keep session rows small and allow admin inline views. `get_previous_findings` reads across sessions by repo URL so the agent avoids re-exploring known ground.

**SQLite:** Sufficient for a demo and take-home; no Postgres setup friction. Would move to Postgres with connection pooling at scale.

## Key Design Decisions and Trade-offs

**Synchronous agent in the request.** The brief allows it for a demo. Simple to deploy and reason about, but clients must tolerate 30–90s latency and workers block under load. Production would use Celery + polling or WebSockets.

**Shallow clone (`depth=1`).** Saves time and disk; enough for structure search and reading source. Misses git history and old branches.

**Groq-first, paid fallbacks.** Groq’s free tier fits development and submission cost constraints. When the daily token cap is hit (easy with multi-step agents), OpenAI or Anthropic can take over if keys are present — no code change required.

**Prior findings injected, not tool-called.** Groq models sometimes emit invalid `<function=...>` XML instead of proper tool calls for `get_previous_findings`. Bootstrapping prior findings in the user message avoids that failure mode.

**Auto-save findings from answer text.** Models often skip `save_finding`. A regex pass on `final_answer` creates `Finding` rows for backtick citations so admin and API are not empty.

**Path normalization.** The model frequently passes `repo_cache\owner_repo` instead of `.`. `normalize_repo_relative_path` corrects this before tools run.

**No authentication.** Per brief; API is open on localhost for evaluation.

## What I'd Do Differently With More Time

- **Background jobs** (Celery + Redis) with `GET /api/sessions/<id>/` polling status
- **Postgres** and indexes on `ResearchSession.repository_id`, `Finding.file_path`
- **Semantic search** (embeddings) instead of regex/`rg` only for large monorepos
- **Provider usage field** on `ResearchSession` instead of footer in `final_answer`
- **Streaming** partial answers to the client
- **Stricter tool budget per tool type** (e.g. one `list_files` at root only)

## How I Used AI Coding Tools

This project was built with **Cursor** (Claude) in phased prompts matching the take-home structure: scaffold → models → clone service → tools → agent loop → API → seed/docs.

**What AI generated:** Initial Django scaffold, model definitions, tool implementations, Groq agent loop, DRF serializers/views, README structure, and much of the provider-chain refactor.

**What I edited manually:** Environment secrets, Groq rate-limit debugging, Postman testing, admin UX for the demo video, and honesty checks on agent answers (e.g. Click `main` at line 1347 vs class definition at 903).

**What worked well:** Fast iteration on boilerplate; tool schema design; fixing Groq `tool_use_failed` with preloaded findings and malformed-call recovery.

**What did not:** Letting the model choose `repo_cache/...` paths wasted tokens; running `seed_demo` repeatedly burned the free Groq daily cap quickly.

*Edit this section before submit so it reflects your actual workflow.*

## Limitations and Known Issues

- **Groq free tier:** ~100k tokens/day; multi-step sessions use 15k–30k+ each
- **Sync API:** Long-running POSTs; no progress indicator
- **Answer quality:** Depends on model; may cite overload signatures instead of implementation
- **Findings:** Auto-extraction is heuristic, not AST-based
- **Private repos:** Not supported (public clone URLs only)
- **No frontend:** API + Django admin only
- **Tool-call format:** Groq occasionally needs retry/recovery; Anthropic/OpenAI are more reliable but paid
