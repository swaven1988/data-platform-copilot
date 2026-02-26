import { useEffect, useState } from "react";
import { api } from "../lib/api";

export default function Modeling() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string>("");

  // Registry
  const [models, setModels] = useState<string[]>([]);
  const [modelName, setModelName] = useState<string>("demo_scd2");
  const [modelSpec, setModelSpec] = useState<string>(
    JSON.stringify(
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
    )
  );

  // Advanced previews
  const [backfill, setBackfill] = useState<any>(null);
  const [cdc, setCdc] = useState<any>(null);
  const [schema, setSchema] = useState<any>(null);
  const [late, setLate] = useState<any>(null);

  const refreshList = () => {
    api
      .get("/api/v1/modeling/list")
      .then((res) => setModels(res.data?.models || []))
      .catch((e) => setErr(e?.response?.data?.detail || e?.message || "Request failed"));
  };

  useEffect(() => {
    api
      .get("/api/v1/modeling/preview-scd2")
      .then((res) => setData(res.data))
      .catch((e) => setErr(e?.response?.data?.detail || e?.message || "Request failed"));

    refreshList();
  }, []);

  const register = async () => {
    setErr("");
    let specObj: any;
    try {
      specObj = JSON.parse(modelSpec);
    } catch {
      setErr("Invalid JSON in model spec");
      return;
    }

    try {
      await api.post("/api/v1/modeling/register", { name: modelName, spec: specObj });
      refreshList();
    } catch (e: any) {
      setErr(e?.response?.data?.detail || e?.message || "Register failed");
    }
  };

  const runAdvancedPreviews = async () => {
    setErr("");
    try {
      const b = await api.get("/api/v1/modeling/preview-backfill", {
        params: { start_dt: "2026-02-01", end_dt: "2026-02-07", partition_column: "dt" },
      });
      setBackfill(b.data);

      const c = await api.get("/api/v1/modeling/preview-cdc-merge", {
        params: { target: "dim_customer", staging: "staging_customer_cdc", pk: "customer_id" },
      });
      setCdc(c.data);

      const s = await api.post("/api/v1/modeling/preview-schema-evolution", {
        current_schema: { customer_id: "bigint", name: "string", email: "string" },
        new_schema: { customer_id: "bigint", name: "string", email: "string", city: "string" },
      });
      setSchema(s.data);

      const l = await api.get("/api/v1/modeling/preview-late-arriving", { params: { scd_type: "type2" } });
      setLate(l.data);
    } catch (e: any) {
      setErr(e?.response?.data?.detail || e?.message || "Advanced preview failed");
    }
  };

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Modeling</h1>

      {err ? (
        <div style={{ padding: 12, border: "1px solid #a33", borderRadius: 12, marginBottom: 16 }}>
          <b>Error:</b> {err}
        </div>
      ) : null}

      {/* Registry */}
      <div style={{ padding: 16, border: "1px solid #333", borderRadius: 12, marginBottom: 16 }}>
        <div style={{ fontWeight: 700, marginBottom: 8 }}>Model Registry</div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div>
            <div style={{ fontSize: 12, opacity: 0.85, marginBottom: 6 }}>Model Name</div>
            <input
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #444", background: "transparent", color: "inherit" }}
            />
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "end" }}>
            <button
              onClick={register}
              style={{ padding: "10px 14px", borderRadius: 10, border: "1px solid #444", background: "transparent", color: "inherit", cursor: "pointer" }}
            >
              Register (admin)
            </button>
            <button
              onClick={refreshList}
              style={{ padding: "10px 14px", borderRadius: 10, border: "1px solid #444", background: "transparent", color: "inherit", cursor: "pointer" }}
            >
              Refresh
            </button>
            <button
              onClick={runAdvancedPreviews}
              style={{ padding: "10px 14px", borderRadius: 10, border: "1px solid #444", background: "transparent", color: "inherit", cursor: "pointer" }}
            >
              Run Advanced Previews
            </button>
          </div>
        </div>

        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 12, opacity: 0.85, marginBottom: 6 }}>Model Spec (JSON)</div>
          <textarea
            value={modelSpec}
            onChange={(e) => setModelSpec(e.target.value)}
            rows={10}
            style={{
              width: "100%",
              padding: 10,
              borderRadius: 10,
              border: "1px solid #444",
              background: "transparent",
              color: "inherit",
              fontFamily: "monospace",
              fontSize: 12,
            }}
          />
        </div>

        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 12, opacity: 0.85, marginBottom: 6 }}>Registered Models</div>
          <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 12 }}>
            {models.length ? JSON.stringify(models, null, 2) : "(none)"}
          </pre>
        </div>
      </div>

      {/* Existing SCD2 Preview */}
      <div style={{ marginTop: 16, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div style={{ padding: 16, border: "1px solid #333", borderRadius: 12 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>SCD2 Merge SQL</div>
          <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 12 }}>
            {data?.scd_merge_sql || "(loading...)"}
          </pre>
        </div>

        <div style={{ padding: 16, border: "1px solid #333", borderRadius: 12 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Spark / DQ / Cost</div>
          <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 12 }}>
            {data
              ? JSON.stringify(
                  {
                    partition_recommendation: data.partition_recommendation,
                    spark_analysis: data.spark_analysis,
                    dq_recommendations: data.dq_recommendations,
                    cost_estimation: data.cost_estimation,
                  },
                  null,
                  2
                )
              : "(loading...)"}
          </pre>
        </div>
      </div>

      {/* Advanced previews results */}
      <div style={{ marginTop: 16, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div style={{ padding: 16, border: "1px solid #333", borderRadius: 12 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Backfill Plan</div>
          <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 12 }}>
            {backfill ? JSON.stringify(backfill, null, 2) : "(run advanced previews)"}
          </pre>
        </div>

        <div style={{ padding: 16, border: "1px solid #333", borderRadius: 12 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>CDC Merge SQL</div>
          <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 12 }}>
            {cdc?.cdc_merge_sql || "(run advanced previews)"}
          </pre>
        </div>

        <div style={{ padding: 16, border: "1px solid #333", borderRadius: 12 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Schema Evolution</div>
          <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 12 }}>
            {schema ? JSON.stringify(schema, null, 2) : "(run advanced previews)"}
          </pre>
        </div>

        <div style={{ padding: 16, border: "1px solid #333", borderRadius: 12 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Late Arriving Strategy</div>
          <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 12 }}>
            {late ? JSON.stringify(late, null, 2) : "(run advanced previews)"}
          </pre>
        </div>
      </div>
    </div>
  );
}
