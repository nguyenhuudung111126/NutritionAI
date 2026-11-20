import { useState } from 'react';
import {
  Eye,
  EyeOff,
  Loader2,
  Lock,
  LogIn,
  Stethoscope,
  UserRound,
} from 'lucide-react';
import { api, setAuthToken } from '../api';

const DEMO_ACCOUNTS = [
  { id: 'patient', label: 'Bệnh nhân', username: 'dung', password: '123456' },
  { id: 'admin', label: 'Quản trị', username: 'admin', password: 'admin123' },
];

export default function LoginPage({ onLoginSuccess }) {
  const [selectedDemo, setSelectedDemo] = useState(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSelectDemo = (acc) => {
    setSelectedDemo(acc.id);
    setUsername(acc.username);
    setPassword(acc.password);
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password) return;
    setLoading(true);
    setError('');
    try {
      const res = await api.login(username.trim(), password);
      setAuthToken(res.token);
      onLoginSuccess(res.user);
    } catch (err) {
      setError(err.message || 'Đăng nhập thất bại.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center px-3.5 py-6 sm:px-4 sm:py-10">
      <div className="w-full max-w-4xl overflow-hidden rounded-3xl border border-white/90 bg-white/88 shadow-2xl shadow-sky-900/10 backdrop-blur-2xl lg:grid lg:grid-cols-12">
        {/* Left Clinical Intro Panel */}
        <div
          className="relative flex flex-col justify-between overflow-hidden p-5 text-slate-900 sm:p-7 lg:col-span-5 lg:p-8"
          style={{
            backgroundColor: '#dff2fe',
            backgroundImage:
              'radial-gradient(circle at 15% 15%, rgba(56, 189, 248, 0.35), transparent 55%), radial-gradient(circle at 90% 85%, rgba(20, 184, 166, 0.32), transparent 55%)',
          }}
        >
          <div className="space-y-6">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500 to-teal-500 text-white shadow-md shadow-sky-500/25">
                <Stethoscope className="h-6 w-6" />
              </span>
              <div>
                <div className="text-lg font-extrabold tracking-tight text-slate-900">NutriGuard AI</div>
                <div className="text-xs font-semibold text-teal-800">Trạm Dinh dưỡng Lâm sàng</div>
              </div>
            </div>

            <div className="pt-4">
              <h1 className="text-2xl font-extrabold leading-snug text-slate-900">
                Hệ thống Dinh dưỡng Cá nhân hóa Theo Phác đồ Bộ Y tế
              </h1>
            </div>
          </div>

          <div className="mt-10 text-[11px] font-medium text-slate-600">
            Phác đồ QĐ 2879/QĐ-BYT • Dữ liệu Viện Dinh dưỡng Quốc gia
          </div>
        </div>

        {/* Right Login Form */}
        <div className="flex flex-col justify-center p-7 sm:p-9 lg:col-span-7">
          <div className="mb-5">
            <h2 className="text-xl font-extrabold text-slate-900">Đăng nhập hệ thống</h2>
            <p className="mt-1 text-xs text-slate-500">
              Chọn một tài khoản demo hoặc nhập thông tin.
            </p>

            {/* Demo role pills */}
            <div className="mt-3.5 flex flex-wrap items-center gap-2">
              {DEMO_ACCOUNTS.map((acc) => {
                const active = selectedDemo === acc.id;
                return (
                  <button
                    key={acc.id}
                    type="button"
                    disabled={loading}
                    onClick={() => handleSelectDemo(acc)}
                    className={`rounded-full border px-4 py-1.5 text-xs font-bold transition ${
                      active
                        ? 'border-teal-600 bg-teal-50 text-teal-800 shadow-2xs'
                        : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    {acc.label}
                  </button>
                );
              })}
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-bold text-slate-700">
                Tên đăng nhập hoặc Email
              </label>
              <div className="relative">
                <UserRound className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => {
                    setUsername(e.target.value);
                    setSelectedDemo(null);
                  }}
                  placeholder="VD: admin hoặc dung"
                  className="w-full rounded-xl border border-slate-200 bg-slate-50/60 py-2.5 pl-10 pr-4 text-sm text-slate-900 outline-none transition focus:border-sky-500 focus:bg-white focus:ring-2 focus:ring-sky-500/15"
                />
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-bold text-slate-700">Mật khẩu</label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  type={showPwd ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setSelectedDemo(null);
                  }}
                  placeholder="Nhập mật khẩu..."
                  className="w-full rounded-xl border border-slate-200 bg-slate-50/60 py-2.5 pl-10 pr-10 text-sm text-slate-900 outline-none transition focus:border-sky-500 focus:bg-white focus:ring-2 focus:ring-sky-500/15"
                />
                <button
                  type="button"
                  onClick={() => setShowPwd((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  aria-label="Hiện/ẩn mật khẩu"
                >
                  {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs font-medium text-rose-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-sky-500 to-teal-500 px-5 py-3 text-sm font-bold text-white shadow-md shadow-sky-500/25 transition hover:brightness-105 disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
              {loading ? 'Đang xác thực...' : 'Đăng nhập'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
