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
