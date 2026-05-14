import { useEffect, useState } from "react";

import { fetchDependencyHealth } from "../api/client";

function statusClass(status) {
  if (status === "ok") return "status-chip status-ok";
  if (status === "degraded") return "status-chip status-degraded";
  if (status === "error") return "status-chip status-error";
  return "status-chip status-unknown";
}

export default function DependencyHealthStrip() {
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadHealth() {
      try {
        const data = await fetchDependencyHealth();
        if (!active) return;
        setPayload(data);
        setError("");
      } catch (err) {
        if (!active) return;
        setError(String(err.message || err));
      }
    }

    loadHealth();
    const timerId = setInterval(loadHealth, 15000);
    return () => {
      active = false;
      clearInterval(timerId);
    };
  }, []);

  return (
    <section className="health-strip">
      <div className="health-header">
        <p className="health-title">Dependency Health</p>
        <span className={statusClass(payload?.status || "unknown")}>{payload?.status || "unknown"}</span>
      </div>
      {error && <div className="dep-detail">{error}</div>}
      {!error && payload?.dependencies && (
        <div className="dep-grid">
          {Object.entries(payload.dependencies).map(([name, check]) => (
            <div key={name} className="dep-card">
              <strong>{name}</strong>
              <span className={statusClass(check.status)}>{check.status}</span>
              <div className="dep-detail">{check.detail}</div>
            </div>
          ))}
        </div>
      )}
      {!error && payload?.checked_at && <div className="dep-detail">checked at {payload.checked_at}</div>}
    </section>
  );
}