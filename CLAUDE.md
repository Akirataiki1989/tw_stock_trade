# tw_stock_trade — Claude Working Guide

## Project Overview
Taiwan stock AI simulation trading platform backend. FastAPI + PostgreSQL + Redis + LangGraph.
Frontend (React) is deployed independently on Vercel; this project is pure backend.

## Environment

| Item | Value |
|------|-------|
| NAS Path | `/volume1/web/codeserver/tw_stock_trade` |
| Python | 3.12 (NAS local) |
| Package Manager | `uv` (must run on NAS DSM terminal, not from Windows or code-server) |
| uv binary (NAS DSM) | `/volume1/web/codeserver/.tools/uv` (copied from code-server container) |
| venv | `.venv/bin/python`, `.venv/bin/alembic` |
| App Port | `8090` (8000 is occupied) |

### Common Commands
```bash
# NAS DSM SSH：每次 session 必須先設定環境變數
export PATH="/volume1/web/codeserver/.tools:$PATH"
export UV_CACHE_DIR=/volume1/web/codeserver/.uv-cache
export UV_DATA_DIR=/volume1/web/codeserver/.uv-data
export UV_PYTHON_INSTALL_DIR=/volume1/web/codeserver/.uv-python

# Install dependencies
uv sync --dev

# DB migration
.venv/bin/alembic upgrade head
.venv/bin/alembic downgrade base

# Ruff check
uv run ruff check app/

# Start dev server (NAS DSM)
uv run uvicorn app.main:app --host 0.0.0.0 --port 8090
```

## Tech Stack

| Layer | Package |
|-------|---------|
| Web | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| Migration | Alembic (async engine) |
| Auth | fastapi-users (JWT) |
| Task Queue | ARQ + Redis |
| AI | LangGraph + LangChain + Google Gemini |
| Monitoring | Langfuse |
| Scheduler | APScheduler |
| Encryption | Fernet (AES-256, for storing API Keys) |

## Known Limitations & Conventions

- `model_config` in pydantic-settings must not have a type annotation, or it will be treated as a field
- `arq` requires `redis<6`; do not explicitly pin the redis version in pyproject.toml
- `uv sync` must run on the NAS terminal; running from Windows creates a Windows-format venv (no `bin/`)
- Ruff `line-length = 100`, `select = ["E", "F", "I"]`
- All model `__table_args__` must include `{"schema": "market"}` or `{"schema": "trading"}`
- When UniqueConstraint is present: `__table_args__ = (UniqueConstraint(...), {"schema": "trading"})`
- NAS DSM home dir (`/var/services/homes/Gui`) has filesystem issues; all uv dirs must be redirected to `/volume1/` via env vars
- App runs directly on NAS DSM (not Docker); Docker Compose step is skipped; use Synology Task Scheduler for process management

## Working Style

### Communication
- All responses must be in **Traditional Chinese**
- For changes to 2+ files or any architectural decision, present a plan first and wait for explicit confirmation before proceeding

### Proactive Pushback
In the following cases, **raise a discussion first — do not execute directly**:
- Logically inconsistent or contradictory requirements
- Non-professional development practices (e.g. skipping tests, directly modifying production schema)
- Plans that deviate from the main development roadmap (e.g. features not yet scheduled in current phase)
- Technology choices that conflict with the existing tech stack

### Docs Maintenance
When a development stage (roadmap Step) is complete, **proactively ask the user whether to update the docs**:
- `docs/overview.md` — update status table (✅ / 🔜 / ⏳) and code map section
- `docs/codemap/` — add a new `.md` for each newly created source file
- `docs/codemap/directory.md` — update the directory tree index
- `docs/progress/roadmap.md` — mark completed tasks, set next step
- `docs/changelog/` — add new version entry

### Tool Usage
- For library documentation, use context7 MCP first (`resolve-library-id` + `query-docs`); do not rely on training data
- For Python type issues, use the `LSP` tool (pyright-lsp is enabled)
- For read-then-edit tasks (lint fixes, batch formatting, template-based edits): spawn a sub-agent with `model: haiku` to handle the work — do not consume main context for mechanical edits

## Docs Index

All detailed docs are in `docs/`.

**New sessions: start with `docs/overview.md`** — one file covering current status, code map, DB structure, and drill-down links.

| Need | File Path |
|------|-----------|
| **Project status / quick overview** | **`docs/overview.md`** |
| DB ORM class ↔ table, FK diagram | `docs/schema/orm.md` |
| DB column full specs | `docs/schema/tables.md` |
| Code directory / file CodeMap | `docs/codemap/directory.md` |
| API endpoint specs | `docs/api.md` |
| Dev progress / task dependencies | `docs/progress/roadmap.md` |
| Version update summary | `docs/changelog/Index.md` |
