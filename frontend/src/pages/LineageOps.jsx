import { useEffect, useState } from "react";
import { fetchPipelineLineage, fetchTrainingJobs, runBackfill, triggerTrainingJob } from "../api/client";

const initialBackfill = {
  run_id_prefix: "backfill-ui",
  start_date: "2026-01-01T00:00:00Z",
  end_date: "2026-01-03T00:00:00Z",
  window_days: 1,
  source: {
    source_type: "warehouse",
    source_name: "bigquery",
    config: {
      query: "SELECT 1 AS entity_id, CURRENT_TIMESTAMP() AS event_ts, 42.0 AS amount",
      allow_demo_fallback: true,
    },
  },
  transformations: {
    register_features: [{ name: "amount", entity_key: "entity_id", dtype: "float" }],
  },
};

export default function LineageOps() {
  const [lineage, setLineage] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [runId, setRunId] = useState("");
  const [trainingSourceRun, setTrainingSourceRun] = useState("manual-run-001");
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [backfillBusy, setBackfillBusy] = useState(false);

  async function loadData(filterRunId = "") {
    try {
      const [lineageRows, trainingJobs] = await Promise.all([
        fetchPipelineLineage({ runId: filterRunId, limit: 20 }),
        fetchTrainingJobs(20),
      ]);
      setLineage(lineageRows);
      setJobs(trainingJobs);
    } catch (err) {
      setError(String(err.message || err));
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function onTriggerTraining() {
    setError("");
    const response = await triggerTrainingJob({
      source_run_id: trainingSourceRun,
      drift_scores: { feature_a: 0.29, feature_b: 0.06 },
      force: false,
    });
    setStatus(response.scheduled ? `Training job ${response.training_job.id} scheduled` : response.reason);
    await loadData(runId);
  }

  async function onRunBackfill() {
    setBackfillBusy(true);
    setError("");
    try {
      const response = await runBackfill(initialBackfill);
      setStatus(`Backfill windows completed: ${response.run_count}`);
      await loadData(runId);
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setBackfillBusy(false);
    }
  }

  return (
    <section className="panel ops-grid-panel">
      <div className="ops-controls">
        <h2>Lineage & Ops</h2>
        <div className="usage-form">
          <input
            className="search"
            placeholder="Filter lineage by run id"
            value={runId}
            onChange={(e) => setRunId(e.target.value)}
          />
          <button type="button" className="primary" onClick={() => loadData(runId)}>
            Refresh Lineage
          </button>
          <input
            className="search"
            placeholder="Training source run id"
            value={trainingSourceRun}
            onChange={(e) => setTrainingSourceRun(e.target.value)}
          />
          <button type="button" className="primary secondary-action" onClick={onTriggerTraining}>
            Trigger Retraining
          </button>
          <button type="button" className="primary" onClick={onRunBackfill} disabled={backfillBusy}>
            {backfillBusy ? "Running Backfill..." : "Run Backfill"}
          </button>
        </div>
        {status && <p className="dispatch-summary">{status}</p>}
        {error && <pre className="error-box">{error}</pre>}
      </div>

      <div className="ops-grid">
        <div>
          <h3>Recent Lineage Events</h3>
          <ul className="events-list">
            {lineage.map((event, index) => (
              <li key={`${event.run_id}-${event.event_type}-${index}`}>
                <strong>{event.event_type}</strong>
                <span>{event.run_id}</span>
                <em>{event.created_at}</em>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h3>Training Jobs</h3>
          <ul className="events-list">
            {jobs.map((job) => (
              <li key={job.id}>
                <strong>{job.status}</strong>
                <span>{job.source_run_id}</span>
                <em>{job.trigger_reason}</em>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}