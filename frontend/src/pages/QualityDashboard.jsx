import { useEffect, useState } from "react";
import { dispatchPipelineAlerts, fetchPipelineAlerts, fetchQualityReport } from "../api/client";

function Bar({ label, value }) {
  return (
    <div className="bar-row">
      <strong>{label}</strong>
      <div className="bar">
        <span style={{ width: `${Math.min(100, Math.round(value * 100))}%` }} />
      </div>
      <em>{(value * 100).toFixed(1)}%</em>
    </div>
  );
}

export default function QualityDashboard() {
  const [report, setReport] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [dispatchSummary, setDispatchSummary] = useState(null);
  const [dispatchBusy, setDispatchBusy] = useState(false);
  const [error, setError] = useState("");

  async function loadDashboard() {
    try {
      const [quality, recentAlerts] = await Promise.all([fetchQualityReport(), fetchPipelineAlerts(12)]);
      setReport(quality);
      setAlerts(recentAlerts);
    } catch {
      setReport(null);
      setAlerts([]);
    }
  }

  useEffect(() => {
    loadDashboard();
  }, []);

  async function onDispatchAlerts() {
    setDispatchBusy(true);
    setError("");
    try {
      const summary = await dispatchPipelineAlerts(12);
      setDispatchSummary(summary);
      const refreshed = await fetchPipelineAlerts(12);
      setAlerts(refreshed);
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setDispatchBusy(false);
    }
  }

  return (
    <section className="panel">
      <h2>Data Quality Dashboard</h2>
      {!report && <p>Loading quality metrics...</p>}
      {report && (
        <>
          <p>Rows scanned: {report.row_count}</p>
          <h3>Missing Rates</h3>
          {Object.entries(report.missing_rates).map(([k, v]) => (
            <Bar key={k} label={k} value={v} />
          ))}
          <h3>Outlier Rates</h3>
          {Object.entries(report.outlier_rates).map(([k, v]) => (
            <Bar key={k} label={k} value={v} />
          ))}

          <div className="quality-alerts">
            <div className="quality-alerts-header">
              <h3>Recent Alerts</h3>
              <button type="button" className="primary" onClick={onDispatchAlerts} disabled={dispatchBusy}>
                {dispatchBusy ? "Dispatching..." : "Dispatch Alerts"}
              </button>
            </div>

            {dispatchSummary && (
              <p className="dispatch-summary">
                Sent: {dispatchSummary.notifications_sent} | Simulated: {dispatchSummary.notifications_simulated} |
                Failed: {dispatchSummary.notifications_failed}
              </p>
            )}

            {error && <pre className="error-box">{error}</pre>}

            {!alerts.length && <p>No alerts captured yet.</p>}
            {alerts.length > 0 && (
              <ul className="alerts-list">
                {alerts.map((alert, index) => (
                  <li key={`${alert.run_id}-${alert.alert_type}-${index}`}>
                    <strong>{alert.alert_type}</strong>
                    <span>{alert.severity}</span>
                    <em>{alert.run_id}</em>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </section>
  );
}
