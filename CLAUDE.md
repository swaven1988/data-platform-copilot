# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Enterprise-grade GenAI Copilot that converts natural language requirements into data pipelines (PySpark jobs, Airflow DAGs, SQL). Python 3.10+ required.

## Common Commands

```bash
# Development
make api          # Run FastAPI server on port 8001
make ui           # Run Streamlit dashboard
make ci           # Run all pytest tests

# Testing
python -m pytest -q                                # All tests
python -m pytest tests/test_<name>.py             # Single test file
python -m pytest tests/test_<name>.py::test_fn    # Single test function

# Release tooling
make snapshot              # Regenerate OpenAPI snapshot
make verify-snapshot       # Verify OpenAPI snapshot matches current API
make manifest              # Generate packaging manifest
make manifest-check        # Validate packaging manifest (run in CI)
python tools/check_v1_readiness.py  # V1 readiness gate check

# Docker (dev)
docker compose -f deploy/docker-compose.dev.yml up -d --build

# Docker (prod)
docker compose -f deploy/docker-compose.prod.yml up -d --build
# Access via nginx gateway: http://localhost:8080
# Health check: curl http://127.0.0.1:8080/api/v1/health/live -H "Authorization: Bearer dev_admin_token"
```

## Code Style

- Black + Ruff, 100-character line length (`E`, `F`, `I` ruff checks)
- No special formatter config needed beyond `pyproject.toml`

## Architecture

### Layered Processing Flow

```
User Input (NL Requirements)
        ↓
Intent Parser (app/core/compiler/)    ← converts text to CopilotSpec
        ↓
Build Planner (app/core/build_plan/)  ← generates plan steps
        ↓
Advisors | Policy Engine | Intelligence
(app/advisors/, plugins/) | (PASS/WARN/BLOCK) | (app/core/intelligence/)
        ↓
Plan Runner → Code Generation (app/core/generators/)
        ↓
Workspace + Git (versioned output in workspace/)
```

### Key Modules

- **`app/api/main.py`** — FastAPI app with full middleware stack: `AuthMiddleware` → `RateLimitMiddleware` → `TenantIsolationMiddleware` → `AuditMiddleware` → `SafeErrorMiddleware`. Also starts the stale-run reconciliation background loop.
- **`app/core/spec_schema.py`** — `CopilotSpec` Pydantic model is the central data contract. All build inputs validate against it.
- **`app/core/ai/`** — LLM gateway, confidence scoring, semantic diff. AI requests go through `ai_gateway.py` endpoint, gated by confidence thresholds.
- **`app/core/billing/`** — Token ledger + monthly budget hard enforcement. Budget race condition known (TOCTOU); mitigation: ceiling estimates with headroom (see `KNOWN_LIMITATIONS.md`).
- **`app/core/policy/`** — Evaluates each plan step; returns `PASS`, `WARN`, or `BLOCK`. `BLOCK` halts the build.
- **`app/core/execution/`** — Supports `docker` and `local` backends. Stale runs are reconciled by the background loop (`COPILOT_EXEC_RECONCILE_INTERVAL_SECONDS`, default 60s).
- **`app/core/generators/`** — Jinja2-based code generators. Templates live in `templates/` (pyspark, airflow, sql, dq, readme).
- **`app/advisors/` + `app/plugins/`** — Plugin registry; advisors are discovered and executed per build plan.

### API Versioning

Endpoints span v1, v2, and v3. The Build API has three versions (`build.py`, `build_v2_impl.py`, `build_v3.py`). The OpenAPI snapshot in `tests/snapshots/` must stay in sync — CI enforces this via `make verify-snapshot`.

### Authentication

- Dev: static Bearer tokens (`dev_admin_token`, `dev_viewer_token`)
- Prod: file-based secrets at paths set by `COPILOT_STATIC_ADMIN_TOKEN_FILE` / `COPILOT_STATIC_VIEWER_TOKEN_FILE`
- JWT also supported (`COPILOT_AUTH_MODE=jwt`)
- `COPILOT_ALLOW_STATIC_TOKEN_IN_PROD=false` by default — static tokens are blocked in prod mode

### CI Gates

The CI pipeline (`ci.yml`) enforces three additional gates beyond `pytest`:
1. Packaging manifest drift — `gen_packaging_manifest.py --check`
2. OpenAPI snapshot match — `test_openapi_snapshot.py`
3. V1 readiness (manual trigger) — `check_v1_readiness.py`

Adding new endpoints or changing the API schema requires regenerating the snapshot (`make snapshot`) before CI passes.

### Frontend

React 19 + TypeScript + Vite app in `frontend/`. Built separately from the Python backend. Served via nginx in production.

```bash
cd frontend
npm run dev      # Dev server
npm run build    # Production build
npm run lint     # ESLint
npm run e2e      # Playwright tests
```

### Release Process

Releases are triggered by pushing a `v*` tag. The workflow: tests → manifest check → SBOM generation → tarball build → checksum → GitHub Release upload. The tarball excludes `__pycache__`, `.git`, `.venv`, test caches.

### Important Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `COPILOT_ENV` | `dev` | `dev` or `prod` |
| `COPILOT_AUTH_MODE` | `static_token` | `static_token` or `jwt` |
| `COPILOT_RATE_LIMIT_RPM` | `120` | Requests per minute limit |
| `COPILOT_EXEC_RECONCILE_INTERVAL_SECONDS` | `60` | Stale run reconciliation interval |
| `COPILOT_TENANT_STRICT` | — | Enforce tenant header on all requests |
| `AI_MODEL` | — | LLM model selection for AI gateway |
