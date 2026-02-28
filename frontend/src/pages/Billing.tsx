import { useState, useEffect, useCallback } from "react";
import { RefreshCw, CreditCard } from "lucide-react";
import { toast } from "sonner";
import {
    getApiErrorMessage,
    getBillingSummary,
    type BillingSummaryResponse,
} from "../lib/api";
import PageHeader from "../components/PageHeader";
import Card from "../components/Card";

const MONTHS = Array.from({ length: 6 }, (_, i) => {
    const d = new Date();
    d.setMonth(d.getMonth() - i);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
});

export default function Billing() {
    const [month, setMonth] = useState(MONTHS[0]);
    const [summary, setSummary] = useState<BillingSummaryResponse | null>(null);
    const [loading, setLoading] = useState(false);

    const load = useCallback(async (m: string) => {
        setLoading(true);
        setSummary(null);
        try {
            const data = await getBillingSummary({ month: m });
            setSummary(data);
        } catch (e: unknown) {
            toast.error(getApiErrorMessage(e, "Billing fetch failed"));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void load(month);
    }, [month, load]);

    const totalEstimated = summary?.spent_estimated_usd ?? 0;
    const totalActual = summary?.spent_actual_usd ?? 0;
    const budget = summary?.limit_usd ?? 500;
    const spent_pct = Math.min(
        Math.max((summary?.utilization_estimated ?? (budget > 0 ? totalEstimated / budget : 0)) * 100, 0),
        100,
    );
    const remaining = summary?.remaining_estimated_usd ?? Math.max(budget - totalEstimated, 0);
    const jobsRun = summary?.entries_count ?? 0;

    return (
        <div>
            <PageHeader
                title="Billing"
                subtitle="Monthly spend overview and per-job cost ledger"
                actions={
                    <div className="flex items-center gap-3">
                        <select style={{ width: "auto" }} value={month} onChange={e => setMonth(e.target.value)}>
                            {MONTHS.map(m => <option key={m} value={m}>{m}</option>)}
                        </select>
                        <button className="btn btn-secondary btn-icon" onClick={() => void load(month)} disabled={loading}>
                            {loading ? <span className="spinner" /> : <RefreshCw size={14} />}
                        </button>
                    </div>
                }
            />

            {/* KPI cards */}
            <div className="grid-3" style={{ marginBottom: 20 }}>
                <div className="kpi-card">
                    <div className="kpi-card__label"><CreditCard size={10} style={{ marginRight: 4, verticalAlign: "middle" }} />Total Spend</div>
                    <div className="kpi-card__value">${totalEstimated.toFixed(2)}</div>
                    <div className="kpi-card__sub">of ${budget.toFixed(0)} budget</div>
                </div>
                <div className="kpi-card">
                    <div className="kpi-card__label">Budget Remaining</div>
                    <div className="kpi-card__value" style={{ color: remaining < budget * 0.2 ? "var(--error)" : "var(--success)" }}>
                        ${remaining.toFixed(2)}
                    </div>
                    <div className="kpi-card__sub">{(100 - spent_pct).toFixed(1)}% left</div>
                </div>
                <div className="kpi-card">
                    <div className="kpi-card__label">Ledger Entries</div>
                    <div className="kpi-card__value">{jobsRun}</div>
                    <div className="kpi-card__sub">in {month}</div>
                </div>
            </div>

            {/* Budget progress */}
            <Card title="Budget Utilization" style={{ marginBottom: 20 }}>
                <div className="progress-track" style={{ height: 8 }}>
                    <div
                        className={`progress-bar ${spent_pct > 80 ? "danger" : spent_pct > 60 ? "warn" : ""}`}
                        style={{ width: `${spent_pct}%` }}
                    />
                </div>
                <div className="flex justify-between mt-2" style={{ fontSize: 12, color: "var(--text-muted)" }}>
                    <span>${totalEstimated.toFixed(2)} spent</span>
                    <span>{spent_pct.toFixed(1)}%</span>
                    <span>${budget.toFixed(0)} budget</span>
                </div>
            </Card>

            {/* Billing detail table */}
            <Card title="Billing Summary" subtitle={summary ? `${summary.entries_count} entries` : "No summary data"} noPadding>
                <div className="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Metric</th>
                                <th>Value</th>
                            </tr>
                        </thead>
                        <tbody>
                            {!summary ? (
                                <tr><td colSpan={2} style={{ textAlign: "center", color: "var(--text-muted)" }}>
                                    {loading ? "Loading…" : "No summary for this month"}
                                </td></tr>
                            ) : (
                                [
                                    ["Tenant", summary.tenant],
                                    ["Month", summary.month],
                                    ["Budget (USD)", `$${summary.limit_usd.toFixed(2)}`],
                                    ["Estimated Spend (USD)", `$${summary.spent_estimated_usd.toFixed(2)}`],
                                    ["Actual Spend (USD)", `$${totalActual.toFixed(2)}`],
                                    ["Remaining (USD)", `$${summary.remaining_estimated_usd.toFixed(2)}`],
                                    ["Utilization", `${(summary.utilization_estimated * 100).toFixed(1)}%`],
                                    ["Entries", String(summary.entries_count)],
                                ].map(([label, value]) => (
                                    <tr key={label}>
                                        <td style={{ color: "var(--text-primary)", fontWeight: 500 }}>{label}</td>
                                        <td>{value}</td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </Card>
        </div>
    );
}
