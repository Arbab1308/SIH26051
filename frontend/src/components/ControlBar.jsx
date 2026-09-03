/**
 * ControlBar.jsx
 * Floating control bar for toggling views (Explode, Stress Map, Camera).
 */
import React from 'react';
import useSimulationStore from '../store/simulationStore';
import './ControlBar.css';

export default function ControlBar() {
  const explodedView = useSimulationStore((s) => s.explodedView);
  const stressMapVisible = useSimulationStore((s) => s.stressMapVisible);
  const setExplodedView = useSimulationStore((s) => s.setExplodedView);
  const setStressMapVisible = useSimulationStore((s) => s.setStressMapVisible);

  return (
    <div className="control-bar">
      <button
        className={explodedView ? 'active' : ''}
        onClick={() => setExplodedView(!explodedView)}
        title="Toggle exploded layer view"
      >
        💥 {explodedView ? 'Collapse' : 'Explode'}
      </button>
      <button
        className={stressMapVisible ? 'active' : ''}
        onClick={() => setStressMapVisible(!stressMapVisible)}
        title="Toggle stress heat map"
      >
        🔥 {stressMapVisible ? 'Thermal' : 'Stress Map'}
      </button>
      <button
        className="dashboard-btn"
        onClick={() => window.open('http://localhost:8501', '_blank')}
        title="Open Advanced Analytics Dashboard"
      >
        📊 Open Analytics Dashboard
      </button>
    </div>
  );
}
