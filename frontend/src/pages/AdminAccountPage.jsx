import { useState } from 'react';
import { KeyRound, ShieldCheck, UserCheck } from 'lucide-react';
import { api } from '../api';

export default function AdminAccountPage({ user }) {
  const [oldPwd, setOldPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMsg('');
    setErr('');
    try {
      const res = await api.changePassword(oldPwd, newPwd);
      setMsg(res.message || 'Đã cập nhật mật khẩu thành công.');
      setOldPwd('');
      setNewPwd('');
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <div className="inline-flex items-center gap-1.5 rounded-full bg-sky-100 px-3 py-0.5 text-[11px] font-bold text-sky-800">
          <ShieldCheck className="h-3.5 w-3.5" /> Hệ thống & Bảo mật
        </div>
        <h1 className="mt-1.5 text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
          Tài khoản Quản trị viên
        </h1>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-6 shadow-xs space-y-4">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500 to-teal-500 text-white shadow-sm">
              <UserCheck className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-base font-bold text-slate-900">{user?.display_name || user?.username}</h2>
              <p className="text-xs text-slate-500">@{user?.username} • {user?.email}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="rounded-xl border border-slate-200/70 bg-slate-50/70 p-3">
              <div className="text-[10px] font-bold uppercase text-slate-400">Vai trò</div>
              <div className="mt-1 font-extrabold text-sky-700">QUẢN TRỊ VIÊN (ADMIN)</div>
            </div>
            <div className="rounded-xl border border-slate-200/70 bg-slate-50/70 p-3">
              <div className="text-[10px] font-bold uppercase text-slate-400">Trạng thái</div>
              <div className="mt-1 font-extrabold text-emerald-700">Đang hoạt động</div>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="rounded-2xl border border-slate-200/80 bg-white/95 p-6 shadow-xs space-y-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-teal-50 text-teal-600">
              <KeyRound className="h-4 w-4" />
            </span>
            <div>
              <h2 className="text-base font-bold text-slate-900">Đổi mật khẩu Admin</h2>
              <p className="text-xs text-slate-500">Bảo vệ quyền truy cập hệ thống quản trị</p>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">Mật khẩu hiện tại</label>
            <input
              type="password"
              required
              value={oldPwd}
              onChange={(e) => setOldPwd(e.target.value)}
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">Mật khẩu mới (tối thiểu 4 ký tự)</label>
            <input
              type="password"
              required
              minLength={4}
              value={newPwd}
              onChange={(e) => setNewPwd(e.target.value)}
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500"
            />
          </div>

          {err && <div className="rounded-xl bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700">{err}</div>}
          {msg && <div className="rounded-xl bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-900">{msg}</div>}

          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-500 to-teal-500 px-5 py-2.5 text-xs font-bold text-white shadow-sm hover:brightness-105 disabled:opacity-50"
          >
            <KeyRound className="h-4 w-4" />
            {saving ? 'Đang cập nhật...' : 'Cập nhật mật khẩu'}
          </button>
        </form>
      </div>
    </div>
  );
}
