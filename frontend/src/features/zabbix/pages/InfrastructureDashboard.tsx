import { useEffect, useState } from 'react';
import { 
  Server, ServerOff, AlertTriangle, ShieldAlert,
  Activity, Zap, Clock, Search, CheckCircle2, XCircle,
  Cpu, Globe, Radio
} from 'lucide-react';
import { getOverview, getTopServers, getProblems, getHosts } from '../api';
import type { ZabbixOverviewResponse, ZabbixTopServer, ZabbixProblemOut, ZabbixHostOut } from '../types';


// ─── Agent type badge helpers ─────────────────────────────────────────────────

/** Returns Tailwind classes for each agent type badge in the table */
function agentTypeBadge(type: string): string {
  switch (type) {
    case 'Zabbix Agent':
      return 'text-indigo-400 bg-indigo-500/10 border-indigo-500/30';
    case 'SNMP':
      return 'text-cyan-400 bg-cyan-500/10 border-cyan-500/30';
    case 'HTTP Agent':
      return 'text-violet-400 bg-violet-500/10 border-violet-500/30';
    case 'IPMI':
      return 'text-orange-400 bg-orange-500/10 border-orange-500/30';
    case 'JMX':
      return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
    default:
      return 'text-slate-400 bg-slate-500/10 border-slate-500/30';
  }
}

/** Returns Tailwind classes for the active filter button */
function agentTypeBadgeActive(type: string): string {
  switch (type) {
    case 'All':        return 'bg-indigo-600 border-indigo-500 text-white';
    case 'Zabbix Agent': return 'bg-indigo-500/20 border-indigo-400 text-indigo-300';
    case 'SNMP':       return 'bg-cyan-500/20 border-cyan-400 text-cyan-300';
    case 'HTTP Agent': return 'bg-violet-500/20 border-violet-400 text-violet-300';
    case 'IPMI':       return 'bg-orange-500/20 border-orange-400 text-orange-300';
    case 'JMX':        return 'bg-amber-500/20 border-amber-400 text-amber-300';
    default:           return 'bg-slate-700 border-slate-500 text-slate-200';
  }
}

/** Returns a small icon element for each agent type */
function agentTypeIcon(type: string) {
  const cls = 'w-2.5 h-2.5';
  switch (type) {
    case 'Zabbix Agent': return <Cpu className={cls} />;
    case 'HTTP Agent':   return <Globe className={cls} />;
    case 'SNMP':         return <Radio className={cls} />;
    case 'IPMI':         return <Zap className={cls} />;
    case 'JMX':          return <Activity className={cls} />;
    default:             return null;
  }
}

export function InfrastructureDashboard() {

  const [overview, setOverview] = useState<ZabbixOverviewResponse | null>(null);
  const [topServers, setTopServers] = useState<ZabbixTopServer[]>([]);
  const [problems, setProblems] = useState<ZabbixProblemOut[]>([]);
  const [hosts, setHosts] = useState<ZabbixHostOut[]>([]);
  const [search, setSearch] = useState('');
  const [agentFilter, setAgentFilter] = useState<string>('All');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [ovData, topData, probData, hostsData] = await Promise.all([
          getOverview(),
          getTopServers(50),
          getProblems(),
          getHosts()
        ]);
        setOverview(ovData);
        setTopServers(topData);
        setProblems(probData); // Hiển thị toàn bộ các vấn đề (có scroll)
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

  const filteredHosts = hosts.filter(h => {
    const matchSearch = 
      h.name.toLowerCase().includes(search.toLowerCase()) ||
      (h.ip_address && h.ip_address.includes(search)) ||
      h.agent_types.some(t => t.toLowerCase().includes(search.toLowerCase()));
    const matchAgent = agentFilter === 'All' || h.agent_types.includes(agentFilter);
    return matchSearch && matchAgent;
  });

  // Derive unique agent types for filter tabs
  const agentTypeOptions = ['All', ...Array.from(
    new Set(hosts.flatMap(h => h.agent_types))
  ).sort()];

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
            <p className="text-xs text-emerald-400 mt-1">{overview.online_servers} hoạt động</p>
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
        {/* All Servers by Resource */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 flex flex-col max-h-[600px]">
          <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2 mb-4 shrink-0">
            <Activity className="w-4 h-4 text-indigo-400" />
            Trạng thái tài nguyên máy chủ ({topServers.length})
          </h2>
          <div className="space-y-4 overflow-y-auto pr-2">
            {topServers.map(server => (
              <div key={server.host_id} className="bg-slate-950 border border-slate-800/50 p-3 rounded-lg flex flex-col gap-2">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-semibold text-slate-300">{server.host_name}</span>
                  <span className="text-[10px] text-slate-500 font-mono">{server.ip_address || 'Không rõ IP'}</span>
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
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 flex flex-col max-h-[600px]">
          <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2 mb-4 shrink-0">
            <Zap className="w-4 h-4 text-rose-400" />
            Các vấn đề mới được phát hiện
          </h2>
          <div className="space-y-3 overflow-y-auto pr-2">
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
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <Server className="w-4 h-4 text-indigo-400" />
              Danh sách máy chủ giám sát ({filteredHosts.length}/{hosts.length})
            </h2>
            <div className="flex items-center gap-3 flex-wrap">
              {/* Agent Type Filter Tabs */}
              <div className="flex items-center gap-1 flex-wrap">
                {agentTypeOptions.map(type => (
                  <button
                    key={type}
                    onClick={() => setAgentFilter(type)}
                    className={`px-2.5 py-1 rounded text-[10px] font-semibold uppercase tracking-wider border transition ${
                      agentFilter === type
                        ? agentTypeBadgeActive(type)
                        : 'bg-slate-900 border-slate-700 text-slate-400 hover:border-slate-600'
                    }`}
                  >
                    {type === 'All' ? 'Tất cả' : type}
                  </button>
                ))}
              </div>
              {/* Search */}
              <div className="relative">
                <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input 
                  type="text"
                  placeholder="Tên, IP, giao thức..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="pl-9 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500 w-full md:w-56 transition"
                />
              </div>
            </div>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[900px]">
            <thead>
              <tr className="bg-slate-900/80 border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
                <th className="px-5 py-3">Tên máy chủ</th>
                <th className="px-5 py-3">Địa chỉ IP</th>
                <th className="px-5 py-3">Giao thức</th>
                <th className="px-5 py-3">Trạng thái</th>
                <th className="px-5 py-3 text-center">Vấn đề</th>
                <th className="px-5 py-3">Cảnh báo cao nhất</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {filteredHosts.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-center text-slate-500 text-sm">
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
                      <div className="flex flex-wrap gap-1">
                        {(host.agent_types ?? []).length === 0 ? (
                          <span className="text-[10px] text-slate-600">—</span>
                        ) : (
                          host.agent_types.map(type => (
                            <span
                              key={type}
                              title={type}
                              className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider border ${agentTypeBadge(type)}`}
                            >
                              {agentTypeIcon(type)}
                              {type}
                            </span>
                          ))
                        )}
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      {(() => {
                        const code = host.available_label?.toLowerCase();
                        if (code === 'available') return (
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider uppercase border text-emerald-400 bg-emerald-500/10 border-emerald-500/20">
                            <CheckCircle2 className="w-3 h-3" />
                            Hoạt động
                          </span>
                        );
                        if (code === 'unavailable') return (
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider uppercase border text-rose-400 bg-rose-500/10 border-rose-500/20">
                            <XCircle className="w-3 h-3" />
                            Không hoạt động
                          </span>
                        );
                        // Unknown — could be HTTP Agent still resolving
                        return (
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider uppercase border text-amber-400 bg-amber-500/10 border-amber-500/20">
                            <Clock className="w-3 h-3" />
                            Không rõ
                          </span>
                        );
                      })()}
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
