import { useState, useEffect } from "react";
import { X, Copy, Check, Download, Wifi, RefreshCw } from "lucide-react";
import { getConnectorStatus } from "../api";

export default function ConnectionModal({ token, onClose, onSubmit, isLoading }) {
  const [activeTab, setActiveTab] = useState("direct"); // "direct" | "local"
  const [name, setName] = useState("");
  const [connString, setConnString] = useState("");
  const [dialect, setDialect] = useState("PostgreSQL");

  // Local Connector tab states
  const [copiedToken, setCopiedToken] = useState(false);
  const [copiedCmd, setCopiedCmd] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [checkingStatus, setCheckingStatus] = useState(false);
  const [localDbString, setLocalDbString] = useState("");

  const serverUrl = (import.meta.env.VITE_API_BASE_URL || window.location.origin).replace(/\/$/, "");
  const runCommand = `python connector.py --server ${serverUrl} --token ${token || "YOUR_TOKEN"} --db "${localDbString}"`;

  const checkStatus = async () => {
    if (!token) return;
    setCheckingStatus(true);
    try {
      const res = await getConnectorStatus(token);
      setIsConnected(res.connected);
    } catch {
      setIsConnected(false);
    } finally {
      setCheckingStatus(false);
    }
  };

  useEffect(() => {
    if (activeTab === "local" && token) {
      checkStatus();
      const interval = setInterval(checkStatus, 3000);
      return () => clearInterval(interval);
    }
  }, [activeTab, token]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    const finalConnString = activeTab === "local" ? localDbString.trim() : connString.trim();
    if (!finalConnString) return;

    onSubmit({
      name: name.trim(),
      connectionString: finalConnString,
      dbDialect: dialect,
    });
  };

  const copyToClipboard = (text, type) => {
    navigator.clipboard.writeText(text);
    if (type === "token") {
      setCopiedToken(true);
      setTimeout(() => setCopiedToken(false), 2000);
    } else {
      setCopiedCmd(true);
      setTimeout(() => setCopiedCmd(false), 2000);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-large" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Add Database Connection</h2>
          <button className="btn-icon" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {/* Connection Type Tabs */}
        <div className="modal-tabs" style={{ display: "flex", gap: "8px", marginBottom: "16px", borderBottom: "1px solid var(--border-color, #333)", paddingBottom: "8px" }}>
          <button
            type="button"
            className={`tab-btn ${activeTab === "direct" ? "active" : ""}`}
            style={{
              padding: "8px 16px",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              fontWeight: 500,
              background: activeTab === "direct" ? "#3b82f6" : "transparent",
              color: activeTab === "direct" ? "#fff" : "#9ca3af",
            }}
            onClick={() => setActiveTab("direct")}
          >
            Cloud / Direct DB
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === "local" ? "active" : ""}`}
            style={{
              padding: "8px 16px",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              fontWeight: 500,
              display: "flex",
              alignItems: "center",
              gap: "6px",
              background: activeTab === "local" ? "#3b82f6" : "transparent",
              color: activeTab === "local" ? "#fff" : "#9ca3af",
            }}
            onClick={() => setActiveTab("local")}
          >
            <Wifi size={16} /> Local PC Database (WebSocket)
          </button>
        </div>

        <form onSubmit={handleSubmit} autoComplete="off">
          <div className="form-group">
            <label htmlFor="conn-name">Connection Name</label>
            <input
              id="conn-name"
              type="text"
              placeholder="e.g. production_analytics"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="conn-dialect">Database Dialect</label>
            <select
              id="conn-dialect"
              value={dialect}
              onChange={(e) => setDialect(e.target.value)}
            >
              <option value="PostgreSQL">PostgreSQL</option>
              <option value="MySQL">MySQL</option>
              <option value="MSSQL">SQL Server</option>
              <option value="SQLite">SQLite</option>
            </select>
          </div>

          {activeTab === "direct" ? (
            <div className="form-group">
              <label htmlFor="conn-string">Connection String</label>
              <input
                id="conn-string"
                type="text"
                placeholder="postgresql://user:pass@host:5432/dbname"
                value={connString}
                onChange={(e) => setConnString(e.target.value)}
                required
              />
              <small style={{ color: "#9ca3af", marginTop: "4px", display: "block" }}>
                Use this for Cloud DBs (Supabase, Neon, AWS) or publicly accessible endpoints.
              </small>
            </div>
          ) : (
            <div className="local-connector-box" style={{ background: "#111827", padding: "16px", borderRadius: "8px", marginBottom: "16px", border: "1px solid #374151" }}>
              {/* Connection Status Indicator */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", paddingBottom: "8px", borderBottom: "1px solid #1f2937" }}>
                <span style={{ fontSize: "14px", fontWeight: 600, color: "#d1d5db" }}>Local Connector Status:</span>
                <span style={{ display: "inline-flex", alignItems: "center", gap: "6px", fontSize: "13px", fontWeight: 600, color: isConnected ? "#10b981" : "#f59e0b" }}>
                  <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: isConnected ? "#10b981" : "#f59e0b", display: "inline-block" }} />
                  {isConnected ? "Connected & Ready" : "Waiting for connector..."}
                </span>
                <button
                  type="button"
                  onClick={checkStatus}
                  disabled={checkingStatus}
                  style={{ background: "none", border: "none", color: "#9ca3af", cursor: "pointer", display: "flex", alignItems: "center" }}
                  title="Refresh Status"
                >
                  <RefreshCw size={14} className={checkingStatus ? "spin" : ""} />
                </button>
              </div>

              <div className="form-group" style={{ marginBottom: "12px" }}>
                <label htmlFor="local-db-string">Local Database Connection String</label>
                <input
                  id="local-db-string"
                  type="text"
                  placeholder="postgresql://postgres:root@localhost:5432/pagila"
                  value={localDbString}
                  onChange={(e) => setLocalDbString(e.target.value)}
                  required
                />
              </div>

              <p style={{ fontSize: "13px", color: "#9ca3af", marginBottom: "12px" }}>
                Run this command in terminal on your computer to connect your local DB:
              </p>

              {/* Step 1: Download script */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: "#1f2937", padding: "8px 12px", borderRadius: "6px", marginBottom: "8px" }}>
                <span style={{ fontSize: "13px", color: "#e5e7eb" }}>1. Download Connector Script</span>
                <a
                  href={`${serverUrl}/api/v1/connector/script`}
                  download="connector.py"
                  className="btn-secondary"
                  style={{ display: "inline-flex", alignItems: "center", gap: "4px", padding: "4px 10px", fontSize: "12px", borderRadius: "4px", textDecoration: "none", background: "#374151", color: "#fff" }}
                >
                  <Download size={14} /> Download connector.py
                </a>
              </div>

              {/* Step 2: Copy command */}
              <div style={{ background: "#1f2937", padding: "8px 12px", borderRadius: "6px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <span style={{ fontSize: "13px", color: "#e5e7eb" }}>2. Run in Terminal</span>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(runCommand, "cmd")}
                    style={{ background: "none", border: "none", color: "#60a5fa", cursor: "pointer", display: "flex", alignItems: "center", gap: "4px", fontSize: "12px" }}
                  >
                    {copiedCmd ? <Check size={14} /> : <Copy size={14} />} {copiedCmd ? "Copied" : "Copy Command"}
                  </button>
                </div>
                <code style={{ display: "block", background: "#111827", padding: "8px", borderRadius: "4px", fontSize: "12px", color: "#34d399", wordBreak: "break-all" }}>
                  {runCommand}
                </code>
              </div>
            </div>
          )}

          <button type="submit" className="btn-primary" disabled={isLoading}>
            {isLoading ? (
              <span className="btn-spinner" />
            ) : (
              "Connect Database"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
