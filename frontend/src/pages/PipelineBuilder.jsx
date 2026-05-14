import { useState } from "react";
import { ingestRealtimeEvent, runPipeline } from "../api/client";

const initialStages = ["Ingestion", "Validation", "Feature Engineering", "Point-in-Time Store", "Export"];

const samplePayload = {
  run_id: `run-${Date.now()}`,
  source: {
    source_type: "warehouse",
    source_name: "bigquery",
    config: {
      query: "SELECT 1 AS entity_id, CURRENT_TIMESTAMP() AS event_ts, 10.2 AS amount",
      allow_demo_fallback: true,
    },
  },
  transformations: {
    required_columns: ["entity_id", "event_ts"],
    feature_engineering: [{ name: "amount_x2", expression: "amount * 2" }],
    register_features: [{ name: "amount_x2", entity_key: "entity_id", dtype: "float" }],
  },
};

export default function PipelineBuilder() {
  const [stages, setStages] = useState(initialStages);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [realtimeBusy, setRealtimeBusy] = useState(false);
  const [realtimeResult, setRealtimeResult] = useState(null);
  const [dragFrom, setDragFrom] = useState(-1);

  function onDragStart(index) {
    setDragFrom(index);
  }

  function onDropAt(index) {
    if (dragFrom < 0 || dragFrom === index) return;
    setStages((prev) => {
      const next = [...prev];
      const [item] = next.splice(dragFrom, 1);
      next.splice(index, 0, item);
      return next;
    });
    setDragFrom(-1);
  }

  async function onRun() {
    setBusy(true);
    setError("");
    try {
      const data = await runPipeline(samplePayload);
      setResult(data);
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setBusy(false);
    }
  }

  async function onSendRealtimeEvent() {
    setRealtimeBusy(true);
    setError("");
    try {
      const payload = {
        run_id: `rt-ui-${Date.now()}`,
        source_name: "pipeline-builder-ui",
        stream_name: "feature-events",
        event: {
          entity_id: "demo-ui-1",
          event_ts: new Date().toISOString(),
          amount: 17.25,
          channel: "ui",
        },
      };
      const data = await ingestRealtimeEvent(payload);
      setRealtimeResult(data);
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setRealtimeBusy(false);
    }
  }

  return (
    <section className="panel">
      <h2>Visual Pipeline Builder</h2>
      <p>Drag and drop stages to define execution order for ingestion, quality, transforms, feature-store write, and export.</p>

      <div className="stage-grid">
        {stages.map((stage, index) => (
          <div
            key={stage}
            className={`stage-card ${dragFrom === index ? "dragging" : ""}`}
            draggable
            onDragStart={() => onDragStart(index)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => onDropAt(index)}
          >
            <span>{stage}</span>
            <small>Step {index + 1}</small>
          </div>
        ))}
      </div>

      <p className="stage-order">Execution order: {stages.join(" -> ")}</p>

      <button type="button" className="primary" onClick={onRun} disabled={busy}>
        {busy ? "Running..." : "Run Sample Pipeline"}
      </button>

      <button
        type="button"
        className="primary secondary-action"
        onClick={onSendRealtimeEvent}
        disabled={realtimeBusy}
      >
        {realtimeBusy ? "Sending..." : "Send Realtime Event"}
      </button>

      {error && <pre className="error-box">{error}</pre>}
      {result && <pre className="code-box">{JSON.stringify(result, null, 2)}</pre>}
      {realtimeResult && <pre className="code-box">{JSON.stringify(realtimeResult, null, 2)}</pre>}
    </section>
  );
}
