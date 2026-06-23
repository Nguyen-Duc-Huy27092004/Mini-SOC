import { useEffect, useState } from 'react';
import { 
  Server, ServerOff, AlertTriangle, ShieldAlert,
  Activity, Zap, Clock, Search, CheckCircle2, XCircle
} from 'lucide-react';
import { getOverview, getTopServers, getProblems, getHosts } from '../api';
import type { ZabbixOverviewResponse, ZabbixTopServer, ZabbixProblemOut, ZabbixHostOut } from '../types';

export function InfrastructureDashboard() {
  const [overview, setOverview] = useState<ZabbixOverviewResponse | null>(null);
  const [topServers, setTopServers] = useState<ZabbixTopServer[]>([]);
  const [problems, setProblems] = useState<ZabbixProblemOut[]>([]);
  const [hosts, setHosts] = useState<ZabbixHostOut[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [ovData, topData, probData, hostsData] = await Promise.all([
          getOverview(),
          getTopServers(5),
          getProblems(),
          getHosts()
        ]);
        setOverview(ovData);
        setTopServers(topData);
        setProblems(probData.slice(0, 5)); // show top 5 active problems
        setHosts(hostsData);
      } catch (err) {
        console.error('Failed to fetch dashboard data', err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400">
        <Activity className="w-6 h-6 animate-pulse mr-2" />
        Đang tải thông số hạ tầng...
      </div>
    );
  }

  if (!overview || !overview.is_online) {
    return (
      <div className="bg-red-950/30 border border-red-900 text-red-400 p-4 rounded-xl flex items-center gap-3">
        <ServerOff className="w-5 h-5 shrink-0" />
        <div>
          <h3 className="font-semibold text-sm">Zabbix không thể kết nối</h3>
          <p className="text-xs opacity-80 mt-1">{overview?.error || 'Không thể kết nối đến máy chủ giám sát.'}</p>
        </div>
      </div>
    );
  }

  const filteredHosts = hosts.filter(h => 
    h.name.toLowerCase().includes(search.toLowerCase()) || 
    (h.ip_address && h.ip_address.includes(search))
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Server className="w-5 h-5 text-indigo-400" />
            Tổng quan hạ tầng
          </h1>
          <p className="text-xs text-slate-400 mt-1">Hiện trạng và mức độ sử dụng tài nguyên</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-xs font-mono text-slate-300">
            Chỉ số: <span className={
              overview.health_score >= 90 ? 'text-emerald-400' :
              overview.health_score >= 70 ? 'text-amber-400' : 'text-red-400'
            }>{overview.health_score}%</span>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Servers */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Máy chủ được theo dõi</p>
            <p className="text-2xl font-bold text-slate-200">{overview.total_servers}</p>
            <p className="text-xs text-emerald-400 mt-1">{overview.online_servers} online</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
            <Server className="w-5 h-5 text-indigo-400" />
          </div>
        </div>

        {/* Warning Servers */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Cảnh báo máy chủ </p>
            <p className="text-2xl font-bold text-slate-200">{overview.warning_servers}</p>
            <p className="text-xs text-amber-400 mt-1">Cần chú ý</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
          </div>
        </div>

        {/* Critical Servers */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Máy chủ khẩn cấp</p>
            <p className="text-2xl font-bold text-slate-200">{overview.critical_servers}</p>
            <p className="text-xs text-red-400 mt-1">Cần can thiệp ngay</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center justify-center">
            <ShieldAlert className="w-5 h-5 text-red-400" />
          </div>
        </div>

        {/* Total Problems */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Vấn đề còn tồn tại</p>
            <p className="text-2xl font-bold text-slate-200">{overview.total_problems}</p>
            <p className="text-xs text-rose-400 mt-1">{overview.unacknowledged_problems} Chưa xác nhận</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
            <Zap className="w-5 h-5 text-rose-400" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top 5 Servers by Resource */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2 mb-4">
            <Activity className="w-4 h-4 text-indigo-400" />
            Top 5 máy chủ tiêu tốn tài nguyên
          </h2>
          <div className="space-y-4">
            {topServers.map(server => (
              <div key={server.host_id} className="bg-slate-950 border border-slate-800/50 p-3 rounded-lg flex flex-col gap-2">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-semibold text-slate-300">{server.host_name}</span>
                  <span className="text-[10px] text-slate-500 font-mono">{server.ip_address || 'Unknown IP'}</span>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  {/* CPU Bar */}
                  <div>
                    <div className="flex justify-between text-[10px] mb-1">
                      <span className="text-slate-400">CPU</span>
                      <span className={server.cpu_pct && server.cpu_pct > 80 ? 'text-red-400 font-semibold' : 'text-slate-300'}>
                        {server.cpu_pct?.toFixed(1) || 0}%
                      </span>
                    </div>
                    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div 
                        className={`h-full ${server.cpu_pct && server.cpu_pct > 80 ? 'bg-red-500' : 'bg-indigo-500'}`} 
                        style={{ width: `${Math.min(server.cpu_pct || 0, 100)}%` }}
                      />
                    </div>
                  </div>
                  {/* RAM Bar */}
                  <div>
                    <div className="flex justify-between text-[10px] mb-1">
                      <span className="text-slate-400">RAM</span>
                      <span className={server.mem_pct && server.mem_pct > 85 ? 'text-amber-400 font-semibold' : 'text-slate-300'}>
                        {server.mem_pct?.toFixed(1) || 0}%
                      </span>
                    </div>
                    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div 
                        className={`h-full ${server.mem_pct && server.mem_pct > 85 ? 'bg-amber-500' : 'bg-emerald-500'}`} 
                        style={{ width: `${Math.min(server.mem_pct || 0, 100)}%` }}
                      />
                    </div>
                  </div>
                  {/* Disk Bar */}
                  <div>
                    <div className="flex justify-between text-[10px] mb-1">
                      <span className="text-slate-400">Ổ đĩa</span>
                      <span className={server.disk_pct && server.disk_pct > 90 ? 'text-red-400 font-semibold' : 'text-slate-300'}>
                        {server.disk_pct?.toFixed(1) || 0}%
                      </span>
                    </div>
                    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div 
                        className={`h-full ${server.disk_pct && server.disk_pct > 90 ? 'bg-red-500' : 'bg-cyan-500'}`} 
                        style={{ width: `${Math.min(server.disk_pct || 0, 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            ))}
            {topServers.length === 0 && (
              <div className="text-xs text-slate-500 text-center py-4">Không có dữ liệu</div>
            )}
          </div>
        </div>

        {/* Top Active Problems */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2 mb-4">
            <Zap className="w-4 h-4 text-rose-400" />
            Các vấn đề mới được phát hiện
          </h2>
          <div className="space-y-3">
            {problems.map(p => (
              <div key={p.event_id} className="bg-slate-950 border border-slate-800/50 p-3 rounded-lg flex items-start gap-3">
                <div 
                  className="w-2 h-2 rounded-full mt-1.5 shrink-0" 
                  style={{ backgroundColor: p.severity_color }}
                />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-slate-200 truncate">{p.name}</p>
                  <p className="text-[10px] text-slate-500 mt-1">{p.host_name}</p>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-[10px] font-semibold" style={{ color: p.severity_color }}>
                    {p.severity_label.toUpperCase()}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-1 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {p.clock_iso ? new Date(p.clock_iso).toLocaleTimeString() : 'N/A'}
                  </div>
                </div>
              </div>
            ))}
            {problems.length === 0 && (
              <div className="text-xs text-emerald-500 text-center py-4 flex items-center justify-center gap-2">
                <ShieldAlert className="w-4 h-4" />
                Không có vấn đề nào
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Host List Table */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
        <div className="p-5 border-b border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Server className="w-4 h-4 text-indigo-400" />
            Danh sách máy chủ giám sát ({hosts.length})
          </h2>
          <div className="relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input 
              type="text"
              placeholder="Tìm kiếm máy chủ, IP..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-9 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500 w-full md:w-64 transition"
            />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[800px]">
            <thead>
              <tr className="bg-slate-900/80 border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
                <th className="px-5 py-3">Tên máy chủ</th>
                <th className="px-5 py-3">IP Address</th>
                <th className="px-5 py-3">Trạng thái</th>
                <th className="px-5 py-3 text-center">Vấn đề</th>
                <th className="px-5 py-3">Cảnh báo cao nhất</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {filteredHosts.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-slate-500 text-sm">
                    Không tìm thấy máy chủ nào phù hợp.
                  </td>
                </tr>
              ) : (
                filteredHosts.map(host => (
                  <tr key={host.host_id} className="hover:bg-slate-800/20 transition">
                    <td className="px-5 py-3">
                      <div className="font-semibold text-xs text-slate-200">{host.name}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5 truncate max-w-[200px]">
                        {host.groups.join(', ')}
                      </div>
                    </td>
                    <td className="px-5 py-3 text-xs font-mono text-slate-400">
                      {host.ip_address || '—'}
                    </td>
                    <td className="px-5 py-3">
                      <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider uppercase border ${
                        host.available 
                          ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' 
                          : 'text-rose-400 bg-rose-500/10 border-rose-500/20'
                      }`}>
                        {host.available ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                        {host.available_label}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-center">
                      <span className={`text-xs font-mono ${host.problem_count > 0 ? 'text-amber-400 font-semibold' : 'text-slate-500'}`}>
                        {host.problem_count}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      {host.problem_count > 0 ? (
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-rose-400">
                          {host.max_severity_label}
                        </span>
                      ) : (
                        <span className="text-[10px] text-slate-600">—</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
