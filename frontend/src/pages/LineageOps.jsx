import { useEffect, useState } from "react";
import {
  fetchLineageGraph,
  fetchPipelineLineage,
  fetchTrainingJobs,
  runBackfill,
  runScaleProof,
  runWarehouseValidation,
  triggerTrainingJob,
} from "../api/client";

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
  const [proofSummary, setProofSummary] = useState(null);

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

  async function onRunScaleProof() {
    setError("");
    const proof = await runScaleProof({
      model_count: 120,
      feature_pool_size: 300,
      features_per_model: 20,
      synthetic_rows: 50000,
      synthetic_partitions: 4,
    });
    setProofSummary({
      title: "Scale Proof",
      details: `models=${proof.feature_reuse_benchmark.model_count}, target100=${proof.feature_reuse_benchmark.target_100_models_met}, projected_petabyte_hours=${proof.transformation_benchmark.projected_petabyte_hours.toFixed(2)}`,
    });
    await loadData(runId);
  }

  async function onLoadLineageGraph() {
    setError("");
    const graph = await fetchLineageGraph({ runId, limit: 500 });
    setProofSummary({
      title: "Lineage Graph",
      details: `runs=${graph.summary.runs_covered}, events=${graph.summary.events_covered}, coverage=${(graph.summary.event_type_coverage * 100).toFixed(1)}%`,
    });
  }

  async function onRunWarehouseValidation() {
    setError("");
    const report = await runWarehouseValidation({
      checks: [
        { source_name: "bigquery", query: "SELECT 1", config: {} },
        { source_name: "snowflake", query: "SELECT 1", config: {} },
      ],
    });
    setProofSummary({
      title: "Warehouse Validation",
      details: `checks=${report.checks_total}, passed=${report.checks_passed}, failed=${report.checks_failed}`,
    });
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
          <button type="button" className="primary secondary-action" onClick={onRunScaleProof}>
            Run Scale Proof
          </button>
          <button type="button" className="primary secondary-action" onClick={onLoadLineageGraph}>
            Build Lineage Graph
          </button>
          <button type="button" className="primary secondary-action" onClick={onRunWarehouseValidation}>
            Validate Warehouses
          </button>
        </div>
        {status && <p className="dispatch-summary">{status}</p>}
        {proofSummary && <p className="dispatch-summary">{proofSummary.title}: {proofSummary.details}</p>}
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