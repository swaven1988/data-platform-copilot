Param(
  [string]$BaseUrl = "http://127.0.0.1:8001",
  [string]$Token = "dev_admin_token"
)

$ErrorActionPreference = "Stop"

Write-Host "== Smoke Test =="
Write-Host "BASE_URL: $BaseUrl"
Write-Host "TOKEN: $Token"

Invoke-WebRequest -UseBasicParsing "$BaseUrl/api/v1/health/live" | Out-Null
Write-Host "OK: health/live"

Invoke-WebRequest -UseBasicParsing "$BaseUrl/openapi.json" | Out-Null
Write-Host "OK: openapi.json"

$headers = @{ Authorization = "Bearer $Token" }

Invoke-WebRequest -UseBasicParsing "$BaseUrl/api/v1/system/status" -Headers $headers | Out-Null
Write-Host "OK: system/status (authed)"

Invoke-WebRequest -UseBasicParsing "$BaseUrl/api/v1/tenants/default/health" -Headers $headers | Out-Null
Write-Host "OK: tenants/default/health (authed)"

Invoke-WebRequest -UseBasicParsing "$BaseUrl/api/v1/billing/summary" -Headers $headers | Out-Null
Write-Host "OK: billing/summary (authed)"

Write-Host "== Smoke Test Passed =="