# Production Validation Checklist
## Data Platform Copilot — v0.18.x

Run these checks after every production deployment.
All commands assume the stack is up at `http://127.0.0.1:8080`.

---

## 1. Stack Health

```bash
# Verify all containers are running and healthy
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
# Expected: copilot-api (healthy), copilot-web (healthy), copilot-gateway (running)

# Confirm non-root user in API container
docker exec -it copilot-api sh -lc "id"
# Expected: uid=1000(appuser)

# Confirm read-only filesystem (write to root should fail)
docker exec -it copilot-api sh -lc "touch /testfile"
# Expected: Permission denied

# Confirm workspace is writable
docker exec -it copilot-api sh -lc "touch /app/workspace/test && ls -l /app/workspace"
# Expected: file created successfully
```

---

## 2. Liveness and Readiness

```bash
curl -i http://127.0.0.1:8080/api/v1/health/live
# Expected: HTTP 200, {"status":"ok"}

curl -i http://127.0.0.1:8080/api/v1/health/ready
# Expected: HTTP 200

curl -i http://127.0.0.1:8080/api/v1/tenants/default/health \
  -H "Authorization: Bearer dev_admin_token"
# Expected: HTTP 200
```

---

## 3. Authentication Gates

```bash
# No auth → 401
curl -i http://127.0.0.1:8080/api/v2/billing/summary \
  -H "X-Tenant: default"
# Expected: HTTP 401

# Valid auth → 200
curl -i http://127.0.0.1:8080/api/v2/billing/summary \
  -H "Authorization: Bearer dev_admin_token" \
  -H "X-Tenant: default"
# Expected: HTTP 200, JSON with budget_status, ai_spent_actual_usd, ai_by_task
```

---

## 4. Rate Limiting

```bash
# Fire 130 requests — last ~10 should get 429
for i in {1..130}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    http://127.0.0.1:8080/api/v1/health/live
done
# Expected: 200 × ~120, then 429 responses
```

---

## 5. Prometheus Metrics

```bash
curl -i http://127.0.0.1:8001/metrics
# Expected: HTTP 200, text/plain; version=0.0.4
# Must include: copilot_http_requests_total
```

---

## 6. Build Approvals

```bash
# Grant approval
curl -X POST http://127.0.0.1:8080/api/v2/build/approvals \
  -H "Authorization: Bearer dev_admin_token" \
  -H "X-Tenant: default" \
  -H "Content-Type: application/json" \
  -d '{"job_name":"smoke_job","plan_hash":"abc123","approver":"validator","notes":"prod check"}'
# Expected: HTTP 200, {"ok":true,"approval":{...}}

# Look up approval
curl http://127.0.0.1:8080/api/v2/build/approvals/smoke_job/abc123 \
  -H "Authorization: Bearer dev_admin_token" -H "X-Tenant: default"
# Expected: HTTP 200, approval record with approved_at

# Revoke approval
curl -X DELETE http://127.0.0.1:8080/api/v2/build/approvals/smoke_job/abc123 \
  -H "Authorization: Bearer dev_admin_token"
# Expected: HTTP 200, {"ok":true,"revoked":true}
```

---

## 7. API and OpenAPI

```bash
curl -i http://127.0.0.1:8080/openapi.json \
  -H "Authorization: Bearer dev_admin_token" \
  -H "X-Tenant: default"
# Expected: HTTP 200, valid JSON with paths

curl -i http://127.0.0.1:8080/api/v2/repo/status \
  -H "Authorization: Bearer dev_admin_token" \
  -H "X-Tenant: default"
# Expected: HTTP 200

curl -i -X POST http://127.0.0.1:8080/api/v2/sync/plan \
  -H "Authorization: Bearer dev_admin_token" \
  -H "X-Tenant: default" \
  -H "Content-Type: application/json" \
  -d '{"job_name":"test","paths":"jobs,dags"}'
# Expected: HTTP 200 or 422 (schema error), NOT 500
```

---

## 8. Security Headers

```bash
curl -I http://127.0.0.1:8080/api/v2/billing/summary \
  -H "Authorization: Bearer dev_admin_token" \
  -H "X-Tenant: default"
# Expected headers: X-Frame-Options, X-Content-Type-Options, X-XSS-Protection
```
