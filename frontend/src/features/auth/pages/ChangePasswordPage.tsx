import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { KeyRound, ShieldAlert } from 'lucide-react';
import api from '../../../shared/api/client';
import { useAuthStore } from '../store';

export function ChangePasswordPage() {
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const setUser = useAuthStore((s) => s.setUser);
  const user = useAuthStore((s) => s.user);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (newPassword.length < 12) {
      setError('Mật khẩu mới phải có ít nhất 12 ký tự');
      return;
    }
    if (newPassword !== confirm) {
      setError('Mật khẩu xác nhận không khớp');
      return;
    }

    setLoading(true);
    try {
      await api.post('/auth/change-password', {
        old_password: oldPassword,
        new_password: newPassword,
      });
      // Update local user state
      if (user) setUser({ ...user, must_change_password: false });
      navigate('/', { replace: true });
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || 'Đổi mật khẩu thất bại';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 p-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md p-8 rounded-xl border border-slate-700 bg-slate-900 shadow-xl"
      >
        <div className="flex items-center gap-3 mb-2">
          <ShieldAlert className="w-7 h-7 text-cyan-400" />
          <h1 className="text-xl font-bold">Đổi mật khẩu</h1>
        </div>
        <p className="text-sm text-amber-400 mb-6 flex items-center gap-2">
          <KeyRound className="w-4 h-4 shrink-0" />
          Bạn cần đổi mật khẩu trước khi tiếp tục sử dụng hệ thống.
        </p>

        {error && (
          <div className="mb-4 px-3 py-2 rounded-lg bg-red-950/50 border border-red-800 text-red-300 text-sm">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-300 mb-1">Mật khẩu hiện tại</label>
            <input
              type="password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 focus:border-cyan-500 focus:outline-none text-sm"
              required
              autoComplete="current-password"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-300 mb-1">Mật khẩu mới</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 focus:border-cyan-500 focus:outline-none text-sm"
              required
              minLength={12}
              autoComplete="new-password"
            />
            <p className="text-xs text-slate-500 mt-1">Tối thiểu 12 ký tự</p>
          </div>
          <div>
            <label className="block text-sm text-slate-300 mb-1">Xác nhận mật khẩu mới</label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 focus:border-cyan-500 focus:outline-none text-sm"
              required
              autoComplete="new-password"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="mt-6 w-full py-2.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-900 font-semibold text-sm transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Đang xử lý...' : 'Xác nhận đổi mật khẩu'}
        </button>
      </form>
    </div>
  );
}
