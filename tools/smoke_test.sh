#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
TOKEN="${TOKEN:-dev_admin_token}"

echo "== Smoke Test =="
echo "BASE_URL: ${BASE_URL}"
echo "TOKEN: ${TOKEN}"

curl -fsS "${BASE_URL}/api/v1/health/live" >/dev/null
echo "OK: health/live"

curl -fsS "${BASE_URL}/openapi.json" >/dev/null
echo "OK: openapi.json"

curl -fsS "${BASE_URL}/api/v1/system/status" \
  -H "Authorization: Bearer ${TOKEN}" >/dev/null
echo "OK: system/status (authed)"

curl -fsS "${BASE_URL}/api/v1/tenants/default/health" \
  -H "Authorization: Bearer ${TOKEN}" >/dev/null
echo "OK: tenants/default/health (authed)"

curl -fsS "${BASE_URL}/api/v1/billing/summary" \
  -H "Authorization: Bearer ${TOKEN}" >/dev/null
echo "OK: billing/summary (authed)"

echo "== Smoke Test Passed =="