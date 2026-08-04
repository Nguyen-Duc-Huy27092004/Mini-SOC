import { useState, useEffect, useCallback } from 'react';
import { CheckCircle, XCircle, Clock, RefreshCw, Workflow, AlertTriangle } from 'lucide-react';
import api from '../../../shared/api/client';

interface Approval {
  id: string;
  run_id: string;
  status: string;
  requested_at: string;
  decided_at: string | null;
  decided_by_id: string | null;
}

export function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [decidingId, setDecidingId] = useState<string>('');

  const fetchApprovals = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await api.get('/soar/approvals');
      setApprovals(data);
    } catch (err) {
      console.warn('Approvals fetch failed:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchApprovals();
    const interval = setInterval(fetchApprovals, 30_000);
    return () => clearInterval(interval);
  }, [fetchApprovals]);

  const handleDecide = async (approvalId: string, decision: 'Approved' | 'Rejected') => {
    setDecidingId(approvalId);
    try {
      await api.post(`/soar/approvals/${approvalId}/decide`, null, {
        params: { decision },
      });
      // Remove from pending list after decision
      setApprovals(prev => prev.filter(a => a.id !== approvalId));
    } catch (err) {
      console.warn('Decision failed:', err);
    } finally {
      setDecidingId('');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <Workflow className="w-7 h-7 text-amber-400" />
            <h1 className="text-2xl font-bold text-white tracking-tight">Phê duyệt SOAR</h1>
          </div>
          <p className="text-slate-400 text-sm mt-1">
            Các hành động tự động cần phê duyệt trước khi thực thi (chế độ bán tự động)
          </p>
        </div>
        <button
          onClick={fetchApprovals}
          className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm rounded-lg border border-slate-700 transition"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Làm mới
        </button>
      </div>

      {/* Pending count badge */}
      {!loading && approvals.length > 0 && (
        <div className="flex items-center gap-3 p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
          <p className="text-amber-300 text-sm font-medium">
            Có <span className="font-bold">{approvals.length}</span> hành động đang chờ phê duyệt của bạn.
            Hệ thống SOAR đang tạm dừng cho đến khi được xử lý.
          </p>
        </div>
      )}

      {/* Approvals list */}
      {loading ? (
        <div className="p-10 text-center text-slate-500 border border-dashed border-slate-700 rounded-xl">
          Đang tải danh sách phê duyệt...
        </div>
      ) : approvals.length === 0 ? (
        <div className="p-10 text-center border border-dashed border-slate-700 rounded-xl bg-slate-900/30">
          <CheckCircle className="w-10 h-10 text-emerald-500/50 mx-auto mb-3" />
          <p className="text-slate-400 font-medium">Không có hành động nào đang chờ phê duyệt.</p>
          <p className="text-slate-500 text-sm mt-1">
            Tất cả hành động bán tự động đã được xử lý. Danh sách tự động làm mới mỗi 30 giây.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {approvals.map(approval => (
            <div
              key={approval.id}
              className="bg-slate-900/80 border border-amber-500/20 rounded-xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-amber-400 shrink-0" />
                  <span className="text-sm font-semibold text-white">Yêu cầu phê duyệt</span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30 font-medium">
                    Chờ xử lý
                  </span>
                </div>
                <p className="text-xs text-slate-400">
                  Run ID: <span className="font-mono text-slate-300">{approval.run_id?.slice(0, 16)}…</span>
                </p>
                <p className="text-xs text-slate-500">
                  Yêu cầu lúc:{' '}
                  {approval.requested_at
                    ? new Date(approval.requested_at).toLocaleString('vi-VN')
                    : '—'}
                </p>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <button
                  onClick={() => handleDecide(approval.id, 'Rejected')}
                  disabled={decidingId === approval.id}
                  className="flex items-center gap-1.5 px-4 py-2 bg-slate-800 hover:bg-rose-950/50 border border-slate-700 hover:border-rose-700 text-slate-300 hover:text-rose-300 text-sm font-medium rounded-lg transition disabled:opacity-50"
                >
                  <XCircle className="w-4 h-4" />
                  Từ chối
                </button>
                <button
                  onClick={() => handleDecide(approval.id, 'Approved')}
                  disabled={decidingId === approval.id}
                  className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
                >
                  {decidingId === approval.id
                    ? <RefreshCw className="w-4 h-4 animate-spin" />
                    : <CheckCircle className="w-4 h-4" />
                  }
                  Phê duyệt
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
