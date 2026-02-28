import { useState, useEffect, useRef } from "react";
import { RefreshCw, Radio, ChevronDown, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import {
    getApiErrorMessage,
    getAuditLogEntries,
    type AuditLogRecord,
} from "../lib/api";
import PageHeader from "../components/PageHeader";
import Card from "../components/Card";
import Badge from "../components/Badge";

interface AuditFilter {
    tenant: string;
    actor: string;
    event: string;
}

function formatTimestamp(entry: AuditLogRecord): string {
    if (typeof entry.timestamp === "string" && entry.timestamp.trim()) {
        return new Date(entry.timestamp).toLocaleString();
    }
    if (typeof entry.ts_ms === "number") {
        return new Date(entry.ts_ms).toLocaleString();
    }
    return "—";
}

function getActor(entry: AuditLogRecord): string {
    const actor = typeof entry.actor === "string" ? entry.actor : typeof entry.user === "string" ? entry.user : "";
    return actor || "—";
}

function getEvent(entry: AuditLogRecord): string {
    const event =
        typeof entry.event_type === "string"
            ? entry.event_type
            : typeof entry.event === "string"
                ? entry.event
                : typeof entry.type === "string"
                    ? entry.type
                    : "";
    return event || "—";
}

function getDetails(entry: AuditLogRecord): string {
    if (typeof entry.details === "string" && entry.details.trim()) return entry.details;
    if (typeof entry.message === "string" && entry.message.trim()) return entry.message;
    if (entry.http && typeof entry.http === "object") {
        const method = typeof entry.http.method === "string" ? entry.http.method : "?";
        const path = typeof entry.http.path === "string" ? entry.http.path : "?";
        const status = typeof entry.http.status === "number" ? String(entry.http.status) : "?";
        return `${method} ${path} (${status})`;
    }
    return JSON.stringify(entry);
}

function LogRow({ entry }: { entry: AuditLogRecord }) {
    const [open, setOpen] = useState(false);
    const ts = formatTimestamp(entry);
    return (
        <tr style={{ cursor: "pointer" }} onClick={() => setOpen(o => !o)}>
            <td style={{ fontSize: 11, whiteSpace: "nowrap", color: "var(--text-muted)" }}>{ts}</td>
            <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{entry.tenant ?? "—"}</span></td>
            <td>{getActor(entry)}</td>
            <td>
                <Badge variant="accent">{getEvent(entry)}</Badge>
            </td>
            <td style={{ maxWidth: 260 }}>
                <div className="flex items-center gap-2">
                    {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                    <span className="truncate text-sm">{getDetails(entry)}</span>
                </div>
                {open && (
                    <pre style={{ margin: "8px 0 0", whiteSpace: "pre-wrap", fontSize: 11, color: "var(--text-secondary)" }}>
                        {JSON.stringify(entry, null, 2)}
                    </pre>
                )}
            </td>
        </tr>
    );
}

export default function AuditLog() {
    const [entries, setEntries] = useState<AuditLogRecord[]>([]);
    const [loading, setLoading] = useState(false);
    const [liveTail, setLiveTail] = useState(false);
    const [filter, setFilter] = useState<AuditFilter>({ tenant: "", actor: "", event: "" });
    const pollRef = useRef<number | null>(null);

    const fetch = async () => {
        setLoading(true);
        try {
            const raw = await getAuditLogEntries();
            setEntries(raw.slice().reverse()); // newest first
        } catch (e: unknown) {
            toast.error(getApiErrorMessage(e, "Audit fetch failed"));
        } finally {
            setLoading(false);
        }
    };

    const stopPoll = () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };

    useEffect(() => {
        fetch();
        return stopPoll;
    }, []);

    useEffect(() => {
        if (liveTail) {
            pollRef.current = setInterval(fetch, 5000) as unknown as number;
        } else {
            stopPoll();
        }
        return stopPoll;
    }, [liveTail]);

    const filtered = entries.filter(e => {
        const t = filter.tenant.toLowerCase();
        const a = filter.actor.toLowerCase();
        const ev = filter.event.toLowerCase();
        const tenant = typeof e.tenant === "string" ? e.tenant : "";
        const actor = getActor(e);
        const event = getEvent(e);
        return (
            (!t || tenant.toLowerCase().includes(t)) &&
            (!a || actor.toLowerCase().includes(a)) &&
            (!ev || event.toLowerCase().includes(ev))
        );
    });

    return (
        <div>
            <PageHeader
                title="Audit Log"
                subtitle="Actor and event history across all tenants"
                actions={
                    <div className="flex items-center gap-3">
                        <button
                            className={`btn btn-sm ${liveTail ? "btn-primary" : "btn-secondary"}`}
                            onClick={() => setLiveTail(l => !l)}
                        >
                            <Radio size={13} style={liveTail ? { animation: "spin 2s linear infinite" } : {}} />
                            {liveTail ? "Live (5s)" : "Live Tail"}
                        </button>
                        <button className="btn btn-secondary btn-icon" onClick={fetch} disabled={loading}>
                            {loading ? <span className="spinner" /> : <RefreshCw size={14} />}
                        </button>
                    </div>
                }
            />

            {/* Filter bar */}
            <div className="filter-bar" style={{ marginBottom: 20 }}>
                <div style={{ flex: 1 }}>
                    <input
                        type="text"
                        placeholder="Filter by tenant"
                        value={filter.tenant}
                        onChange={e => setFilter(f => ({ ...f, tenant: e.target.value }))}
                    />
                </div>
                <div style={{ flex: 1 }}>
                    <input
                        type="text"
                        placeholder="Filter by actor"
                        value={filter.actor}
                        onChange={e => setFilter(f => ({ ...f, actor: e.target.value }))}
                    />
                </div>
                <div style={{ flex: 1 }}>
                    <input
                        type="text"
                        placeholder="Filter by event type"
                        value={filter.event}
                        onChange={e => setFilter(f => ({ ...f, event: e.target.value }))}
                    />
                </div>
            </div>

            <Card title="Events" subtitle={`${filtered.length} of ${entries.length} entries`} noPadding>
                <div className="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Tenant</th>
                                <th>Actor</th>
                                <th>Event</th>
                                <th>Details</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.length === 0 ? (
                                <tr><td colSpan={5} style={{ textAlign: "center", color: "var(--text-muted)" }}>
                                    {loading ? "Loading…" : "No audit entries found"}
                                </td></tr>
                            ) : filtered.map((entry, i) => (
                                <LogRow key={i} entry={entry} />
                            ))}
                        </tbody>
                    </table>
                </div>
            </Card>
        </div>
    );
}
