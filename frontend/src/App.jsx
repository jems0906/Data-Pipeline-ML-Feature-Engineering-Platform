import { useState } from "react";
import TopNav from "./components/TopNav";
import DependencyHealthStrip from "./components/DependencyHealthStrip";
import FeatureCatalog from "./pages/FeatureCatalog";
import PipelineBuilder from "./pages/PipelineBuilder";
import QualityDashboard from "./pages/QualityDashboard";
import UsageTracking from "./pages/UsageTracking";

export default function App() {
  const [current, setCurrent] = useState("Pipeline Builder");

  return (
    <div className="app-shell">
      <div className="bg-orb orb-a" />
      <div className="bg-orb orb-b" />
      <TopNav current={current} setCurrent={setCurrent} />
      <DependencyHealthStrip />
      <main>
        {current === "Pipeline Builder" && <PipelineBuilder />}
        {current === "Quality Dashboard" && <QualityDashboard />}
        {current === "Feature Catalog" && <FeatureCatalog />}
        {current === "Usage Tracking" && <UsageTracking />}
      </main>
    </div>
  );
}
