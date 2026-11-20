import { useEffect, useState } from 'react';
import { Apple, Edit3, Loader2, Plus, Search, Trash2, X } from 'lucide-react';
import { api } from '../api';

const EMPTY_FOOD = {
  name: '',
  unit: 'g',
  energy_kcal: 0,
  protein_g: 0,
  lipid_g: 0,
  glucid_g: 0,
  fiber_g: 0,
  sodium_mg: 0,
  potassium_mg: 0,
  phosphorus_mg: 0,
  gi: 'Thấp',
};

export default function AdminFoodsPage() {
  const [foods, setFoods] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [lowGi, setLowGi] = useState(false);
  const [lowPotassium, setLowPotassium] = useState(false);
  const [lowSodium, setLowSodium] = useState(false);
  const [editingFood, setEditingFood] = useState(null);
  const [form, setForm] = useState(EMPTY_FOOD);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  const loadFoods = async () => {
    setLoading(true);
    try {
      const list = await api.getFoods({ q: query, lowGi, lowPotassium, lowSodium });
      setFoods(list);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => {
      loadFoods();
    }, 200);
    return () => clearTimeout(t);
  }, [query, lowGi, lowPotassium, lowSodium]);

  const openNew = () => {
    setEditingFood({ isNew: true });
    setForm(EMPTY_FOOD);
    setErr('');
  };

  const openEdit = (f) => {
    setEditingFood(f);
    setForm({
      name: f.name || '',
      unit: f.unit || 'g',
      energy_kcal: f.energy_kcal ?? 0,
      protein_g: f.protein_g ?? 0,
      lipid_g: f.lipid_g ?? 0,
      glucid_g: f.glucid_g ?? 0,
      fiber_g: f.fiber_g ?? 0,
      sodium_mg: f.sodium_mg ?? 0,
      potassium_mg: f.potassium_mg ?? 0,
      phosphorus_mg: f.phosphorus_mg ?? 0,
      gi: f.gi || 'Thấp',
    });
    setErr('');
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setErr('');
    setMsg('');
    const payload = {
      name: form.name,
      unit: form.unit,
      energy_kcal: Number(form.energy_kcal || 0),
      protein_g: Number(form.protein_g || 0),
      lipid_g: Number(form.lipid_g || 0),
      glucid_g: Number(form.glucid_g || 0),
      fiber_g: Number(form.fiber_g || 0),
      sodium_mg: Number(form.sodium_mg || 0),
      potassium_mg: Number(form.potassium_mg || 0),
      phosphorus_mg: Number(form.phosphorus_mg || 0),
      gi: form.gi || null,
    };
    try {
      if (editingFood?.isNew) {
        const created = await api.adminCreateFood(payload);
        setMsg(`Đã thêm món "${created.name}" (#${created.id}) vào kho thực phẩm.`);
      } else {
        const updated = await api.adminUpdateFood(editingFood.id, payload);
        setMsg(`Đã cập nhật thông số món "${updated.name}" (#${updated.id}).`);
      }
      setEditingFood(null);
      await loadFoods();
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (f) => {
    setErr('');
    setMsg('');
    try {
      await api.adminDeleteFood(f.id);
      setMsg(`Đã xóa thực phẩm "${f.name}".`);
      await loadFoods();
    } catch (e2) {
      setErr(e2.message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-sky-100 px-3 py-0.5 text-[11px] font-bold text-sky-800">
            <Apple className="h-3.5 w-3.5" /> Dữ liệu Viện Dinh dưỡng Quốc gia
          </div>
          <h1 className="mt-1.5 text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
            Quản lý Kho Thực phẩm
          </h1>
          <p className="mt-1 text-xs text-slate-600">
            Tra cứu, bổ sung và hiệu chỉnh giá trị dinh dưỡng trên 100g ăn được (Calo, Đạm, Natri, Kali, Phospho, Chỉ số GI).
          </p>
        </div>

        <button
          type="button"
          onClick={openNew}
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-500 to-teal-500 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-sky-500/20 hover:brightness-105"
        >
          <Plus className="h-4 w-4" /> Thêm thực phẩm mới
        </button>
      </div>

      {err && <div className="rounded-xl bg-rose-50 px-4 py-2.5 text-xs font-medium text-rose-700">{err}</div>}
      {msg && <div className="rounded-xl bg-emerald-50 px-4 py-2.5 text-xs font-semibold text-emerald-900">{msg}</div>}

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-xs">
        <div className="relative flex-1 min-w-0 w-full sm:w-auto sm:min-w-[220px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Tìm tên thực phẩm (có dấu hoặc không dấu)..."
            className="w-full rounded-xl border border-slate-200 bg-slate-50/70 py-2 pl-9 pr-3 text-xs outline-none focus:border-sky-500 focus:bg-white"
          />
        </div>
        {[
          { label: 'GI Thấp', active: lowGi, toggle: () => setLowGi((v) => !v) },
          { label: 'Kali ≤ 200mg', active: lowPotassium, toggle: () => setLowPotassium((v) => !v) },
          { label: 'Natri ≤ 200mg', active: lowSodium, toggle: () => setLowSodium((v) => !v) },
        ].map((f) => (
          <button
            key={f.label}
            type="button"
            onClick={f.toggle}
            className={`rounded-full px-3.5 py-1.5 text-xs font-bold transition ${
              f.active ? 'bg-sky-600 text-white' : 'border border-slate-200 bg-slate-50 text-slate-700 hover:bg-sky-50'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-xs">
        {loading ? (
          <div className="flex items-center gap-2 py-8 text-xs text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin text-sky-600" /> Đang tải dữ liệu thực phẩm...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-[11px] font-bold uppercase text-slate-400">
                  <th className="py-2.5 pr-3">ID</th>
                  <th className="py-2.5 px-3">Tên thực phẩm (100g)</th>
                  <th className="py-2.5 px-3">Calo</th>
                  <th className="py-2.5 px-3">Đạm (g)</th>
                  <th className="py-2.5 px-3">Béo (g)</th>
                  <th className="py-2.5 px-3">Đường bột (g)</th>
                  <th className="py-2.5 px-3">Kali (mg)</th>
                  <th className="py-2.5 px-3">Natri (mg)</th>
                  <th className="py-2.5 px-3">GI</th>
                  <th className="py-2.5 pl-3 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {foods.map((f) => (
                  <tr key={f.id} className="hover:bg-sky-50/40">
                    <td className="py-2.5 pr-3 font-semibold text-slate-500">#{f.id}</td>
                    <td className="py-2.5 px-3 font-bold text-slate-900">{f.name}</td>
                    <td className="py-2.5 px-3 tabular-nums">{f.energy_kcal ?? '—'}</td>
                    <td className="py-2.5 px-3 tabular-nums">{f.protein_g ?? '—'}</td>
                    <td className="py-2.5 px-3 tabular-nums">{f.lipid_g ?? '—'}</td>
                    <td className="py-2.5 px-3 tabular-nums">{f.glucid_g ?? '—'}</td>
                    <td className="py-2.5 px-3 tabular-nums">{f.potassium_mg ?? '—'}</td>
                    <td className="py-2.5 px-3 tabular-nums">{f.sodium_mg ?? '—'}</td>
                    <td className="py-2.5 px-3">
                      {f.gi ? (
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                            f.gi === 'Thấp'
                              ? 'bg-emerald-100 text-emerald-800'
                              : f.gi === 'Trung bình'
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-rose-100 text-rose-800'
                          }`}
                        >
                          {f.gi}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="py-2.5 pl-3 text-right">
                      <div className="inline-flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => openEdit(f)}
                          className="rounded-lg border border-slate-200 bg-white p-1.5 text-slate-700 hover:bg-sky-50 hover:text-sky-700"
                          title="Chỉnh sửa"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(f)}
                          className="rounded-lg border border-rose-200 bg-rose-50/70 p-1.5 text-rose-600 hover:bg-rose-100"
                          title="Xóa"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Create / Edit Modal */}
      {editingFood && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-xs">
          <form
            onSubmit={handleSave}
            className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl space-y-4"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">
                {editingFood.isNew ? 'Thêm Thực phẩm mới' : `Chỉnh sửa #${editingFood.id}`}
              </h3>
              <button type="button" onClick={() => setEditingFood(null)} className="text-slate-400 hover:text-slate-600">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs font-semibold text-slate-700">Tên thực phẩm *</label>
                <input
                  type="text"
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs outline-none focus:border-sky-500"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Chỉ số GI</label>
                <select
                  value={form.gi}
                  onChange={(e) => setForm({ ...form, gi: e.target.value })}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs outline-none focus:border-sky-500"
                >
                  <option value="Thấp">Thấp</option>
                  <option value="Trung bình">Trung bình</option>
                  <option value="Cao">Cao</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { key: 'energy_kcal', label: 'Calo (kcal)' },
                { key: 'protein_g', label: 'Đạm (g)' },
                { key: 'lipid_g', label: 'Béo (g)' },
                { key: 'glucid_g', label: 'Glucid (g)' },
                { key: 'fiber_g', label: 'Chất xơ (g)' },
                { key: 'sodium_mg', label: 'Natri (mg)' },
                { key: 'potassium_mg', label: 'Kali (mg)' },
                { key: 'phosphorus_mg', label: 'Phospho (mg)' },
              ].map((fld) => (
                <div key={fld.key}>
                  <label className="mb-1 block text-[11px] font-semibold text-slate-600">{fld.label}</label>
                  <input
                    type="number"
                    step="0.1"
                    value={form[fld.key]}
                    onChange={(e) => setForm({ ...form, [fld.key]: e.target.value })}
                    className="w-full rounded-xl border border-slate-200 px-2.5 py-1.5 text-xs outline-none focus:border-sky-500"
                  />
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setEditingFood(null)}
                className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50"
              >
                Hủy
              </button>
              <button
                type="submit"
                disabled={saving}
                className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-sky-500 to-teal-500 px-4 py-2 text-xs font-bold text-white hover:brightness-105 disabled:opacity-50"
              >
                {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Lưu thực phẩm
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
