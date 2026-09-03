/**
 * useWebSocket.js
 * Robust WebSocket hook with automatic reconnection, throttling,
 * and graceful offline fallback for field deployments.
 */
import { useEffect, useRef, useCallback } from 'react';
import useSimulationStore from '../store/simulationStore';

const WS_URL = 'ws://localhost:8000/telemetry';
const RECONNECT_INTERVAL = 5000;
const THROTTLE_MS = 100; // Max 10 updates/sec to prevent React thrashing

export default function useWebSocket() {
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const lastUpdateRef = useRef(0);
  const setTelemetry = useSimulationStore((s) => s.setTelemetry);
  const setWsConnected = useSimulationStore((s) => s.setWsConnected);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        console.log('[WS] Connected to telemetry stream');
        setWsConnected(true);
        if (reconnectTimer.current) {
          clearTimeout(reconnectTimer.current);
          reconnectTimer.current = null;
        }
      };

      ws.onmessage = (event) => {
        const now = Date.now();
        if (now - lastUpdateRef.current < THROTTLE_MS) return; // Throttle
        lastUpdateRef.current = now;

        try {
          const data = JSON.parse(event.data);
          setTelemetry(data);
        } catch (err) {
          console.warn('[WS] Failed to parse message:', err);
        }
      };

      ws.onclose = () => {
        console.log('[WS] Disconnected. Reconnecting in 5s...');
        setWsConnected(false);
        wsRef.current = null;
        scheduleReconnect();
      };

      ws.onerror = (err) => {
        console.warn('[WS] Error:', err);
        ws.close();
      };

      wsRef.current = ws;
    } catch (err) {
      console.warn('[WS] Connection failed:', err);
      setWsConnected(false);
      scheduleReconnect();
    }
  }, [setTelemetry, setWsConnected]);

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimer.current) return;
    reconnectTimer.current = setTimeout(() => {
      reconnectTimer.current = null;
      connect();
    }, RECONNECT_INTERVAL);
  }, [connect]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [connect]);
}
