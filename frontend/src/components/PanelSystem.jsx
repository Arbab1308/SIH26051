/**
 * PanelSystem.jsx
 * Iron Man "JARVIS" style glassmorphism HUD panels.
 * 5 draggable, semi-transparent panels displaying real-time telemetry.
 */
import React, { useState, useCallback } from 'react';
import useSimulationStore from '../store/simulationStore';
import './PanelSystem.css';

/* ── Animated Number (smooth count-up/down) ─────────────────── */
function AnimVal({ value, unit = '', decimals = 1, color }) {
  return (
    <span className="anim-val" style={{ color: color || 'inherit' }}>
      {typeof value === 'number' ? value.toFixed(decimals) : value}{unit}
    </span>
  );
}

/* ── Status Badge ────────────────────────────────────────────── */
function StatusBadge({ status }) {
  const map = {
    low: { label: 'LOW RISK', color: '#00ff88' },
    medium: { label: 'MEDIUM RISK', color: '#ffaa00' },
    high: { label: 'HIGH RISK', color: '#ff3333' },
    critical: { label: 'CRITICAL', color: '#ff0000' },
  };
  const s = map[status] || map.low;
  return <span className="status-badge" style={{ color: s.color, borderColor: s.color }}>{s.label}</span>;
}

/* ── Generic Draggable Panel ─────────────────────────────────── */
function Panel({ id, title, icon, children, defaultPos, onPartHover }) {
  const [pos, setPos] = useState(defaultPos);
  const [collapsed, setCollapsed] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  const handleMouseDown = useCallback((e) => {
    setDragging(true);
    setDragOffset({ x: e.clientX - pos.x, y: e.clientY - pos.y });
  }, [pos]);

  const handleMouseMove = useCallback((e) => {
    if (!dragging) return;
    setPos({ x: e.clientX - dragOffset.x, y: e.clientY - dragOffset.y });
  }, [dragging, dragOffset]);

  const handleMouseUp = useCallback(() => setDragging(false), []);

  return (
    <div
      className={`hud-panel ${collapsed ? 'collapsed' : ''}`}
      style={{ left: pos.x, top: pos.y }}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <div className="panel-header" onMouseDown={handleMouseDown}>
        <span className="panel-icon">{icon}</span>
        <span className="panel-title">{title}</span>
        <button className="panel-toggle" onClick={() => setCollapsed(!collapsed)}>
          {collapsed ? '▼' : '▲'}
        </button>
      </div>
      {!collapsed && <div className="panel-body">{children}</div>}
    </div>
  );
}

/* ── PANEL SYSTEM (all 5 panels) ─────────────────────────────── */
export default function PanelSystem() {
  const panels = useSimulationStore((s) => s.panels);
  const telemetry = useSimulationStore((s) => s.telemetry);
  const wsConnected = useSimulationStore((s) => s.wsConnected);
  const currentDay = useSimulationStore((s) => s.currentDay);
  const fps = useSimulationStore((s) => s.fps);
  const setHoveredPart = useSimulationStore((s) => s.setHoveredPart);

  const riskStatus = telemetry.shelter_temp < -15 ? 'high' : telemetry.shelter_temp < 0 ? 'medium' : 'low';

  return (
    <div className="panel-system">
      {/* ── Connection Status ──────────────── */}
      <div className="connection-badge" style={{ color: wsConnected ? '#00ff88' : '#ff4444' }}>
        {wsConnected ? '● LIVE' : '● OFFLINE'} | DAY {currentDay}/30 | {fps} FPS
      </div>

      {/* ── 1. Thermal Panel ─────────────── */}
      <Panel id="thermal" title="THERMAL" icon="🌡️" defaultPos={{ x: 16, y: 60 }}>
        <div className="panel-row big">
          <AnimVal value={telemetry.shelter_temp} unit="°C" color={telemetry.shelter_temp < -10 ? '#4488ff' : telemetry.shelter_temp < 0 ? '#00cc66' : '#ffaa00'} />
        </div>
        <div className="panel-row">
          <span className="label">Target</span>
          <AnimVal value={panels.thermal.target} unit="°C" />
        </div>
        <div className="panel-row">
          <span className="label">Outside</span>
          <AnimVal value={telemetry.outside_temp} unit="°C" color="#4488ff" />
        </div>
        <div className="panel-row">
          <span className="label">Deficit</span>
          <AnimVal value={telemetry.power_demand} unit=" W" decimals={0} />
        </div>
        <StatusBadge status={riskStatus} />
      </Panel>

      {/* ── 2. Power Panel ───────────────── */}
      <Panel id="power" title="POWER GRID" icon="⚡" defaultPos={{ x: 16, y: 320 }}>
        <div className="panel-row">
          <span className="label">Solar</span>
          <AnimVal value={telemetry.solar_irradiance} unit=" W/m²" decimals={0} color="#ffcc00" />
        </div>
        <div className="panel-row">
          <span className="label">Demand</span>
          <AnimVal value={telemetry.power_demand} unit=" W" decimals={0} color="#ff6644" />
        </div>
        <div className="panel-row">
          <span className="label">Battery</span>
          <AnimVal value={telemetry.battery_soc} unit="%" decimals={0} color={telemetry.battery_soc < 20 ? '#ff3333' : '#00ff88'} />
        </div>
        <div className="panel-bar">
          <div className="bar-fill" style={{ width: `${telemetry.battery_soc}%`, background: telemetry.battery_soc < 20 ? '#ff3333' : '#00ffcc' }} />
        </div>
      </Panel>

      {/* ── 3. Materials Panel ───────────── */}
      <Panel id="materials" title="MATERIALS" icon="🧱" defaultPos={{ x: window.innerWidth - 270, y: 60 }}>
        <div
          className="panel-row clickable"
          onMouseEnter={() => setHoveredPart('wall-front')}
          onMouseLeave={() => setHoveredPart(null)}
        >
          <span className="label">Walls</span>
          <span>{panels.materials.walls.name} (R={panels.materials.walls.r})</span>
        </div>
        <div
          className="panel-row clickable"
          onMouseEnter={() => setHoveredPart('roof')}
          onMouseLeave={() => setHoveredPart(null)}
        >
          <span className="label">Roof</span>
          <span>{panels.materials.roof.name} (R={panels.materials.roof.r})</span>
        </div>
        <div
          className="panel-row clickable"
          onMouseEnter={() => setHoveredPart('window')}
          onMouseLeave={() => setHoveredPart(null)}
        >
          <span className="label">Windows</span>
          <span>{panels.materials.windows.name}</span>
        </div>
        <hr className="panel-divider" />
        <div className="panel-row">
          <span className="label">Cost</span>
          <span>₹{panels.materials.totalCost.toLocaleString()}</span>
        </div>
        <div className="panel-row">
          <span className="label">Weight</span>
          <span>{panels.materials.totalWeight.toLocaleString()} kg</span>
        </div>
      </Panel>

      {/* ── 4. Status Panel ──────────────── */}
      <Panel id="status" title="STATUS" icon="📊" defaultPos={{ x: window.innerWidth - 270, y: 340 }}>
        <div className="panel-row">
          <span className="label">Occupants</span>
          <span>{panels.status.occupants}/{panels.status.maxOccupants}</span>
        </div>
        <div className="panel-row">
          <span className="label">Freeze-Thaw</span>
          <span>{panels.status.freezeThawCycles}/30 cycles</span>
        </div>
        <div className="panel-row">
          <span className="label">Wind</span>
          <AnimVal value={telemetry.wind_speed} unit=" km/h" decimals={0} />
        </div>
        <div className="panel-row">
          <span className="label">Stress</span>
          <AnimVal value={telemetry.material_stress * 100} unit="%" decimals={0} color={telemetry.material_stress > 0.7 ? '#ff3333' : '#00ff88'} />
        </div>
        {telemetry.failures.length > 0 && (
          <div className="alert-box">
            ⚠️ {telemetry.failures.join(', ')}
          </div>
        )}
      </Panel>

      {/* ── 5. Recommendations Panel ─────── */}
      <Panel id="recs" title="RECOMMENDATIONS" icon="💡" defaultPos={{ x: 16, y: window.innerHeight - 180 }}>
        {panels.recommendations.map((rec, i) => (
          <div key={i} className="panel-row rec">
            <span className="rec-num">{i + 1}.</span> {rec}
          </div>
        ))}
      </Panel>
    </div>
  );
}
