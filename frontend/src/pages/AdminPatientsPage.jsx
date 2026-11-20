import { useEffect, useMemo, useState } from 'react';
import {
  Loader2,
  Lock,
  Pencil,
  Plus,
  Search,
  Trash2,
  Unlock,
  Users,
  X,
} from 'lucide-react';
import { api } from '../api';

export default function AdminPatientsPage({ currentUser, onPatientsChanged }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [feedback, setFeedback] = useState('');
  const [errMsg, setErrMsg] = useState('');
  const [busyId, setBusyId] = useState(null);

  // Modal: Thêm mới tài khoản
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newUsername, setNewUsername] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newRole, setNewRole] = useState('PATIENT');
  const [newPassword, setNewPassword] = useState('');
  const [creating, setCreating] = useState(false);

  // Modal: Sửa tài khoản
  const [editTarget, setEditTarget] = useState(null);
  const [editName, setEditName] = useState('');
  const [editEmail, setEditEmail] = useState('');
  const [editRole, setEditRole] = useState('PATIENT');
  const [editPassword, setEditPassword] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const list = await api.adminGetUsers();
      setUsers(Array.isArray(list) ? list : []);
    } catch (err) {
      setErrMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const filteredUsers = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return users;
    return users.filter((u) => {
      const text = [u.display_name, u.username, u.email, u.role]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return text.includes(q);
    });
  }, [users, search]);

  const handleToggleLock = async (u) => {
    setBusyId(u.id);
    setErrMsg('');
    setFeedback('');
    try {
      await api.adminUpdateUser(u.id, { is_active: !u.is_active });
      setFeedback(
        !u.is_active
          ? `Đã mở khóa tài khoản "${u.display_name || u.username}".`
          : `Đã khóa tài khoản "${u.display_name || u.username}".`
      );
      await loadUsers();
    } catch (err) {
      setErrMsg(err.message);
    } finally {
      setBusyId(null);
    }
  };

  const openEditModal = (u) => {
    setEditTarget(u);
    setEditName(u.display_name || '');
    setEditEmail(u.email || '');
    setEditRole((u.role || 'PATIENT').toUpperCase());
    setEditPassword('');
    setConfirmDelete(false);
  };

  const handleSaveEdit = async (e) => {
    e.preventDefault();
    if (!editTarget) return;
    setSavingEdit(true);
    setErrMsg('');
    setFeedback('');
    try {
      const payload = {
        display_name: editName.trim(),
        email: editEmail.trim(),
        role: editRole,
      };
      if (editPassword.trim()) {
        payload.password = editPassword.trim();
      }
      await api.adminUpdateUser(editTarget.id, payload);
      setFeedback(`Đã cập nhật tài khoản "${editName.trim()}".`);
      setEditTarget(null);
      await loadUsers();
      onPatientsChanged?.();
    } catch (err) {
      setErrMsg(err.message);
    } finally {
      setSavingEdit(false);
    }
  };

  const handleDeleteUser = async () => {
    if (!editTarget) return;
    setSavingEdit(true);
    setErrMsg('');
    setFeedback('');
    try {
      await api.adminDeleteUser(editTarget.id);
      setFeedback(`Đã xóa tài khoản "${editTarget.display_name || editTarget.username}".`);
      setEditTarget(null);
      await loadUsers();
      onPatientsChanged?.();
    } catch (err) {
      setErrMsg(err.message);
    } finally {
      setSavingEdit(false);
    }
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setCreating(true);
    setErrMsg('');
    setFeedback('');
    try {
      await api.adminCreateUser({
        display_name: newName.trim(),
        username: newUsername.trim().toLowerCase(),
        email: newEmail.trim() || undefined,
        role: newRole,
        password: newPassword.trim(),
      });
      setFeedback(`Đã thêm tài khoản mới "${newName.trim()}".`);
      setShowCreate(false);
      setNewName('');
      setNewUsername('');
      setNewEmail('');
      setNewRole('PATIENT');
      setNewPassword('');
      await loadUsers();
      onPatientsChanged?.();
    } catch (err) {
      setErrMsg(err.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-teal-100 px-3 py-0.5 text-[11px] font-bold text-teal-800">
            <Users className="h-3.5 w-3.5" /> Phân quyền & Tài khoản
          </div>
          <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
            Quản lý Tài khoản
          </h1>
          <p className="mt-0.5 text-xs text-slate-600">
            Quản trị danh sách tài khoản truy cập, phân quyền vai trò và trạng thái hoạt động.
          </p>
        </div>
      </div>

      {errMsg && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-xs font-medium text-rose-800">
          {errMsg}
        </div>
      )}
      {feedback && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-xs font-medium text-emerald-800">
          {feedback}
        </div>
      )}

      {/* Main Card matching clean screenshot layout */}
      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-4">
          <div className="flex items-center gap-2.5">
            <h2 className="text-base font-extrabold text-slate-900">Danh sách Tài khoản</h2>
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-bold text-slate-600">
              {filteredUsers.length}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Tìm kiếm..."
                className="w-48 rounded-xl border border-slate-200 bg-slate-50/60 py-1.5 pl-8 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-teal-400 focus:bg-white focus:outline-none sm:w-56"
              />
            </div>

            <button
              type="button"
              onClick={() => setShowCreate(true)}
              className="inline-flex items-center gap-1.5 rounded-xl bg-teal-800 px-4 py-2 text-xs font-bold text-white shadow-xs transition hover:bg-teal-900"
            >
              <Plus className="h-3.5 w-3.5" /> Thêm mới
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 py-12 text-xs text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin text-teal-600" /> Đang tải danh sách tài khoản...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-[11px] font-semibold text-slate-400">
                  <th className="py-3 pr-3">Họ và tên</th>
                  <th className="py-3 px-3">Địa chỉ Email</th>
                  <th className="py-3 px-3">Vai trò</th>
                  <th className="py-3 px-3">Trạng thái</th>
                  <th className="py-3 pl-3 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredUsers.map((u) => {
                  const isSelf = currentUser?.id === u.id;
                  const isBusy = busyId === u.id;
                  const roleLabel = (u.role || 'PATIENT').toLowerCase();
                  return (
                    <tr key={u.id} className="hover:bg-slate-50/70">
                      <td className="py-3.5 pr-3">
                        <div className="font-semibold text-slate-900">
                          {u.display_name || u.username}
                          {isSelf && (
                            <span className="ml-1.5 rounded bg-sky-100 px-1.5 py-0.5 text-[10px] font-bold text-sky-700">
                              Bạn
                            </span>
                          )}
                        </div>
                        <div className="font-mono text-[11px] text-slate-400">@{u.username}</div>
                      </td>
                      <td className="py-3.5 px-3 text-slate-600">{u.email || '—'}</td>
                      <td className="py-3.5 px-3">
                        <span
                          className={`inline-block rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
                            roleLabel === 'admin'
                              ? 'bg-indigo-50 text-indigo-700'
                              : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {roleLabel}
                        </span>
                      </td>
                      <td className="py-3.5 px-3">
                        <span
                          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
                            u.is_active
                              ? 'bg-emerald-50 text-emerald-700'
                              : 'bg-rose-50 text-rose-700'
                          }`}
                        >
                          {u.is_active ? 'Hoạt động' : 'Đã khóa'}
                        </span>
                      </td>
                      <td className="py-3.5 pl-3 text-right">
                        <div className="inline-flex items-center gap-1.5">
                          <button
                            type="button"
                            disabled={isSelf || isBusy}
                            onClick={() => handleToggleLock(u)}
                            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            {u.is_active ? (
                              <>
                                <Lock className="h-3 w-3 text-slate-400" /> Khóa
                              </>
                            ) : (
                              <>
                                <Unlock className="h-3 w-3 text-emerald-600" /> Mở khóa
                              </>
                            )}
                          </button>
                          <button
                            type="button"
                            onClick={() => openEditModal(u)}
                            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-700 transition hover:bg-slate-50"
                          >
                            <Pencil className="h-3 w-3 text-slate-400" /> Sửa
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {filteredUsers.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-xs text-slate-400">
                      Không tìm thấy tài khoản nào phù hợp.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Modal: Thêm mới tài khoản */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-5 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-extrabold text-slate-900">Thêm mới tài khoản</h3>
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleCreateUser} className="mt-4 space-y-3.5 text-xs">
              <div>
                <label className="mb-1 block font-bold text-slate-700">Họ và tên *</label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="Ví dụ: Nguyễn Văn An"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs focus:border-teal-500 focus:outline-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block font-bold text-slate-700">Tên đăng nhập *</label>
                  <input
                    type="text"
                    required
                    minLength={2}
                    value={newUsername}
                    onChange={(e) => setNewUsername(e.target.value)}
                    placeholder="vd: benhnhan2"
                    className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs focus:border-teal-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="mb-1 block font-bold text-slate-700">Vai trò *</label>
                  <select
                    value={newRole}
                    onChange={(e) => setNewRole(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs focus:border-teal-500 focus:outline-none"
                  >
                    <option value="PATIENT">patient</option>
                    <option value="ADMIN">admin</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="mb-1 block font-bold text-slate-700">Địa chỉ Email</label>
                <input
                  type="email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  placeholder="Tự động tạo nếu để trống"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs focus:border-teal-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block font-bold text-slate-700">Mật khẩu *</label>
                <input
                  type="password"
                  required
                  minLength={4}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Tối thiểu 4 ký tự"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs focus:border-teal-500 focus:outline-none"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="rounded-xl border border-slate-200 px-4 py-2 font-bold text-slate-600 hover:bg-slate-50"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-teal-800 px-4 py-2 font-bold text-white hover:bg-teal-900 disabled:opacity-50"
                >
                  {creating && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  Tạo tài khoản
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Sửa tài khoản */}
      {editTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-5 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-extrabold text-slate-900">
                Chỉnh sửa tài khoản (@{editTarget.username})
              </h3>
              <button
                type="button"
                onClick={() => setEditTarget(null)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleSaveEdit} className="mt-4 space-y-3.5 text-xs">
              <div>
                <label className="mb-1 block font-bold text-slate-700">Họ và tên *</label>
                <input
                  type="text"
                  required
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs focus:border-teal-500 focus:outline-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block font-bold text-slate-700">Địa chỉ Email</label>
                  <input
                    type="email"
                    value={editEmail}
                    onChange={(e) => setEditEmail(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs focus:border-teal-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="mb-1 block font-bold text-slate-700">Vai trò</label>
                  <select
                    value={editRole}
                    disabled={currentUser?.id === editTarget.id}
                    onChange={(e) => setEditRole(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs focus:border-teal-500 focus:outline-none disabled:bg-slate-100"
                  >
                    <option value="PATIENT">patient</option>
                    <option value="ADMIN">admin</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="mb-1 block font-bold text-slate-700">Đặt mật khẩu mới (tùy chọn)</label>
                <input
                  type="password"
                  value={editPassword}
                  onChange={(e) => setEditPassword(e.target.value)}
                  placeholder="Để trống nếu giữ nguyên mật khẩu cũ"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs focus:border-teal-500 focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-between pt-2">
                {currentUser?.id !== editTarget.id ? (
                  confirmDelete ? (
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        disabled={savingEdit}
                        onClick={handleDeleteUser}
                        className="rounded-lg bg-rose-600 px-3 py-1.5 font-bold text-white hover:bg-rose-700"
                      >
                        Xác nhận xóa
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmDelete(false)}
                        className="rounded-lg border border-slate-200 px-2.5 py-1.5 font-semibold text-slate-600"
                      >
                        Thôi
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setConfirmDelete(true)}
                      className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 font-semibold text-rose-600 hover:bg-rose-50"
                    >
                      <Trash2 className="h-3.5 w-3.5" /> Xóa tài khoản
                    </button>
                  )
                ) : (
                  <span />
                )}

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setEditTarget(null)}
                    className="rounded-xl border border-slate-200 px-4 py-2 font-bold text-slate-600 hover:bg-slate-50"
                  >
                    Hủy
                  </button>
                  <button
                    type="submit"
                    disabled={savingEdit}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-teal-800 px-4 py-2 font-bold text-white hover:bg-teal-900 disabled:opacity-50"
                  >
                    {savingEdit && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                    Lưu thay đổi
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
