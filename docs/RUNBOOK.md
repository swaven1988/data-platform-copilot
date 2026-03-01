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

---

## Build Approvals (High-Risk Builds)

Builds with `risk_score >= COPILOT_HIGH_RISK_APPROVAL_THRESHOLD` (default 0.70) return
HTTP 409 `approval_required` until an operator explicitly approves.

**Grant approval:**
```bash
curl -X POST http://localhost:8080/api/v2/build/approvals \
  -H "Authorization: Bearer dev_admin_token" \
  -H "X-Tenant: default" \
  -H "Content-Type: application/json" \
  -d '{"job_name":"my_job","plan_hash":"<plan_hash>","approver":"alice","notes":"reviewed"}'
```

**Check approval status:**
```bash
curl http://localhost:8080/api/v2/build/approvals/my_job/<plan_hash> \
  -H "Authorization: Bearer dev_admin_token"
```

**Revoke approval:**
```bash
curl -X DELETE http://localhost:8080/api/v2/build/approvals/my_job/<plan_hash> \
  -H "Authorization: Bearer dev_admin_token"
```

Approvals expire after `COPILOT_APPROVAL_TTL_SECONDS` (default 3600s = 1 hour).

---

## AI Failure Triage

Failed executions are triaged automatically in the background. Triage results are stored
in the tenant's AI memory and retrievable via API.

**Get triage report:**
```bash
curl http://localhost:8080/api/v2/triage/failure/my_job \
  -H "Authorization: Bearer dev_admin_token" \
  -H "X-Tenant: default"
```

If `LLM_API_KEY` is not set, triage uses deterministic heuristics and still completes.
Check `copilot.triage` log entries if triage is not appearing.

---

## Execution Retry

Retry any `FAILED` or `CANCELED` execution without re-running preflight:

```bash
curl -X POST http://localhost:8080/api/v1/executions/<run_id>/retry \
  -H "Authorization: Bearer dev_admin_token"
```

Response includes `retry_count` for audit trail.

---

## Prometheus Metrics

Metrics are available for Prometheus scraping at `/metrics`.

```bash
curl http://localhost:8001/metrics
```

Key metric: `copilot_http_requests_total{method, path, status}`

Sample `prometheus.yml`:
```yaml
scrape_configs:
  - job_name: copilot
    static_configs:
      - targets: ['copilot-api:8001']
    metrics_path: /metrics
```

---

## Budget Enforcement

Monthly budgets block executions when `spent_usd >= limit_usd`.

**Check current spend:**
```bash
curl http://localhost:8080/api/v2/billing/summary \
  -H "Authorization: Bearer dev_admin_token" \
  -H "X-Tenant: default"
```

Key fields: `budget_status` (ok/warning/exceeded), `ai_spent_actual_usd`, `ai_by_task`
(per-task AI cost breakdown), `remaining_estimated_usd`.

If a build returns HTTP 409 `exec.budget.exceeded`: check billing summary, increase limit
or wait for month rollover.

---

## Stale Execution Recovery

Stale runs are reconciled automatically every `COPILOT_EXEC_RECONCILE_INTERVAL_SECONDS`
(default 60s). Manual trigger:

```bash
curl -X POST "http://localhost:8080/api/v1/executions/reconcile?stale_after_seconds=300" \
  -H "Authorization: Bearer dev_admin_token"
```
