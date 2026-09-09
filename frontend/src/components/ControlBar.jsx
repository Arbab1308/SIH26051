/**
 * ControlBar.jsx
 * Floating control bar for toggling views (Explode, Stress Map, Camera, ANSYS Export).
 */
import React from 'react';
import useSimulationStore from '../store/simulationStore';
import './ControlBar.css';

export default function ControlBar() {
  const explodedView = useSimulationStore((s) => s.explodedView);
  const stressMapVisible = useSimulationStore((s) => s.stressMapVisible);
  const setExplodedView = useSimulationStore((s) => s.setExplodedView);
  const setStressMapVisible = useSimulationStore((s) => s.setStressMapVisible);
  const shelter = useSimulationStore((s) => s.shelter);

  const downloadAnsysScript = async () => {
    try {
      const params = new URLSearchParams({
        wall_material: shelter.wallMaterial || 'Polyurethane Panel (PUF)',
        roof_material: shelter.roofMaterial || 'Polyurethane Panel (PUF)',
        window_material: shelter.windowMaterial || 'Glass (Double Pane)',
        length: shelter.length || 6.0,
        width: shelter.width || 4.0,
        height: shelter.height || 2.5,
        wall_thickness: shelter.wallThickness || 0.20,
        orientation: shelter.orientation || 180,
        occupants: 5,
        wind_speed_kmh: 50,
        outdoor_temp: -25,
        floor_r_value: shelter.floorInsulationR || 2.0,
      });
      const response = await fetch(`http://localhost:8000/export/ansys?${params}`);
      if (!response.ok) throw new Error('Failed to generate ANSYS script');
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'drdo_shelter.mac';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      alert('Error downloading ANSYS script. Is FastAPI backend running?');
      console.error(e);
    }
  };

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
        className="ansys-btn"
        onClick={downloadAnsysScript}
        title="Download ANSYS Mechanical APDL macro script"
      >
        📥 Download ANSYS 3D Script
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
