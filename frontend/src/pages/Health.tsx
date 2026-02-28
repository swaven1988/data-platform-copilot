import { useState, useEffect, useCallback } from "react";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";
import {
    getApiErrorMessage,
    getHealthLive,
    getSystemStatus,
    type HealthLiveResponse,
    type SystemStatusResponse,
} from "../lib/api";
import PageHeader from "../components/PageHeader";
import Card from "../components/Card";
import Badge from "../components/Badge";

type ServiceValue = boolean | string | number | null | undefined;

function evalStatus(val: ServiceValue): "green" | "yellow" | "red" {
    if (val === true || val === "ok" || val === "healthy") return "green";
    if (val === false || val === "error" || val === "unhealthy") return "red";
    return "yellow";
}

function evalBadge(color: "green" | "yellow" | "red"): "success" | "warning" | "error" {
    return color === "green" ? "success" : color === "red" ? "error" : "warning";
}

export default function Health() {
    const [health, setHealth] = useState<HealthLiveResponse | null>(null);
    const [sysstat, setSysstat] = useState<SystemStatusResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [lastAt, setLastAt] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [h, s] = await Promise.allSettled([
                getHealthLive(),
                getSystemStatus(),
            ]);

            let sawFailure = false;

            if (h.status === "fulfilled") {
                setHealth(h.value);
            } else {
                sawFailure = true;
            }

            if (s.status === "fulfilled") {
                setSysstat(s.value);
            } else {
                sawFailure = true;
            }

            if (sawFailure) {
                const firstFailure = h.status === "rejected" ? h.reason : s.status === "rejected" ? s.reason : null;
                toast.error(getApiErrorMessage(firstFailure, "One or more health checks failed"));
            }

            setLastAt(new Date().toLocaleTimeString());
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
        const t = setInterval(load, 30_000);
        return () => clearInterval(t);
    }, [load]);

    const artifact = sysstat?.artifact;
    const services: { name: string; value: ServiceValue; detail?: string }[] = [
        { name: "API", value: health?.status, detail: "/api/v1/health/live" },
        {
            name: "Artifact Integrity",
            value: artifact?.valid,
            detail: artifact?.reason ? `reason: ${artifact.reason}` : "integrity check",
        },
        {
            name: "Metrics Present",
            value: sysstat ? Object.keys(sysstat.metrics).length > 0 : undefined,
            detail: sysstat ? `${Object.keys(sysstat.metrics).length} counters` : "",
        },
        { name: "Auth Context", value: "protected", detail: "requires admin token" },
    ];

    const allGreen = services.every(s => evalStatus(s.value) === "green");

    return (
        <div>
            <PageHeader
                title="System Health"
                subtitle="Real-time service status — auto-refreshes every 30s"
                actions={
                    <div className="flex items-center gap-3">
                        {lastAt && <span className="text-sm text-muted">Updated {lastAt}</span>}
                        <button className="btn btn-secondary btn-icon" onClick={load} disabled={loading}>
                            {loading ? <span className="spinner" /> : <RefreshCw size={14} />}
                        </button>
                    </div>
                }
            />

            {/* Overall */}
            <div style={{ marginBottom: 20 }}>
                <Badge variant={allGreen ? "success" : "warning"} dot style={{ fontSize: 13, padding: "4px 12px" }}>
                    {allGreen ? "All Systems Operational" : "Degraded / Partial"}
                </Badge>
            </div>

            {/* Status grid */}
            <div className="status-grid" style={{ marginBottom: 24 }}>
                {services.map(({ name, value, detail }) => {
                    const color = evalStatus(value);
                    return (
                        <div className="status-item" key={name}>
                            <div className={`dot ${color}`} />
                            <div>
                                <div className="status-item__name">{name}</div>
                                <div className="status-item__detail">
                                    <Badge variant={evalBadge(color)}>{String(value ?? "unknown")}</Badge>
                                    {detail ? <span style={{ marginLeft: 6, fontSize: 11, color: "var(--text-muted)" }}>{detail}</span> : null}
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Detail cards */}
            <div className="grid-2">
                {health && (
                    <Card title="API Health Response" subtitle="liveness endpoint">
                        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                            {[
                                ["Status", health.status],
                            ].filter(([, v]) => v != null).map(([k, v]) => (
                                <div key={String(k)} className="flex justify-between text-sm" style={{ borderBottom: "1px solid var(--border-soft)", paddingBottom: 6 }}>
                                    <span className="text-muted">{String(k)}</span>
                                    <span style={{ fontWeight: 500 }}>{String(v)}</span>
                                </div>
                            ))}
                        </div>
                    </Card>
                )}

                {sysstat && (
                    <Card title="System Status">
                        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                            {[
                                ["artifact.valid", String(sysstat.artifact.valid)],
                                ["artifact.reason", sysstat.artifact.reason ?? "—"],
                                ["artifact.expected_sha", sysstat.artifact.expected_sha ?? "—"],
                                ["artifact.actual_sha", sysstat.artifact.actual_sha ?? "—"],
                                ["metrics.count", String(Object.keys(sysstat.metrics).length)],
                            ].map(([k, v]) => (
                                <div key={k} className="flex justify-between text-sm" style={{ borderBottom: "1px solid var(--border-soft)", paddingBottom: 6 }}>
                                    <span className="text-muted">{k}</span>
                                    <span style={{ fontWeight: 500, maxWidth: 200, textAlign: "right", wordBreak: "break-all" }}>{String(v)}</span>
                                </div>
                            ))}
                        </div>
                    </Card>
                )}
            </div>

            {/* Recent errors */}
            {(artifact?.reason || (artifact?.valid === false && (artifact.expected_sha || artifact.actual_sha))) && (
                <div style={{ marginTop: 20 }}>
                    <Card title="Artifact Check Detail" subtitle="From system status endpoint">
                        <pre style={{ margin: 0, fontSize: 12, color: "var(--error)", whiteSpace: "pre-wrap" }}>
                            {JSON.stringify(artifact, null, 2)}
                        </pre>
                    </Card>
                </div>
            )}
        </div>
    );
}
