import { useState, useEffect } from 'react';
import { PlaySquare, Play, RefreshCw, ChevronDown, ChevronUp, CheckCircle, XCircle, Clock, Zap } from 'lucide-react';
import api from '../../../shared/api/client';

interface PlaybookAction {
  id: string;
  action_type: string;
  order: number;
}

interface PlaybookRule {
  id: string;
  field: string;
  operator: string;
  value: string;
}

interface Playbook {
  id: string;
  name: string;
  description: string;
  is_active: boolean;
  execution_mode: string;
  rules: PlaybookRule[];
  actions: PlaybookAction[];
}

interface RunItem {
  id: string;
  playbook_id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  trigger_source: string;
}

const modeLabel: Record<string, string> = {
  auto: 'Tự động',
  semi_auto: 'Bán tự động',
  manual: 'Thủ công',
};

const statusStyle: Record<string, string> = {
  Completed: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
  Failed: 'text-rose-400 bg-rose-500/10 border-rose-500/30',
  Running: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/30',
  Pending: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
};

export function PlaybooksPage() {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningId, setRunningId] = useState<string>('');
  const [expanded, setExpanded] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'playbooks' | 'runs'>('playbooks');

  const fetchAll = async () => {
    try {
      setLoading(true);
      const [pbRes, runsRes] = await Promise.allSettled([
        api.get('/soar/playbooks'),
        api.get('/soar/runs'),
      ]);
      if (pbRes.status === 'fulfilled') setPlaybooks(pbRes.value.data);
      if (runsRes.status === 'fulfilled') setRuns(runsRes.value.data);
    } catch (err) {
      console.warn('PlaybooksPage fetch failed:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  const handleRun = async (id: string) => {
    setRunningId(id);
    try {
      await api.post(`/soar/playbooks/${id}/run`, { source: 'manual' });
      await fetchAll(); // refresh runs
    } catch (err) {
      console.warn('Manual trigger failed:', err);
    } finally {
      setRunningId('');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <PlaySquare className="w-7 h-7 text-cyan-400" />
            <h1 className="text-2xl font-bold text-white tracking-tight">Quản lý Playbooks</h1>
          </div>
          <p className="text-slate-400 text-sm mt-1">
            Danh sách kịch bản tự động hoá ứng phó sự cố (SOAR Playbooks)
          </p>
        </div>
        <button
          onClick={fetchAll}
          className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm rounded-lg border border-slate-700 transition"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Làm mới
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-900/60 border border-slate-800 rounded-lg p-1 w-fit">
        <button
          onClick={() => setActiveTab('playbooks')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition ${
            activeTab === 'playbooks'
              ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <span className="flex items-center gap-2">
            <PlaySquare className="w-4 h-4" />
            Danh sách Playbooks ({playbooks.length})
          </span>
        </button>
        <button
          onClick={() => setActiveTab('runs')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition ${
            activeTab === 'runs'
              ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <span className="flex items-center gap-2">
            <Zap className="w-4 h-4" />
            Lịch sử kích hoạt ({runs.length})
          </span>
        </button>
      </div>

      {/* Playbooks Tab */}
      {activeTab === 'playbooks' && (
        <div className="space-y-3">
          {loading ? (
            <div className="p-10 text-center text-slate-500 border border-dashed border-slate-700 rounded-xl">
              Đang tải danh sách playbooks...
            </div>
          ) : playbooks.length === 0 ? (
            <div className="p-10 text-center border border-dashed border-slate-700 rounded-xl bg-slate-900/30">
              <PlaySquare className="w-10 h-10 text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400 font-medium">Chưa có playbook nào.</p>
              <p className="text-slate-500 text-sm mt-1">Tạo playbook mới để tự động hóa xử lý sự cố.</p>
            </div>
          ) : (
            playbooks.map(pb => (
              <div key={pb.id} className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden">
                <div
                  className="p-4 flex items-center justify-between cursor-pointer hover:bg-slate-800/40 transition"
                  onClick={() => setExpanded(expanded === pb.id ? '' : pb.id)}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${pb.is_active ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'}`} />
                    <div className="min-w-0">
                      <p className="font-semibold text-white text-sm">{pb.name}</p>
                      <p className="text-xs text-slate-400 truncate mt-0.5">{pb.description || 'Không có mô tả'}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0 ml-4">
                    <span className={`text-xs px-2.5 py-0.5 rounded-full border font-medium ${
                      pb.is_active
                        ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
                        : 'text-slate-500 bg-slate-800 border-slate-700'
                    }`}>
                      {pb.is_active ? 'Hoạt động' : 'Tắt'}
                    </span>
                    <span className="text-xs text-slate-500 bg-slate-800 px-2.5 py-0.5 rounded border border-slate-700">
                      {modeLabel[pb.execution_mode] || pb.execution_mode}
                    </span>
                    <button
                      onClick={e => { e.stopPropagation(); handleRun(pb.id); }}
                      disabled={runningId === pb.id}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white text-xs font-medium rounded-lg transition"
                    >
                      {runningId === pb.id
                        ? <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        : <Play className="w-3.5 h-3.5" />
                      }
                      Kích hoạt
                    </button>
                    {expanded === pb.id
                      ? <ChevronUp className="w-4 h-4 text-slate-500" />
                      : <ChevronDown className="w-4 h-4 text-slate-500" />
                    }
                  </div>
                </div>

                {expanded === pb.id && (
                  <div className="border-t border-slate-800 p-4 grid md:grid-cols-2 gap-4 bg-slate-950/40">
                    <div>
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                        Điều kiện kích hoạt ({pb.rules?.length || 0})
                      </p>
                      {pb.rules?.length === 0 ? (
                        <p className="text-xs text-slate-600 italic">Không có điều kiện (kích hoạt thủ công)</p>
                      ) : (
                        pb.rules?.map(r => (
                          <div key={r.id} className="text-xs text-slate-300 bg-slate-900 border border-slate-800 rounded px-2 py-1 mb-1 font-mono">
                            {r.field} <span className="text-cyan-400">{r.operator}</span> "{r.value}"
                          </div>
                        ))
                      )}
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                        Hành động thực thi ({pb.actions?.length || 0})
                      </p>
                      {pb.actions?.length === 0 ? (
                        <p className="text-xs text-slate-600 italic">Chưa có hành động nào được cấu hình</p>
                      ) : (
                        pb.actions?.map(a => (
                          <div key={a.id} className="text-xs text-slate-300 bg-slate-900 border border-slate-800 rounded px-2 py-1 mb-1">
                            <span className="text-amber-400 font-mono">[{a.order}]</span> {a.action_type}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Runs Tab */}
      {activeTab === 'runs' && (
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden">
          {loading ? (
            <div className="p-10 text-center text-slate-500 text-sm">Đang tải lịch sử...</div>
          ) : runs.length === 0 ? (
            <div className="p-10 text-center text-slate-500 text-sm">Chưa có lịch sử kích hoạt nào.</div>
          ) : (
            <table className="w-full text-sm text-slate-300">
              <thead className="bg-slate-950/60 text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-800">
                <tr>
                  <th className="px-5 py-3 text-left">Playbook</th>
                  <th className="px-5 py-3 text-left">Nguồn</th>
                  <th className="px-5 py-3 text-left">Bắt đầu</th>
                  <th className="px-5 py-3 text-left">Kết thúc</th>
                  <th className="px-5 py-3 text-left">Trạng thái</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {runs.map(run => (
                  <tr key={run.id} className="hover:bg-slate-800/30 transition">
                    <td className="px-5 py-3 font-mono text-xs text-slate-400">{run.playbook_id?.slice(0, 8)}…</td>
                    <td className="px-5 py-3 capitalize text-slate-300">{run.trigger_source || 'auto'}</td>
                    <td className="px-5 py-3 text-xs text-slate-400">
                      {run.started_at ? new Date(run.started_at).toLocaleString('vi-VN') : '—'}
                    </td>
                    <td className="px-5 py-3 text-xs text-slate-400">
                      {run.finished_at ? new Date(run.finished_at).toLocaleString('vi-VN') : '—'}
                    </td>
                    <td className="px-5 py-3">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${statusStyle[run.status] || 'text-slate-400 bg-slate-800 border-slate-700'}`}>
                        {run.status === 'Completed' && <CheckCircle className="w-3 h-3" />}
                        {run.status === 'Failed' && <XCircle className="w-3 h-3" />}
                        {run.status === 'Pending' && <Clock className="w-3 h-3" />}
                        {run.status === 'Running' && <RefreshCw className="w-3 h-3 animate-spin" />}
                        {run.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
