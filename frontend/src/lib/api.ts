import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "";

export const api = axios.create({
  baseURL,
  timeout: 30000,
});

interface ApiErrorLike {
  response?: {
    data?: {
      detail?: unknown;
      message?: unknown;
      error?: unknown;
    };
  };
  message?: unknown;
}

export interface BuildV3RunParams {
  job_name: string;
  contract_hash: string;
  plan_hash: string;
  intelligence_hash: string;
  policy_eval_hash: string;
}

export interface BuildV3RunResponse {
  build_id: string;
  decision: string;
  policy_profile: string;
  policy_reasons: string[];
  lineage: Record<string, unknown>;
  build_result: Record<string, unknown> | null;
}

export type ExecutionState =
  | "DRAFT"
  | "PLAN_READY"
  | "PRECHECK_PASSED"
  | "APPLIED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "BLOCKED"
  | "CANCELED";

export interface ExecutionEvent {
  ts: string;
  state: ExecutionState;
  message: string;
  data: Record<string, unknown>;
}

export interface ExecutionRecordResponse {
  job_name: string;
  build_id: string;
  tenant: string;
  state: ExecutionState;
  created_ts: string;
  updated_ts: string;
  runtime_profile: string | null;
  preflight_hash: string | null;
  cost_estimate: Record<string, unknown> | null;
  request_id: string | null;
  backend: string | null;
  backend_ref: string | null;
  submitted_ts: string | null;
  finished_ts: string | null;
  actual_runtime_seconds: number | null;
  actual_cost_usd: number | null;
  backend_meta: Record<string, unknown>;
  last_error: string | null;
  events: ExecutionEvent[];
}

export interface ExecutionRunRequest {
  job_name: string;
  backend?: string;
  workspace_dir?: string;
}

export interface ExecutionCancelRequest {
  job_name: string;
  workspace_dir?: string;
}

export interface ExecutionRunResponse {
  ok: boolean;
  execution: ExecutionRecordResponse;
  audit?: Record<string, unknown>;
}

export interface ExecutionCancelResponse {
  ok: boolean;
  execution: ExecutionRecordResponse;
  audit?: Record<string, unknown>;
}

export interface ExecutionStatusResponse {
  job_name: string;
  state: ExecutionState;
  execution: ExecutionRecordResponse;
  tenant: string;
}

export interface PreflightRunRequest {
  job_name: string;
  runtime_profile: string;
  dataset?: {
    estimated_input_gb?: number;
    shuffle_multiplier?: number;
    estimated_rows?: number;
  };
  pricing?: {
    cost_per_executor_hour?: number;
    executors?: number;
  };
  sla?: {
    max_runtime_minutes?: number | null;
  } | null;
  spark_conf?: Record<string, string> | null;
}

export interface PreflightEstimate {
  runtime_minutes: number;
  compute_cost_usd: number;
  confidence: number;
}

export interface PreflightRisk {
  risk_score: number;
  risk_reasons: string[];
}

export interface PreflightReport {
  job_name: string;
  preflight_hash: string;
  estimate: PreflightEstimate;
  risk: PreflightRisk;
  policy_decision: string;
}

export interface BillingSummaryResponse {
  tenant: string;
  month: string;
  limit_usd: number;
  spent_estimated_usd: number;
  spent_actual_usd: number;
  remaining_estimated_usd: number;
  utilization_estimated: number;
  entries_count: number;
}

export interface BillingSummaryQuery {
  month?: string;
  workspace_dir?: string;
}

export interface HealthLiveResponse {
  status: string;
}

export interface ArtifactIntegrityResult {
  valid: boolean;
  reason?: string;
  expected_sha?: string;
  actual_sha?: string;
}

export interface SystemStatusResponse {
  metrics: Record<string, number>;
  artifact: ArtifactIntegrityResult;
}

export interface AuditLogRecord {
  ts_ms?: number;
  timestamp?: string;
  tenant?: string;
  actor?: string;
  user?: string;
  event_type?: string;
  event?: string;
  type?: string;
  details?: string;
  message?: string;
  request_id?: string | null;
  extra?: Record<string, unknown>;
  http?: {
    method?: string | null;
    path?: string | null;
    status?: number | null;
  };
  [key: string]: unknown;
}

interface AuditLogResponse {
  entries?: AuditLogRecord[];
}

export async function runBuildV3(params: BuildV3RunParams): Promise<BuildV3RunResponse> {
  const response = await api.post<BuildV3RunResponse>("/api/v3/build/run", null, {
    params,
  });
  return response.data;
}

export async function runExecutionBuild(
  payload: ExecutionRunRequest,
  contractHash: string,
): Promise<ExecutionRunResponse> {
  const response = await api.post<ExecutionRunResponse>("/api/v2/build/run", payload, {
    params: { contract_hash: contractHash },
  });
  return response.data;
}

export async function getExecutionStatus(
  jobName: string,
  workspaceDir?: string,
): Promise<ExecutionStatusResponse> {
  const response = await api.get<ExecutionStatusResponse>(
    `/api/v2/build/status/${encodeURIComponent(jobName)}`,
    {
      params: workspaceDir ? { workspace_dir: workspaceDir } : undefined,
    },
  );
  return response.data;
}

export async function cancelExecutionBuild(
  payload: ExecutionCancelRequest,
): Promise<ExecutionCancelResponse> {
  const response = await api.post<ExecutionCancelResponse>("/api/v2/build/cancel", payload);
  return response.data;
}

export async function runPreflight(
  payload: PreflightRunRequest,
): Promise<PreflightReport> {
  const response = await api.post<PreflightReport>("/api/v2/preflight/analyze", payload);
  return response.data;
}

export async function getPreflightReport(
  jobName: string,
  preflightHash: string,
): Promise<PreflightReport> {
  const response = await api.get<PreflightReport>(
    `/api/v2/preflight/report/${encodeURIComponent(jobName)}/${encodeURIComponent(preflightHash)}`,
  );
  return response.data;
}

export async function getBillingSummary(
  params: BillingSummaryQuery,
): Promise<BillingSummaryResponse> {
  const response = await api.get<BillingSummaryResponse>("/api/v2/billing/summary", {
    params,
  });
  return response.data;
}

export async function getHealthLive(): Promise<HealthLiveResponse> {
  const response = await api.get<HealthLiveResponse>("/api/v1/health/live");
  return response.data;
}

export async function getSystemStatus(): Promise<SystemStatusResponse> {
  const response = await api.get<SystemStatusResponse>("/api/v1/system/status");
  return response.data;
}

export async function getAuditLogEntries(): Promise<AuditLogRecord[]> {
  const response = await api.get<AuditLogResponse | AuditLogRecord[]>("/api/v1/audit/log");
  const data = response.data;
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.entries)) return data.entries;
  return [];
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  const e = error as ApiErrorLike;
  const detail = e?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;

  const message = e?.response?.data?.message;
  if (typeof message === "string" && message.trim()) return message;

  const err = e?.response?.data?.error;
  if (typeof err === "string" && err.trim()) return err;

  if (typeof e?.message === "string" && e.message.trim()) return e.message;

  return fallback;
}

api.interceptors.request.use((config) => {
  config.headers = config.headers || {};

  // Auth — fallback to dev token when not explicitly set
  const token = localStorage.getItem("COPILOT_TOKEN") || "dev_admin_token";
  config.headers["Authorization"] = `Bearer ${token}`;

  // Tenant — required by TenantIsolationMiddleware on every request
  const tenant = localStorage.getItem("COPILOT_TENANT") || "default";
  config.headers["X-Tenant"] = tenant;

  return config;
});
