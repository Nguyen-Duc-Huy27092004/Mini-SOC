import { useEffect, useState } from 'react';
import { Activity, HardDrive, Monitor, Server } from 'lucide-react';
import api from '../../../shared/api/client';

interface Agent {
  agent_id: string;
  agent_name: string;
  status: string;
  ip_address?: string;
  os_name?: string;
  risk_score: number;
  critical_alerts: number;
}

interface BackupStatus {
  status: string;
  message?: string;
}

interface UserEvent {
  user: string;
  events: number;
}

export function OperationsDashboard() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [users, setUsers] = useState<UserEvent[]>([]);
  const [backup, setBackup] = useState<BackupStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      api.get('/dashboard/agents'),
      api.get('/users'),
      api.get('/backup'),
    ])
      .then(([a, u, b]) => {
        setAgents(a.data ?? []);
        setUsers(u.data.users ?? []);
        setBackup(b.data);
      })
      .catch(() => setError('Không thể tải dữ liệu vận hành'))
      .finally(() => setLoading(false));
  }, []);

  const online = agents.filter((x) => x.status === 'active').length;
  const offline = agents.length - online;

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Vận hành IT</h1>
          <p className="text-sm text-slate-400 mt-1">Trạng thái endpoint · Đăng nhập · Dịch vụ</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 rounded-xl border border-slate-700 bg-slate-900/50 animate-pulse" />
          ))}
        </div>
        <div className="h-64 rounded-xl border border-slate-700 bg-slate-900/50 animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-white">Vận hành IT</h1>
        <div className="p-4 rounded-xl border border-red-800/50 bg-red-950/30 text-red-300 text-sm">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Vận hành IT</h1>
        <p className="text-sm text-slate-400 mt-1">Trạng thái endpoint · Đăng nhập · Dịch vụ</p>
      </div>

      {/* KPI Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Endpoint online" value={online} icon={Monitor} color="text-emerald-400" />
        <StatCard label="Endpoint offline" value={offline} icon={Server} color="text-red-400" />
        <StatCard label="Tổng agent" value={agents.length} icon={Activity} color="text-cyan-400" />
        <StatCard
          label="Backup"
          value={backup?.status || '—'}
          icon={HardDrive}
          color={backup?.status === 'ok' ? 'text-emerald-400' : 'text-amber-400'}
        />
      </div>

      {/* Agent Table */}
      <section className="rounded-xl border border-slate-700 bg-slate-900/40 p-4">
        <h2 className="font-semibold text-slate-100 mb-3">Danh sách máy chủ / agent</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[600px]">
            <thead className="text-slate-400 border-b border-slate-800">
              <tr>
                <th className="text-left p-2 font-medium">Tên agent</th>
                <th className="text-left p-2 font-medium">IP</th>
                <th className="text-left p-2 font-medium">OS</th>
                <th className="text-left p-2 font-medium">Trạng thái</th>
                <th className="text-right p-2 font-medium">Risk</th>
                <th className="text-right p-2 font-medium">Critical</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((ag) => (
                <tr key={ag.agent_id} className="border-b border-slate-800/50 hover:bg-slate-800/20 transition">
                  <td className="p-2 font-medium text-slate-200">{ag.agent_name}</td>
                  <td className="p-2 font-mono text-xs text-slate-400">{ag.ip_address || '—'}</td>
                  <td className="p-2 text-slate-400">{ag.os_name || '—'}</td>
                  <td className="p-2">
                    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${
                      ag.status === 'active' ? 'text-emerald-400' : 'text-red-400'
                    }`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${
                        ag.status === 'active' ? 'bg-emerald-400' : 'bg-red-400'
                      }`} />
                      {ag.status === 'active' ? 'Online' : 'Offline'}
                    </span>
                  </td>
                  <td className="p-2 text-right">
                    <span className={`font-mono text-xs ${
                      ag.risk_score >= 70 ? 'text-red-400' :
                      ag.risk_score >= 40 ? 'text-amber-400' : 'text-emerald-400'
                    }`}>
                      {ag.risk_score.toFixed(0)}
                    </span>
                  </td>
                  <td className="p-2 text-right">
                    <span className={`font-mono text-xs ${ag.critical_alerts > 0 ? 'text-red-400' : 'text-slate-500'}`}>
                      {ag.critical_alerts}
                    </span>
                  </td>
                </tr>
              ))}
              {!agents.length && (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-slate-500 text-sm">
                    Chưa có agent nào được đăng ký
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Login Events */}
      <section className="rounded-xl border border-slate-700 bg-slate-900/40 p-4">
        <h2 className="font-semibold text-slate-100 mb-3">
          Đăng nhập thất bại / bất thường (24h)
        </h2>
        {users.length > 0 ? (
          <ul className="space-y-2">
            {users.map((u) => (
              <li
                key={u.user}
                className="flex items-center justify-between py-2 border-b border-slate-800/60 last:border-0"
              >
                <span className="text-sm text-slate-300 font-mono">{u.user}</span>
                <span className={`text-xs font-mono px-2 py-0.5 rounded ${
                  u.events >= 10 ? 'bg-red-950/50 text-red-300' :
                  u.events >= 5 ? 'bg-amber-950/50 text-amber-300' :
                  'bg-slate-800 text-slate-400'
                }`}>
                  {u.events} sự kiện
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-slate-500 text-sm py-4 text-center">
            Không có hoạt động đăng nhập bất thường trong 24 giờ qua
          </p>
        )}
      </section>
    </div>
  );
}

function StatCard({
  label, value, icon: Icon, color,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  color: string;
}) {
  return (
    <div className="p-4 rounded-xl border border-slate-700 bg-slate-900/50 hover:border-slate-600 transition">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-slate-400">{label}</p>
        <Icon className={`w-4 h-4 ${color}`} />
      </div>
      <p className="text-2xl font-bold text-white tabular-nums">{value}</p>
    </div>
  );
}
