/**
 * TimelineControl.jsx
 * 30-day simulation playback scrubber with speed controls.
 */
import React, { useEffect, useRef } from 'react';
import useSimulationStore from '../store/simulationStore';
import './TimelineControl.css';

export default function TimelineControl() {
  const currentDay = useSimulationStore((s) => s.currentDay);
  const currentHour = useSimulationStore((s) => s.currentHour);
  const isPlaying = useSimulationStore((s) => s.isPlaying);
  const playbackSpeed = useSimulationStore((s) => s.playbackSpeed);
  const setCurrentDay = useSimulationStore((s) => s.setCurrentDay);
  const setIsPlaying = useSimulationStore((s) => s.setIsPlaying);
  const setPlaybackSpeed = useSimulationStore((s) => s.setPlaybackSpeed);
  const tickPlayback = useSimulationStore((s) => s.tickPlayback);
  const telemetry = useSimulationStore((s) => s.telemetry);
  const intervalRef = useRef(null);

  // Playback tick loop
  useEffect(() => {
    if (isPlaying) {
      const ms = Math.max(33, 1000 / playbackSpeed);
      intervalRef.current = setInterval(() => {
        tickPlayback();
      }, ms);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isPlaying, playbackSpeed, tickPlayback]);

  const speeds = [1, 5, 10, 30];

  return (
    <div className="timeline-control">
      <div className="timeline-row">
        {/* Playback buttons */}
        <div className="playback-buttons">
          <button onClick={() => setCurrentDay(0)} title="Jump to start">⏮</button>
          <button onClick={() => setCurrentDay(Math.max(0, currentDay - 1))} title="Back 1 day">◀</button>
          <button
            className={isPlaying ? 'active' : ''}
            onClick={() => setIsPlaying(!isPlaying)}
            title={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying ? '⏸' : '▶'}
          </button>
          <button onClick={() => setCurrentDay(Math.min(29, currentDay + 1))} title="Forward 1 day">▶</button>
          <button onClick={() => setCurrentDay(29)} title="Jump to end">⏭</button>
        </div>

        {/* Scrubber */}
        <input
          type="range"
          className="timeline-slider"
          min={0}
          max={29}
          value={currentDay}
          onChange={(e) => setCurrentDay(parseInt(e.target.value))}
        />

        {/* Speed selector */}
        <div className="speed-buttons">
          {speeds.map((s) => (
            <button
              key={s}
              className={playbackSpeed === s ? 'active' : ''}
              onClick={() => setPlaybackSpeed(s)}
            >
              {s}x
            </button>
          ))}
        </div>
      </div>

      {/* Info bar */}
      <div className="timeline-info">
        <span>Day <strong>{currentDay}</strong> / 30</span>
        <span>Hour: {String(currentHour % 24).padStart(2, '0')}:00 IST</span>
        <span>Temp: {telemetry.shelter_temp.toFixed(1)}°C</span>
        <span>Wind: {telemetry.wind_speed} km/h</span>
      </div>
    </div>
  );
}
