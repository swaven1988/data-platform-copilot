import { useEffect, useState } from "react";
import { RefreshCw, Plus, Play } from "lucide-react";
import { toast } from "sonner";
import {
  api,
  getApiErrorMessage,
  runBuildV3,
  type BuildV3RunResponse,
} from "../lib/api";
import PageHeader from "../components/PageHeader";
import Card from "../components/Card";
import Badge from "../components/Badge";

import CodeBlock from "../components/CodeBlock";
import Skeleton from "../components/Skeleton";

const DEFAULT_SPEC = JSON.stringify(
  {
    table_name: "dim_customer",
    model_type: "scd2",
    columns: ["customer_id", "name", "email", "city", "updated_at"],
    partition: { strategy: "none" },
    scd: {
      type: "scd2",
      natural_keys: ["customer_id"],
      surrogate_key: "customer_sk",
      change_detection: { strategy: "hash", columns: ["name", "email", "city"] },
    },
  },
  null,
  2
);

interface ModelingPreview {
  scd_merge_sql?: string;
  partition_recommendation?: unknown;
  spark_analysis?: unknown;
  dq_recommendations?: unknown;
  cost_estimation?: unknown;
}

type JsonObject = Record<string, unknown>;

interface RegisterModelPayload {
  name: string;
  spec: JsonObject;
}

function safeJsonParseObject(raw: string): JsonObject | null {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as JsonObject;
    }
    return null;
  } catch {
    return null;
  }
}

function getStringField(obj: JsonObject | null, key: string): string | null {
  if (!obj) return null;
  const value = obj[key];
  return typeof value === "string" && value.trim() ? value : null;
}

export default function Modeling() {
  const [preview, setPreview] = useState<ModelingPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(true);
  const [models, setModels] = useState<string[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [modelName, setModelName] = useState("demo_scd2");
  const [modelSpec, setModelSpec] = useState(DEFAULT_SPEC);
  const [registering, setRegistering] = useState(false);

  // Advanced previews
  const [backfill, setBackfill] = useState<JsonObject | null>(null);
  const [cdc, setCdc] = useState<JsonObject | null>(null);
  const [schema, setSchema] = useState<JsonObject | null>(null);
  const [late, setLate] = useState<JsonObject | null>(null);
  const [advLoading, setAdvLoading] = useState(false);

  // Build V3 execution
  const [buildJobName, setBuildJobName] = useState("demo_pipeline");
  const [contractHash, setContractHash] = useState("chash_demo");
  const [planHash, setPlanHash] = useState("phash_demo");
  const [intelligenceHash, setIntelligenceHash] = useState("ihash_demo");
  const [policyEvalHash, setPolicyEvalHash] = useState("pehash_demo");
  const [buildRunning, setBuildRunning] = useState(false);
  const [buildResult, setBuildResult] = useState<BuildV3RunResponse | null>(null);

  const refreshList = () => {
    setListLoading(true);
    api
      .get("/api/v1/modeling/list")
      .then(res => setModels(res.data?.models || []))
      .catch(e => toast.error(getApiErrorMessage(e, "List failed")))
      .finally(() => setListLoading(false));
  };

  useEffect(() => {
    api
      .get("/api/v1/modeling/preview-scd2")
      .then(res => setPreview((res.data || null) as ModelingPreview | null))
      .catch(e => toast.error(getApiErrorMessage(e, "Preview failed")))
      .finally(() => setPreviewLoading(false));
    refreshList();
  }, []);

  const register = async () => {
    const specObj = safeJsonParseObject(modelSpec);
    if (!specObj) {
      toast.error("Invalid JSON object in model spec");
      return;
    }

    setRegistering(true);
    try {
      const payload: RegisterModelPayload = { name: modelName, spec: specObj };
      await api.post("/api/v1/modeling/register", payload);
      toast.success(`Model "${modelName}" registered`);
      refreshList();
    } catch (e: unknown) {
      toast.error(getApiErrorMessage(e, "Register failed"));
    } finally {
      setRegistering(false);
    }
  };

  const runAdvancedPreviews = async () => {
    setAdvLoading(true);
    try {
      const [b, c, s, l] = await Promise.all([
        api.get("/api/v1/modeling/preview-backfill", {
          params: { start_dt: "2026-02-01", end_dt: "2026-02-07", partition_column: "dt" },
        }),
        api.get("/api/v1/modeling/preview-cdc-merge", {
          params: { target: "dim_customer", staging: "staging_customer_cdc", pk: "customer_id" },
        }),
        api.post("/api/v1/modeling/preview-schema-evolution", {
          current_schema: { customer_id: "bigint", name: "string", email: "string" },
          new_schema: { customer_id: "bigint", name: "string", email: "string", city: "string" },
        }),
        api.get("/api/v1/modeling/preview-late-arriving", { params: { scd_type: "type2" } }),
      ]);
      setBackfill(b.data);
      setCdc(c.data);
      setSchema(s.data);
      setLate(l.data);
      toast.success("Advanced previews loaded");
    } catch (e: unknown) {
      toast.error(getApiErrorMessage(e, "Advanced preview failed"));
    } finally {
      setAdvLoading(false);
    }
  };

  const runBuild = async () => {
    if (!buildJobName || !contractHash || !planHash || !intelligenceHash || !policyEvalHash) {
      toast.error("All Build V3 fields are required");
      return;
    }

    setBuildRunning(true);
    setBuildResult(null);
    try {
      const result = await runBuildV3({
        job_name: buildJobName.trim(),
        contract_hash: contractHash.trim(),
        plan_hash: planHash.trim(),
        intelligence_hash: intelligenceHash.trim(),
        policy_eval_hash: policyEvalHash.trim(),
      });
      setBuildResult(result);
      toast.success(`Build ${result.build_id} completed with decision: ${result.decision}`);
    } catch (e: unknown) {
      toast.error(getApiErrorMessage(e, "Build V3 run failed"));
    } finally {
      setBuildRunning(false);
    }
  };

  const decisionVariant = (decision?: string): "success" | "warning" | "error" | "neutral" => {
    const d = (decision || "").trim().toLowerCase();
    if (["allow", "proceed", "approved"].includes(d)) return "success";
    if (["warn", "warning"].includes(d)) return "warning";
    if (["block", "blocked", "deny", "denied"].includes(d)) return "error";
    return "neutral";
  };

  return (
    <div>
      <PageHeader
        title="Modeling"
        subtitle="Register models and preview generated SQL, Spark plans, and schema evolution"
        actions={
          <button className="btn btn-secondary btn-sm" onClick={runAdvancedPreviews} disabled={advLoading}>
            {advLoading ? <span className="spinner" /> : <RefreshCw size={13} />}
            Advanced Previews
          </button>
        }
      />

      {/* Registry */}
      <Card title="Model Registry" subtitle={`${models.length} registered model${models.length !== 1 ? "s" : ""}`}
        actions={
          <>
            <button className="btn btn-ghost btn-sm btn-icon" onClick={refreshList} title="Refresh"><RefreshCw size={13} /></button>
            <button className="btn btn-primary btn-sm" onClick={register} disabled={registering}>
              {registering ? <span className="spinner" /> : <Plus size={13} />}
              Register
            </button>
          </>
        }
      >
        <div className="grid-2" style={{ marginBottom: 14 }}>
          <div>
            <label htmlFor="mod-name">Model Name</label>
            <input id="mod-name" type="text" value={modelName} onChange={e => setModelName(e.target.value)} />
          </div>
          <div>
            <label htmlFor="mod-list">Registered Models</label>
            {listLoading
              ? <Skeleton height={38} />
              : <div id="mod-list" style={{ fontSize: 12, color: "var(--text-secondary)", paddingTop: 8 }}>
                {models.length ? models.join(", ") : <span className="text-muted">None yet</span>}
              </div>
            }
          </div>
        </div>
        <div>
          <label htmlFor="mod-spec">Model Spec (JSON)</label>
          <textarea id="mod-spec" rows={10} value={modelSpec} onChange={e => setModelSpec(e.target.value)} />
        </div>
      </Card>

      {/* SCD2 Preview */}
      <div style={{ marginTop: 20 }}>
        <div className="grid-2">
          <Card title="SCD2 Merge SQL">
            {previewLoading
              ? <Skeleton height={16} lines={8} />
              : <CodeBlock>{preview?.scd_merge_sql || "(no data)"}</CodeBlock>
            }
          </Card>
          <Card title="Spark / DQ / Cost">
            {previewLoading
              ? <Skeleton height={16} lines={8} />
              : <CodeBlock>
                {preview
                  ? JSON.stringify({
                    partition_recommendation: preview.partition_recommendation,
                    spark_analysis: preview.spark_analysis,
                    dq_recommendations: preview.dq_recommendations,
                    cost_estimation: preview.cost_estimation,
                  }, null, 2)
                  : "(no data)"}
              </CodeBlock>
            }
          </Card>
        </div>
      </div>

      {/* Advanced previews */}
      {(backfill || cdc || schema || late) && (
        <div style={{ marginTop: 20 }}>
          <div className="grid-2">
            <Card title="Backfill Plan">
              <CodeBlock>{backfill ? JSON.stringify(backfill, null, 2) : "(run advanced previews)"}</CodeBlock>
            </Card>
            <Card title="CDC Merge SQL">
              <CodeBlock>{getStringField(cdc, "cdc_merge_sql") || "(run advanced previews)"}</CodeBlock>
            </Card>
            <Card title="Schema Evolution">
              <CodeBlock>{schema ? JSON.stringify(schema, null, 2) : "(run advanced previews)"}</CodeBlock>
            </Card>
            <Card title="Late Arriving Strategy">
              <CodeBlock>{late ? JSON.stringify(late, null, 2) : "(run advanced previews)"}</CodeBlock>
            </Card>
          </div>
        </div>
      )}

      {/* Build V3 */}
      <div style={{ marginTop: 20 }}>
        <Card
          title="Build V3 Execution"
          subtitle="Run policy-gated build and inspect decision, lineage, and runner output"
          actions={
            <button className="btn btn-primary btn-sm" onClick={runBuild} disabled={buildRunning}>
              {buildRunning ? <span className="spinner" /> : <Play size={13} />}
              Run Build
            </button>
          }
        >
          <div className="grid-2" style={{ marginBottom: 14 }}>
            <div>
              <label htmlFor="build-job-name">Job Name</label>
              <input
                id="build-job-name"
                type="text"
                value={buildJobName}
                onChange={e => setBuildJobName(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="build-contract-hash">Contract Hash</label>
              <input
                id="build-contract-hash"
                type="text"
                value={contractHash}
                onChange={e => setContractHash(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="build-plan-hash">Plan Hash</label>
              <input
                id="build-plan-hash"
                type="text"
                value={planHash}
                onChange={e => setPlanHash(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="build-intelligence-hash">Intelligence Hash</label>
              <input
                id="build-intelligence-hash"
                type="text"
                value={intelligenceHash}
                onChange={e => setIntelligenceHash(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="build-policy-hash">Policy Eval Hash</label>
              <input
                id="build-policy-hash"
                type="text"
                value={policyEvalHash}
                onChange={e => setPolicyEvalHash(e.target.value)}
              />
            </div>
          </div>

          {!buildResult ? (
            <div className="text-muted" style={{ fontSize: 12 }}>
              Submit a build to view decision and lineage output.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div className="flex items-center gap-3">
                <Badge variant={decisionVariant(buildResult.decision)} dot>
                  {buildResult.decision || "unknown"}
                </Badge>
                <span className="text-sm text-muted">build_id: {buildResult.build_id}</span>
                <span className="text-sm text-muted">profile: {buildResult.policy_profile}</span>
              </div>

              <div className="grid-2">
                <Card title="Policy Reasons" noPadding>
                  <div className="card__body">
                    <CodeBlock>
                      {JSON.stringify(buildResult.policy_reasons || [], null, 2)}
                    </CodeBlock>
                  </div>
                </Card>
                <Card title="Lineage" noPadding>
                  <div className="card__body">
                    <CodeBlock>
                      {JSON.stringify(buildResult.lineage || {}, null, 2)}
                    </CodeBlock>
                  </div>
                </Card>
              </div>

              <Card title="Runner Result" noPadding>
                <div className="card__body">
                  <CodeBlock>
                    {JSON.stringify(buildResult.build_result, null, 2)}
                  </CodeBlock>
                </div>
              </Card>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
