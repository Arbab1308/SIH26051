/**
 * Zustand Global State Store
 * Central nervous system for the 3D Tactical Visualization.
 * All telemetry, UI state, and playback controls flow through here.
 */
import { create } from 'zustand';

const useSimulationStore = create((set, get) => ({
  // ── Telemetry (from WebSocket) ──────────────────────────
  telemetry: {
    shelter_temp: -5.0,
    outside_temp: -25.0,
    solar_irradiance: 0,
    wind_speed: 35,
    battery_soc: 75,
    power_demand: 5200,
    material_stress: 0.45,
    failures: [],
  },
  setTelemetry: (data) => set({ telemetry: { ...get().telemetry, ...data } }),

  // ── Shelter Geometry ────────────────────────────────────
  shelter: {
    length: 6,
    width: 4,
    height: 2.5,
    wallThickness: 0.2,
    roofThickness: 0.15,
    wallMaterial: 'Brick',
    roofMaterial: 'Polyurethane Panel (PUF)',
    windowMaterial: 'Glass (Double Pane)',
  },
  setShelter: (data) => set({ shelter: { ...get().shelter, ...data } }),

  // ── Panel Data ──────────────────────────────────────────
  panels: {
    thermal: { temp: -5, target: 5, deficit: 2000, status: 'medium' },
    power: { solar: 8200, demand: 12500, battery: 250, capacity: 400, autonomy: 14 },
    materials: {
      walls: { name: 'Brick', r: 0.3, cost: 4 },
      roof: { name: 'PUF', r: 5.0, cost: 250 },
      windows: { name: 'Double Pane', r: 0.35, cost: 120 },
      totalCost: 50000,
      totalWeight: 6800,
    },
    status: { occupants: 10, maxOccupants: 10, freezeThawCycles: 8, daysRemaining: 22, alerts: 2 },
    recommendations: [
      'Monitor battery health — SOC dropping',
      'Plan resupply for Day 22',
      'Roof stress rising — inspect PUF seams',
    ],
  },
  setPanels: (data) => set({ panels: { ...get().panels, ...data } }),

  // ── Timeline / Playback ─────────────────────────────────
  currentDay: 0,
  currentHour: 0,
  isPlaying: false,
  playbackSpeed: 1, // 1x, 5x, 10x, 30x
  simulationData: [], // 720 hourly data points
  setCurrentDay: (day) => set({ currentDay: day, currentHour: day * 24 }),
  setIsPlaying: (v) => set({ isPlaying: v }),
  setPlaybackSpeed: (s) => set({ playbackSpeed: s }),
  setSimulationData: (d) => set({ simulationData: d }),
  tickPlayback: () => {
    const { currentHour, simulationData, isPlaying } = get();
    if (!isPlaying || simulationData.length === 0) return;
    const nextHour = (currentHour + 1) % simulationData.length;
    const point = simulationData[nextHour];
    set({
      currentHour: nextHour,
      currentDay: Math.floor(nextHour / 24),
      telemetry: point ? { ...get().telemetry, ...point } : get().telemetry,
    });
  },

  // ── 3D View State ───────────────────────────────────────
  cameraMode: 'orbit',
  explodedView: false,
  stressMapVisible: false,
  selectedPart: null, // 'wall' | 'roof' | 'window' | 'floor' | null
  hoveredPart: null,
  setCameraMode: (m) => set({ cameraMode: m }),
  setExplodedView: (v) => set({ explodedView: v }),
  setStressMapVisible: (v) => set({ stressMapVisible: v }),
  setSelectedPart: (p) => set({ selectedPart: p }),
  setHoveredPart: (p) => set({ hoveredPart: p }),

  // ── WebSocket Connection ────────────────────────────────
  wsConnected: false,
  setWsConnected: (v) => set({ wsConnected: v }),

  // ── Performance ─────────────────────────────────────────
  fps: 60,
  setFps: (f) => set({ fps: f }),
}));

export default useSimulationStore;
