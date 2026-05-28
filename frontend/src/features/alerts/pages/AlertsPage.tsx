import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useAlertStore } from '../store';
import { SeverityBadge } from '../../../shared/ui/SeverityBadge';
import { formatDateTime } from '../../../utils/format';

const PAGE_SIZE = 50;

export function AlertsPage() {
  const { alerts, totalAlerts, loading, error, fetchAlerts } = useAlertStore();
  const [page, setPage] = useState(1);
  const [severity, setSeverity] = useState('');

  useEffect(() => {
    fetchAlerts({ page, page_size: PAGE_SIZE, severity: severity || undefined });
  }, [page, severity, fetchAlerts]);

  const totalPages = Math.max(1, Math.ceil(totalAlerts / PAGE_SIZE));

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Luồng cảnh báo</h1>
          <p className="text-sm text-slate-400 mt-0.5">
            {totalAlerts > 0 ? `${totalAlerts.toLocaleString('vi-VN')} cảnh báo` : 'Chưa có cảnh báo'}
          </p>
        </div>
      </div>

      {/* Severity filter */}
      <div className="flex gap-2 flex-wrap">
        {[
          { value: '', label: 'Tất cả' },
          { value: 'critical', label: 'Nguy cấp' },
          { value: 'high', label: 'Cao' },
          { value: 'medium', label: 'Trung bình' },
          { value: 'low', label: 'Thấp' },
        ].map(({ value, label }) => (
          <button
            key={value || 'all'}
            type="button"
            onClick={() => { setSeverity(value); setPage(1); }}
            className={`px-3 py-1.5 rounded-lg text-xs border transition ${
              severity === value
                ? 'border-cyan-500 bg-cyan-500/10 text-cyan-300'
                : 'border-slate-700 text-slate-400 hover:text-white'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="px-4 py-3 rounded-xl border border-red-800/50 bg-red-950/30 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="rounded-xl border border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-900 text-slate-400 border-b border-slate-800">
            <tr>
              <th className="p-3 text-left font-medium">Thời gian</th>
              <th className="p-3 text-left font-medium">Mức</th>
              <th className="p-3 text-left font-medium">Mô tả</th>
              <th className="p-3 text-left font-medium">Agent</th>
              <th className="p-3 text-left font-medium">IP nguồn</th>
              <th className="p-3 text-right font-medium">Risk</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <tr key={i} className="border-t border-slate-800">
                  {Array.from({ length: 6 }).map((__, j) => (
                    <td key={j} className="p-3">
                      <div className="h-4 rounded bg-slate-800 animate-pulse" />
                    </td>
                  ))}
                </tr>
              ))
            ) : alerts.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-12 text-center text-slate-500">
                  Không có cảnh báo nào{severity ? ` với mức "${severity}"` : ''}
                </td>
              </tr>
            ) : (
              alerts.map((a) => (
                <tr key={a.id} className="border-t border-slate-800 hover:bg-slate-900/50 transition">
                  <td className="p-3 font-mono text-xs text-slate-400 whitespace-nowrap">
                    {formatDateTime(a.timestamp)}
                  </td>
                  <td className="p-3">
                    <SeverityBadge severity={a.severity} />
                  </td>
                  <td className="p-3 max-w-sm">
                    <span className="block truncate text-slate-200" title={a.description}>
                      {a.description}
                    </span>
                    <span className="text-xs text-slate-500">{a.category}</span>
                  </td>
                  <td className="p-3 text-slate-300">{a.agent_name}</td>
                  <td className="p-3 font-mono text-xs text-slate-400">{a.source_ip || '—'}</td>
                  <td className="p-3 text-right">
                    <span className={`font-mono text-xs ${
                      a.risk_score >= 70 ? 'text-red-400' :
                      a.risk_score >= 40 ? 'text-amber-400' : 'text-emerald-400'
                    }`}>
                      {a.risk_score.toFixed(0)}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">
          Trang {page} / {totalPages}
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={page <= 1 || loading}
            onClick={() => setPage((p) => p - 1)}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-700 text-xs text-slate-400 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            <ChevronLeft className="w-3.5 h-3.5" /> Trước
          </button>
          <button
            type="button"
            disabled={page >= totalPages || loading}
            onClick={() => setPage((p) => p + 1)}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-700 text-xs text-slate-400 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            Sau <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
