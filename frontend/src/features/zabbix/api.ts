import { api } from '@/shared/api/client';
import type {
  ZabbixAssetCreate,
  ZabbixAssetOut,
  ZabbixAssetUpdate,
  ZabbixAvailabilitySummary,
  ZabbixChartsResponse,
  ZabbixHostOut,
  ZabbixMaintenanceCreate,
  ZabbixMaintenanceOut,
  ZabbixMaintenanceUpdate,
  ZabbixNotificationOut,
  ZabbixOverviewResponse,
  ZabbixProblemOut,
  ZabbixResourceUsage,
  ZabbixSeverityDistribution,
  ZabbixSummaryResponse,
  ZabbixTaskOut,
  ZabbixTaskUpdate,
  ZabbixTimelinePoint,
  ZabbixTopHost,
  ZabbixTopServer,
  ZabbixTriggerOut,
  ZabbixSmtpStatus,
} from './types';

// =========================================================================
// Core Zabbix Endpoints
// =========================================================================

export const getOverview = async (): Promise<ZabbixOverviewResponse> => {
  const { data } = await api.get<ZabbixOverviewResponse>('/zabbix/overview');
  return data;
};

export const getSummary = async (): Promise<ZabbixSummaryResponse> => {
  const { data } = await api.get<ZabbixSummaryResponse>('/zabbix/summary');
  return data;
};

export const getHosts = async (): Promise<ZabbixHostOut[]> => {
  const { data } = await api.get<ZabbixHostOut[]>('/zabbix/hosts');
  return data;
};

export const getProblems = async (): Promise<ZabbixProblemOut[]> => {
  const { data } = await api.get<ZabbixProblemOut[]>('/zabbix/problems');
  return data;
};

export const getTriggers = async (): Promise<ZabbixTriggerOut[]> => {
  const { data } = await api.get<ZabbixTriggerOut[]>('/zabbix/triggers');
  return data;
};

export const getEvents = async (): Promise<any[]> => {
  const { data } = await api.get<any[]>('/zabbix/events');
  return data;
};

export const getSeverityDistribution = async (): Promise<ZabbixSeverityDistribution[]> => {
  const { data } = await api.get<ZabbixSeverityDistribution[]>('/zabbix/severity');
  return data;
};

export const getTopHosts = async (limit = 10): Promise<ZabbixTopHost[]> => {
  const { data } = await api.get<ZabbixTopHost[]>('/zabbix/top-hosts', { params: { limit } });
  return data;
};

export const getTopServers = async (limit = 10): Promise<ZabbixTopServer[]> => {
  const { data } = await api.get<ZabbixTopServer[]>('/zabbix/top-servers', { params: { limit } });
  return data;
};

export const getResourceUsage = async (): Promise<ZabbixResourceUsage[]> => {
  const { data } = await api.get<ZabbixResourceUsage[]>('/zabbix/resources');
  return data;
};

export const getAvailability = async (): Promise<ZabbixAvailabilitySummary[]> => {
  const { data } = await api.get<ZabbixAvailabilitySummary[]>('/zabbix/availability');
  return data;
};

export const getTimeline = async (hours = 24): Promise<ZabbixTimelinePoint[]> => {
  const { data } = await api.get<ZabbixTimelinePoint[]>('/zabbix/timeline', { params: { hours } });
  return data;
};

export const getCharts = async (): Promise<ZabbixChartsResponse> => {
  const { data } = await api.get<ZabbixChartsResponse>('/zabbix/charts');
  return data;
};

// =========================================================================
// Asset Management
// =========================================================================

export const getAssets = async (): Promise<ZabbixAssetOut[]> => {
  const { data } = await api.get<ZabbixAssetOut[]>('/zabbix/assets');
  return data;
};

export const createAsset = async (asset: ZabbixAssetCreate): Promise<ZabbixAssetOut> => {
  const { data } = await api.post<ZabbixAssetOut>('/zabbix/assets', asset);
  return data;
};

export const updateAsset = async (id: string, asset: ZabbixAssetUpdate): Promise<ZabbixAssetOut> => {
  const { data } = await api.put<ZabbixAssetOut>(`/zabbix/assets/${id}`, asset);
  return data;
};

export const deleteAsset = async (id: string): Promise<void> => {
  await api.delete(`/zabbix/assets/${id}`);
};

// =========================================================================
// Maintenance Schedule
// =========================================================================

export const getMaintenance = async (): Promise<ZabbixMaintenanceOut[]> => {
  const { data } = await api.get<ZabbixMaintenanceOut[]>('/zabbix/maintenance');
  return data;
};

export const createMaintenance = async (maintenance: ZabbixMaintenanceCreate): Promise<ZabbixMaintenanceOut> => {
  const { data } = await api.post<ZabbixMaintenanceOut>('/zabbix/maintenance', maintenance);
  return data;
};

export const updateMaintenance = async (id: string, maintenance: ZabbixMaintenanceUpdate): Promise<ZabbixMaintenanceOut> => {
  const { data } = await api.put<ZabbixMaintenanceOut>(`/zabbix/maintenance/${id}`, maintenance);
  return data;
};

export const deleteMaintenance = async (id: string): Promise<void> => {
  await api.delete(`/zabbix/maintenance/${id}`);
};

// =========================================================================
// Task Recommendations
// =========================================================================

export const getTasks = async (): Promise<ZabbixTaskOut[]> => {
  const { data } = await api.get<ZabbixTaskOut[]>('/zabbix/tasks');
  return data;
};

export const updateTask = async (id: string, task: ZabbixTaskUpdate): Promise<ZabbixTaskOut> => {
  const { data } = await api.put<ZabbixTaskOut>(`/zabbix/tasks/${id}`, task);
  return data;
};

// =========================================================================
// Notifications
// =========================================================================

export const getNotifications = async (limit = 100): Promise<ZabbixNotificationOut[]> => {
  const { data } = await api.get<ZabbixNotificationOut[]>('/zabbix/notifications', { params: { limit } });
  return data;
};

export const testNotification = async (email: string): Promise<ZabbixNotificationOut> => {
  const { data } = await api.post<ZabbixNotificationOut>('/zabbix/notifications/test', { email });
  return data;
};

export const getSmtpStatus = async (): Promise<ZabbixSmtpStatus> => {
  const { data } = await api.get<ZabbixSmtpStatus>('/zabbix/smtp-status');
  return data;
};

