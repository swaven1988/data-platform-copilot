import { useState, useEffect, useRef } from "react";
import { Play, XCircle, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import {
    cancelExecutionBuild,
    getApiErrorMessage,
    getExecutionStatus,
    runExecutionBuild,
    type ExecutionRecordResponse,
    type ExecutionState,
} from "../lib/api";
import PageHeader from "../components/PageHeader";
import Card from "../components/Card";
import Badge from "../components/Badge";

type JobStatus = "PENDING" | ExecutionState | null;
type ExecutionBackend = "local" | "docker";

const statusVariant: Record<string, "accent" | "warning" | "success" | "error" | "neutral"> = {
    PENDING: "accent",
    RUNNING: "warning",
    SUCCEEDED: "success",
    FAILED: "error",
    CANCELED: "neutral",
};

const TERMINAL = new Set<JobStatus>(["SUCCEEDED", "FAILED", "CANCELED"]);

interface ActualsView {
    cost_usd: number | null;
    duration_seconds: number | null;
    exit_code: number | null;
}

function toActualsView(rec: ExecutionRecordResponse | null): ActualsView | null {
    if (!rec) return null;

    const statusRaw = rec.backend_meta?.last_status;
    const statusObj =
        statusRaw && typeof statusRaw === "object" && !Array.isArray(statusRaw)
            ? (statusRaw as Record<string, unknown>)
            : null;

    const exitRaw = statusObj?.exit_code;
    const exitCode = typeof exitRaw === "number" ? exitRaw : null;

    return {
        cost_usd: typeof rec.actual_cost_usd === "number" ? rec.actual_cost_usd : null,
        duration_seconds: typeof rec.actual_runtime_seconds === "number" ? rec.actual_runtime_seconds : null,
        exit_code: exitCode,
    };
}

export default function Execution() {
    const [jobName, setJobName] = useState("example_pipeline");
    const [backend, setBackend] = useState<ExecutionBackend>("local");
    const [maxCost, setMaxCost] = useState("50");
    const [maxMins, setMaxMins] = useState("180");
    const [maxExec, setMaxExec] = useState("50");
    const [contractHash, setContractHash] = useState("demo_contract_hash");

    const [submitting, setSubmitting] = useState(false);
    const [status, setStatus] = useState<JobStatus>(null);
    const [actuals, setActuals] = useState<ActualsView | null>(null);

    const pollRef = useRef<number | null>(null);

    const stopPoll = () => {
        if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    };

    const poll = (name: string) => {
        stopPoll();
        pollRef.current = setInterval(async () => {
            try {
                const res = await getExecutionStatus(name);
                const st: JobStatus = res.state ?? null;
                setStatus(st);
                setActuals(toActualsView(res.execution));
                if (st && TERMINAL.has(st)) stopPoll();
            } catch {
                // ignore poll errors
            }
        }, 3000) as unknown as number;
    };

    useEffect(() => () => stopPoll(), []);

    const submit = async () => {
        setSubmitting(true);
        setStatus("PENDING");
        setActuals(null);
        try {
            const out = await runExecutionBuild({
                job_name: jobName,
                backend,
            }, contractHash || "demo_contract_hash");
            setStatus(out.execution.state);
            toast.success("Job submitted");
            poll(jobName);
        } catch (e: unknown) {
            toast.error(getApiErrorMessage(e, "Submit failed"));
            setStatus(null);
        } finally {
            setSubmitting(false);
        }
    };

    const cancel = async () => {
        try {
            const out = await cancelExecutionBuild({ job_name: jobName });
            toast.success("Cancel requested");
            setStatus(out.execution.state);
            setActuals(toActualsView(out.execution));
            stopPoll();
        } catch (e: unknown) {
            toast.error(getApiErrorMessage(e, "Cancel failed"));
        }
    };

    const refreshStatus = async () => {
        try {
            const res = await getExecutionStatus(jobName);
            setStatus(res.state ?? null);
            setActuals(toActualsView(res.execution));
        } catch (e: unknown) {
            toast.error(getApiErrorMessage(e, "Status fetch failed"));
        }
    };

    return (
        <div>
            <PageHeader title="Execution" subtitle="Submit jobs, monitor status, and view actuals" />

            <div className="grid-2" style={{ alignItems: "start" }}>
                {/* Form */}
                <Card title="Job Configuration">
                    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                        <div>
                            <label htmlFor="ex-name">Job Name</label>
                            <input id="ex-name" type="text" value={jobName} onChange={e => setJobName(e.target.value)} />
                        </div>
                        <div>
                            <label htmlFor="ex-backend">Backend</label>
                            <select id="ex-backend" value={backend} onChange={e => setBackend(e.target.value as ExecutionBackend)}>
                                <option value="local">local (simulated)</option>
                                <option value="docker">docker</option>
                            </select>
                        </div>
                        <div>
                            <label htmlFor="ex-contract">Contract Hash</label>
                            <input id="ex-contract" type="text" value={contractHash} onChange={e => setContractHash(e.target.value)} />
                        </div>
                        <div className="grid-3">
                            <div>
                                <label htmlFor="ex-cost">Max Cost (USD)</label>
                                <input id="ex-cost" type="number" value={maxCost} onChange={e => setMaxCost(e.target.value)} />
                            </div>
                            <div>
                                <label htmlFor="ex-mins">Max Mins</label>
                                <input id="ex-mins" type="number" value={maxMins} onChange={e => setMaxMins(e.target.value)} />
                            </div>
                            <div>
                                <label htmlFor="ex-exec">Max Executors</label>
                                <input id="ex-exec" type="number" value={maxExec} onChange={e => setMaxExec(e.target.value)} />
                            </div>
                        </div>
                        <div className="flex gap-3">
                            <button className="btn btn-primary" onClick={submit} disabled={submitting}>
                                {submitting ? <span className="spinner" /> : <Play size={14} />}
                                Submit Job
                            </button>
                            {status && !TERMINAL.has(status) && (
                                <button className="btn btn-danger" onClick={cancel}>
                                    <XCircle size={14} />
                                    Cancel
                                </button>
                            )}
                        </div>
                    </div>
                </Card>

                {/* Status */}
                <Card
                    title="Job Status"
                    actions={
                        status && <button className="btn btn-ghost btn-sm btn-icon" onClick={refreshStatus}><RefreshCw size={13} /></button>
                    }
                >
                    {!status ? (
                        <p style={{ margin: 0, color: "var(--text-muted)", fontSize: 13 }}>Submit a job to see status</p>
                    ) : (
                        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                            <div className="flex items-center gap-3">
                                <Badge variant={statusVariant[status] ?? "neutral"} dot>{status}</Badge>
                                <span className="text-sm text-muted">{jobName}</span>
                            </div>

                            {status === "RUNNING" && (
                                <div>
                                    <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>Auto-polling every 3s…</div>
                                    <div className="progress-track">
                                        <div className="progress-bar warn" style={{ width: "100%", animation: "shimmer 1.4s linear infinite" }} />
                                    </div>
                                </div>
                            )}

                            {actuals && (
                                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                                    <div className="text-sm" style={{ fontWeight: 600, color: "var(--text-secondary)" }}>Actuals</div>
                                    {[
                                        { label: "Cost", value: actuals.cost_usd != null ? `$${actuals.cost_usd.toFixed(4)}` : "—" },
                                        { label: "Duration", value: actuals.duration_seconds != null ? `${actuals.duration_seconds}s` : "—" },
                                        { label: "Exit Code", value: actuals.exit_code ?? "—" },
                                    ].map(({ label, value }) => (
                                        <div key={label} className="flex justify-between" style={{ fontSize: 13, padding: "6px 0", borderBottom: "1px solid var(--border-soft)" }}>
                                            <span className="text-muted">{label}</span>
                                            <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>{String(value)}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </Card>
            </div>
        </div>
    );
}
