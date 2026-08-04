import { useState, useEffect } from 'react';
import { Workflow, RefreshCw, Shield } from 'lucide-react';
import api from '../../../shared/api/client';

interface PlaybookRule {
  id: string;
  field: string;
  operator: string;
  value: string;
}

interface Playbook {
  id: string;
  name: string;
  is_active: boolean;
  execution_mode: string;
  rules: PlaybookRule[];
}

const operatorLabel: Record<string, string> = {
  equals: '=',
  not_equals: '≠',
  contains: 'chứa',
  not_contains: 'không chứa',
  greater_than: '>',
  less_than: '<',
  starts_with: 'bắt đầu bằng',
  regex: '~regex',
};

export function RulesPage() {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchRules = async () => {
    try {
      setLoading(true);
      const { data } = await api.get('/soar/playbooks');
      setPlaybooks(data);
    } catch (err) {
      console.warn('Rules fetch failed:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchRules(); }, []);

  const allRules = playbooks.flatMap(pb =>
    (pb.rules || []).map(r => ({ ...r, playbook_name: pb.name, playbook_active: pb.is_active }))
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <Workflow className="w-7 h-7 text-purple-400" />
            <h1 className="text-2xl font-bold text-white tracking-tight">Cấu hình Rules</h1>
          </div>
          <p className="text-slate-400 text-sm mt-1">
            Các điều kiện kích hoạt Playbook tự động — tổng hợp từ tất cả playbooks
          </p>
        </div>
        <button
          onClick={fetchRules}
          className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm rounded-lg border border-slate-700 transition"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Làm mới
        </button>
      </div>

      {loading ? (
        <div className="p-10 text-center text-slate-500 border border-dashed border-slate-700 rounded-xl">
          Đang tải danh sách rules...
        </div>
      ) : allRules.length === 0 ? (
        <div className="p-10 text-center border border-dashed border-slate-700 rounded-xl bg-slate-900/30">
          <Shield className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400 font-medium">Chưa có rule nào được cấu hình.</p>
          <p className="text-slate-500 text-sm mt-1">
            Rules được tạo trong từng Playbook. Truy cập trang{' '}
            <span className="text-cyan-400">Quản lý Playbooks</span> để thêm điều kiện kích hoạt.
          </p>
        </div>
      ) : (
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-slate-800 flex items-center justify-between">
            <h2 className="font-semibold text-white text-sm">
              Tất cả điều kiện kích hoạt ({allRules.length} rules)
            </h2>
            <span className="text-xs text-slate-400 bg-slate-800 px-3 py-1 rounded-full border border-slate-700">
              {playbooks.length} playbooks
            </span>
          </div>
          <table className="w-full text-sm text-slate-300">
            <thead className="bg-slate-950/60 text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="px-5 py-3 text-left">Playbook</th>
                <th className="px-5 py-3 text-left">Trường dữ liệu</th>
                <th className="px-5 py-3 text-left">Toán tử</th>
                <th className="px-5 py-3 text-left">Giá trị so sánh</th>
                <th className="px-5 py-3 text-left">Trạng thái PB</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {allRules.map(rule => (
                <tr key={rule.id} className="hover:bg-slate-800/30 transition">
                  <td className="px-5 py-3">
                    <span className="text-white font-medium text-xs">{rule.playbook_name}</span>
                  </td>
                  <td className="px-5 py-3 font-mono text-cyan-300 text-xs">{rule.field}</td>
                  <td className="px-5 py-3">
                    <span className="text-xs px-2 py-0.5 bg-purple-500/10 text-purple-300 border border-purple-500/20 rounded font-medium">
                      {operatorLabel[rule.operator] || rule.operator}
                    </span>
                  </td>
                  <td className="px-5 py-3 font-mono text-amber-300 text-xs">"{rule.value}"</td>
                  <td className="px-5 py-3">
                    <span className={`text-xs px-2.5 py-0.5 rounded-full border font-medium ${
                      rule.playbook_active
                        ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
                        : 'text-slate-500 bg-slate-800 border-slate-700'
                    }`}>
                      {rule.playbook_active ? 'Đang dùng' : 'Tắt'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
