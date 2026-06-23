import { useCallback, useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import api from '../../../shared/api/client';
import { useAlertStore } from '../../alerts/store';
import { SeverityBadge } from '../../../shared/ui/SeverityBadge';
import { formatDateTime } from '../../../utils/format';

interface Incident {
  id: string;
  title: string;
  status: string;
  severity: string;
  alert_count: number;
  source_ip?: string;
  correlation_type: string;
  created_at: string;
}

const STATUS_LABEL: Record<string, string> = {
  open: 'Mở',
  investigating: 'Đang điều tra',
  contained: 'Đã kiểm soát',
  resolved: 'Đã giải quyết',
  closed: 'Đã đóng',
};

const STATUS_COLOR: Record<string, string> = {
  open: 'text-red-400',
  investigating: 'text-amber-400',
  contained: 'text-cyan-400',
  resolved: 'text-emerald-400',
  closed: 'text-slate-500',
};

export function AnalystDashboard() {
  const { alerts, fetchAlerts, loading: alertLoading } = useAlertStore();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [incLoading, setIncLoading] = useState(false);
  const [incError, setIncError] = useState<string | null>(null);
  const [severity, setSeverity] = useState<string>('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadIncidents = useCallback(async () => {
    setIncLoading(true);
    setIncError(null);
    try {
      const res = await api.get('/incidents', { params: { limit: 20 } });
      setIncidents(res.data.incidents ?? []);
    } catch {
      setIncError('Không thể tải danh sách sự cố');
    } finally {
      setIncLoading(false);
    }
  }, []);

  const loadAlerts = useCallback(() => {
    fetchAlerts({ page: 1, page_size: 30, severity: severity || undefined });
  }, [fetchAlerts, severity]);

  useEffect(() => {
    loadIncidents();
    loadAlerts();
  }, [loadIncidents, loadAlerts]);

  const acknowledge = async (id: string) => {
    setActionLoading(id);
    try {
      await api.post(`/incidents/${id}/acknowledge`);
      await loadIncidents();
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Trung tâm phân tích</h1>
          <p className="text-sm text-slate-400 mt-1">Điều tra · Xác nhận · Phân công sự cố</p>
        </div>
        <button
          type="button"
          onClick={() => { loadIncidents(); loadAlerts(); }}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-700 text-slate-400 hover:text-white hover:border-slate-500 text-xs transition"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Làm mới
        </button>
      </div>

      {/* Severity filter */}
      <div className="flex gap-2 flex-wrap">
        {['', 'critical', 'high', 'medium', 'low'].map((s) => (
          <button
            key={s || 'all'}
            type="button"
            onClick={() => setSeverity(s)}
            className={`px-3 py-1.5 rounded-lg text-xs border transition ${
              severity === s
                ? 'border-cyan-500 bg-cyan-500/10 text-cyan-300'
                : 'border-slate-700 text-slate-400 hover:text-white'
            }`}
          >
            {s ? s.toUpperCase() : 'Tất cả'}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Incident Queue */}
        <section className="rounded-xl border border-slate-700 bg-slate-900/40 p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-slate-100">Hàng đợi sự cố</h2>
            {incidents.length > 0 && (
              <span className="text-xs text-slate-500">{incidents.length} sự cố</span>
            )}
          </div>

          {incError && (
            <div className="mb-3 px-3 py-2 rounded-lg bg-red-950/40 border border-red-800/50 text-red-300 text-xs">
              {incError}
            </div>
          )}

          {incLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 rounded-lg bg-slate-800/50 animate-pulse" />
              ))}
            </div>
          ) : (
            <div className="space-y-2 max-h-[520px] overflow-y-auto pr-1">
              {incidents.map((inc) => (
                <div
                  key={inc.id}
                  className="p-3 rounded-lg border border-slate-800 bg-slate-950/50 hover:border-slate-700 transition"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-medium text-sm text-slate-100 leading-snug">{inc.title}</p>
                    <SeverityBadge severity={inc.severity} />
                  </div>
                  <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                    <span className="text-xs text-slate-500">{inc.correlation_type}</span>
                    <span className="text-slate-700">·</span>
                    <span className="text-xs text-slate-500">{inc.alert_count} cảnh báo</span>
                    <span className="text-slate-700">·</span>
                    <span className={`text-xs font-medium ${STATUS_COLOR[inc.status] || 'text-slate-400'}`}>
                      {STATUS_LABEL[inc.status] || inc.status}
                    </span>
                  </div>
                  {inc.source_ip && (
                    <p className="text-xs text-slate-600 font-mono mt-1">{inc.source_ip}</p>
                  )}
                  <p className="text-xs text-slate-600 mt-1">{formatDateTime(inc.created_at)}</p>
                  {inc.status === 'open' && (
                    <button
                      type="button"
                      onClick={() => acknowledge(inc.id)}
                      disabled={actionLoading === inc.id}
                      className="mt-2 text-xs px-3 py-1 rounded-lg bg-cyan-600/80 hover:bg-cyan-500 text-white transition disabled:opacity-50"
                    >
                      {actionLoading === inc.id ? 'Đang xử lý...' : 'Xác nhận sự cố'}
                    </button>
                  )}
                </div>
              ))}
              {!incidents.length && !incLoading && (
                <div className="py-12 text-center">
                  <p className="text-slate-500 text-sm">Chưa có sự cố tương quan</p>
                  <p className="text-slate-600 text-xs mt-1">Hệ thống sẽ tự động tạo khi phát hiện mẫu tấn công</p>
                </div>
              )}
            </div>
          )}
        </section>

        {/* Alert Feed */}
        <section className="rounded-xl border border-slate-700 bg-slate-900/40 p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-slate-100">Luồng cảnh báo realtime</h2>
            {alerts.length > 0 && (
              <span className="text-xs text-slate-500">{alerts.length} cảnh báo</span>
            )}
          </div>

          {alertLoading ? (
            <div className="space-y-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-10 rounded bg-slate-800/50 animate-pulse" />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto max-h-[520px]">
              <table className="w-full text-sm min-w-[480px]">
                <thead className="text-left text-slate-400 border-b border-slate-800 sticky top-0 bg-slate-900/90">
                  <tr>
                    <th className="p-2 font-medium">Mức</th>
                    <th className="p-2 font-medium">Mô tả</th>
                    <th className="p-2 font-medium">Agent</th>
                    <th className="p-2 font-medium">IP nguồn</th>
                    <th className="p-2 font-medium text-right">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((a) => (
                    <tr key={a.id} className="border-b border-slate-800/60 hover:bg-slate-800/30 transition">
                      <td className="p-2"><SeverityBadge severity={a.severity} /></td>
                      <td className="p-2 max-w-[200px] truncate text-slate-300" title={a.description}>
                        {a.description}
                      </td>
                      <td className="p-2 text-slate-400">{a.agent_name}</td>
                      <td className="p-2 font-mono text-xs text-slate-400">{a.source_ip || '—'}</td>
                      <td className="p-2 text-right">
                        <span className={`font-mono text-xs ${
                          a.risk_score >= 70 ? 'text-red-400' :
                          a.risk_score >= 40 ? 'text-amber-400' : 'text-emerald-400'
                        }`}>
                          {a.risk_score.toFixed(0)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!alerts.length && (
                <div className="py-12 text-center">
                  <p className="text-slate-500 text-sm">Chưa có cảnh báo</p>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
