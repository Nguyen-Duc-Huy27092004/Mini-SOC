import { useEffect, useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import api from '../../../shared/api/client';

interface DashboardData {
  data_status: string;
  security_score: { score: number; level: string };
  critical_alerts: number;
  high_alerts: number;
  total_servers: number;
  agents_online: number;
  alert_distribution_severity: Record<string, number>;
  attack_timeline: { timestamp: string; count: number }[];
}

export function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get('/dashboard/overview').then((r) => setData(r.data)).catch((e) => setError(e.message));
  }, []);

  const chartOption = useMemo(() => {
    if (!data) return {};
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: data.attack_timeline.map((t) => t.timestamp) },
      yAxis: { type: 'value' },
      series: [{ type: 'line', smooth: true, data: data.attack_timeline.map((t) => t.count), areaStyle: {} }],
    };
  }, [data]);

  const pieOption = useMemo(() => {
    if (!data) return {};
    const d = data.alert_distribution_severity;
    return {
      backgroundColor: 'transparent',
      series: [{
        type: 'pie',
        radius: ['45%', '70%'],
        data: Object.entries(d).map(([name, value]) => ({ name, value })),
      }],
    };
  }, [data]);

  if (error) return <p className="text-cyber-critical">{error}</p>;
  if (!data) return <p className="text-cyber-muted">Đang tải dashboard...</p>;

  const degraded = data.data_status !== 'available';

  return (
    <div className="space-y-6">
      {degraded && (
        <div className="p-4 rounded-lg border border-amber-600/50 bg-amber-950/30 text-amber-200 text-sm">
          Dữ liệu SIEM không khả dụng — hiển thị trạng thái degraded. Không dùng KPI giả.
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Kpi title="Security Score" value={data.security_score.level} sub={`${data.security_score.score}`} />
        <Kpi title="Critical" value={String(data.critical_alerts)} />
        <Kpi title="High" value={String(data.high_alerts)} />
        <Kpi title="Servers Online" value={`${data.agents_online}/${data.total_servers}`} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="p-4 rounded-xl border border-cyber-border bg-cyber-card">
          <h3 className="text-sm font-semibold mb-3">Attack Timeline</h3>
          <ReactECharts option={chartOption} style={{ height: 280 }} notMerge lazyUpdate />
        </div>
        <div className="p-4 rounded-xl border border-cyber-border bg-cyber-card">
          <h3 className="text-sm font-semibold mb-3">Alert Distribution</h3>
          <ReactECharts option={pieOption} style={{ height: 280 }} notMerge lazyUpdate />
        </div>
      </div>
    </div>
  );
}

function Kpi({ title, value, sub }: { title: string; value: string; sub?: string }) {
  return (
    <div className="p-4 rounded-xl border border-cyber-border bg-cyber-card">
      <p className="text-xs text-cyber-muted uppercase">{title}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs text-cyber-muted mt-1">{sub}</p>}
    </div>
  );
}
