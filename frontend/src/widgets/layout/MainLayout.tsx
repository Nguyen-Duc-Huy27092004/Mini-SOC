import { useEffect } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard, Bell, ShieldAlert, LogOut, Wifi, WifiOff,
  Briefcase, Wrench, Shield, User, Server, CalendarClock, ListTodo, MailWarning
} from 'lucide-react';
import { useAuthStore, selectUser } from '../../features/auth/store';
import { useAlertStore } from '../../features/alerts/store';
import { useWebSocket } from '../../shared/hooks/useWebSocket';
import { SeverityBadge } from '../../shared/ui/SeverityBadge';

const wazuhNav = [
  { to: '/executive', label: 'Ban Lãnh đạo', icon: Briefcase },
  { to: '/analyst', label: 'SOC Analyst', icon: ShieldAlert },
  { to: '/operations', label: 'Vận hành IT', icon: Wrench },
  { to: '/alerts', label: 'Cảnh báo', icon: Bell },
];

const zabbixNav = [
  { to: '/infrastructure', label: 'Overview Dashboard', icon: LayoutDashboard },
  { to: '/infrastructure/assets', label: 'Asset Management', icon: Server },
  { to: '/infrastructure/maintenance', label: 'Maintenance Center', icon: CalendarClock },
  { to: '/infrastructure/tasks', label: 'Task Center', icon: ListTodo },
  { to: '/infrastructure/notifications', label: 'Notifications', icon: MailWarning },
];

export function MainLayout() {
  const user = useAuthStore(selectUser);
  const logout = useAuthStore((s) => s.logout);
  const { activeNotification, clearNotification } = useAlertStore();
  const { connected } = useWebSocket();

  useEffect(() => {
    if (!activeNotification) return;
    const t = setTimeout(clearNotification, 8000);
    return () => clearTimeout(t);
  }, [activeNotification, clearNotification]);

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 border-r border-slate-800 flex flex-col bg-slate-900/80">
        {/* Logo */}
        <div className="p-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-cyan-400 shrink-0" />
            <div>
              <p className="font-bold text-sm text-white leading-tight">Mini SOC Portal</p>
              <p className="text-[10px] text-slate-500 uppercase tracking-widest">Enterprise</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-4 overflow-y-auto">
          
          {/* Dashboard (Home) */}
          <div className="space-y-0.5">
            <NavLink
              to="/"
              end={true}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition ${
                  isActive
                    ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                }`
              }
            >
              <LayoutDashboard className="w-4 h-4 shrink-0" />
              Tổng quan
            </NavLink>
          </div>

          {/* Wazuh Section */}
          <div>
            <p className="px-3 mb-2 text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Threat Monitoring (Wazuh)</p>
            <div className="space-y-0.5">
              {wazuhNav.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition ${
                      isActive
                        ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
                        : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                    }`
                  }
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  {label}
                </NavLink>
              ))}
            </div>
          </div>

          {/* Zabbix Section */}
          <div>
            <p className="px-3 mb-2 text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Infrastructure (Zabbix)</p>
            <div className="space-y-0.5">
              {zabbixNav.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition ${
                      isActive
                        ? 'bg-indigo-500/15 text-indigo-300 border border-indigo-500/30'
                        : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                    }`
                  }
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  {label}
                </NavLink>
              ))}
            </div>
          </div>

        </nav>

        {/* User info */}
        <div className="p-3 border-t border-slate-800">
          <div className="flex items-center gap-2.5 px-2 py-2 mb-2">
            <div className="w-7 h-7 rounded-full bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center shrink-0">
              <User className="w-3.5 h-3.5 text-cyan-400" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium text-slate-200 truncate">{user?.full_name}</p>
              <p className="text-[10px] text-slate-500 truncate">{user?.roles?.[0] || 'User'}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => logout()}
            className="w-full flex items-center justify-center gap-2 py-1.5 text-xs border border-red-900/50 rounded-lg text-red-400 hover:bg-red-950/30 transition"
          >
            <LogOut className="w-3 h-3" />
            Đăng xuất
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar */}
        <header className="h-11 shrink-0 border-b border-slate-800 flex items-center justify-between px-5 text-xs bg-slate-900/40">
          <span className="text-slate-500">Giám sát an ninh thời gian thực · Wazuh</span>
          <span className={`flex items-center gap-1.5 ${connected ? 'text-emerald-400' : 'text-red-400'}`}>
            {connected
              ? <><Wifi className="w-3.5 h-3.5" /> Realtime</>
              : <><WifiOff className="w-3.5 h-3.5" /> Mất kết nối</>
            }
          </span>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>

      {/* Critical alert toast */}
      {activeNotification && (
        <div className="fixed bottom-5 right-5 w-80 p-4 rounded-xl border border-red-700 bg-slate-900 shadow-2xl z-50">
          <div className="flex items-start justify-between gap-2 mb-2">
            <SeverityBadge severity={activeNotification.severity} />
            <button
              type="button"
              onClick={clearNotification}
              className="text-slate-500 hover:text-white text-xs leading-none"
            >
              ✕
            </button>
          </div>
          <p className="font-semibold text-sm text-white leading-snug">
            {activeNotification.description}
          </p>
          <p className="text-xs text-slate-400 mt-1">{activeNotification.agent_name}</p>
        </div>
      )}
    </div>
  );
}
