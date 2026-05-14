import { useEffect, useState } from "react";
import { fetchFeatures } from "../api/client";

export default function FeatureCatalog() {
  const [search, setSearch] = useState("");
  const [items, setItems] = useState([]);

  useEffect(() => {
    fetchFeatures(search).then(setItems).catch(() => setItems([]));
  }, [search]);

  return (
    <section className="panel">
      <h2>Feature Catalog</h2>
      <input
        className="search"
        placeholder="Search features"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Entity Key</th>
              <th>Type</th>
              <th>Schema Version</th>
              <th>Freshness (s)</th>
              <th>Usage Events</th>
              <th>Models</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.name}>
                <td>{item.name}</td>
                <td>{item.entity_key}</td>
                <td>{item.dtype}</td>
                <td>{item.schema_version}</td>
                <td>{item.freshness_seconds}</td>
                <td>{item.usage_count}</td>
                <td>{item.model_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
