import { useState } from "react";
import { Link } from "react-router-dom";
import { Play, ShieldCheck, CreditCard, Activity, ScrollText, Database, Key, RefreshCw } from "lucide-react";
import PageHeader from "../components/PageHeader";
import Card from "../components/Card";
import Badge from "../components/Badge";

const quickLinks = [
  { to: "/modeling", icon: Database, label: "Modeling", desc: "Register & preview data models" },
  { to: "/execution", icon: Play, label: "Execution", desc: "Submit and monitor jobs" },
  { to: "/preflight", icon: ShieldCheck, label: "Preflight", desc: "Run pre-execution gate checks" },
  { to: "/billing", icon: CreditCard, label: "Billing", desc: "View monthly spend & ledger" },
  { to: "/health", icon: Activity, label: "Health", desc: "System status & uptime" },
  { to: "/audit", icon: ScrollText, label: "Audit Log", desc: "Actor & event history" },
];

export default function Dashboard() {
  const [token, setToken] = useState(localStorage.getItem("COPILOT_TOKEN") || "");
  const [tenant, setTenant] = useState(localStorage.getItem("COPILOT_TENANT") || "default");
  const [saved, setSaved] = useState(false);

  const save = () => {
    localStorage.setItem("COPILOT_TOKEN", token || "dev_admin_token");
    localStorage.setItem("COPILOT_TENANT", tenant || "default");
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle="Data Platform Copilot — developer console"
        actions={<Badge variant="success" dot>Connected</Badge>}
      />

      {/* Quick nav cards */}
      <div className="grid-3" style={{ marginBottom: 24 }}>
        {quickLinks.map(({ to, icon: Icon, label, desc }) => (
          <Link
            key={to}
            to={to}
            style={{ textDecoration: "none" }}
          >
            <div
              className="card"
              style={{
                padding: "18px 20px",
                cursor: "pointer",
                transition: "border-color var(--transition), box-shadow var(--transition), transform 120ms",
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLDivElement).style.borderColor = "var(--accent)";
                (e.currentTarget as HTMLDivElement).style.boxShadow = "0 0 0 1px var(--accent-glow)";
                (e.currentTarget as HTMLDivElement).style.transform = "translateY(-1px)";
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLDivElement).style.borderColor = "var(--border)";
                (e.currentTarget as HTMLDivElement).style.boxShadow = "none";
                (e.currentTarget as HTMLDivElement).style.transform = "translateY(0)";
              }}
            >
              <div className="flex items-center gap-3" style={{ marginBottom: 8 }}>
                <div style={{
                  width: 32, height: 32, borderRadius: "var(--radius-md)",
                  background: "var(--accent-subtle)", display: "flex",
                  alignItems: "center", justifyContent: "center", flexShrink: 0,
                }}>
                  <Icon size={15} color="var(--accent)" strokeWidth={2} />
                </div>
                <span style={{ fontWeight: 600, fontSize: 13, color: "var(--text-primary)" }}>{label}</span>
              </div>
              <p style={{ margin: 0, fontSize: 12, color: "var(--text-muted)" }}>{desc}</p>
            </div>
          </Link>
        ))}
      </div>

      {/* Auth settings */}
      <Card title="Auth & Tenant" subtitle="Credentials are stored in localStorage for this dev session">
        <div className="grid-2" style={{ gap: 16 }}>
          <div>
            <label htmlFor="dash-token"><Key size={11} style={{ marginRight: 4, verticalAlign: "middle" }} />Bearer Token</label>
            <input
              id="dash-token"
              type="text"
              placeholder="dev_admin_token"
              value={token}
              onChange={e => setToken(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="dash-tenant">X-Tenant</label>
            <input
              id="dash-tenant"
              type="text"
              placeholder="default"
              value={tenant}
              onChange={e => setTenant(e.target.value)}
            />
          </div>
        </div>
        <div style={{ marginTop: 14, display: "flex", gap: 10, alignItems: "center" }}>
          <button className="btn btn-primary btn-sm" onClick={save}>
            <RefreshCw size={12} />
            {saved ? "Saved!" : "Apply & Reload"}
          </button>
          <span className="text-sm text-muted">Tip: use <code style={{ background: "var(--surface-3)", padding: "1px 5px", borderRadius: 4 }}>dev_admin_token</code> for full access.</span>
        </div>
      </Card>
    </div>
  );
}
