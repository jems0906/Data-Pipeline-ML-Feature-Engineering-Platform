import { useEffect, useState } from "react";
import { fetchFeatureUsage, recordFeatureUsage } from "../api/client";

const initialForm = {
  model_name: "",
  feature_name: "",
  usage: "training",
};

export default function UsageTracking() {
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function loadRows() {
    try {
      const data = await fetchFeatureUsage();
      setRows(data);
    } catch {
      setRows([]);
    }
  }

  useEffect(() => {
    loadRows();
  }, []);

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await recordFeatureUsage(form);
      setForm(initialForm);
      await loadRows();
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <h2>Feature Usage Tracking</h2>

      <form className="usage-form" onSubmit={onSubmit}>
        <input
          className="search"
          placeholder="Model name"
          value={form.model_name}
          onChange={(e) => setForm((prev) => ({ ...prev, model_name: e.target.value }))}
          required
        />
        <input
          className="search"
          placeholder="Feature name"
          value={form.feature_name}
          onChange={(e) => setForm((prev) => ({ ...prev, feature_name: e.target.value }))}
          required
        />
        <select
          className="search"
          value={form.usage}
          onChange={(e) => setForm((prev) => ({ ...prev, usage: e.target.value }))}
        >
          <option value="training">training</option>
          <option value="inference">inference</option>
          <option value="training+inference">training+inference</option>
        </select>
        <button type="submit" className="primary" disabled={busy}>
          {busy ? "Saving..." : "Record Usage"}
        </button>
      </form>

      {error && <pre className="error-box">{error}</pre>}

      <ul className="usage-list">
        {rows.map((row) => (
          <li key={`${row.created_at}-${row.model_name}-${row.feature_name}`}>
            <strong>{row.model_name}</strong>
            <span>{row.feature_name}</span>
            <em>{row.usage}</em>
          </li>
        ))}
      </ul>
    </section>
  );
}
