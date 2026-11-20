import { useEffect, useState } from 'react';
import { ClipboardList, Loader2, ShieldAlert, Stethoscope } from 'lucide-react';
import { api } from '../api';

export default function AdminCatalogPage() {
  const [catalog, setCatalog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [section, setSection] = useState('regimes');

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.adminGetCatalog();
      setCatalog(res);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleToggleCondition = async (code) => {
    await api.adminToggleCondition(code);
    await load();
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-12 text-xs text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin text-sky-600" /> Đang tải danh mục bệnh lý & phác đồ...
      </div>
    );
  }

  const conditions = catalog?.conditions || [];
  const regimes = catalog?.regimes || [];
  const rules = catalog?.rules || [];

  return (
    <div className="space-y-6">
      <div>
        <div className="inline-flex items-center gap-1.5 rounded-full bg-indigo-100 px-3 py-0.5 text-[11px] font-bold text-indigo-800">
          <Stethoscope className="h-3.5 w-3.5" /> Chuẩn Lâm sàng QĐ 2879/QĐ-BYT
        </div>
        <h1 className="mt-1.5 text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
          Danh mục Bệnh lý & Phác đồ Điều trị
        </h1>
        <p className="mt-1 text-xs text-slate-600">
          Kiểm soát danh mục bệnh lý đang kích hoạt, khung định mức dinh dưỡng theo mã phác đồ và ma trận luật lọc thực phẩm.
        </p>
      </div>

      {/* Sub-tab switch */}
      <div className="inline-flex rounded-xl border border-slate-200 bg-white/90 p-1 shadow-2xs">
        {[
          { id: 'regimes', label: `Phác đồ BYT (${regimes.length})` },
          { id: 'conditions', label: `Bệnh lý (${conditions.length})` },
          { id: 'rules', label: `Luật kiểm soát thực phẩm (${rules.length})` },
        ].map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setSection(t.id)}
            className={`rounded-lg px-4 py-2 text-xs font-bold transition ${
              section === t.id
                ? 'bg-gradient-to-r from-sky-500 to-teal-500 text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {section === 'regimes' && (
        <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-xs">
          <div className="mb-3 flex items-center gap-2">
            <ClipboardList className="h-4 w-4 text-sky-600" />
            <h2 className="text-base font-bold text-slate-900">Phác đồ Chế độ ăn Bộ Y tế</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-[11px] font-bold uppercase text-slate-400">
                  <th className="py-2 pr-3">Mã</th>
                  <th className="py-2 px-3">Nhóm bệnh</th>
                  <th className="py-2 px-3">Tên phác đồ</th>
                  <th className="py-2 px-3">Năng lượng / Đạm</th>
                  <th className="py-2 px-3">Giới hạn Natri / Kali / P</th>
                  <th className="py-2 pl-3">Bắt buộc GI</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {regimes.map((r) => (
                  <tr key={r.id} className="hover:bg-sky-50/30">
                    <td className="py-2.5 pr-3 font-extrabold text-sky-700">{r.code}</td>
                    <td className="py-2.5 px-3 text-slate-600">{r.group_name}</td>
                    <td className="py-2.5 px-3 font-semibold text-slate-900">
                      <div>{r.name}</div>
                      {r.notes && <div className="mt-0.5 text-[11px] font-normal text-slate-500">{r.notes}</div>}
                    </td>
                    <td className="py-2.5 px-3 tabular-nums text-slate-700">
                      {r.energy_kcal_per_kg_min
                        ? `${r.energy_kcal_per_kg_min}–${r.energy_kcal_per_kg_max || r.energy_kcal_per_kg_min} kcal/kg`
                        : `${r.energy_min_kcal || '—'}–${r.energy_max_kcal || '—'} kcal`}
                      <div className="text-[11px] text-slate-500">
                        Đạm:{' '}
                        {r.protein_g_per_kg_min
                          ? `${r.protein_g_per_kg_min}–${r.protein_g_per_kg_max || r.protein_g_per_kg_min} g/kg`
                          : `${r.protein_min_g || '—'}–${r.protein_max_g || '—'} g`}
                      </div>
                    </td>
                    <td className="py-2.5 px-3 tabular-nums text-[11px] text-slate-700">
                      Na ≤ {r.sodium_max_mg ?? '—'} • K ≤ {r.potassium_max_mg ?? '—'} • P ≤ {r.phosphate_max_mg ?? '—'} mg
                    </td>
                    <td className="py-2.5 pl-3">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                          r.require_low_gi ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {r.require_low_gi ? 'GI thấp' : 'Chuẩn'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {section === 'conditions' && (
        <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-[11px] font-bold uppercase text-slate-400">
                  <th className="py-2 pr-3">Mã bệnh</th>
                  <th className="py-2 px-3">Tên bệnh lý</th>
                  <th className="py-2 px-3">Nhóm</th>
                  <th className="py-2 px-3">ICD-10</th>
                  <th className="py-2 pl-3 text-right">Trạng thái</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {conditions.map((c) => (
                  <tr key={c.id}>
                    <td className="py-2.5 pr-3 font-extrabold text-sky-700">{c.code}</td>
                    <td className="py-2.5 px-3 font-bold text-slate-900">{c.name}</td>
                    <td className="py-2.5 px-3 text-slate-600">{c.group_name}</td>
                    <td className="py-2.5 px-3 text-slate-500">{c.icd10 || '—'}</td>
                    <td className="py-2.5 pl-3 text-right">
                      <button
                        type="button"
                        onClick={() => handleToggleCondition(c.code)}
                        className={`rounded-full px-3 py-1 text-[11px] font-bold transition ${
                          c.is_enabled
                            ? 'bg-emerald-100 text-emerald-800 hover:bg-emerald-200'
                            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                        }`}
                      >
                        {c.is_enabled ? 'Đang bật' : 'Đang tắt'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {section === 'rules' && (
        <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-xs space-y-3">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-rose-600" />
            <h2 className="text-base font-bold text-slate-900">Ma trận Luật Chặn & Cảnh báo Thực phẩm</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-[11px] font-bold uppercase text-slate-400">
                  <th className="py-2 pr-3">Mức</th>
                  <th className="py-2 px-3">Nguồn</th>
                  <th className="py-2 px-3">Điều kiện ngưỡng</th>
                  <th className="py-2 pl-3">Giải thích lâm sàng</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rules.map((r) => (
                  <tr key={r.id}>
                    <td className="py-2.5 pr-3">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-extrabold ${
                          r.action === 'BLOCK' ? 'bg-rose-100 text-rose-800' : 'bg-amber-100 text-amber-900'
                        }`}
                      >
                        {r.action}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-bold text-slate-800">{r.source_code}</td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-sky-800">
                      {r.nutrient_column} {r.operator}{' '}
                      {r.threshold_num != null ? r.threshold_num : (r.threshold_text || []).join(', ')}
                    </td>
                    <td className="py-2.5 pl-3 text-slate-600">{r.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
