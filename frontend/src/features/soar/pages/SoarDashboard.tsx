import { useState, useEffect } from 'react';
import { PlaySquare, Zap, Clock, XCircle, RefreshCw, ShieldCheck, Workflow, Brain } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import api from '../../../shared/api/client';

interface SoarStats {
  total_playbooks: number;
  active_playbooks: number;
  runs_24h: number;
  failed_24h: number;
  pending_approvals: number;
}

interface PlaybookItem {
  id: string;
  name: string;
  description: string;
  is_active: boolean;
  execution_mode: string;
}

interface RunItem {
  id: string;
  playbook_id: string;
  status: string;
  started_at: string;
  trigger_source: string;
}

interface AiStatus {
  mode: 'live' | 'simulation';
  gemini_configured: boolean;
  gemini_model: string;
  slack_configured: boolean;
  telegram_configured: boolean;
}

export function SoarDashboard() {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<SoarStats>({
    total_playbooks: 0,
    active_playbooks: 0,
    runs_24h: 0,
    failed_24h: 0,
    pending_approvals: 0,
  });
  const [recentRuns, setRecentRuns] = useState<RunItem[]>([]);
  const [aiStatus, setAiStatus] = useState<AiStatus | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [playbooksRes, runsRes, approvalsRes, aiStatusRes] = await Promise.allSettled([
        api.get('/soar/playbooks'),
        api.get('/soar/runs'),
        api.get('/soar/approvals'),
        api.get('/ai/status'),
      ]);

      const playbooks: PlaybookItem[] = playbooksRes.status === 'fulfilled' ? playbooksRes.value.data : [];
      const runs: RunItem[] = runsRes.status === 'fulfilled' ? runsRes.value.data : [];
      const approvals = approvalsRes.status === 'fulfilled' ? approvalsRes.value.data : [];
      if (aiStatusRes.status === 'fulfilled') setAiStatus(aiStatusRes.value.data);

      const cutoff24h = Date.now() - 24 * 60 * 60 * 1000;
      const recent = runs.filter(r => new Date(r.started_at).getTime() > cutoff24h);

      setStats({
        total_playbooks: playbooks.length,
        active_playbooks: playbooks.filter(p => p.is_active).length,
        runs_24h: recent.length,
        failed_24h: recent.filter(r => r.status === 'Failed').length,
        pending_approvals: approvals.length,
      });

      setRecentRuns(runs.slice(0, 5));
    } catch (err) {
      console.warn('SOAR dashboard fetch failed:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const statusColor: Record<string, string> = {
    Completed: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
    Failed: 'text-rose-400 bg-rose-500/10 border-rose-500/30',
    Running: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/30',
    Pending: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Tổng quan SOAR</h1>
          <p className="text-slate-400 text-sm mt-1">Security Orchestration, Automation & Response</p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm rounded-lg border border-slate-700 transition"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Làm mới
        </button>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/80">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Tổng Playbooks</p>
            <PlaySquare className="w-4 h-4 text-cyan-400" />
          </div>
          <p className="text-3xl font-bold text-white">{loading ? '—' : stats.total_playbooks}</p>
          <p className="text-xs text-slate-500 mt-1">{stats.active_playbooks} đang hoạt động</p>
        </div>

        <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/80">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Kích hoạt (24h)</p>
            <Zap className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-3xl font-bold text-emerald-400">{loading ? '—' : stats.runs_24h}</p>
          <p className="text-xs text-slate-500 mt-1">Lần chạy tự động</p>
        </div>

        <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/80">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Chờ phê duyệt</p>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-3xl font-bold text-amber-400">{loading ? '—' : stats.pending_approvals}</p>
          <p className="text-xs text-slate-500 mt-1">
            {stats.pending_approvals > 0 ? 'Cần xử lý ngay' : 'Không có gì chờ'}
          </p>
        </div>

        <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/80">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Thất bại (24h)</p>
            <XCircle className="w-4 h-4 text-rose-400" />
          </div>
          <p className="text-3xl font-bold text-rose-400">{loading ? '—' : stats.failed_24h}</p>
          <p className="text-xs text-slate-500 mt-1">Hành động lỗi</p>
        </div>
      </div>

      {/* Quick Nav Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <NavLink
          to="/soar/ddos"
          className="flex items-center gap-4 p-5 rounded-xl border border-slate-800 bg-slate-900/60 hover:bg-slate-800/60 hover:border-rose-500/30 transition group"
        >
          <div className="w-10 h-10 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-center justify-center shrink-0">
            <ShieldCheck className="w-5 h-5 text-rose-400" />
          </div>
          <div>
            <p className="font-semibold text-white text-sm group-hover:text-rose-300 transition">Chống DDoS & IDS/IPS</p>
            <p className="text-xs text-slate-500 mt-0.5">Quản lý IP bị chặn, engine anti-DDoS</p>
          </div>
        </NavLink>

        <NavLink
          to="/soar/playbooks"
          className="flex items-center gap-4 p-5 rounded-xl border border-slate-800 bg-slate-900/60 hover:bg-slate-800/60 hover:border-cyan-500/30 transition group"
        >
          <div className="w-10 h-10 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center shrink-0">
            <PlaySquare className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <p className="font-semibold text-white text-sm group-hover:text-cyan-300 transition">Quản lý Playbooks</p>
            <p className="text-xs text-slate-500 mt-0.5">Xem, tạo, kích hoạt tự động hoá</p>
          </div>
        </NavLink>

        <NavLink
          to="/soar/approvals"
          className="flex items-center gap-4 p-5 rounded-xl border border-slate-800 bg-slate-900/60 hover:bg-slate-800/60 hover:border-amber-500/30 transition group"
        >
          <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center shrink-0">
            <Workflow className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <p className="font-semibold text-white text-sm group-hover:text-amber-300 transition">Phê duyệt ({stats.pending_approvals})</p>
            <p className="text-xs text-slate-500 mt-0.5">Xem xét và xử lý các yêu cầu phê duyệt</p>
          </div>
        </NavLink>

        {/* AI-SOAR Chat */}
        <NavLink
          to="/soar/ai-chat"
          className="flex items-center gap-4 p-5 rounded-xl border border-slate-800 bg-slate-900/60 hover:bg-slate-800/60 hover:border-violet-500/30 transition group relative overflow-hidden"
        >
          <div className="absolute inset-0 bg-gradient-to-br from-violet-500/5 to-transparent pointer-events-none" />
          <div className="w-10 h-10 rounded-lg bg-violet-500/10 border border-violet-500/20 flex items-center justify-center shrink-0">
            <Brain className="w-5 h-5 text-violet-400" />
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-white text-sm group-hover:text-violet-300 transition flex items-center gap-1.5">
              AI SOC Chat
              {aiStatus?.mode === 'live'
                ? <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-semibold">LIVE</span>
                : <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-semibold">SIM</span>
              }
            </p>
            <p className="text-xs text-slate-500 mt-0.5 truncate">
              {aiStatus?.gemini_configured ? `Gemini ${aiStatus.gemini_model}` : 'Cấu hình API key'}
            </p>
          </div>
        </NavLink>
      </div>

      {/* Recent Runs */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <h2 className="font-semibold text-white text-sm">Lịch sử kích hoạt gần đây</h2>
          <NavLink to="/soar/playbooks" className="text-xs text-cyan-400 hover:text-cyan-300 transition">Xem tất cả →</NavLink>
        </div>
        {loading ? (
          <div className="p-8 text-center text-slate-500 text-sm">Đang tải dữ liệu...</div>
        ) : recentRuns.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-sm">Chưa có lịch sử kích hoạt nào.</div>
        ) : (
          <table className="w-full text-sm text-slate-300">
            <thead className="bg-slate-950/60 text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="px-5 py-3 text-left">Playbook ID</th>
                <th className="px-5 py-3 text-left">Nguồn kích hoạt</th>
                <th className="px-5 py-3 text-left">Thời gian bắt đầu</th>
                <th className="px-5 py-3 text-left">Trạng thái</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {recentRuns.map(run => (
                <tr key={run.id} className="hover:bg-slate-800/30 transition">
                  <td className="px-5 py-3 font-mono text-xs text-slate-400">{run.playbook_id?.slice(0, 8)}…</td>
                  <td className="px-5 py-3 capitalize">{run.trigger_source || 'auto'}</td>
                  <td className="px-5 py-3 text-slate-400 text-xs">
                    {run.started_at ? new Date(run.started_at).toLocaleString('vi-VN') : '—'}
                  </td>
                  <td className="px-5 py-3">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${statusColor[run.status] || 'text-slate-400 bg-slate-800 border-slate-700'}`}>
                      {run.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
