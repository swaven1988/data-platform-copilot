# Role Matrix

## Tokens (dev)
- **dev_admin_token** → role: `admin`
- **dev_viewer_token** → role: `viewer`

## Tenant Boundary
All versioned APIs under `/api/v1/**` and `/api/v2/**` execute in a tenant context.
Tenant is derived from:
- `X-Tenant` header (preferred)
- or `/api/v*/tenants/{tenant}/...` path segments (where applicable)

Strict mode:
- `COPILOT_TENANT_STRICT=1` requires explicit tenant for versioned APIs.

## Endpoint Access
| Surface | Viewer | Admin | Notes |
|---|---:|---:|---|
| Health (GET) | ✅ | ✅ | `/api/v1/health/live` |
| Health (POST ping) | ✅ | ✅ | `/api/v1/health/ping` (used for smoke + rate limiting tests) |
| Metrics snapshot | ✅ | ✅ | `/api/v1/metrics/snapshot` |
| Sync plan | ✅ | ✅ | plan is read-only diff; apply is mutating |
| Sync apply | ❌ (default) | ✅ | depends on RBAC policy used in implementation |
| Build / Apply | ❌ (default) | ✅ | mutating surfaces should be rate-limited |