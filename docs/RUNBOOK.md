# Data Platform Copilot — Runbook

## Prereqs
- Docker + Docker Compose
- Python 3.11 (optional for local dev)
- curl (Windows: Git Bash or WSL preferred)

## Start (Docker Compose)
```bash
docker compose up -d --build
docker ps

# Runbook (Gateway-only Prod Style)

## Components
- **copilot-gateway**: nginx front door (exposes `/api/**`)
- **copilot-api**: FastAPI service (internal)

## Health
- Gateway: `GET /api/v1/health/live`
- Tenant health: `GET /api/v1/tenants/{tenant}/health`

## Common Issues

### 1) 401 Unauthorized
- Missing/invalid `Authorization: Bearer <token>`
- Verify token used:
  - dev: `dev_admin_token` or `dev_viewer_token`

### 2) 400 Missing X-Tenant (strict mode)
- If `COPILOT_TENANT_STRICT=1`, must send:
  - `X-Tenant: default` (or appropriate)

### 3) 429 Rate limit exceeded
- Guardrail active when:
  - `COPILOT_RATE_LIMIT_ENABLED=1`
- Increase RPM:
  - `COPILOT_RATE_LIMIT_RPM=120` (or higher)

### 4) 500 Internal Server Error
- Client receives sanitized JSON without stack trace.
- Inspect API logs for traceback.

## Recovery Steps
1. Restart stack:
   - `docker compose restart`
2. Verify gateway health:
   - `curl -i http://127.0.0.1:8080/api/v1/health/live -H "Authorization: Bearer dev_admin_token" -H "X-Tenant: default"`
3. Run smoke test:
   - `bash tools/smoke_test.sh`