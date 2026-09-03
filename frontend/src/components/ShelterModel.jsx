/**
 * ShelterModel.jsx
 * Core 3D shelter geometry with thermal shader, raycasting, and exploded-view support.
 * Renders walls, roof, floor, and windows as separate meshes for independent interaction.
 */
import React, { useRef, useMemo, useCallback } from 'react';
import { useFrame } from '@react-three/fiber';
import { a, useSpring } from '@react-spring/three';
import * as THREE from 'three';
import useSimulationStore from '../store/simulationStore';

/* ── Thermal Color Scale ──────────────────────────────────────── */
function tempToColor(temp) {
  // -30 → dark blue,  -15 → light blue,  0 → green,  +5 → yellow,  +15 → red
  const stops = [
    { t: -30, r: 0.00, g: 0.00, b: 0.78 },
    { t: -15, r: 0.39, g: 0.59, b: 1.00 },
    { t:   0, r: 0.00, g: 0.78, b: 0.00 },
    { t:   5, r: 1.00, g: 1.00, b: 0.00 },
    { t:  15, r: 1.00, g: 0.00, b: 0.00 },
  ];
  const clamped = Math.max(-30, Math.min(15, temp));
  let lower = stops[0], upper = stops[stops.length - 1];
  for (let i = 0; i < stops.length - 1; i++) {
    if (clamped >= stops[i].t && clamped <= stops[i + 1].t) {
      lower = stops[i];
      upper = stops[i + 1];
      break;
    }
  }
  const t = (clamped - lower.t) / (upper.t - lower.t || 1);
  return new THREE.Color(
    lower.r + (upper.r - lower.r) * t,
    lower.g + (upper.g - lower.g) * t,
    lower.b + (upper.b - lower.b) * t
  );
}

/* ── Stress Color Scale ───────────────────────────────────────── */
function stressToColor(stress) {
  if (stress < 0.25) return new THREE.Color(0.0, 0.8, 0.0);
  if (stress < 0.50) return new THREE.Color(0.9, 0.9, 0.0);
  if (stress < 0.75) return new THREE.Color(1.0, 0.5, 0.0);
  return new THREE.Color(1.0, 0.0, 0.0);
}

/* ── Interactive Part (Wall / Roof / Floor / Window) ──────────── */
function ShelterPart({ name, size, position, color, emissiveIntensity, opacity = 1 }) {
  const meshRef = useRef();
  const hoveredPart = useSimulationStore((s) => s.hoveredPart);
  const selectedPart = useSimulationStore((s) => s.selectedPart);
  const setHoveredPart = useSimulationStore((s) => s.setHoveredPart);
  const setSelectedPart = useSimulationStore((s) => s.setSelectedPart);

  const isHovered = hoveredPart === name;
  const isSelected = selectedPart === name;
  
  // Smoothly animate scale and position instead of rebuilding geometry
  const { animatedScale, animatedPosition } = useSpring({
    animatedScale: isHovered || isSelected ? [size[0]*1.02, size[1]*1.02, size[2]*1.02] : size,
    animatedPosition: position,
    config: { mass: 1, tension: 280, friction: 60 }
  });

  return (
    <a.mesh
      ref={meshRef}
      position={animatedPosition}
      scale={animatedScale}
      onPointerOver={(e) => { e.stopPropagation(); setHoveredPart(name); document.body.style.cursor = 'pointer'; }}
      onPointerOut={() => { setHoveredPart(null); document.body.style.cursor = 'default'; }}
      onClick={(e) => { e.stopPropagation(); setSelectedPart(isSelected ? null : name); }}
      castShadow
      receiveShadow
    >
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={emissiveIntensity}
        roughness={0.6}
        metalness={0.1}
        transparent={opacity < 1}
        opacity={opacity}
        side={THREE.DoubleSide}
      />
    </a.mesh>
  );
}

/* ── Main Shelter Model ──────────────────────────────────────── */
export default function ShelterModel() {
  const groupRef = useRef();
  const shelter = useSimulationStore((s) => s.shelter);
  const telemetry = useSimulationStore((s) => s.telemetry);
  const explodedView = useSimulationStore((s) => s.explodedView);
  const stressMapVisible = useSimulationStore((s) => s.stressMapVisible);

  const { length, width, height, wallThickness } = shelter;
  const explodeOffset = explodedView ? 0.8 : 0;

  // Thermal color based on current shelter temperature
  const thermalColor = useMemo(() => tempToColor(telemetry.shelter_temp), [telemetry.shelter_temp]);
  const stressColor = useMemo(() => stressToColor(telemetry.material_stress), [telemetry.material_stress]);
  const displayColor = stressMapVisible ? stressColor : thermalColor;

  // Emissive glow — brighter when warmer
  const emissive = useMemo(() => {
    const normalized = (telemetry.shelter_temp + 30) / 45; // -30→0, +15→1
    return Math.max(0.05, Math.min(0.6, normalized * 0.6));
  }, [telemetry.shelter_temp]);

  // Gentle rotation when idle
  useFrame((_, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.05;
    }
  });

  return (
    <group ref={groupRef} position={[0, height / 2, 0]}>
      {/* ── Floor ─────────────────────────── */}
      <ShelterPart
        name="floor"
        size={[length, 0.1, width]}
        position={[0, -height / 2 - explodeOffset, 0]}
        color={new THREE.Color(0.3, 0.3, 0.3)}
        emissiveIntensity={0.05}
      />

      {/* ── Front Wall ────────────────────── */}
      <ShelterPart
        name="wall-front"
        size={[length, height, wallThickness]}
        position={[0, 0, width / 2 + explodeOffset]}
        color={displayColor}
        emissiveIntensity={emissive}
      />

      {/* ── Back Wall ─────────────────────── */}
      <ShelterPart
        name="wall-back"
        size={[length, height, wallThickness]}
        position={[0, 0, -width / 2 - explodeOffset]}
        color={displayColor}
        emissiveIntensity={emissive}
      />

      {/* ── Left Wall ─────────────────────── */}
      <ShelterPart
        name="wall-left"
        size={[wallThickness, height, width]}
        position={[-length / 2 - explodeOffset, 0, 0]}
        color={displayColor}
        emissiveIntensity={emissive}
      />

      {/* ── Right Wall (with window cutout) ─ */}
      <ShelterPart
        name="wall-right"
        size={[wallThickness, height, width]}
        position={[length / 2 + explodeOffset, 0, 0]}
        color={displayColor}
        emissiveIntensity={emissive}
      />

      {/* ── Window (on right wall) ────────── */}
      <ShelterPart
        name="window"
        size={[wallThickness + 0.02, height * 0.4, width * 0.3]}
        position={[length / 2 + explodeOffset, height * 0.1, 0]}
        color={new THREE.Color(0.6, 0.85, 1.0)}
        emissiveIntensity={0.15}
        opacity={0.5}
      />

      {/* ── Roof ──────────────────────────── */}
      <ShelterPart
        name="roof"
        size={[length + 0.3, 0.15, width + 0.3]}
        position={[0, height / 2 + explodeOffset, 0]}
        color={displayColor}
        emissiveIntensity={emissive * 0.8}
      />
    </group>
  );
}
