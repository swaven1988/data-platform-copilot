export default function Dashboard() {
  const token = localStorage.getItem("COPILOT_TOKEN") || "";

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Dashboard</h1>

      <div style={{ marginTop: 16, padding: 16, border: "1px solid #333", borderRadius: 12 }}>
        <div style={{ fontWeight: 700, marginBottom: 8 }}>Auth Token</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            style={{ flex: 1, padding: 10, borderRadius: 8, border: "1px solid #555", background: "transparent", color: "inherit" }}
            placeholder="Paste token (e.g., dev_admin_token)"
            defaultValue={token}
            onChange={(e) => localStorage.setItem("COPILOT_TOKEN", e.target.value)}
          />
          <button
            style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid #555", background: "transparent", color: "inherit", cursor: "pointer" }}
            onClick={() => window.location.reload()}
          >
            Apply
          </button>
        </div>

        <div style={{ marginTop: 10, opacity: 0.8 }}>
          Tip: use <code>dev_admin_token</code> for full access in your dev env.
        </div>
      </div>
    </div>
  );
}
