import { useEffect, useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import {
  AlertTriangle, Shield, Server, Activity, Ban, Gauge,
} from 'lucide-react';
import api from '../../../shared/api/client';
import { KpiCard } from '../../../shared/ui/KpiCard';
import { useAlertStore } from '../../alerts/store';
import { SeverityBadge } from '../../../shared/ui/SeverityBadge';

interface Summary {
  alerts_today: number;
  critical_alerts: number;
  servers_under_attack: number;
  agents_online: number;
  agents_total: number;
  attacks_blocked: number;
  average_risk_score: number;
}

export function ExecutiveDashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [trends, setTrends] = useState<{ hour: string; count: number }[]>([]);
  const [severity, setSeverity] = useState<{ severity: string; count: number }[]>([]);
  const [topServers, setTopServers] = useState<{ agent_name: string; alert_count: number; max_severity: string }[]>([]);
  const [topIps, setTopIps] = useState<{ ip: string; country?: string; count: number }[]>([]);
  const [geo, setGeo] = useState<{ country: string; count: number }[]>([]);
  const [mitre, setMitre] = useState<{ tactic: string; technique: string; count: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const { alerts, fetchAlerts } = useAlertStore();

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const [s, t, sev, srv, ips, g, m] = await Promise.all([
          api.get('/dashboard/summary', { params: { hours: 24 } }),
          api.get('/dashboard/trends', { params: { hours: 168 } }),   // 7 ngày
          api.get('/dashboard/severity', { params: { hours: 24 } }),
          api.get('/dashboard/top-attacked-servers', { params: { hours: 24 } }),
          api.get('/dashboard/top-attack-ips', { params: { hours: 24 } }),
          api.get('/dashboard/geo', { params: { hours: 24 } }),
          api.get('/dashboard/mitre', { params: { hours: 24 } }),
        ]);
        setSummary(s.data);
        setTrends(t.data);
        setSeverity(sev.data);
        setTopServers(srv.data);
        setTopIps(ips.data);
        setGeo(g.data);
        setMitre(m.data);
        await fetchAlerts({ page: 1, page_size: 8 });
      } finally {
        setLoading(false);
      }
    })();
  }, [fetchAlerts]);

  const trendOpt = useMemo(() => ({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 16, top: 24, bottom: 40 },
    xAxis: {
      type: 'category',
      data: trends.map((x) => x.hour),
      axisLine: { lineStyle: { color: '#475569' } },
      axisLabel: {
        // Shorten "2026-07-03 08:00" → "03/07 08h" for compact display
        formatter: (val: string) => {
          if (val.includes(' ')) {
            const [datePart, timePart] = val.split(' ');
            const [_, m, d] = datePart.split('-');
            const h = timePart.split(':')[0];
            return `${d}/${m} ${h}h`;
          }
          return val;
        },
        rotate: 30,
        fontSize: 10,
      },
    },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#1e293b' } } },
    series: [{ type: 'line', smooth: true, areaStyle: { opacity: 0.2 }, data: trends.map((x) => x.count), color: '#22d3ee' }],
  }), [trends]);

  const sevOpt = useMemo(() => ({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      data: severity.map((s) => ({
        name: s.severity,
        value: s.count,
        itemStyle: {
          color: s.severity === 'critical' ? '#ef4444' : s.severity === 'high' ? '#f97316' : s.severity === 'medium' ? '#eab308' : '#22c55e',
        },
      })),
    }],
  }), [severity]);

  const geoOpt = useMemo(() => ({
    backgroundColor: 'transparent',
    tooltip: {},
    series: [{
      type: 'bar',
      data: geo.map((g) => g.count),
      itemStyle: { color: '#38bdf8' },
    }],
    xAxis: { type: 'category', data: geo.map((g) => g.country) },
    yAxis: { type: 'value' },
  }), [geo]);

  if (loading || !summary) {
    return <p className="text-slate-400 animate-pulse">Đang tải bảng điều khiển lãnh đạo...</p>;
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-white">Tổng quan An ninh</h1>
        <p className="text-sm text-slate-400 mt-1">Dữ liệu thời gian thực từ Wazuh · PostgreSQL</p>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6 gap-4">
        <KpiCard title="Cảnh báo hôm nay" value={summary.alerts_today} icon={AlertTriangle} accent="text-amber-400" />
        <KpiCard title="Nghiêm trọng" value={summary.critical_alerts} icon={Shield} accent="text-red-400" />
        <KpiCard title="Máy chủ bị tấn công" value={summary.servers_under_attack} icon={Server} accent="text-orange-400" />
        <KpiCard title="Endpoint online" value={`${summary.agents_online}/${summary.agents_total}`} icon={Activity} accent="text-emerald-400" />
        <KpiCard title="Tấn công bị chặn" value={summary.attacks_blocked} icon={Ban} accent="text-cyan-400" />
        <KpiCard title="Điểm rủi ro TB" value={summary.average_risk_score} icon={Gauge} accent="text-violet-400" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel title="Xu hướng tấn công (7 ngày gần nhất)">
          <ReactECharts option={trendOpt} style={{ height: 280 }} notMerge lazyUpdate />
        </Panel>
        <Panel title="Phân bố mức độ">
          <ReactECharts option={sevOpt} style={{ height: 280 }} notMerge lazyUpdate />
        </Panel>
        <Panel title="Top máy chủ bị tấn công">
          <ul className="space-y-2 text-sm">
            {topServers.map((s) => (
              <li key={s.agent_name} className="flex justify-between border-b border-slate-800 pb-2">
                <span>{s.agent_name}</span>
                <span className="flex gap-2 items-center">
                  <SeverityBadge severity={s.max_severity} />
                  <span className="font-mono">{s.alert_count}</span>
                </span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Top IP tấn công">
          <ul className="space-y-2 text-sm">
            {topIps.map((ip) => (
              <li key={ip.ip} className="flex justify-between border-b border-slate-800 pb-2">
                <span className="font-mono">{ip.ip} <span className="text-slate-500">({ip.country || 'N/A'})</span></span>
                <span>{ip.count}</span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Quốc gia nguồn tấn công">
          <ReactECharts option={geoOpt} style={{ height: 260 }} notMerge lazyUpdate />
        </Panel>
        <Panel title="MITRE ATT&CK">
          <ul className="space-y-2 text-sm max-h-64 overflow-y-auto">
            {mitre.map((m) => (
              <li key={m.technique} className="flex justify-between">
                <span>{m.tactic} · {m.technique}</span>
                <span className="font-mono text-cyan-400">{m.count}</span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <Panel title="Cảnh báo mới nhất (realtime)">
        <div className="space-y-2">
          {alerts.slice(0, 8).map((a) => (
            <div key={a.id} className="flex items-center gap-3 p-2 rounded-lg bg-slate-900/50 border border-slate-800">
              <SeverityBadge severity={a.severity} />
              <div className="min-w-0 flex-1">
                <p className="text-sm truncate">{a.description}</p>
                <p className="text-xs text-slate-500">{a.agent_name} · {a.source_ip || '—'}</p>
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="p-4 rounded-xl border border-slate-700/80 bg-slate-900/40">
      <h3 className="text-sm font-semibold text-slate-200 mb-3">{title}</h3>
      {children}
    </section>
  );
}
