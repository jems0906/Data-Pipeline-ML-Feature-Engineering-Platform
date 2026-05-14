const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api/v1";

export async function fetchQualityReport() {
  const res = await fetch(`${API_BASE}/pipelines/quality-report`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to fetch quality report");
  return res.json();
}

export async function fetchPipelineLineage({ runId = "", limit = 50 } = {}) {
  const params = new URLSearchParams({ run_id: runId, limit: String(limit) });
  const res = await fetch(`${API_BASE}/pipelines/lineage?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch lineage events");
  return res.json();
}

export async function fetchTrainingJobs(limit = 25) {
  const res = await fetch(`${API_BASE}/pipelines/training-jobs?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch training jobs");
  return res.json();
}

export async function triggerTrainingJob(payload) {
  const res = await fetch(`${API_BASE}/pipelines/training-jobs/trigger`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Failed to trigger training job");
  }
  return res.json();
}

export async function runBackfill(payload) {
  const res = await fetch(`${API_BASE}/pipelines/backfill`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Failed to run backfill");
  }
  return res.json();
}

export async function fetchLineageGraph({ runId = "", limit = 500 } = {}) {
  const params = new URLSearchParams({ run_id: runId, limit: String(limit) });
  const res = await fetch(`${API_BASE}/pipelines/lineage/graph?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch lineage graph");
  return res.json();
}

export async function runScaleProof(payload) {
  const res = await fetch(`${API_BASE}/pipelines/proofs/scale`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Failed to run scale proof");
  }
  return res.json();
}

export async function runWarehouseValidation(payload) {
  const res = await fetch(`${API_BASE}/pipelines/proofs/warehouse-validation`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Failed to run warehouse validation");
  }
  return res.json();
}

export async function fetchFeatures(search = "") {
  const params = new URLSearchParams({ search });
  const res = await fetch(`${API_BASE}/features?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch features");
  return res.json();
}

export async function fetchDependencyHealth() {
  const res = await fetch(`${API_BASE}/health/dependencies`);
  if (!res.ok) throw new Error("Failed to fetch dependency health");
  return res.json();
}

export async function runPipeline(payload) {
  const res = await fetch(`${API_BASE}/pipelines/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Failed to run pipeline");
  }
  return res.json();
}

export async function fetchFeatureUsage({ modelSearch = "", featureSearch = "" } = {}) {
  const params = new URLSearchParams({ model_search: modelSearch, feature_search: featureSearch });
  const res = await fetch(`${API_BASE}/features/usage?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch feature usage");
  return res.json();
}

export async function recordFeatureUsage(payload) {
  const res = await fetch(`${API_BASE}/features/usage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Failed to record feature usage");
  }
  return res.json();
}

export async function fetchPipelineAlerts(limit = 50) {
  const res = await fetch(`${API_BASE}/pipelines/alerts?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch pipeline alerts");
  return res.json();
}

export async function dispatchPipelineAlerts(limit = 20) {
  const res = await fetch(`${API_BASE}/pipelines/alerts/dispatch?limit=${limit}`, {
    method: "POST",
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Failed to dispatch pipeline alerts");
  }
  return res.json();
}

export async function ingestRealtimeEvent(payload) {
  const res = await fetch(`${API_BASE}/pipelines/realtime-event`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Failed to ingest realtime event");
  }
  return res.json();
}
