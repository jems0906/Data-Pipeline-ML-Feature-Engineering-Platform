export default function TopNav({ current, setCurrent }) {
  const tabs = ["Pipeline Builder", "Quality Dashboard", "Feature Catalog", "Usage Tracking"];

  return (
    <nav className="top-nav">
      <h1>FlowForge ML Data Platform</h1>
      <div className="tab-row">
        {tabs.map((tab) => (
          <button
            key={tab}
            type="button"
            className={current === tab ? "tab active" : "tab"}
            onClick={() => setCurrent(tab)}
          >
            {tab}
          </button>
        ))}
      </div>
    </nav>
  );
}
