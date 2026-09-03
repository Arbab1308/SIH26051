/**
 * App.jsx
 * Main entry — Assembles the 3D scene, HUD panels, timeline, and WebSocket.
 * This is the "Iron Man Command Center" for the DRDO Shelter Simulator.
 */
import React, { Suspense, useEffect, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Environment, Grid, Stars, Html } from '@react-three/drei';
import { Leva, useControls } from 'leva';
import ShelterModel from './components/ShelterModel';
import PanelSystem from './components/PanelSystem';
import TimelineControl from './components/TimelineControl';
import ControlBar from './components/ControlBar';
import useWebSocket from './hooks/useWebSocket';
import useSimulationStore from './store/simulationStore';
import './App.css';

/* ── Ground Plane ─────────────────────────────────────────────── */
function Ground() {
  return (
    <Grid
      args={[30, 30]}
      cellSize={1}
      cellColor="#1a3a4a"
      sectionSize={5}
      sectionColor="#0a2a3a"
      fadeDistance={30}
      fadeStrength={1}
      position={[0, 0, 0]}
    />
  );
}

/* ── Temperature HUD Overlay (inside 3D canvas) ──────────────── */
function TempOverlay() {
  const telemetry = useSimulationStore((s) => s.telemetry);
  const shelter = useSimulationStore((s) => s.shelter);

  return (
    <Html position={[0, shelter.height + 1.2, 0]} center distanceFactor={8}>
      <div style={{
        color: telemetry.shelter_temp < -10 ? '#4488ff' : telemetry.shelter_temp < 0 ? '#00cc66' : '#ffaa00',
        fontSize: '28px',
        fontFamily: "'JetBrains Mono', monospace",
        fontWeight: 600,
        textShadow: '0 0 20px rgba(0,255,255,0.4)',
        whiteSpace: 'nowrap',
        userSelect: 'none',
      }}>
        {telemetry.shelter_temp.toFixed(1)}°C
      </div>
    </Html>
  );
}

/* ── Synthetic 30-Day Data Generator ─────────────────────────── */
function generateSyntheticData() {
  const data = [];
  for (let h = 0; h < 720; h++) {
    const day = Math.floor(h / 24);
    const hourOfDay = h % 24;
    // Simulate diurnal cycle with multi-day degradation
    const baseTempOut = -25 + 5 * Math.sin((day / 30) * Math.PI); // gradual warming
    const diurnal = 8 * Math.sin(((hourOfDay - 6) / 24) * 2 * Math.PI); // day-night
    const outsideTemp = baseTempOut + diurnal + (Math.random() - 0.5) * 3;
    const solar = hourOfDay >= 7 && hourOfDay <= 17
      ? Math.max(0, 800 * Math.sin(((hourOfDay - 7) / 10) * Math.PI) * (0.6 + Math.random() * 0.4))
      : 0;
    const wind = 20 + 30 * Math.random() + (hourOfDay > 18 ? 15 : 0);
    const shelterTemp = outsideTemp + 18 + (solar / 200) - (wind / 40);
    const stress = Math.min(1, 0.1 + day * 0.025 + (wind > 50 ? 0.2 : 0));
    const failures = [];
    if (day >= 7 && stress > 0.6) failures.push('concrete_crack');
    if (day >= 15 && stress > 0.8) failures.push('steel_corrosion');

    data.push({
      shelter_temp: parseFloat(shelterTemp.toFixed(1)),
      outside_temp: parseFloat(outsideTemp.toFixed(1)),
      solar_irradiance: Math.round(solar),
      wind_speed: Math.round(wind),
      battery_soc: Math.max(5, Math.round(100 - day * 2.5 - (hourOfDay > 18 ? 10 : 0) + solar / 50)),
      power_demand: Math.round(3000 + Math.abs(shelterTemp) * 100 + wind * 20),
      material_stress: parseFloat(stress.toFixed(2)),
      failures,
    });
  }
  return data;
}

/* ── Debug Controls (Leva) ───────────────────────────────────── */
function DebugControls() {
  const shelter = useSimulationStore((s) => s.shelter);
  const setShelter = useSimulationStore((s) => s.setShelter);
  const panels = useSimulationStore((s) => s.panels);
  const setPanels = useSimulationStore((s) => s.setPanels);

  useControls('Shelter Dimensions', {
    length: { value: shelter.length, min: 4, max: 15, step: 0.5, onChange: (v) => setShelter({ length: v }) },
    width: { value: shelter.width, min: 2.5, max: 8, step: 0.5, onChange: (v) => setShelter({ width: v }) },
    height: { value: shelter.height, min: 2, max: 4, step: 0.1, onChange: (v) => setShelter({ height: v }) },
    wallThickness: { value: shelter.wallThickness, min: 0.05, max: 0.5, step: 0.05, onChange: (v) => setShelter({ wallThickness: v }) },
  });

  useControls('Materials (Phase 7 Preview)', {
    wallMaterial: {
      options: ['Brick', 'Concrete', 'PUF Sandwich Panel', 'Carbon Fiber'],
      value: panels.materials.walls.name,
      onChange: (v) => setPanels({ materials: { ...panels.materials, walls: { ...panels.materials.walls, name: v } } })
    },
    roofMaterial: {
      options: ['PUF', 'Corrugated Steel', 'Titanium'],
      value: panels.materials.roof.name,
      onChange: (v) => setPanels({ materials: { ...panels.materials, roof: { ...panels.materials.roof, name: v } } })
    }
  });

  useControls('AI Optimizer (NSGA-II)', {
    "Run Generative Design": {
      button: async () => {
        alert("Running NSGA-II Genetic Algorithm... (Check backend terminal for logs)");
        try {
          const res = await fetch("http://localhost:8000/optimize/generate-blueprints", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pop_size: 10, n_gen: 5 })
          });
          const data = await res.json();
          console.log("Optimized Blueprints:", data);
          alert(`Success! Found ${data.blueprints_found} optimal blueprints. (See browser console for data)`);
        } catch (e) {
          alert("Error running optimizer. Is FastAPI running?");
          console.error(e);
        }
      }
    }
  });

  return null;
}

/* ── MAIN APP ─────────────────────────────────────────────────── */
export default function App() {
  useWebSocket();
  const setSimulationData = useSimulationStore((s) => s.setSimulationData);
  const simulationData = useSimulationStore((s) => s.simulationData);

  // Generate synthetic 30-day data on mount (will be replaced by backend)
  useEffect(() => {
    if (simulationData.length === 0) {
      setSimulationData(generateSyntheticData());
    }
  }, []);

  return (
    <div className="app-container">
      <Leva collapsed={false} />
      <DebugControls />

      {/* ── 3D Canvas ─────────────────────── */}
      <Canvas
        camera={{ position: [12, 8, 12], fov: 50 }}
        shadows
        dpr={[1, 1.5]}
        gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
        style={{ background: '#050a15' }}
      >
        <Suspense fallback={null}>
          {/* Lighting */}
          <ambientLight intensity={0.3} color="#4466aa" />
          <directionalLight
            position={[10, 15, 8]}
            intensity={1.2}
            color="#ffe8c0"
            castShadow
            shadow-mapSize-width={1024}
            shadow-mapSize-height={1024}
            shadow-camera-far={50}
            shadow-camera-left={-10}
            shadow-camera-right={10}
            shadow-camera-top={10}
            shadow-camera-bottom={-10}
          />
          <pointLight position={[0, 5, 0]} intensity={0.4} color="#00ffcc" distance={15} />

          {/* Environment */}
          <Stars radius={100} depth={50} count={1000} factor={4} saturation={0} fade={false} speed={0.5} />
          <Ground />
          <fog attach="fog" args={['#050a15', 20, 60]} />

          {/* Shelter */}
          <ShelterModel />
          <TempOverlay />

          {/* Camera Controls */}
          <OrbitControls
            enableDamping
            dampingFactor={0.08}
            minDistance={3}
            maxDistance={40}
            maxPolarAngle={Math.PI / 2.1}
            touches={{ ONE: 0, TWO: 2 }}
          />
        </Suspense>
      </Canvas>

      {/* ── HUD Overlays ──────────────────── */}
      <PanelSystem />
      <ControlBar />
      <TimelineControl />
    </div>
  );
}
