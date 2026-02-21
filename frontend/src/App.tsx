import { Routes, Route, Link } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Modeling from "./pages/Modeling";

export default function App() {
  return (
    <div style={{ fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Arial" }}>
      <header style={{ padding: 16, borderBottom: "1px solid #333" }}>
        <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
          <div style={{ fontWeight: 700 }}>Data Platform Copilot</div>
          <nav style={{ display: "flex", gap: 12 }}>
            <Link to="/" style={{ color: "inherit" }}>Dashboard</Link>
            <Link to="/modeling" style={{ color: "inherit" }}>Modeling</Link>
          </nav>
        </div>
      </header>

      <main style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/modeling" element={<Modeling />} />
        </Routes>
      </main>
    </div>
  );
}
