import { useEffect, useState } from 'react';
import { CalendarDays, CheckCircle2, ChevronDown, ChevronUp, Loader2, Sparkles, AlertTriangle } from 'lucide-react';
import { api } from '../api';

export default function MealPlanPage({ patientId, overview }) {
  const [numDays, setNumDays] = useState(1);
  const [mealsPerDay, setMealsPerDay] = useState(null); // null = theo phác đồ BYT
  const [preferences, setPreferences] = useState('');
  const [generating, setGenerating] = useState(false);
  const [latestResult, setLatestResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [expandedPlanId, setExpandedPlanId] = useState(null);
  const [error, setError] = useState('');

  const loadHistory = async () => {
    if (!patientId) return;
    try {
      const data = await api.getMealPlans(patientId);
      setHistory(data);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    setLatestResult(null);
    loadHistory();
  }, [patientId]);

  const handleGenerate = async (e) => {
    e.preventDefault();
    setGenerating(true);
    setError('');
    try {
      const res = await api.generateMealPlan(patientId, {
        num_days: numDays,
        meals_per_day: mealsPerDay,
        user_preferences: preferences,
      });
      setLatestResult(res);
      await loadHistory();
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  };

  const target = overview?.target;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
          Lập Thực đơn Cá nhân hóa
        </h1>
      </div>

      {/* Generator Card */}
      <form onSubmit={handleGenerate} className="rounded-xl border border-slate-200/80 bg-white/95 p-6 shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-bold text-slate-600 mr-1">Số ngày:</span>
            {[1, 3, 7].map((d) => (
              <button
                type="button"
                key={d}
                onClick={() => setNumDays(d)}
                className={`rounded-xl px-4 py-1.5 text-xs font-bold transition ${
                  numDays === d
                    ? 'bg-gradient-to-r from-sky-500 to-teal-500 text-white shadow-sm shadow-sky-500/20'
                    : 'border border-slate-200 bg-slate-50 text-slate-700 hover:bg-sky-50 hover:border-sky-200'
                }`}
              >
                {d} ngày
              </button>
            ))}
          </div>
          {target && (
            <div className="rounded-full border border-sky-200/80 bg-sky-50 px-3.5 py-1.5 text-xs font-semibold text-sky-900">
              Mục tiêu: ~{target.energy_kcal} kcal • Đạm {target.protein_g}g • K ≤ {target.potassium_max_mg}mg • Na ≤ {target.sodium_max_mg}mg
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold text-slate-600 mr-1">Số bữa / ngày:</span>
          {[
            { val: null, label: `Theo Bộ Y tế (${target?.meals_per_day || 5} bữa)` },
            { val: 3, label: '3 bữa chính (không phụ)' },
            { val: 4, label: '4 bữa (+1 phụ chiều)' },
            { val: 5, label: '5 bữa (+2 phụ)' },
          ].map((opt) => (
            <button
              type="button"
              key={String(opt.val)}
              onClick={() => setMealsPerDay(opt.val)}
              className={`rounded-xl px-3.5 py-1.5 text-xs font-semibold transition ${
                mealsPerDay === opt.val
                  ? 'bg-sky-600 text-white shadow-sm shadow-sky-500/20'
                  : 'border border-slate-200 bg-slate-50 text-slate-700 hover:bg-sky-50 hover:border-sky-200'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <div>
          <textarea
            rows={2}
            value={preferences}
            onChange={(e) => setPreferences(e.target.value)}
            placeholder="VD: Thích món luộc/hấp từ trứng, đậu phụ, bí đao, thịt gà ta, không ăn cá..."
            className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-4 py-3 text-sm text-slate-800 outline-none transition focus:border-sky-500 focus:bg-white focus:ring-2 focus:ring-sky-500/15"
          />
        </div>

        {error && <div className="rounded-xl bg-rose-50 px-4 py-2 text-xs font-medium text-rose-700">{error}</div>}

        <button
          type="submit"
          disabled={generating}
          className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-sky-500 to-teal-500 px-6 py-2.5 text-xs font-bold text-white shadow-md shadow-sky-500/25 transition hover:brightness-105 disabled:opacity-50"
        >
          {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          {generating ? 'Đang tạo thực đơn phù hợp...' : `Tạo thực đơn ${numDays} ngày`}
        </button>
      </form>

      {/* Latest Generated Meal Plan */}
      {latestResult && (
        <div className="rounded-xl border border-sky-200/80 bg-white/95 p-6 shadow-md space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              {latestResult.guardrail_passed ? (
                <CheckCircle2 className="h-5 w-5 text-emerald-600" />
              ) : (
                <AlertTriangle className="h-5 w-5 text-amber-500" />
              )}
              <h3 className="text-base font-bold text-slate-900">
                Thực đơn mới #{latestResult.meal_plan_id} ({latestResult.total_days} ngày)
              </h3>
            </div>
            <span
              className={`rounded-full px-3 py-1 text-xs font-bold ${
                latestResult.guardrail_passed ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
              }`}
            >
              {latestResult.guardrail_passed ? 'Đạt chuẩn an toàn' : 'Cần lưu ý vi chất'}
            </span>
          </div>

          {latestResult.plan?.note_for_patient && (
            <div className="rounded-xl border border-sky-100 bg-sky-50/70 p-3.5 text-xs text-sky-950">
              <strong>💡 Ghi chú cá nhân hóa:</strong> {latestResult.plan.note_for_patient}
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {(latestResult.plan?.days || []).map((day, idx) => {
              const rep = latestResult.day_reports?.[idx];
              const t = rep?.totals || {};
              return (
                <div key={day.day_index} className="rounded-2xl border border-sky-100 bg-gradient-to-b from-sky-50/40 to-white p-4 space-y-3">
                  <div className="flex items-center justify-between border-b border-sky-100 pb-2">
                    <span className="text-sm font-bold text-slate-900">Ngày {day.day_index}</span>
                    <span className="rounded-full bg-sky-100 px-2.5 py-0.5 text-[11px] font-bold text-sky-800">{t.energy_kcal} kcal</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5 text-[11px] text-slate-600">
                    <span className="rounded-lg border border-slate-200/70 bg-white px-2 py-0.5">Đạm {t.protein_g}g</span>
                    <span className="rounded-lg border border-slate-200/70 bg-white px-2 py-0.5">Béo {t.lipid_g}g</span>
                    <span className="rounded-lg border border-slate-200/70 bg-white px-2 py-0.5">Bột {t.glucid_g}g</span>
                    <span className="rounded-lg border border-slate-200/70 bg-white px-2 py-0.5">Xơ {t.fiber_g}g</span>
                    <span className="rounded-lg border border-slate-200/70 bg-white px-2 py-0.5">Kali {t.potassium_mg}mg</span>
                    <span className="rounded-lg border border-slate-200/70 bg-white px-2 py-0.5">Natri {t.sodium_mg}mg</span>
                  </div>
                  <div className="space-y-2.5">
                    {day.meals.map((meal, mIdx) => (
                      <div key={mIdx}>
                        <div className="text-xs font-bold text-sky-700">{meal.meal}</div>
                        <ul className="mt-1 space-y-1 text-xs text-slate-700">
                          {meal.dishes.map((dish, dIdx) => {
                            const ingStr = dish.ingredients
                              .map((i) => `${latestResult.food_map?.[i.food_id] || i.food_id} (${i.grams}g)`)
                              .join(', ');
                            return (
                              <li key={dIdx}>
                                <strong>{dish.name}</strong> <em className="text-slate-400">({dish.cooking_method})</em>: {ingStr}
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Saved Meal Plans History */}
      <div className="rounded-xl border border-slate-200/80 bg-white/95 p-6 shadow-xs">
        <div className="mb-4 flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-sky-50 text-sky-600">
            <CalendarDays className="h-4 w-4" />
          </span>
          <h2 className="text-base font-bold text-slate-900">Lịch sử thực đơn đã lưu ({history.length})</h2>
        </div>
        {history.length === 0 ? (
          <p className="text-xs text-slate-500">Chưa có thực đơn nào được lưu cho bệnh nhân này.</p>
        ) : (
          <div className="space-y-2.5">
            {history.map((p) => {
              const open = expandedPlanId === p.id;
              return (
                <div key={p.id} className="rounded-xl border border-slate-200/80 bg-slate-50/50 transition hover:border-sky-200">
                  <button
                    onClick={() => setExpandedPlanId(open ? null : p.id)}
                    className="flex w-full items-center justify-between px-4 py-3 text-left"
                  >
                    <div className="flex flex-wrap items-center gap-2.5">
                      <span className="text-xs font-bold text-slate-900">Thực đơn #{p.id}</span>
                      <span className="rounded-full bg-sky-100 px-2.5 py-0.5 text-[11px] font-bold text-sky-800">
                        {p.regime_code}
                      </span>
                      <span className="text-xs text-slate-500">
                        {p.days?.length || 0} ngày • {p.model_name || 'AI'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold ${
                          p.guardrail_passed ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {p.guardrail_passed ? 'Đạt chuẩn' : 'Lưu ý'}
                      </span>
                      {open ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
                    </div>
                  </button>
                  {open && (
                    <div className="border-t border-slate-200/80 p-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                      {p.days.map((d) => (
                        <div key={d.day_index} className="rounded-xl bg-white p-3 text-xs space-y-1.5 border border-sky-100/80">
                          <div className="font-bold text-slate-900">
                            Ngày {d.day_index} • {d.totals.energy_kcal} kcal (Đạm {d.totals.protein_g}g | Béo {d.totals.lipid_g}g | Bột {d.totals.glucid_g}g | K {d.totals.potassium_mg}mg)
                          </div>
                          {d.meals.map((m, mi) => (
                            <div key={mi}>
                              <span className="font-semibold text-sky-700">{m.meal}:</span>{' '}
                              {m.dishes.map((dish) => dish.name).join(', ')}
                            </div>
                          ))}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
