import { useCallback, useEffect, useRef, useState } from 'react';
import api from '../api/client';
import { useAlertStore } from '../../features/alerts/store';
import { useAuthStore, selectIsAuthenticated } from '../../features/auth/store';

const MAX_BACKOFF_MS = 60000;

export function useWebSocket() {
  const isAuthenticated = useAuthStore(selectIsAuthenticated);
  const addRealtimeAlert = useAlertStore((s) => s.addRealtimeAlert);
  const socketRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const backoffRef = useRef(1000);
  const reconnectRef = useRef<number | null>(null);
  const pingRef = useRef<number | null>(null);
  const mountedRef = useRef(true);

  const cleanup = useCallback(() => {
    if (pingRef.current) clearInterval(pingRef.current);
    if (reconnectRef.current) clearTimeout(reconnectRef.current);
    pingRef.current = null;
    reconnectRef.current = null;
  }, []);

  const connect = useCallback(async () => {
    if (!mountedRef.current || !isAuthenticated || socketRef.current) return;

    try {
      const { data } = await api.get<{ ticket: string }>('/auth/ws-ticket');
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = import.meta.env.VITE_WS_URL
        ? import.meta.env.VITE_WS_URL.replace(/^https?:/, proto)
        : `${proto}//${window.location.host}`;
      const wsUrl = `${host}/ws?ticket=${encodeURIComponent(data.ticket)}`;
      const socket = new WebSocket(wsUrl);
      socketRef.current = socket;

      socket.onopen = () => {
        setConnected(true);
        backoffRef.current = 1000;
        pingRef.current = window.setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) socket.send('ping');
        }, 30000);
      };

      socket.onmessage = (event) => {
        if (event.data === 'pong') return;
        try {
          const payload = JSON.parse(event.data);
          if (payload?.severity) {
          addRealtimeAlert({
            ...payload,
            description: payload.description || payload.rule?.description || payload.message,
            agent_name: payload.agent_name || payload.agent?.name,
            source_ip: payload.source_ip || payload.source?.ip,
          });
        }
        } catch {
          /* ignore malformed */
        }
      };

      socket.onclose = () => {
        setConnected(false);
        socketRef.current = null;
        cleanup();
        if (mountedRef.current && isAuthenticated) {
          reconnectRef.current = window.setTimeout(() => {
            backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
            connect();
          }, backoffRef.current);
        }
      };

      socket.onerror = () => socket.close();
    } catch {
      reconnectRef.current = window.setTimeout(connect, backoffRef.current);
    }
  }, [isAuthenticated, addRealtimeAlert, cleanup]);

  useEffect(() => {
    mountedRef.current = true;
    if (isAuthenticated) connect();
    else if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    return () => {
      mountedRef.current = false;
      cleanup();
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [isAuthenticated, connect, cleanup]);

  return { connected };
}
