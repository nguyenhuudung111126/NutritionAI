import { useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Ban,
  Bot,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  Droplets,
  FileText,
  Flame,
  HeartPulse,
  PieChart,
  Scale,
  Search,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  Upload,
} from 'lucide-react';

const CONDITION_LABELS = {
  DTD: 'Đái tháo đường',
  CKD: 'Suy thận mạn',
  AKI: 'Suy thận cấp',
  GN_ACUTE: 'Viêm cầu thận cấp',
  GN_CHRONIC: 'Viêm cầu thận mạn',
  NEPHROTIC: 'Hội chứng thận hư',
  HEART_FAILURE: 'Suy tim',
  HTN: 'Cao huyết áp',
  DYSLIPIDEMIA: 'RL mỡ máu',
};

const NUTRIENT_LABELS = {
  glucid_g: { label: 'Đường bột (Glucid)', unit: 'g/100g' },
  protein_g: { label: 'Chất đạm (Protid)', unit: 'g/100g' },
  sodium_mg: { label: 'Natri (Na)', unit: 'mg/100g' },
  potassium_mg: { label: 'Kali (K)', unit: 'mg/100g' },
  phosphorus_mg: { label: 'Phospho (P)', unit: 'mg/100g' },
  gi: { label: 'Chỉ số GI', unit: '' },
};

function fmtHumanRule(rule) {
  const meta = NUTRIENT_LABELS[rule.nutrient_column];
  const name = meta ? meta.label : rule.nutrient_column || 'Quy tắc';
  const unit = meta?.unit ? ` ${meta.unit}` : '';
  if (rule.operator === 'IN' && rule.threshold_text?.length) {
    return `${name}: ${rule.threshold_text.join(', ')}`;
  }
  if (rule.threshold_num != null) {
    return `${name} ${rule.operator} ${rule.threshold_num}${unit}`;
  }
  return name;
}

function fmtRange(minVal, maxVal, unit) {
  if (minVal != null && maxVal != null) return `${minVal}–${maxVal} ${unit}`;
  if (minVal != null) return `≥ ${minVal} ${unit}`;
  if (maxVal != null) return `≤ ${maxVal} ${unit}`;
  return unit || '';
}

function QuickSafetyBadge({ action }) {
  if (action === 'PASS') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-[11px] font-bold text-emerald-800">
        <CheckCircle2 className="h-3 w-3" /> An toàn
      </span>
    );
  }
  if (action === 'PORTION') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-teal-100 px-2.5 py-0.5 text-[11px] font-bold text-teal-800">
        <Scale className="h-3 w-3" /> Kiểm soát khẩu phần
      </span>
    );
  }
  if (action === 'WARN') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-[11px] font-bold text-amber-900">
        <AlertTriangle className="h-3 w-3" /> Hạn chế
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2.5 py-0.5 text-[11px] font-bold text-rose-800">
      <Ban className="h-3 w-3" /> Cấm / Tránh
    </span>
  );
}

function MacroDistributionCard({ target }) {
  const totalKcal = Number(target.energy_kcal || 1800);
  const protG = Number(target.protein_g || Math.round((totalKcal * 0.15) / 4));
  const protKcal = protG * 4;
  const lipidG = target.lipid_g ? Number(target.lipid_g) : Math.round((totalKcal * 0.25) / 9);
  const lipidKcal = lipidG * 9;
  const glucidKcal = Math.max(200, totalKcal - protKcal - lipidKcal);
  const glucidG = target.glucid_g ? Number(target.glucid_g) : Math.round(glucidKcal / 4);

  const sumKcal = protKcal + lipidKcal + glucidKcal || 1;
  const pctProt = Math.round((protKcal / sumKcal) * 100);
  const pctLipid = Math.round((lipidKcal / sumKcal) * 100);
  const pctGlucid = Math.max(0, 100 - pctProt - pctLipid);

  // SVG Donut ring geometry
  const r = 48;
  const c = 2 * Math.PI * r;
  const seg1 = (pctGlucid / 100) * c;
  const seg2 = (pctLipid / 100) * c;
  const seg3 = (pctProt / 100) * c;

  const mealSplits = useMemo(() => {
    const meals = Number(target.meals_per_day || 4);
    if (meals === 3) {
      return [
        { name: 'Sáng', pct: 30, kcal: Math.round(totalKcal * 0.3) },
        { name: 'Trưa', pct: 40, kcal: Math.round(totalKcal * 0.4) },
        { name: 'Tối', pct: 30, kcal: Math.round(totalKcal * 0.3) },
      ];
    }
    if (meals === 4) {
      return [
        { name: 'Sáng', pct: 25, kcal: Math.round(totalKcal * 0.25) },
        { name: 'Trưa', pct: 35, kcal: Math.round(totalKcal * 0.35) },
        { name: 'Phụ chiều', pct: 15, kcal: Math.round(totalKcal * 0.15) },
        { name: 'Tối', pct: 25, kcal: Math.round(totalKcal * 0.25) },
      ];
    }
    return [
      { name: 'Sáng', pct: 20, kcal: Math.round(totalKcal * 0.2) },
      { name: 'Phụ sáng', pct: 10, kcal: Math.round(totalKcal * 0.1) },
      { name: 'Trưa', pct: 35, kcal: Math.round(totalKcal * 0.35) },
      { name: 'Phụ chiều', pct: 10, kcal: Math.round(totalKcal * 0.1) },
      { name: 'Tối', pct: 25, kcal: Math.round(totalKcal * 0.25) },
    ];
  }, [target.meals_per_day, totalKcal]);

  return (
    <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-xs space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-50 text-sky-600">
            <PieChart className="h-4 w-4" />
          </span>
          <div>
            <h2 className="text-sm font-bold text-slate-900">Phân bổ Đa chất & Năng lượng Theo bữa</h2>
            <p className="text-[11px] text-slate-500">Cân bằng Calo mục tiêu theo phác đồ {target.regime_code}</p>
          </div>
        </div>
        <span className="rounded-md bg-sky-50 px-2.5 py-1 text-[11px] font-bold text-sky-700 tabular-nums">
          {target.meals_per_day} bữa/ngày
        </span>
      </div>

      <div className="flex flex-col items-center gap-5 sm:flex-row">
        {/* SVG Multi-Segment Donut */}
        <div className="relative flex h-32 w-32 shrink-0 items-center justify-center">
          <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
            <circle cx="60" cy="60" r={r} fill="none" stroke="#f1f5f9" strokeWidth="14" />
            <circle
              cx="60"
              cy="60"
              r={r}
              fill="none"
              stroke="#0ea5e9"
              strokeWidth="14"
              strokeDasharray={`${seg1} ${c}`}
              strokeDashoffset="0"
              strokeLinecap="butt"
            />
            <circle
              cx="60"
              cy="60"
              r={r}
              fill="none"
              stroke="#14b8a6"
              strokeWidth="14"
              strokeDasharray={`${seg2} ${c}`}
              strokeDashoffset={-seg1}
            />
            <circle
              cx="60"
              cy="60"
              r={r}
              fill="none"
              stroke="#6366f1"
              strokeWidth="14"
              strokeDasharray={`${seg3} ${c}`}
              strokeDashoffset={-(seg1 + seg2)}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
            <span className="text-lg font-extrabold text-slate-900 tabular-nums">{totalKcal}</span>
            <span className="text-[10px] font-semibold text-slate-400">kcal</span>
          </div>
        </div>

        {/* Macro Breakdown Legend */}
        <div className="flex-1 w-full space-y-2.5">
          {[
            {
              label: target.require_low_gi ? 'Đường bột (GI thấp)' : 'Đường bột (Glucid)',
              grams: `${glucidG}g`,
              pct: pctGlucid,
              dot: 'bg-sky-500',
              bar: 'bg-sky-500',
            },
            {
              label: 'Chất béo (Lipid)',
              grams: `${lipidG}g`,
              pct: pctLipid,
              dot: 'bg-teal-500',
              bar: 'bg-teal-500',
            },
            {
              label: 'Chất đạm (Protein)',
              grams: `${protG}g`,
              pct: pctProt,
              dot: 'bg-indigo-500',
              bar: 'bg-indigo-500',
            },
          ].map((m) => (
            <div key={m.label} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 font-semibold text-slate-700">
                  <span className={`h-2.5 w-2.5 rounded-full ${m.dot}`} />
                  {m.label}
                </span>
                <span className="font-bold text-slate-900 tabular-nums">
                  {m.grams} <span className="font-medium text-slate-400">({m.pct}%)</span>
                </span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
                <div className={`h-full rounded-full ${m.bar}`} style={{ width: `${m.pct}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Per-Meal Calorie Guidance */}
      <div className="border-t border-slate-100 pt-3">
        <div className="mb-2 text-[11px] font-bold uppercase tracking-wider text-slate-400">
          Gợi ý chia năng lượng từng bữa
        </div>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
          {mealSplits.map((ms) => (
            <div key={ms.name} className="rounded-lg border border-sky-100/80 bg-sky-50/45 px-2.5 py-2 text-center">
              <div className="text-[10px] font-semibold text-slate-500">{ms.name}</div>
              <div className="text-xs font-extrabold text-sky-800 tabular-nums">{ms.kcal}</div>
              <div className="text-[9px] text-slate-400">{ms.pct}% kcal</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function PlanComplianceCard({ latestPlan, target, onNavigate }) {
  const metrics = useMemo(() => {
    if (!latestPlan) return [];
    const list = [
      {
        label: 'Năng lượng',
        val: Math.round(latestPlan.energy_kcal),
        lim: Math.round(target.energy_kcal || 1800),
        unit: 'kcal',
        isCeiling: false,
      },
      {
        label: 'Chất đạm (Protein)',
        val: Number(latestPlan.protein_g).toFixed(1),
        lim: target.protein_g ? Number(target.protein_g) : null,
        unit: 'g',
        isCeiling: true,
        tol: 1.1,
      },
      {
        label: 'Kali (K)',
        val: Math.round(latestPlan.potassium_mg),
        lim: target.potassium_max_mg ? Math.round(target.potassium_max_mg) : null,
        unit: 'mg',
        isCeiling: true,
      },
      {
        label: 'Natri (Na)',
        val: Math.round(latestPlan.sodium_mg),
        lim: target.sodium_max_mg ? Math.round(target.sodium_max_mg) : null,
        unit: 'mg',
        isCeiling: true,
      },
      {
        label: 'Phospho (P)',
        val: Math.round(latestPlan.phosphorus_mg),
        lim: target.phosphate_max_mg ? Math.round(target.phosphate_max_mg) : null,
        unit: 'mg',
        isCeiling: true,
      },
    ];
    return list.filter((x) => x.lim != null && x.lim > 0);
  }, [latestPlan, target]);

  return (
    <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-xs flex flex-col justify-between space-y-4">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-50 text-teal-600">
            <TrendingUp className="h-4 w-4" />
          </span>
          <div>
            <h2 className="text-sm font-bold text-slate-900">
              {latestPlan ? `Đối chiếu Thực đơn #${latestPlan.id} vs Phác đồ` : 'Hiệu suất Tuân thủ Phác đồ'}
            </h2>
            <p className="text-[11px] text-slate-500">
              {latestPlan
                ? 'So sánh tổng dinh dưỡng ngày 1 thực đơn mới nhất với giới hạn an toàn'
                : 'Chưa có thực đơn nào được tạo cho hồ sơ này'}
            </p>
          </div>
        </div>
        {latestPlan && (
          <span
            className={`shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-bold ${
              latestPlan.guardrail_passed ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-900'
            }`}
          >
            {latestPlan.guardrail_passed ? 'Đạt chuẩn' : 'Cần lưu ý'}
          </span>
        )}
      </div>

      {!latestPlan ? (
        <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-sky-200 bg-sky-50/40 p-6 text-center">
          <p className="text-xs text-slate-600 mb-3">
            Tạo thực đơn 1–7 ngày để xem biểu đồ đối chiếu mức an toàn Đạm, Kali, Natri và Phospho.
          </p>
          <button
            onClick={() => onNavigate('meal-plan')}
            className="rounded-full bg-gradient-to-r from-sky-500 to-teal-500 px-4 py-2 text-xs font-bold text-white shadow-sm"
          >
            Lập thực đơn ngay
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {metrics.map((m) => {
            const numVal = Number(m.val);
            const pct = Math.min(130, Math.round((numVal * 100) / m.lim));
            const maxAllow = m.tol ? m.lim * m.tol : m.lim;
            const over = m.isCeiling && numVal > maxAllow;
            const near = m.isCeiling && !over && pct >= 85;
            const barColor = over
              ? 'bg-rose-500'
              : near
                ? 'bg-amber-500'
                : m.isCeiling
                  ? 'bg-teal-500'
                  : 'bg-sky-500';
            return (
              <div key={m.label} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-700">{m.label}</span>
                  <span className="tabular-nums font-bold text-slate-900">
                    {m.val} <span className="font-normal text-slate-400">/ {m.lim} {m.unit} ({pct}%)</span>
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${barColor}`}
                    style={{ width: `${Math.min(100, pct)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {latestPlan && (
        <div className="flex items-center justify-between border-t border-slate-100 pt-3 text-xs">
          <span className="text-slate-500">
            Chất xơ đạt: <strong className="text-slate-900">{Number(latestPlan.fiber_g).toFixed(1)}g</strong>
            {target.fiber_min_g ? ` (mục tiêu ≥ ${target.fiber_min_g}g)` : ''}
          </span>
          <button
            onClick={() => onNavigate('meal-plan')}
            className="font-bold text-sky-600 hover:text-sky-800 hover:underline"
          >
            Xem chi tiết thực đơn →
          </button>
        </div>
      )}
    </section>
  );
}

export default function OverviewPage({ overview, onNavigate }) {
  const [ruleTab, setRuleTab] = useState('ALL');
  const [labFilter, setLabFilter] = useState('all'); // 'all' | 'abnormal'
  const [quickQuery, setQuickQuery] = useState('');
  const [quickHits, setQuickHits] = useState([]);
  const [quickLoading, setQuickLoading] = useState(false);

  if (!overview) {
    return <div className="p-8 text-center text-sm text-slate-500">Đang tải bảng điều khiển lâm sàng...</div>;
  }

  const { profile, target, clinical_matrix, lab_items, latest_plan_summary, recent_documents, meal_plans_count } =
    overview;
  const allRules = [
    ...(clinical_matrix?.blocking_rules || []),
    ...(clinical_matrix?.warning_rules || []),
  ];

  const ruleSources = Array.from(new Set(allRules.map((r) => r.source_code).filter(Boolean)));
  const visibleRules = ruleTab === 'ALL' ? allRules : allRules.filter((r) => r.source_code === ruleTab);

  const normalizedLabs = (lab_items && lab_items.length > 0
    ? lab_items
    : Object.entries(profile.labs || {}).map(([code, value]) => ({
        code,
        name: code,
        value,
        unit: '',
        normal_min: null,
        normal_max: null,
      }))
  ).map((item) => {
    const valNum = Number(item.value);
    const low = item.normal_min != null && valNum < Number(item.normal_min);
    const high = item.normal_max != null && valNum > Number(item.normal_max);
    return { ...item, isAbnormal: low || high, statusLabel: low ? 'Thấp' : high ? 'Cao' : 'Đạt chuẩn' };
  });
  const abnormalCount = normalizedLabs.filter((l) => l.isAbnormal).length;
  const visibleLabs = labFilter === 'abnormal' ? normalizedLabs.filter((l) => l.isAbnormal) : normalizedLabs;

  const runQuickCheck = async (qText) => {
    const term = (qText ?? quickQuery).trim();
    if (!term) {
      setQuickHits([]);
      return;
    }
    setQuickLoading(true);
    try {
      const rows = await api.getFoods({ q: term, patientId: profile.id });
      setQuickHits((rows || []).slice(0, 3));
    } catch {
      setQuickHits([]);
    } finally {
      setQuickLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. Clinical Hero Banner */}
      <section className="relative overflow-hidden rounded-3xl border border-sky-200/80 bg-gradient-to-br from-white via-sky-50/85 to-teal-50/75 p-6 shadow-sm">
        <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-sky-300/20 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-16 left-1/3 h-44 w-44 rounded-full bg-teal-300/20 blur-2xl" />

        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-3 max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-white/90 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-sky-700 shadow-2xs">
              <ClipboardList className="h-3.5 w-3.5 text-sky-600" /> Phác đồ Bộ Y tế (QĐ 2879/QĐ-BYT)
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
              {profile.nickname} — Phác đồ <span className="text-sky-600">{target.regime_code}</span>
            </h1>
            <div className="flex flex-wrap gap-2 text-xs">
              {(profile.conditions || []).map((c) => (
                <span
                  key={c}
                  className="rounded-md border border-sky-200/80 bg-sky-100/80 px-2.5 py-1 font-semibold text-sky-800"
                >
                  {CONDITION_LABELS[c] || c}
                </span>
              ))}
              {profile.ckd_stage && (
                <span className="rounded-md border border-amber-200/80 bg-amber-100/85 px-2.5 py-1 font-semibold text-amber-900">
                  CKD Giai đoạn {profile.ckd_stage}
                </span>
              )}
              {(clinical_matrix?.allergies || []).length > 0 && (
                <span className="rounded-md border border-rose-200 bg-rose-100/85 px-2.5 py-1 font-semibold text-rose-800">
                  Dị ứng: {clinical_matrix.allergies.join(', ')}
                </span>
              )}
            </div>
          </div>

          <div className="flex flex-wrap gap-2.5">
            <button
              onClick={() => onNavigate('meal-plan')}
              className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-sky-500 to-teal-500 px-5 py-2.5 text-xs font-bold text-white shadow-sm shadow-sky-500/20 transition hover:brightness-105"
            >
              <CalendarDays className="h-4 w-4" /> Lập thực đơn ngay
            </button>
            <button
              onClick={() => onNavigate('assistant')}
              className="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-white/95 px-4 py-2.5 text-xs font-bold text-sky-800 shadow-2xs transition hover:bg-sky-50"
            >
              <Bot className="h-4 w-4 text-sky-600" /> Hỏi Trợ lý AI
            </button>
          </div>
        </div>

        {target.notes && (
          <div className="relative mt-4 rounded-xl border border-sky-200/70 border-l-[3px] border-l-sky-500 bg-white/90 px-4 py-2.5 text-xs text-slate-700 shadow-2xs">
            <strong className="text-slate-900">Lưu ý lâm sàng từ phác đồ:</strong> {target.notes}
          </div>
        )}
      </section>

      {/* 2. Top 5 Executive KPI Cards */}
      <section className="grid grid-cols-2 gap-3.5 sm:grid-cols-3 lg:grid-cols-5">
        <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-xs transition hover:-translate-y-0.5 hover:border-sky-200 hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase text-slate-400">Năng lượng</span>
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-orange-50 text-orange-500">
              <Flame className="h-4 w-4" />
            </span>
          </div>
          <div className="mt-2 text-2xl font-extrabold text-slate-900 tabular-nums">{target.energy_kcal}</div>
          <div className="text-xs text-slate-500">kcal / ngày ({target.meals_per_day} bữa)</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-xs transition hover:-translate-y-0.5 hover:border-sky-200 hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase text-slate-400">Đạm (Protein)</span>
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
              <HeartPulse className="h-4 w-4" />
            </span>
          </div>
          <div className="mt-2 text-2xl font-extrabold text-slate-900 tabular-nums">{target.protein_g} g</div>
          <div className="text-xs text-slate-500">mục tiêu mỗi ngày</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-xs transition hover:-translate-y-0.5 hover:border-sky-200 hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase text-slate-400">Natri tối đa</span>
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-sky-50 text-sky-600">
              <Droplets className="h-4 w-4" />
            </span>
          </div>
          <div className="mt-2 text-2xl font-extrabold text-sky-700 tabular-nums">
            {target.sodium_max_mg != null ? `${target.sodium_max_mg} mg` : 'Theo chuẩn'}
          </div>
          <div className="text-xs text-slate-500">
            {target.sodium_max_mg != null ? 'kiểm soát muối' : 'không giới hạn nghiêm ngặt'}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-xs transition hover:-translate-y-0.5 hover:border-sky-200 hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase text-slate-400">Kali tối đa</span>
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-teal-50 text-teal-600">
              <Activity className="h-4 w-4" />
            </span>
          </div>
          <div className="mt-2 text-2xl font-extrabold text-teal-700 tabular-nums">
            {target.potassium_max_mg != null ? `${target.potassium_max_mg} mg` : 'Theo chuẩn'}
          </div>
          <div className="text-xs text-slate-500">
            {target.potassium_max_mg != null ? 'bảo vệ thận & tim' : 'không giới hạn nghiêm ngặt'}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-xs transition hover:-translate-y-0.5 hover:border-sky-200 hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase text-slate-400">Phospho & GI</span>
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-50 text-violet-600">
              <Sparkles className="h-4 w-4" />
            </span>
          </div>
          <div className="mt-2 text-2xl font-extrabold text-slate-900 tabular-nums">
            {target.phosphate_max_mg != null ? `${target.phosphate_max_mg} mg` : 'Theo chuẩn'}
          </div>
          <div className="text-xs text-slate-500">{target.require_low_gi ? 'Bắt buộc GI thấp' : 'GI tiêu chuẩn'}</div>
        </div>
      </section>

      {/* 3. Visual Nutrition Analytics Dashboard (Priority Showcase Row) */}
      <div className="grid gap-6 lg:grid-cols-2">
        <MacroDistributionCard target={target} />
        <PlanComplianceCard latestPlan={latest_plan_summary} target={target} onNavigate={onNavigate} />
      </div>

      {/* 4. Middle Row: Interactive Quick Food Check & Highlighted Labs */}
      <div className="grid gap-6 lg:grid-cols-12">
        {/* Left 7 cols: Smart Highlighted Labs */}
        <section className="lg:col-span-7 rounded-xl border border-slate-200/80 bg-white/95 p-5 shadow-xs space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-50 text-teal-600">
                <Activity className="h-4 w-4" />
              </span>
              <div>
                <h2 className="text-sm font-bold text-slate-900">Chỉ số Xét nghiệm Gần nhất</h2>
                <p className="text-[11px] text-slate-500">
                  {abnormalCount > 0 ? `Phát hiện ${abnormalCount} chỉ số ngoài ngưỡng chuẩn` : 'Tất cả chỉ số trong ngưỡng ổn định'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1 rounded-lg bg-slate-100 p-0.5 text-[11px]">
                <button
                  type="button"
                  onClick={() => setLabFilter('all')}
                  className={`rounded-md px-2.5 py-1 font-bold transition ${
                    labFilter === 'all' ? 'bg-white text-sky-700 shadow-2xs' : 'text-slate-600'
                  }`}
                >
                  Tất cả ({normalizedLabs.length})
                </button>
                <button
                  type="button"
                  onClick={() => setLabFilter('abnormal')}
                  className={`rounded-md px-2.5 py-1 font-bold transition ${
                    labFilter === 'abnormal' ? 'bg-white text-amber-800 shadow-2xs' : 'text-slate-600'
                  }`}
                >
                  Cần chú ý ({abnormalCount})
                </button>
              </div>
              <button
                onClick={() => onNavigate('trends')}
                className="text-xs font-semibold text-sky-600 hover:text-sky-800 hover:underline"
              >
                Xem biểu đồ →
              </button>
            </div>
          </div>

          {visibleLabs.length === 0 ? (
            <p className="py-6 text-center text-xs text-slate-500">Chưa có chỉ số xét nghiệm phù hợp bộ lọc.</p>
          ) : (
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
              {visibleLabs.map((item) => (
                <div
                  key={item.code}
                  className={`rounded-lg border px-3 py-2.5 transition ${
                    item.isAbnormal
                      ? 'border-amber-200 bg-amber-50/60'
                      : 'border-slate-200/70 bg-slate-50/70'
                  }`}
                >
                  <div className="flex items-center justify-between gap-1">
                    <span className="truncate text-[10px] font-bold uppercase tracking-wide text-slate-500">
                      {item.code}
                    </span>
                    <span
                      className={`rounded-md px-1.5 py-0.5 text-[9px] font-bold ${
                        item.isAbnormal ? 'bg-amber-200/80 text-amber-950' : 'bg-emerald-100 text-emerald-700'
                      }`}
                    >
                      {item.statusLabel}
                    </span>
                  </div>
                  <div className="mt-1 flex items-baseline gap-1">
                    <span className={`text-base font-extrabold tabular-nums ${item.isAbnormal ? 'text-amber-950' : 'text-slate-900'}`}>
                      {item.value}
                    </span>
                    {item.unit && <span className="text-[10px] text-slate-400">{item.unit}</span>}
                  </div>
                  {(item.normal_min != null || item.normal_max != null) && (
                    <div className="mt-0.5 text-[10px] text-slate-400">
                      Chuẩn: {fmtRange(item.normal_min, item.normal_max, '')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Right 5 cols: Quick Food Checker & Patient Records Summary */}
        <section className="lg:col-span-5 rounded-xl border border-slate-200/80 bg-white/95 p-5 shadow-xs flex flex-col justify-between space-y-4">
          <div className="space-y-3">
            <div className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-50 text-sky-600">
                <Search className="h-4 w-4" />
              </span>
              <div>
                <h2 className="text-sm font-bold text-slate-900">Kiểm tra nhanh 1 món ăn</h2>
                <p className="text-[11px] text-slate-500">Đối chiếu tức thì với hồ sơ {profile.nickname}</p>
              </div>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                runQuickCheck();
              }}
              className="flex gap-2"
            >
              <input
                type="text"
                value={quickQuery}
                onChange={(e) => setQuickQuery(e.target.value)}
                placeholder="VD: rau ngot, gao lut, thit bo..."
                className="flex-1 rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-2 text-xs outline-none focus:border-sky-500 focus:bg-white"
              />
              <button
                type="submit"
                disabled={quickLoading}
                className="rounded-lg bg-sky-600 px-3.5 py-2 text-xs font-bold text-white transition hover:bg-sky-700 disabled:opacity-50"
              >
                {quickLoading ? '...' : 'Kiểm tra'}
              </button>
            </form>

            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[10px] font-semibold text-slate-400">Thử nhanh:</span>
              {['Rau ngót', 'Gạo lứt', 'Bí đao', 'Gạo nếp cái'].map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => {
                    setQuickQuery(s);
                    runQuickCheck(s);
                  }}
                  className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-[11px] font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50 hover:text-sky-800"
                >
                  {s}
                </button>
              ))}
            </div>

            {quickHits.length > 0 && (
              <div className="space-y-2 pt-1">
                {quickHits.map((f) => (
                  <div key={f.id} className="rounded-lg border border-sky-100 bg-sky-50/35 p-2.5 text-xs space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <strong className="text-slate-900">{f.name}</strong>
                      <QuickSafetyBadge action={f.safety_action} />
                    </div>
                    <div className="text-[11px] text-slate-600 tabular-nums">
                      Calo {f.energy_kcal} • Đạm {f.protein_g}g • K {f.potassium_mg ?? '—'} • GI {f.gi || '—'}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="border-t border-slate-100 pt-3 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-500">Thực đơn đã lưu:</span>
              <strong className="text-slate-900 tabular-nums">{meal_plans_count} thực đơn</strong>
            </div>
            {recent_documents?.[0] && (
              <div className="flex items-center gap-1.5 text-xs text-slate-600">
                <FileText className="h-3.5 w-3.5 text-sky-600 shrink-0" />
                <span className="truncate">Phiếu mới nhất: {recent_documents[0].file_path}</span>
              </div>
            )}
            <div className="grid grid-cols-2 gap-2 pt-1">
              <button
                onClick={() => onNavigate('foods')}
                className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-sky-200 bg-sky-50/70 px-3 py-2 text-xs font-bold text-sky-800 transition hover:bg-sky-100/70"
              >
                Quét món bằng AI
              </button>
              <button
                onClick={() => onNavigate('profile')}
                className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 transition hover:bg-slate-50"
              >
                <Upload className="h-3.5 w-3.5" /> Nạp phiếu mới
              </button>
            </div>
          </div>
        </section>
      </div>

      {/* 5. Upgraded Clinical Food Guardrail Matrix (Professional Structured Cards) */}
      <section className="rounded-xl border border-slate-200/80 bg-white/95 p-5 shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-50 text-sky-600">
              <ShieldAlert className="h-4 w-4" />
            </span>
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Hệ thống Quy tắc Kiểm soát Thực phẩm theo Bệnh án
              </h2>
              <p className="text-[11px] text-slate-500">
                Các ngưỡng tự động áp dụng khi lọc món ăn, quét ảnh dinh dưỡng và kiểm tra thực đơn
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-1 rounded-lg bg-slate-100 p-1 text-xs">
            <button
              type="button"
              onClick={() => setRuleTab('ALL')}
              className={`rounded-md px-3 py-1 font-semibold transition ${
                ruleTab === 'ALL' ? 'bg-white text-sky-700 shadow-2xs' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Tất cả ({allRules.length})
            </button>
            {ruleSources.map((src) => {
              const cnt = allRules.filter((r) => r.source_code === src).length;
              return (
                <button
                  key={src}
                  type="button"
                  onClick={() => setRuleTab(src)}
                  className={`rounded-md px-3 py-1 font-semibold transition ${
                    ruleTab === src ? 'bg-white text-sky-700 shadow-2xs' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {src} ({cnt})
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {visibleRules.map((r) => {
            const isBlock = r.action === 'BLOCK';
            return (
              <div
                key={r.id}
                className={`rounded-xl border border-l-[3px] p-4 transition hover:shadow-sm ${
                  isBlock
                    ? 'border-rose-200/80 border-l-rose-500 bg-rose-50/30'
                    : 'border-amber-200/80 border-l-amber-500 bg-amber-50/25'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="text-xs font-extrabold text-slate-900">{fmtHumanRule(r)}</div>
                  <span
                    className={`shrink-0 rounded-md px-2 py-0.5 text-[10px] font-extrabold ${
                      isBlock ? 'bg-rose-100 text-rose-800' : 'bg-amber-100 text-amber-900'
                    }`}
                  >
                    {isBlock ? 'CẤM' : 'HẠN CHẾ'} • {r.source_code}
                  </span>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-slate-600">{r.reason}</p>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
