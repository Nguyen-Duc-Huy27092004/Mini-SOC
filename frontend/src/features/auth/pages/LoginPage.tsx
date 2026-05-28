import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield } from 'lucide-react';
import { useAuthStore } from '../store';

export function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const login = useAuthStore((s) => s.login);
  const error = useAuthStore((s) => s.error);
  const clearError = useAuthStore((s) => s.clearError);
  const loading = useAuthStore((s) => s.loading);
  const navigate = useNavigate();

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    clearError();
    try {
      const user = await login(email, password);
      navigate(user.must_change_password ? '/change-password' : '/', { replace: true });
    } catch {
      // error already set in store
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center mb-4">
            <Shield className="w-7 h-7 text-cyan-400" />
          </div>
          <h1 className="text-xl font-bold text-white">Mini SOC Portal</h1>
          <p className="text-sm text-slate-400 mt-1">Hệ thống giám sát an ninh</p>
        </div>

        {/* Form */}
        <form
          onSubmit={onSubmit}
          className="p-6 rounded-2xl border border-slate-700 bg-slate-900 shadow-xl space-y-4"
        >
          {error && (
            <div className="px-3 py-2.5 rounded-lg bg-red-950/50 border border-red-800/60 text-red-300 text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm text-slate-300 mb-1.5" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@soc.local"
              className="w-full px-3 py-2.5 rounded-lg bg-slate-800 border border-slate-700 focus:border-cyan-500 focus:outline-none text-sm text-white placeholder-slate-600 transition"
              required
              autoComplete="email"
              autoFocus
            />
          </div>

          <div>
            <label className="block text-sm text-slate-300 mb-1.5" htmlFor="password">
              Mật khẩu
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg bg-slate-800 border border-slate-700 focus:border-cyan-500 focus:outline-none text-sm text-white transition"
              required
              autoComplete="current-password"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-900 font-semibold text-sm transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Đang xác thực...' : 'Đăng nhập'}
          </button>
        </form>

        <p className="text-center text-xs text-slate-600 mt-6">
          Mini SOC Portal v2.0 · Enterprise Security
        </p>
      </div>
    </div>
  );
}
