import "./App.css";
import { Routes, Route } from "react-router-dom";
import { Settings } from "lucide-react";
import Sidebar from "./components/Sidebar";
import Toast from "./components/Toast";
import Badge from "./components/Badge";
import Dashboard from "./pages/Dashboard";
import Modeling from "./pages/Modeling";
import Execution from "./pages/Execution";
import Preflight from "./pages/Preflight";
import Billing from "./pages/Billing";
import Health from "./pages/Health";
import AuditLog from "./pages/AuditLog";
import Approvals from "./pages/Approvals";

const tenant = localStorage.getItem("COPILOT_TENANT") || "default";
const token = localStorage.getItem("COPILOT_TOKEN") || "";
const role = token.includes("viewer") ? "viewer" : token.includes("admin") ? "admin" : "admin";

export default function App() {
  return (
    <>
      <div className="app-shell">
        {/* Header */}
        <header className="app-header">
          <div className="app-header__left">
            <div className="app-header__wordmark">
              Data Platform <span>Copilot</span>
            </div>
          </div>
          <div className="app-header__right">
            <Badge variant="neutral">{tenant}</Badge>
            <Badge variant={role === "admin" ? "accent" : "neutral"}>{role}</Badge>
            <button
              className="btn btn-ghost btn-icon"
              title="Settings"
              onClick={() => {
                const t = prompt("Bearer token (leave blank for dev_admin_token):");
                if (t !== null) localStorage.setItem("COPILOT_TOKEN", t || "dev_admin_token");
                const ten = prompt("Tenant (leave blank for 'default'):");
                if (ten !== null) localStorage.setItem("COPILOT_TENANT", ten || "default");
                window.location.reload();
              }}
            >
              <Settings size={15} strokeWidth={1.8} />
            </button>
          </div>
        </header>

        {/* Body */}
        <div className="app-body">
          <Sidebar />
          <main className="main-content">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/modeling" element={<Modeling />} />
              <Route path="/execution" element={<Execution />} />
              <Route path="/preflight" element={<Preflight />} />
              <Route path="/billing" element={<Billing />} />
              <Route path="/health" element={<Health />} />
              <Route path="/audit" element={<AuditLog />} />
              <Route path="/approvals" element={<Approvals />} />
            </Routes>
          </main>
        </div>
      </div>
      <Toast />
    </>
  );
}
