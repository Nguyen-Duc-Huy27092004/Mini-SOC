// Zabbix TypeScript interfaces — mirrors backend Pydantic schemas exactly

// =========================================================================
// Host
// =========================================================================

export interface ZabbixHostSummary {
  total: number;
  available: number;
  unavailable: number;
  unknown: number;
}

export interface ZabbixHostOut {
  host_id: string;
  name: string;
  status: string;
  available: boolean;
  available_label: string;
  ip_address?: string | null;
  groups: string[];
  problem_count: number;
  max_severity: number;
  max_severity_label: string;
}

// =========================================================================
// Problems
// =========================================================================

export interface ZabbixProblemTag {
  tag: string;
  value: string;
}

export interface ZabbixProblemOut {
  event_id: string;
  name: string;
  severity: number;
  severity_label: string;
  severity_color: string;
  acknowledged: boolean;
  suppressed: boolean;
  clock?: string | null;      // ISO-8601 datetime string
  clock_iso?: string | null;
  host_name: string;
  tags: ZabbixProblemTag[];
}

export interface ZabbixProblemSummary {
  total: number;
  by_severity: Record<string, number>;
  unacknowledged: number;
}

// =========================================================================
// Triggers
// =========================================================================

export interface ZabbixTriggerOut {
  trigger_id: string;
  name: string;
  priority: number;
  priority_label: string;
  priority_color: string;
  status: string;
  value: number;
  value_label: string;
  is_problem: boolean;
  host_id: string;
  host_name: string;
  last_change?: string | null;
  last_change_iso?: string | null;
}

// =========================================================================
// Availability
// =========================================================================

export interface ZabbixAvailabilitySummary {
  host_id: string;
  host_name: string;
  available: boolean;
  available_label: string;
  available_code: number;
  groups: string[];
}

// =========================================================================
// Resource Usage
// =========================================================================

export interface ZabbixResourceUsage {
  host_id: string;
  host_name: string;
  cpu_pct?: number | null;
  mem_pct?: number | null;
  disk_pct?: number | null;
}

// =========================================================================
// Charts & Aggregates
// =========================================================================

export interface ZabbixSeverityDistribution {
  severity: number;
  severity_label: string;
  severity_color: string;
  count: number;
}

export interface ZabbixTopHost {
  host_name: string;
  problem_count: number;
  max_severity: number;
  max_severity_label: string;
  max_severity_color: string;
}

export interface ZabbixTopServer {
  host_id: string;
  host_name: string;
  ip_address?: string | null;
  cpu_pct?: number | null;
  mem_pct?: number | null;
  disk_pct?: number | null;
  problem_count: number;
  status: string;
}

export interface ZabbixTimelinePoint {
  timestamp: string;   // "HH:MM"
  count: number;
  severity: number;
  severity_label: string;
}

export interface ZabbixHealthScore {
  score: number;
  grade: 'A' | 'B' | 'C' | 'D' | 'F';
  breakdown: Record<string, number>;
}

// =========================================================================
// Top-level response types
// =========================================================================

export interface ZabbixOverviewResponse {
  total_servers: number;
  online_servers: number;
  offline_servers: number;
  warning_servers: number;
  critical_servers: number;
  health_score: number;
  health_grade: string;
  total_problems: number;
  critical_problems: number;
  disaster_problems: number;
  unacknowledged_problems: number;
  is_online: boolean;
  error?: string | null;
}

export interface ZabbixSummaryResponse {
  hosts: ZabbixHostSummary;
  problems: ZabbixProblemSummary;
  health: ZabbixHealthScore;
  is_online: boolean;
  error?: string | null;
}

export interface ZabbixChartsResponse {
  severity_distribution: ZabbixSeverityDistribution[];
  top_hosts: ZabbixTopHost[];
  timeline: ZabbixTimelinePoint[];
  resource_usage: ZabbixResourceUsage[];
}

// =========================================================================
// Assets
// =========================================================================

export interface ZabbixAssetCreate {
  hostname: string;
  ip_address?: string | null;
  location?: string | null;
  department?: string | null;
  owner?: string | null;
  vendor?: string | null;
  model?: string | null;
  serial_number?: string | null;
  purchase_date?: string | null;
  warranty_expiration?: string | null;
  lifecycle_status: string;
  notes?: string | null;
}

export interface ZabbixAssetOut {
  id: string;
  hostname: string;
  ip_address?: string | null;
  location?: string | null;
  department?: string | null;
  owner?: string | null;
  vendor?: string | null;
  model?: string | null;
  serial_number?: string | null;
  purchase_date?: string | null;
  warranty_expiration?: string | null;
  lifecycle_status: string;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export type ZabbixAssetUpdate = Partial<ZabbixAssetCreate>;

// =========================================================================
// Maintenance
// =========================================================================

export interface ZabbixMaintenanceCreate {
  hostname: string;
  ip_address?: string | null;
  task_type: string;
  last_maintenance_date?: string | null;
  next_maintenance_date: string;
  interval_days: number;
  status: string;
  assigned_to?: string | null;
  notes?: string | null;
}

export interface ZabbixMaintenanceOut {
  id: string;
  hostname: string;
  ip_address?: string | null;
  task_type: string;
  last_maintenance_date?: string | null;
  next_maintenance_date: string;
  interval_days: number;
  status: string;
  assigned_to?: string | null;
  notes?: string | null;
  is_overdue: boolean;
  days_until_due?: number | null;
  created_at: string;
  updated_at: string;
}

export type ZabbixMaintenanceUpdate = Partial<ZabbixMaintenanceCreate>;

// =========================================================================
// Tasks
// =========================================================================

export interface ZabbixTaskOut {
  id: string;
  hostname: string;
  ip_address?: string | null;
  task_type: string;
  description: string;
  priority: string;
  status: string;
  source: string;
  metric_value?: number | null;
  created_at: string;
  updated_at: string;
}

export interface ZabbixTaskUpdate {
  status?: string;
  priority?: string;
}

// =========================================================================
// Notifications
// =========================================================================

export interface ZabbixNotificationOut {
  id: string;
  notification_type: string;
  hostname?: string | null;
  ip_address?: string | null;
  subject: string;
  message: string;
  recipients?: string | null;
  severity?: string | null;
  metric_value?: number | null;
  suggested_action?: string | null;
  status: string;
  error_msg?: string | null;
  sent_at: string;
}
