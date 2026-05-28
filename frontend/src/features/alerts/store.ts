import { create } from 'zustand';
import api from '../../shared/api/client';

export interface AlertItem {
  id: string;
  event_id: string;
  timestamp: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  category: string;
  description: string;
  agent_id: string;
  agent_name: string;
  source_ip?: string;
  source_country?: string;
  risk_score: number;
  rule_id: string;
  incident_id?: string;
}

interface AlertState {
  alerts: AlertItem[];
  totalAlerts: number;
  loading: boolean;
  error: string | null;
  activeNotification: AlertItem | null;
  fetchAlerts: (filters?: Record<string, string | number | undefined>) => Promise<void>;
  addRealtimeAlert: (alert: Partial<AlertItem> & { severity: string; description?: string; message?: string; agent_name?: string }) => void;
  clearNotification: () => void;
}

const MAX_FEED = 150;

export const useAlertStore = create<AlertState>((set, get) => ({
  alerts: [],
  totalAlerts: 0,
  loading: false,
  error: null,
  activeNotification: null,

  fetchAlerts: async (filters = {}) => {
    set({ loading: true, error: null });
    try {
      const res = await api.get('/alerts', { params: filters });
      const { alerts, total } = res.data;
      set({ alerts, totalAlerts: total, loading: false });
    } catch (err: unknown) {
      set({ error: (err as { message?: string }).message || 'Lỗi tải cảnh báo', loading: false });
    }
  },

  addRealtimeAlert: (raw) => {
    const newAlert: AlertItem = {
      id: raw.id || crypto.randomUUID(),
      event_id: raw.event_id || '',
      timestamp: raw.timestamp || new Date().toISOString(),
      severity: (raw.severity as AlertItem['severity']) || 'medium',
      category: raw.category || 'system',
      description: raw.description || raw.message || 'Cảnh báo mới',
      agent_id: raw.agent_id || '',
      agent_name: raw.agent_name || 'unknown',
      source_ip: raw.source_ip,
      source_country: raw.source_country,
      risk_score: raw.risk_score ?? 0,
      rule_id: raw.rule_id || '',
    };
    const list = [newAlert, ...get().alerts].slice(0, MAX_FEED);
    set({
      alerts: list,
      totalAlerts: get().totalAlerts + 1,
      activeNotification:
        newAlert.severity === 'critical' || newAlert.severity === 'high' ? newAlert : get().activeNotification,
    });
  },

  clearNotification: () => set({ activeNotification: null }),
}));
