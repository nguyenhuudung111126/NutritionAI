import { useEffect, useState } from 'react';
import { Check, FileText, KeyRound, Loader2, Plus, Save, Upload, UserPlus, UserRound, X } from 'lucide-react';
import { api } from '../api';

const MAIN_DISEASE_OPTIONS = [
  { code: 'DTD', label: 'Đái tháo đường' },
  { code: 'CKD', label: 'Suy thận mạn' },
  { code: 'AKI', label: 'Suy thận cấp' },
  { code: 'GN_ACUTE', label: 'Viêm cầu thận cấp' },
  { code: 'GN_CHRONIC', label: 'Viêm cầu thận mạn' },
  { code: 'NEPHROTIC', label: 'Hội chứng thận hư' },
];

const COMORBIDITY_OPTIONS = [
  { code: 'HTN', label: 'Cao huyết áp' },
  { code: 'DYSLIPIDEMIA', label: 'RL mỡ máu' },
  { code: 'HEART_FAILURE', label: 'Suy tim (độ 3–4)' },
];

const DISEASE_OPTIONS = [...MAIN_DISEASE_OPTIONS, ...COMORBIDITY_OPTIONS];

export default function ProfilePage({ overview, isAdmin = false, onCreatedPatient, onUpdatedPatient }) {
  const profile = overview?.profile;
  const [editNickname, setEditNickname] = useState('');
  const [editGender, setEditGender] = useState('Nam');
  const [editBirthYear, setEditBirthYear] = useState('');
  const [editWeight, setEditWeight] = useState('');
  const [editHeight, setEditHeight] = useState('');
  const [editDiseases, setEditDiseases] = useState([]);
  const [editStage, setEditStage] = useState('Không');
  const [editDialysis, setEditDialysis] = useState(0);
  const [editAllergies, setEditAllergies] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);
  const [editMsg, setEditMsg] = useState('');

  // Create new patient form
  const [nickname, setNickname] = useState('');
  const [gender, setGender] = useState('Nam');
  const [birthYear, setBirthYear] = useState(1968);
  const [heightCm, setHeightCm] = useState(168);
  const [weightKg, setWeightKg] = useState(65);
  const [diseases, setDiseases] = useState(['DTD', 'CKD']);
  const [ckdStage, setCkdStage] = useState('2');
  const [allergiesTxt, setAllergiesTxt] = useState('');
  const [creating, setCreating] = useState(false);
  const [createMsg, setCreateMsg] = useState('');

  // Upload lab report / medical record
  const [labFiles, setLabFiles] = useState([]);
  const [labDate, setLabDate] = useState('');
  const [uploadingLab, setUploadingLab] = useState(false);
  const [labMsg, setLabMsg] = useState('');
  const [labErr, setLabErr] = useState('');

  // Change password (for Patient self-service)
  const [oldPwd, setOldPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [savingPwd, setSavingPwd] = useState(false);
  const [pwdMsg, setPwdMsg] = useState('');
  const [pwdErr, setPwdErr] = useState('');

  useEffect(() => {
    if (!profile) return;
    setEditNickname(profile.nickname || '');
    setEditGender(profile.gender || 'Nam');
    setEditBirthYear(
      profile.birth_year || (profile.age ? new Date().getFullYear() - Number(profile.age) : 1990)
    );
    setEditWeight(profile.weight_kg || 65);
    setEditHeight(profile.height_cm || 165);
    setEditDiseases(profile.conditions || []);
    setEditStage(profile.ckd_stage || 'Không');
    setEditDialysis(Number(profile.dialysis_per_week || 0));
    setEditAllergies((profile.food_allergies || []).join(', '));
  }, [profile]);

  const toggleDisease = (list, setList, code) => {
    setList(list.includes(code) ? list.filter((c) => c !== code) : [...list, code]);
  };

  const handleSaveEdit = async (e) => {
    e.preventDefault();
    if (!profile) return;
    setSavingEdit(true);
    setEditMsg('');
    try {
      const res = await api.updatePatient(profile.id, {
        nickname: editNickname.trim() || undefined,
        gender: editGender,
        birth_year: editBirthYear ? Number(editBirthYear) : undefined,
        weight_kg: Number(editWeight),
        height_cm: Number(editHeight),
        diseases: editDiseases,
        ckd_stage: editStage,
        dialysis_per_week: editDiseases.includes('CKD') || editDiseases.includes('AKI') ? Number(editDialysis) : 0,
        food_allergies: editAllergies.split(',').map((s) => s.trim()).filter(Boolean),
      });
      setEditMsg(`Đã cập nhật hồ sơ & tính lại phác đồ: ${res.target.regime_code}`);
      onUpdatedPatient();
    } catch (err) {
      setEditMsg(`Lỗi: ${err.message}`);
    } finally {
      setSavingEdit(false);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!nickname.trim()) return;
    setCreating(true);
    setCreateMsg('');
    try {
      const res = await api.createPatient({
        nickname: nickname.trim(),
        gender,
        birth_year: Number(birthYear),
        height_cm: Number(heightCm),
        weight_kg: Number(weightKg),
        diseases,
        ckd_stage: ckdStage,
        food_allergies: allergiesTxt.split(',').map((s) => s.trim()).filter(Boolean),
      });
      setNickname('');
      setAllergiesTxt('');
      setCreateMsg(`Đã tạo hồ sơ mới (Phác đồ: ${res.target.regime_code})`);
      onCreatedPatient(res.id);
    } catch (err) {
      setCreateMsg(`Lỗi: ${err.message}`);
    } finally {
      setCreating(false);
    }
  };

  const handlePickLabFiles = (e) => {
    const picked = Array.from(e.target.files || []);
    if (!picked.length) return;
    setLabFiles((prev) => {
      const seen = new Set(prev.map((f) => `${f.name}:${f.size}`));
      const next = [...prev];
      for (const f of picked) {
        const k = `${f.name}:${f.size}`;
        if (!seen.has(k)) {
          seen.add(k);
          next.push(f);
        }
      }
      return next;
    });
    e.target.value = '';
  };

  const removeLabFile = (idx) => {
    setLabFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleUploadLab = async (e) => {
    e.preventDefault();
    if (!labFiles.length || !profile) return;
    setUploadingLab(true);
    setLabErr('');
    setLabMsg('');
    try {
      const res = await api.uploadCheckup(profile.id, labFiles, labDate);
      const labsTxt = (res.matched_labs || []).join(', ') || 'Đã lưu thông tin khám';
      const prefix = res.merged ? 'Đã gộp bổ sung vào đợt khám' : 'Đã tạo đợt khám mới';
      setLabMsg(
        `${prefix} #${res.checkup_id} (đã đọc ${labFiles.length} tệp) • Chỉ số đọc được: ${labsTxt} • Phác đồ hiện tại: ${res.new_target?.regime_code}`
      );
      setLabFiles([]);
      setLabDate('');
      onUpdatedPatient();
    } catch (err) {
      setLabErr(err.message);
    } finally {
      setUploadingLab(false);
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    setSavingPwd(true);
    setPwdMsg('');
    setPwdErr('');
    try {
      const res = await api.changePassword(oldPwd, newPwd);
      setPwdMsg(res.message || 'Đã đổi mật khẩu thành công.');
      setOldPwd('');
      setNewPwd('');
    } catch (err) {
      setPwdErr(err.message);
    } finally {
      setSavingPwd(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
          {isAdmin ? 'Hồ sơ Bệnh nhân & Bệnh án' : 'Hồ sơ & Bệnh án của tôi'}
        </h1>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Edit current patient */}
        <form onSubmit={handleSaveEdit} className="rounded-xl border border-slate-200/80 bg-white/95 p-6 shadow-xs space-y-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-50 text-sky-600">
              <UserRound className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-base font-bold text-slate-900">
                {isAdmin ? 'Chỉnh sửa hồ sơ đang chọn' : 'Cập nhật thông tin & bệnh lý'}
              </h2>
              <p className="text-xs text-slate-500">{profile?.nickname} • {profile?.age} tuổi • {profile?.gender}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="sm:col-span-1">
              <label className="mb-1 block text-xs font-semibold text-slate-700">Tên hiển thị</label>
              <input
                type="text"
                required
                value={editNickname}
                onChange={(e) => setEditNickname(e.target.value)}
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">Năm sinh</label>
              <input
                type="number"
                min="1910"
                max="2026"
                value={editBirthYear}
                onChange={(e) => setEditBirthYear(e.target.value)}
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">Giới tính</label>
              <select
                value={editGender}
                onChange={(e) => setEditGender(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-sky-500"
              >
                <option value="Nam">Nam</option>
                <option value="Nữ">Nữ</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">Chiều cao (cm)</label>
              <input
                type="number"
                step="0.5"
                value={editHeight}
                onChange={(e) => setEditHeight(e.target.value)}
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">Cân nặng mới nhất (kg)</label>
              <input
                type="number"
                step="0.5"
                value={editWeight}
                onChange={(e) => setEditWeight(e.target.value)}
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500"
              />
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                Bệnh lý chính (theo Phác đồ Bộ Y tế)
              </label>
              <div className="flex flex-wrap gap-2">
                {MAIN_DISEASE_OPTIONS.map((d) => {
                  const active = editDiseases.includes(d.code);
                  return (
                    <button
                      type="button"
                      key={d.code}
                      onClick={() => toggleDisease(editDiseases, setEditDiseases, d.code)}
                      className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold transition ${
                        active
                          ? 'bg-sky-600 text-white shadow-2xs'
                          : 'border border-slate-200 bg-slate-50 text-slate-700 hover:border-sky-200 hover:bg-sky-50'
                      }`}
                    >
                      {active && <Check className="h-3 w-3" />} {d.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-slate-500">
                Yếu tố kèm theo (nếu có)
              </label>
              <div className="flex flex-wrap gap-2">
                {COMORBIDITY_OPTIONS.map((d) => {
                  const active = editDiseases.includes(d.code);
                  return (
                    <button
                      type="button"
                      key={d.code}
                      onClick={() => toggleDisease(editDiseases, setEditDiseases, d.code)}
                      className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold transition ${
                        active
                          ? 'bg-teal-600 text-white shadow-2xs'
                          : 'border border-slate-200 bg-white text-slate-600 hover:border-teal-200 hover:bg-teal-50'
                      }`}
                    >
                      {active && <Check className="h-3 w-3" />} {d.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {(editDiseases.includes('CKD') || editDiseases.includes('AKI')) && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {editDiseases.includes('CKD') && (
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Giai đoạn suy thận (CKD)</label>
                  <select
                    value={editStage}
                    onChange={(e) => setEditStage(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500"
                  >
                    {['Không', '1', '2', '3a', '3b', '4', '5'].map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Lọc máu định kỳ</label>
                <select
                  value={editDialysis}
                  onChange={(e) => setEditDialysis(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500"
                >
                  <option value={0}>Chưa lọc máu (0 lần/tuần)</option>
                  <option value={1}>Lọc máu 1 lần/tuần</option>
                  <option value={2}>Lọc máu 2 lần/tuần</option>
                  <option value={3}>Lọc máu 3 lần/tuần</option>
                </select>
              </div>
            </div>
          )}

          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">
              Dị ứng thực phẩm (cách nhau bởi dấu phẩy)
            </label>
            <input
              type="text"
              value={editAllergies}
              onChange={(e) => setEditAllergies(e.target.value)}
              placeholder="VD: tôm, hải sản, lạc"
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500"
            />
          </div>

          {editMsg && <div className="rounded-xl bg-sky-50 px-3 py-2 text-xs font-medium text-sky-900">{editMsg}</div>}

          <button
            type="submit"
            disabled={savingEdit}
            className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-sky-500 to-teal-500 px-5 py-2.5 text-xs font-bold text-white shadow-md shadow-sky-500/20 transition hover:brightness-105 disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            {savingEdit ? 'Đang cập nhật...' : 'Lưu thay đổi & Tính lại phác đồ'}
          </button>
        </form>

        {/* Right Card: Admin creates patient OR Patient changes password */}
        {isAdmin ? (
          <form onSubmit={handleCreate} className="rounded-xl border border-slate-200/80 bg-white/95 p-6 shadow-xs space-y-4">
            <div className="flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-teal-50 text-teal-600">
                <UserPlus className="h-5 w-5" />
              </span>
              <div>
                <h2 className="text-base font-bold text-slate-900">Tạo hồ sơ bệnh nhân mới</h2>
                <p className="text-xs text-slate-500">Thêm hồ sơ mới để theo dõi đa dạng bệnh lý & dị ứng</p>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <label className="mb-1 block text-xs font-semibold text-slate-700">Tên gọi / Biệt danh</label>
                <input
                  type="text"
                  required
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value)}
                  placeholder="VD: Cô Lan"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Giới tính</label>
                <select
                  value={gender}
                  onChange={(e) => setGender(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500"
                >
                  <option value="Nam">Nam</option>
                  <option value="Nữ">Nữ</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Năm sinh</label>
                <input
                  type="number"
                  value={birthYear}
                  onChange={(e) => setBirthYear(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Chiều cao (cm)</label>
                <input
                  type="number"
                  value={heightCm}
                  onChange={(e) => setHeightCm(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Cân nặng (kg)</label>
                <input
                  type="number"
                  value={weightKg}
                  onChange={(e) => setWeightKg(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500"
                />
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-slate-700">Bệnh lý</label>
              <div className="flex flex-wrap gap-2">
                {DISEASE_OPTIONS.map((d) => {
                  const active = diseases.includes(d.code);
                  return (
                    <button
                      type="button"
                      key={d.code}
                      onClick={() => toggleDisease(diseases, setDiseases, d.code)}
                      className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold transition ${
                        active ? 'bg-teal-600 text-white shadow-2xs' : 'border border-slate-200 bg-slate-50 text-slate-700 hover:bg-teal-50 hover:border-teal-200'
                      }`}
                    >
                      {active && <Check className="h-3 w-3" />} {d.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {diseases.includes('CKD') && (
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Giai đoạn suy thận</label>
                <select
                  value={ckdStage}
                  onChange={(e) => setCkdStage(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500"
                >
                  {['Không', '1', '2', '3a', '3b', '4', '5'].map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">Dị ứng thực phẩm</label>
              <input
                type="text"
                value={allergiesTxt}
                onChange={(e) => setAllergiesTxt(e.target.value)}
                placeholder="VD: hải sản, trứng, lạc"
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500"
              />
            </div>

            {createMsg && <div className="rounded-xl bg-teal-50 px-3 py-2 text-xs font-medium text-teal-800">{createMsg}</div>}

            <button
              type="submit"
              disabled={creating}
              className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-5 py-2.5 text-xs font-bold text-white shadow-md shadow-teal-500/20 transition hover:bg-teal-500 disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
              {creating ? 'Đang lưu hồ sơ...' : 'Tạo hồ sơ mới'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleChangePassword} className="rounded-xl border border-slate-200/80 bg-white/95 p-6 shadow-xs space-y-4 flex flex-col justify-between">
            <div className="space-y-4">
              <div className="flex items-center gap-2.5">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-teal-50 text-teal-600">
                  <KeyRound className="h-5 w-5" />
                </span>
                <div>
                  <h2 className="text-base font-bold text-slate-900">Bảo mật Tài khoản</h2>
                  <p className="text-xs text-slate-500">Đổi mật khẩu đăng nhập cổng Bệnh nhân của bạn</p>
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

              {pwdErr && <div className="rounded-xl bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700">{pwdErr}</div>}
              {pwdMsg && <div className="rounded-xl bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-900">{pwdMsg}</div>}
            </div>

            <button
              type="submit"
              disabled={savingPwd}
              className="inline-flex w-fit items-center gap-2 rounded-lg bg-teal-600 px-5 py-2.5 text-xs font-bold text-white shadow-md shadow-teal-500/20 transition hover:bg-teal-500 disabled:opacity-50"
            >
              <KeyRound className="h-4 w-4" />
              {savingPwd ? 'Đang cập nhật...' : 'Đổi mật khẩu'}
            </button>
          </form>
        )}
      </div>

      {/* Upload Medical Record / Lab Report directly inside Profile */}
      {profile && (
        <form onSubmit={handleUploadLab} className="rounded-xl border border-slate-200/80 bg-white/95 p-6 shadow-xs space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-50 text-sky-600">
                <FileText className="h-5 w-5" />
              </span>
              <div>
                <h2 className="text-base font-bold text-slate-900">Nạp phiếu xét nghiệm / Bệnh án</h2>
                <p className="text-xs text-slate-500">
                  Cập nhật trực tiếp vào hồ sơ <strong className="text-slate-700">{profile.nickname}</strong> và tự động tính lại phác đồ điều trị
                </p>
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3 items-end">
            <label className="md:col-span-2 flex cursor-pointer items-center gap-3 rounded-xl border-2 border-dashed border-sky-200 bg-sky-50/40 px-4 py-3.5 transition hover:border-sky-400 hover:bg-sky-50/80">
              <Upload className="h-6 w-6 shrink-0 text-sky-600" />
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-slate-800">
                  {labFiles.length
                    ? `Đã chọn ${labFiles.length} tệp (bấm để chọn thêm ảnh/tờ khác)`
                    : 'Chọn 1 hoặc nhiều ảnh (PNG, JPG) / PDF kết quả xét nghiệm'}
                </div>
              </div>
              <input
                type="file"
                multiple
                accept=".png,.jpg,.jpeg,.pdf"
                className="hidden"
                onChange={handlePickLabFiles}
              />
            </label>

            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">
                Ngày khám (tùy chọn – bỏ trống = lấy theo phiếu)
              </label>
              <input
                type="date"
                value={labDate}
                onChange={(e) => setLabDate(e.target.value)}
                className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm text-slate-800 outline-none focus:border-sky-500"
              />
            </div>
          </div>

          {labFiles.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {labFiles.map((f, idx) => (
                <span
                  key={`${f.name}-${idx}`}
                  className="inline-flex items-center gap-1.5 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-medium text-sky-900"
                >
                  <span className="max-w-[200px] truncate">{f.name}</span>
                  <button
                    type="button"
                    onClick={() => removeLabFile(idx)}
                    className="rounded-full p-0.5 text-sky-700 hover:bg-sky-200/70"
                    aria-label="Xóa tệp"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </span>
              ))}
            </div>
          )}

          {labErr && <div className="rounded-xl bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700">{labErr}</div>}
          {labMsg && <div className="rounded-xl bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-900">{labMsg}</div>}

          <button
            type="submit"
            disabled={!labFiles.length || uploadingLab}
            className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-sky-500 to-teal-500 px-5 py-2.5 text-xs font-bold text-white shadow-md shadow-sky-500/20 transition hover:brightness-105 disabled:opacity-50"
          >
            {uploadingLab ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            {uploadingLab ? 'AI đang đọc phiếu...' : `Phân tích & Nạp vào hồ sơ (${labFiles.length || 0})`}
          </button>
        </form>
      )}
    </div>
  );
}
