import { useState } from "react";
import { ShieldCheck, FileText, ChevronDown, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import {
    getApiErrorMessage,
    getPreflightReport,
    runPreflight,
    type PreflightReport,
    type PreflightRunRequest,
} from "../lib/api";
import PageHeader from "../components/PageHeader";
import Card from "../components/Card";
import Badge from "../components/Badge";

const DEFAULT_SPEC = JSON.stringify({
    job_name: "example_pipeline",
    backend: "local",
    limits: { max_cost_usd: 50, max_runtime_minutes: 60, max_executors: 50 },
    workspace_path: "workspace/example_pipeline",
}, null, 2);

const severityVariant: Record<string, "error" | "warning" | "info" | "neutral"> = {
    high: "error",
    medium: "warning",
    low: "info",
    info: "info",
};

type PreflightViewStatus = "PASS" | "FAIL";

interface FindingView {
    severity: string;
    message: string;
    passed: boolean;
    raw: unknown;
}

interface PreflightResultView {
    passed: boolean;
    status: PreflightViewStatus;
    risk_score: number;
    estimated_cost_usd: number;
    preflight_hash: string;
    findings: FindingView[];
}

function normalizeFindings(report: PreflightReport): FindingView[] {
    const reasons = Array.isArray(report.risk?.risk_reasons) ? report.risk.risk_reasons : [];
    if (reasons.length === 0) {
        return [{
            severity: "low",
            message: "No risk reasons returned",
            passed: true,
            raw: {},
        }];
    }

    return reasons.map((reason) => {
        const text = String(reason || "");
        const lowered = text.toLowerCase();
        const severity = lowered.includes("high")
            ? "high"
            : lowered.includes("medium")
                ? "medium"
                : lowered.includes("low")
                    ? "low"
                    : "info";

        const isFail = severity === "high" || lowered.includes("block");
        return {
            severity,
            message: text || "Preflight finding",
            passed: !isFail,
            raw: { reason: text },
        };
    });
}

function toPreflightResultView(report: PreflightReport): PreflightResultView {
    const status = (report.policy_decision || "").toUpperCase() === "BLOCK" ? "FAIL" : "PASS";
    const findings = normalizeFindings(report);

    return {
        passed: status === "PASS",
        status,
        risk_score: report.risk?.risk_score ?? 0,
        estimated_cost_usd: report.estimate?.compute_cost_usd ?? 0,
        preflight_hash: report.preflight_hash,
        findings,
    };
}

function parsePreflightSpec(raw: string): PreflightRunRequest | null {
    try {
        const parsed: unknown = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return null;

        const obj = parsed as Record<string, unknown>;
        const job_name = typeof obj.job_name === "string" ? obj.job_name : "";
        const runtime_profile = typeof obj.runtime_profile === "string"
            ? obj.runtime_profile
            : (typeof obj.backend === "string" ? obj.backend : "local");

        if (!job_name.trim() || !runtime_profile.trim()) return null;

        return {
            job_name,
            runtime_profile,
            dataset: {
                estimated_input_gb: 1,
                shuffle_multiplier: 1.5,
            },
            pricing: {
                cost_per_executor_hour: 0.5,
                executors: 2,
            },
            sla: { max_runtime_minutes: 60 },
            spark_conf: null,
        };
    } catch {
        return null;
    }
}

function FindingRow({ f }: { f: FindingView }) {
    const [open, setOpen] = useState(false);
    return (
        <div style={{ borderBottom: "1px solid var(--border-soft)" }}>
            <div
                className="flex items-center gap-3"
                style={{ padding: "10px 0", cursor: "pointer" }}
                onClick={() => setOpen(o => !o)}
            >
                {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                <Badge variant={severityVariant[f.severity?.toLowerCase()] ?? "neutral"} dot>
                    {f.severity || "unknown"}
                </Badge>
                <span style={{ flex: 1, fontSize: 13 }}>{f.message || JSON.stringify(f.raw)}</span>
            </div>
            {open && (
                <pre style={{ margin: "0 0 10px 24px", fontSize: 12, color: "var(--text-secondary)", whiteSpace: "pre-wrap" }}>
                    {JSON.stringify(f.raw, null, 2)}
                </pre>
            )}
        </div>
    );
}

export default function Preflight() {
    const [spec, setSpec] = useState(DEFAULT_SPEC);
    const [jobName, setJobName] = useState("example_pipeline");
    const [preflightHash, setPreflightHash] = useState("");
    const [running, setRunning] = useState(false);
    const [result, setResult] = useState<PreflightResultView | null>(null);
    const [loading, setLoading] = useState(false);

    const run = async () => {
        const req = parsePreflightSpec(spec);
        if (!req) {
            toast.error("Invalid JSON in spec");
            return;
        }

        setRunning(true);
        setResult(null);
        try {
            const report = await runPreflight(req);
            setResult(toPreflightResultView(report));
            setPreflightHash(report.preflight_hash);
            toast.success("Preflight complete");
        } catch (e: unknown) {
            toast.error(getApiErrorMessage(e, "Preflight failed"));
        } finally {
            setRunning(false);
        }
    };

    const loadReport = async () => {
        if (!jobName.trim() || !preflightHash.trim()) {
            toast.error("Job name and preflight hash are required");
            return;
        }

        setLoading(true);
        try {
            const report = await getPreflightReport(jobName.trim(), preflightHash.trim());
            setResult(toPreflightResultView(report));
            toast.success("Report loaded");
        } catch (e: unknown) {
            toast.error(getApiErrorMessage(e, "Report not found"));
        } finally {
            setLoading(false);
        }
    };

    const passed = result?.findings?.filter((f) => f.passed !== false).length ?? 0;
    const failed = result?.findings?.filter((f) => f.passed === false).length ?? 0;
    const total = result?.findings?.length ?? 0;

    return (
        <div>
            <PageHeader title="Preflight" subtitle="Run policy gate checks before job execution" />

            <div className="grid-2" style={{ alignItems: "start" }}>
                {/* Input */}
                <Card title="Job Specification">
                    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                        <div>
                            <label htmlFor="pf-spec">Paste spec JSON</label>
                            <textarea id="pf-spec" rows={12} value={spec} onChange={e => setSpec(e.target.value)} />
                        </div>
                        <div className="flex gap-3 items-center">
                            <button className="btn btn-primary" onClick={run} disabled={running}>
                                {running ? <span className="spinner" /> : <ShieldCheck size={14} />}
                                Run Gate
                            </button>
                            <span className="text-muted text-sm">or</span>
                            <div style={{ flex: 1 }}>
                                <div className="grid-2" style={{ gap: 8 }}>
                                    <input
                                        type="text"
                                        placeholder="Job name"
                                        value={jobName}
                                        onChange={e => setJobName(e.target.value)}
                                        style={{ marginBottom: 0 }}
                                    />
                                    <input
                                        type="text"
                                        placeholder="Preflight hash"
                                        value={preflightHash}
                                        onChange={e => setPreflightHash(e.target.value)}
                                        style={{ marginBottom: 0 }}
                                    />
                                </div>
                            </div>
                            <button className="btn btn-secondary" onClick={loadReport} disabled={loading}>
                                {loading ? <span className="spinner" /> : <FileText size={14} />}
                                Load Report
                            </button>
                        </div>
                    </div>
                </Card>

                {/* Results */}
                <Card title="Gate Results">
                    {!result ? (
                        <p style={{ margin: 0, color: "var(--text-muted)", fontSize: 13 }}>Run the gate to see results</p>
                    ) : (
                        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                            {/* Summary strip */}
                            <div className="flex items-center gap-3">
                                <Badge variant={result.passed === false ? "error" : "success"} dot>
                                    {result.status}
                                </Badge>
                                {typeof result.risk_score === "number" && (
                                    <span className="text-sm text-secondary">Risk score: <strong>{result.risk_score}</strong></span>
                                )}
                                <span className="text-xs text-muted">hash: {result.preflight_hash}</span>
                            </div>

                            {/* Risk meter */}
                            {typeof result.risk_score === "number" && (
                                <div>
                                    <div className="progress-track">
                                        <div
                                            className={`progress-bar ${result.risk_score > 70 ? "danger" : result.risk_score > 40 ? "warn" : ""}`}
                                            style={{ width: `${Math.min(result.risk_score, 100)}%` }}
                                        />
                                    </div>
                                    <div className="text-xs text-muted mt-2">{result.risk_score}/100</div>
                                </div>
                            )}

                            {/* Cost estimate */}
                            {result.estimated_cost_usd != null && (
                                <div className="flex justify-between text-sm" style={{ padding: "8px 12px", background: "var(--surface-2)", borderRadius: "var(--radius-md)" }}>
                                    <span className="text-secondary">Estimated cost</span>
                                    <span style={{ fontWeight: 600 }}>${result.estimated_cost_usd.toFixed(4)}</span>
                                </div>
                            )}

                            {/* Findings */}
                            {total > 0 && (
                                <div>
                                    <div className="flex items-center gap-3 mb-3">
                                        <Badge variant="success">{passed} passed</Badge>
                                        {failed > 0 && <Badge variant="error">{failed} failed</Badge>}
                                    </div>
                                    {result.findings.map((f, i) => <FindingRow key={`${f.severity}-${i}`} f={f} />)}
                                </div>
                            )}
                        </div>
                    )}
                </Card>
            </div>
        </div>
    );
}
