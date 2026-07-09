export function PlaybooksPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white tracking-tight">Quản lý Playbooks</h1>
        <button className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg text-sm font-medium transition">
          + Tạo Playbook
        </button>
      </div>
      <div className="p-8 text-center border border-dashed border-slate-700 rounded-xl bg-slate-900/30">
        <p className="text-slate-400">Chưa có playbook nào. Hãy tạo mới để tự động hóa xử lý sự cố.</p>
      </div>
    </div>
  );
}
