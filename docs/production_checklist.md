# Production Checklist (Gateway-only)

## Build / CI
- [ ] `python -m pytest -q` passes
- [ ] `python tools/gen_packaging_manifest.py --check` is OK
- [ ] OpenAPI snapshot test passes
- [ ] Release metadata exists and includes hashes

## Security / Abuse Guardrails
- [ ] Safe error shaping enabled (no stack traces returned)
- [ ] Rate limiting configured for mutating endpoints
  - `COPILOT_RATE_LIMIT_ENABLED=1`
  - `COPILOT_RATE_LIMIT_RPM=<value>`
- [ ] Tenant strict mode decision documented:
  - `COPILOT_TENANT_STRICT=0/1`

## Runtime
- [ ] Gateway `/api/v1/health/live` returns 200
- [ ] Tenant path checks reject cross-tenant access (403)
- [ ] Audit log includes tenant + actor for HTTP requests
- [ ] Smoke script passes: `bash tools/smoke_test.sh`