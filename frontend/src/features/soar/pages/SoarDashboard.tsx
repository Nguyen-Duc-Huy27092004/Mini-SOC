export function SoarDashboard() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white tracking-tight">Tổng quan SOAR</h1>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/50">
          <p className="text-sm text-slate-400">Tổng số Playbooks</p>
          <p className="text-2xl font-semibold text-white mt-1">12</p>
        </div>
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/50">
          <p className="text-sm text-slate-400">Playbooks Kích hoạt (24h)</p>
          <p className="text-2xl font-semibold text-cyan-400 mt-1">142</p>
        </div>
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/50">
          <p className="text-sm text-slate-400">Chờ phê duyệt</p>
          <p className="text-2xl font-semibold text-amber-400 mt-1">3</p>
        </div>
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/50">
          <p className="text-sm text-slate-400">Hành động Thất bại (24h)</p>
          <p className="text-2xl font-semibold text-red-400 mt-1">1</p>
        </div>
      </div>
    </div>
  );
}
