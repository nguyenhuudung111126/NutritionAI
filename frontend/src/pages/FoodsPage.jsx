import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Ban,
  Camera,
  CheckCircle2,
  ChevronRight,
  Database,
  Loader2,
  RotateCcw,
  Scale,
  Search,
  Sparkles,
  Trash2,
  Utensils,
  X,
} from 'lucide-react';
import { api } from '../api';

const QUICK_DISH_SAMPLES = [
  '1 tô Phở bò tái chín',
  'Bánh mì thịt nguội pate',
  '1 tô Bún bò Huế',
  'Cơm tấm sườn bì chả',
  '1 ly Trà sữa trân châu',
];

const NUTRIENT_KEYS = [
  'energy_kcal',
  'protein_g',
  'lipid_g',
  'glucid_g',
  'fiber_g',
  'water_g',
  'sodium_mg',
  'potassium_mg',
  'phosphorus_mg',
  'calcium_mg',
  'iron_mg',
  'zinc_mg',
  'magnesium_mg',
  'vitamin_c_mg',
];

function SafetyBadge({ action }) {
  if (action === 'PASS') {
    return (
      <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-bold text-emerald-700 border border-emerald-200/70">
        <CheckCircle2 className="h-3 w-3" /> An toàn
      </span>
    );
  }
  if (action === 'PORTION') {
    return (
      <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-teal-50 px-2.5 py-0.5 text-[11px] font-bold text-teal-700 border border-teal-200">
        <Scale className="h-3 w-3" /> Kiểm soát khẩu phần
      </span>
    );
  }
  if (action === 'WARN') {
    return (
      <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-[11px] font-bold text-amber-800 border border-amber-200">
        <AlertTriangle className="h-3 w-3" /> Hạn chế
      </span>
    );
  }
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-rose-50 px-2.5 py-0.5 text-[11px] font-bold text-rose-700 border border-rose-200">
      <Ban className="h-3 w-3" /> Cấm / Tránh
    </span>
  );
}

function FoodDetailModal({ food, onClose }) {
  if (!food) return null;

  const macros = [
    { label: 'Năng lượng', val: food.energy_kcal, unit: 'kcal' },
    { label: 'Đạm (Protein)', val: food.protein_g, unit: 'g' },
    { label: 'Béo (Lipid)', val: food.lipid_g, unit: 'g' },
    { label: 'Bột (Glucid)', val: food.glucid_g, unit: 'g' },
    { label: 'Chất xơ', val: food.fiber_g, unit: 'g' },
    { label: 'Chỉ số GI', val: food.gi || '—', unit: '' },
    { label: 'Nước', val: food.water_g, unit: 'g' },
  ];

  const micros = [
    { label: 'Kali (K)', val: food.potassium_mg, unit: 'mg' },
    { label: 'Natri (Na)', val: food.sodium_mg, unit: 'mg' },
    { label: 'Phospho (P)', val: food.phosphorus_mg, unit: 'mg' },
    { label: 'Canxi (Ca)', val: food.calcium_mg, unit: 'mg' },
    { label: 'Sắt (Fe)', val: food.iron_mg, unit: 'mg' },
    { label: 'Kẽm (Zn)', val: food.zinc_mg, unit: 'mg' },
    { label: 'Magie (Mg)', val: food.magnesium_mg, unit: 'mg' },
    { label: 'Vitamin C', val: food.vitamin_c_mg, unit: 'mg' },
  ];

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/45 p-4 backdrop-blur-xs"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl rounded-xl border border-slate-200 bg-white p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-extrabold text-slate-900">{food.name}</h2>
              <SafetyBadge action={food.safety_action} />
            </div>
            <p className="mt-1 text-xs text-slate-500">Thành phần dinh dưỡng tính trên 100{food.unit || 'g'} ăn được</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-xl p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {food.safety_reasons?.length > 0 && (
          <div
            className={`rounded-xl p-3.5 text-xs space-y-1 ${
              food.safety_action === 'BLOCK'
                ? 'bg-rose-50 text-rose-800'
                : food.safety_action === 'PORTION'
                  ? 'bg-teal-50 text-teal-900'
                  : 'bg-amber-50 text-amber-900'
            }`}
          >
            <div className="font-bold">Lưu ý theo hồ sơ bệnh nhân:</div>
            {food.safety_reasons.map((r, i) => (
              <div key={i}>• {r}</div>
            ))}
          </div>
        )}

        <div>
          <div className="mb-2 text-xs font-bold uppercase tracking-wider text-sky-800">
            Nhóm chất sinh năng lượng & Đường huyết
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {macros.map((m) => (
              <div key={m.label} className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                <div className="text-[11px] text-slate-500">{m.label}</div>
                <div className="text-sm font-bold text-slate-900">
                  {m.val ?? '—'} {m.val != null && m.unit ? m.unit : ''}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="mb-2 text-xs font-bold uppercase tracking-wider text-teal-800">
            Khoáng chất & Vi chất
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {micros.map((m) => (
              <div key={m.label} className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                <div className="text-[11px] text-slate-500">{m.label}</div>
                <div className="text-sm font-bold text-slate-900">
                  {m.val ?? '—'} {m.val != null && m.unit ? m.unit : ''}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function AnyDishScannerCard({ patientId }) {
  const [dishQuery, setDishQuery] = useState('');
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [weights, setWeights] = useState({});
  const [viewMode, setViewMode] = useState('serving'); // 'serving' | '100g'
  const fileInputRef = useRef(null);

  const handleSelectFile = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setImageFile(f);
    setImagePreview(URL.createObjectURL(f));
  };

  const clearImage = () => {
    setImageFile(null);
    setImagePreview('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const runAnalysis = async (customQuery = null) => {
    const qToUse = customQuery !== null ? customQuery : dishQuery;
    if (!imageFile && !qToUse.trim()) {
      setError('Vui lòng chọn/chụp ảnh món ăn hoặc nhập tên món (VD: Phở bò, Bánh mì...).');
      return;
    }
    setAnalyzing(true);
    setError('');
    try {
      const res = await api.analyzeDish({
        dishQuery: qToUse.trim(),
        file: customQuery !== null ? null : imageFile,
        patientId,
      });
      setResult(res);
      const initWeights = {};
      (res.ingredients || []).forEach((ing) => {
        initWeights[ing.id] = ing.weight_g;
      });
      setWeights(initWeights);
      setViewMode('serving');
    } catch (err) {
      setError(err.message || 'Không thể phân tích món ăn');
    } finally {
      setAnalyzing(false);
    }
  };

  // Tính toán lại theo thời gian thực khi người dùng kéo thanh chỉnh gram thành phần
  const liveCalc = useMemo(() => {
    if (!result) return null;
    const ings = result.ingredients || [];
    let totalWeight = 0;
    const serving = {};
    NUTRIENT_KEYS.forEach((k) => {
      serving[k] = 0;
    });

    const updatedIngs = ings.map((ing) => {
      const w = Number(weights[ing.id] ?? ing.weight_g ?? 0);
      totalWeight += w;
      const amt = {};
      NUTRIENT_KEYS.forEach((k) => {
        const val = ((ing.per_100g?.[k] || 0) * w) / 100.0;
        amt[k] = Math.round(val * 10) / 10;
        serving[k] += val;
      });
      return { ...ing, current_weight_g: w, current_amount: amt };
    });

    const safeWeight = totalWeight > 0 ? totalWeight : 100;
    const per100g = {};
    NUTRIENT_KEYS.forEach((k) => {
      serving[k] = Math.round(serving[k] * 10) / 10;
      per100g[k] = Math.round(((serving[k] * 100.0) / safeWeight) * 10) / 10;
    });

    // Đánh giá lại mức độ an toàn động theo khẩu phần đã điều chỉnh
    let tier = result.safety_action === 'BLOCK' ? 'BLOCK' : 'PASS';
    const reasons = [];

    if (result.safety_action === 'BLOCK') {
      // Giữ nguyên cảnh báo dị ứng hoặc chất cấm tuyệt đối
      reasons.push(...(result.safety_reasons || []));
    } else {
      const target = result.patient_target;
      const rank = { PASS: 0, PORTION: 1, WARN: 2, BLOCK: 3 };
      const escalate = (newTier, msg) => {
        if (!reasons.includes(msg)) reasons.push(msg);
        if (rank[newTier] > rank[tier]) tier = newTier;
      };

      if (target) {
        if (target.sodium_max_mg && serving.sodium_mg > target.sodium_max_mg * 0.45) {
          const pct = Math.round((serving.sodium_mg * 100) / target.sodium_max_mg);
          escalate(
            'WARN',
            `Khẩu phần hiện tại chứa ${Math.round(serving.sodium_mg)}mg Natri (chiếm ${pct}% giới hạn cả ngày ${Math.round(target.sodium_max_mg)}mg).`
          );
        }
        if (target.potassium_max_mg && serving.potassium_mg > target.potassium_max_mg * 0.42) {
          const pct = Math.round((serving.potassium_mg * 100) / target.potassium_max_mg);
          escalate(
            'WARN',
            `Khẩu phần hiện tại chứa ${Math.round(serving.potassium_mg)}mg Kali (chiếm ${pct}% giới hạn cả ngày ${Math.round(target.potassium_max_mg)}mg).`
          );
        }
        if (target.phosphate_max_mg && serving.phosphorus_mg > target.phosphate_max_mg * 0.45) {
          const pct = Math.round((serving.phosphorus_mg * 100) / target.phosphate_max_mg);
          escalate(
            'WARN',
            `Khẩu phần hiện tại chứa ${Math.round(serving.phosphorus_mg)}mg Phospho (chiếm ${pct}% giới hạn cả ngày ${Math.round(target.phosphate_max_mg)}mg).`
          );
        }
        if (target.require_low_gi) {
          if (result.estimated_gi === 'Cao' && serving.glucid_g >= 25) {
            escalate(
              'WARN',
              `Món có chỉ số đường huyết (GI) Cao kèm ${serving.glucid_g}g đường bột, dễ gây tăng đường huyết sau ăn.`
            );
          } else if (serving.glucid_g >= 40) {
            escalate(
              'PORTION',
              `Khẩu phần cung cấp ${serving.glucid_g}g tinh bột (Glucid), cần kiểm soát lượng tinh bột trong bữa.`
            );
          } else if (result.estimated_gi === 'Cao' && serving.glucid_g > 0) {
            escalate(
              'PORTION',
              `Đã giảm lượng tinh bột xuống ${serving.glucid_g}g (tải lượng đường huyết GL đã về mức kiểm soát).`
            );
          }
        }
        if (target.protein_g && serving.protein_g > target.protein_g * 0.5) {
          const pct = Math.round((serving.protein_g * 100) / target.protein_g);
          escalate(
            'PORTION',
            `Khẩu phần cung cấp ${serving.protein_g}g Đạm (chiếm ${pct}% hạn mức đạm cả ngày ${Math.round(target.protein_g)}g).`
          );
        }
      }
    }

    return {
      totalWeight: Math.round(totalWeight),
      serving,
      per100g,
      ingredients: updatedIngs,
      safetyAction: tier,
      safetyReasons: reasons,
    };
  }, [result, weights]);

  const applyQuickReduceBroth = () => {
    if (!result) return;
    const next = { ...weights };
    result.ingredients.forEach((ing) => {
      const lower = ing.name.toLowerCase();
      if (ing.role === 'Nước dùng / Sốt' || lower.includes('nước dùng') || lower.includes('nước lèo') || lower.includes('sốt')) {
        next[ing.id] = Math.round(ing.default_weight_g * 0.3);
      }
    });
    setWeights(next);
  };

  const applyQuickReduceCarb = () => {
    if (!result) return;
    const next = { ...weights };
    result.ingredients.forEach((ing) => {
      if (ing.role === 'Tinh bột' || (ing.per_100g?.glucid_g || 0) >= 20) {
        next[ing.id] = Math.round(ing.default_weight_g * 0.6);
      }
    });
    setWeights(next);
  };

  const resetDefaultWeights = () => {
    if (!result) return;
    const init = {};
    result.ingredients.forEach((ing) => {
      init[ing.id] = ing.default_weight_g;
    });
    setWeights(init);
  };

  const activeNumbers = viewMode === 'serving' ? liveCalc?.serving : liveCalc?.per100g;
  const target = result?.patient_target;

  const budgetItems = useMemo(() => {
    if (!target || !liveCalc) return [];
    const s = liveCalc.serving;
    const items = [];
    if (target.energy_kcal) {
      items.push({
        label: 'Năng lượng',
        val: Math.round(s.energy_kcal),
        max: Math.round(target.energy_kcal),
        unit: 'kcal',
      });
    }
    if (target.protein_g) {
      items.push({
        label: 'Đạm (Protein)',
        val: s.protein_g,
        max: Math.round(target.protein_g),
        unit: 'g',
      });
    }
    if (target.sodium_max_mg) {
      items.push({
        label: 'Natri (Muối)',
        val: Math.round(s.sodium_mg),
        max: Math.round(target.sodium_max_mg),
        unit: 'mg',
      });
    }
    if (target.potassium_max_mg) {
      items.push({
        label: 'Kali',
        val: Math.round(s.potassium_mg),
        max: Math.round(target.potassium_max_mg),
        unit: 'mg',
      });
    }
    return items;
  }, [target, liveCalc]);

  return (
    <div className="rounded-xl border border-sky-200/90 bg-gradient-to-br from-sky-50/80 via-white to-teal-50/40 p-5 shadow-xs space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-sky-100 px-3 py-0.5 text-[11px] font-bold text-sky-800">
            <Sparkles className="h-3.5 w-3.5" /> AI Vision & Bóc tách Công thức
          </div>
          <h2 className="mt-1.5 text-lg font-extrabold text-slate-900">
            Quét Ảnh hoặc Phân tích Món ăn Bất kỳ
          </h2>
        </div>
      </div>

      {/* Input Controls: Upload Photo + Text Input */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleSelectFile}
          className="hidden"
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl border border-sky-300 bg-white px-4 py-2.5 text-xs font-bold text-sky-800 shadow-2xs transition hover:bg-sky-50"
        >
          <Camera className="h-4 w-4 text-sky-600" />
          {imageFile ? 'Đổi ảnh món ăn' : 'Chụp / Tải ảnh món ăn'}
        </button>

        <div className="relative flex-1">
          <Utensils className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={dishQuery}
            onChange={(e) => setDishQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                runAnalysis();
              }
            }}
            placeholder="Hoặc nhập tên món bất kỳ (VD: 1 tô phở bò tái chín, bánh mì pate, bún riêu cua...)"
            className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-4 text-sm outline-none focus:border-sky-500"
          />
        </div>

        <button
          type="button"
          onClick={() => runAnalysis()}
          disabled={analyzing}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-sky-600 px-5 py-2.5 text-xs font-bold text-white shadow-sm transition hover:bg-sky-700 disabled:opacity-50"
        >
          {analyzing ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> Đang bóc tách...
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" /> Phân tích chất
            </>
          )}
        </button>
      </div>

      {/* Image Preview if uploaded */}
      {imagePreview && (
        <div className="flex items-center gap-3 rounded-xl border border-sky-200 bg-white p-2.5 w-fit">
          <img
            src={imagePreview}
            alt="Preview món ăn"
            className="h-14 w-14 rounded-lg object-cover border border-slate-200"
          />
          <div className="text-xs">
            <div className="font-bold text-slate-800 truncate max-w-[200px]">{imageFile?.name}</div>
            <div className="text-slate-500">Sẵn sàng quét bằng Gemini Vision</div>
          </div>
          <button
            type="button"
            onClick={clearImage}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
            title="Xóa ảnh"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Quick Dish Sample Chips */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[11px] font-semibold text-slate-500 mr-1">Thử nhanh món ngoài CSDL:</span>
        {QUICK_DISH_SAMPLES.map((sample) => (
          <button
            key={sample}
            type="button"
            disabled={analyzing}
            onClick={() => {
              setDishQuery(sample);
              runAnalysis(sample);
            }}
            className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50 hover:text-sky-900 disabled:opacity-50"
          >
            {sample}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-xs font-medium text-rose-700">
          {error}
        </div>
      )}

      {/* Analysis Result Panel */}
      {result && liveCalc && activeNumbers && (
        <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-5">
          {/* Top Header */}
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
            <div>
              <div className="flex flex-wrap items-center gap-2.5">
                <h3 className="text-xl font-extrabold text-slate-900">{result.dish_name}</h3>
                <SafetyBadge action={liveCalc.safetyAction} />
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-700">
                  GI ước tính: {result.estimated_gi}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-500">
                Khẩu phần gốc: <strong>{result.serving_description}</strong> • Đang tính theo:{' '}
                <strong className="text-sky-700">{liveCalc.totalWeight}g</strong> ({result.db_matched_count}/
                {result.total_ingredients_count} thành phần khớp CSDL chuẩn)
              </p>
            </div>

            <div className="flex items-center gap-1.5 rounded-xl bg-slate-100 p-1">
              <button
                type="button"
                onClick={() => setViewMode('serving')}
                className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                  viewMode === 'serving' ? 'bg-white text-sky-700 shadow-2xs' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Theo 1 suất ({liveCalc.totalWeight}g)
              </button>
              <button
                type="button"
                onClick={() => setViewMode('100g')}
                className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                  viewMode === '100g' ? 'bg-white text-sky-700 shadow-2xs' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Quy đổi trên 100g
              </button>
              <button
                type="button"
                onClick={() => setResult(null)}
                className="ml-1 rounded-lg p-1.5 text-slate-400 hover:bg-slate-200/70 hover:text-slate-700"
                title="Đóng kết quả"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Safety Warnings & Clinical Tips */}
          <div className="grid gap-3 md:grid-cols-2">
            <div
              className={`rounded-xl p-3.5 text-xs space-y-1.5 border ${
                liveCalc.safetyAction === 'BLOCK'
                  ? 'bg-rose-50 border-rose-200 text-rose-900'
                  : liveCalc.safetyAction === 'WARN'
                    ? 'bg-amber-50 border-amber-200 text-amber-900'
                    : liveCalc.safetyAction === 'PORTION'
                      ? 'bg-teal-50 border-teal-200 text-teal-900'
                      : 'bg-emerald-50 border-emerald-200 text-emerald-900'
              }`}
            >
              <div className="font-bold">
                Đánh giá an toàn theo hồ sơ bệnh nhân ({target?.regime_code || 'Chuẩn'}):
              </div>
              {liveCalc.safetyReasons.length > 0 ? (
                liveCalc.safetyReasons.map((r, i) => <div key={i}>• {r}</div>)
              ) : (
                <div>• Khẩu phần hiện tại nằm trong ngưỡng an toàn của phác đồ bệnh nhân.</div>
              )}
            </div>

            {result.clinical_tips?.length > 0 && (
              <div className="rounded-xl border border-sky-200/80 bg-sky-50/70 p-3.5 text-xs text-sky-950 space-y-1.5">
                <div className="font-bold text-sky-900">💡 Mẹo ăn món này an toàn hơn:</div>
                {result.clinical_tips.map((tip, i) => (
                  <div key={i}>• {tip}</div>
                ))}
              </div>
            )}
          </div>

          {/* Patient Daily Budget Impact Bars */}
          {budgetItems.length > 0 && (
            <div className="rounded-xl border border-slate-200/90 bg-slate-50/70 p-3.5 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-800">
                  📊 Tỷ lệ chiếm dụng Ngân sách Dinh dưỡng 1 Ngày của Bệnh nhân (tính cho 1 suất {liveCalc.totalWeight}g)
                </span>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {budgetItems.map((b) => {
                  const pct = Math.min(150, Math.round((b.val * 100) / (b.max || 1)));
                  const high = pct > 45;
                  return (
                    <div key={b.label} className="rounded-xl bg-white p-2.5 border border-slate-200/70 space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-600">{b.label}</span>
                        <span className={`font-bold ${high ? 'text-amber-700' : 'text-slate-900'}`}>
                          {b.val}/{b.max}
                          {b.unit} ({pct}%)
                        </span>
                      </div>
                      <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            pct > 65 ? 'bg-rose-500' : pct > 42 ? 'bg-amber-500' : 'bg-emerald-500'
                          }`}
                          style={{ width: `${Math.min(100, pct)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Interactive Ingredient Breakdown & Quick Portion Tweak */}
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                  Bóc tách Thành phần & Điều chỉnh Khẩu phần Thực tế
                </h4>
                <p className="text-[11px] text-slate-500">
                  Kéo thanh trượt hoặc bấm nút gợi ý bên phải để xem chỉ số Natri, Kali, Đường bột thay đổi tức thì
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                <button
                  type="button"
                  onClick={applyQuickReduceBroth}
                  className="rounded-lg border border-amber-300 bg-amber-50 px-2.5 py-1 text-[11px] font-bold text-amber-900 transition hover:bg-amber-100"
                >
                  🥣 Bỏ 2/3 nước dùng (giảm Natri)
                </button>
                <button
                  type="button"
                  onClick={applyQuickReduceCarb}
                  className="rounded-lg border border-teal-300 bg-teal-50 px-2.5 py-1 text-[11px] font-bold text-teal-900 transition hover:bg-teal-100"
                >
                  🍚 Giảm 40% bánh phở/bún/cơm
                </button>
                <button
                  type="button"
                  onClick={resetDefaultWeights}
                  className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-700 hover:bg-slate-200"
                >
                  <RotateCcw className="h-3 w-3" /> Khẩu phần gốc
                </button>
              </div>
            </div>

            <div className="grid gap-2.5 sm:grid-cols-2">
              {liveCalc.ingredients.map((ing) => (
                <div
                  key={ing.id}
                  className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 flex flex-col justify-between gap-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-xs font-bold text-slate-900">{ing.name}</span>
                        <span className="rounded-md bg-slate-200/80 px-1.5 py-0.5 text-[10px] font-semibold text-slate-700">
                          {ing.role}
                        </span>
                      </div>
                      <div className="mt-0.5 flex items-center gap-1 text-[11px]">
                        {ing.source === 'DB' ? (
                          <span className="inline-flex items-center gap-1 font-medium text-emerald-700">
                            <Database className="h-3 w-3" /> Khớp CSDL: {ing.matched_food_name}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 font-medium text-sky-700">
                            <Sparkles className="h-3 w-3" /> AI ước lượng công thức
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-1">
                      <input
                        type="number"
                        min="0"
                        max="1000"
                        step="10"
                        value={ing.current_weight_g}
                        onChange={(e) =>
                          setWeights((prev) => ({
                            ...prev,
                            [ing.id]: Math.max(0, Number(e.target.value) || 0),
                          }))
                        }
                        className="w-16 rounded-lg border border-slate-300 bg-white px-2 py-1 text-right text-xs font-bold text-slate-900"
                      />
                      <span className="text-xs font-semibold text-slate-500">g</span>
                    </div>
                  </div>

                  <input
                    type="range"
                    min="0"
                    max={Math.max(300, Math.round(ing.default_weight_g * 1.8))}
                    step="5"
                    value={ing.current_weight_g}
                    onChange={(e) =>
                      setWeights((prev) => ({
                        ...prev,
                        [ing.id]: Number(e.target.value),
                      }))
                    }
                    className="w-full accent-sky-600 cursor-pointer"
                  />

                  <div className="flex flex-wrap items-center justify-between gap-1 text-[11px] text-slate-600 border-t border-slate-200/70 pt-1.5">
                    <span>
                      Calo: <strong className="text-slate-900">{ing.current_amount.energy_kcal}</strong>
                    </span>
                    <span>
                      Đạm: <strong className="text-slate-900">{ing.current_amount.protein_g}g</strong>
                    </span>
                    <span>
                      Bột: <strong className="text-slate-900">{ing.current_amount.glucid_g}g</strong>
                    </span>
                    <span>
                      Na: <strong className="text-slate-900">{ing.current_amount.sodium_mg}mg</strong>
                    </span>
                    <span>
                      K: <strong className="text-slate-900">{ing.current_amount.potassium_mg}mg</strong>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Complete 15-Nutrient Breakdown */}
          <div className="grid gap-4 md:grid-cols-2 border-t border-slate-100 pt-4">
            <div>
              <div className="mb-2 text-xs font-bold uppercase tracking-wider text-sky-800">
                Nhóm chất sinh năng lượng ({viewMode === 'serving' ? `1 suất ${liveCalc.totalWeight}g` : 'Trên 100g'})
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {[
                  { label: 'Năng lượng', val: activeNumbers.energy_kcal, unit: 'kcal' },
                  { label: 'Đạm (Protein)', val: activeNumbers.protein_g, unit: 'g' },
                  { label: 'Béo (Lipid)', val: activeNumbers.lipid_g, unit: 'g' },
                  { label: 'Bột (Glucid)', val: activeNumbers.glucid_g, unit: 'g' },
                  { label: 'Chất xơ', val: activeNumbers.fiber_g, unit: 'g' },
                  { label: 'Chỉ số GI', val: result.estimated_gi, unit: '' },
                ].map((m) => (
                  <div key={m.label} className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                    <div className="text-[11px] text-slate-500">{m.label}</div>
                    <div className="text-sm font-bold text-slate-900">
                      {m.val ?? '—'} {m.val != null && m.unit ? m.unit : ''}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="mb-2 text-xs font-bold uppercase tracking-wider text-teal-800">
                Khoáng chất & Vi chất ({viewMode === 'serving' ? `1 suất ${liveCalc.totalWeight}g` : 'Trên 100g'})
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {[
                  { label: 'Kali (K)', val: activeNumbers.potassium_mg, unit: 'mg' },
                  { label: 'Natri (Na)', val: activeNumbers.sodium_mg, unit: 'mg' },
                  { label: 'Phospho (P)', val: activeNumbers.phosphorus_mg, unit: 'mg' },
                  { label: 'Canxi (Ca)', val: activeNumbers.calcium_mg, unit: 'mg' },
                  { label: 'Sắt (Fe)', val: activeNumbers.iron_mg, unit: 'mg' },
                  { label: 'Kẽm (Zn)', val: activeNumbers.zinc_mg, unit: 'mg' },
                  { label: 'Magie (Mg)', val: activeNumbers.magnesium_mg, unit: 'mg' },
                  { label: 'Vitamin C', val: activeNumbers.vitamin_c_mg, unit: 'mg' },
                ].map((m) => (
                  <div key={m.label} className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                    <div className="text-[11px] text-slate-500">{m.label}</div>
                    <div className="text-sm font-bold text-slate-900">
                      {m.val ?? '—'} {m.val != null && m.unit ? m.unit : ''}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function FoodsPage({ patientId }) {
  const [query, setQuery] = useState('');
  const [lowGi, setLowGi] = useState(false);
  const [lowPotassium, setLowPotassium] = useState(false);
  const [lowSodium, setLowSodium] = useState(false);
  const [foods, setFoods] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedFood, setSelectedFood] = useState(null);

  useEffect(() => {
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await api.getFoods({
          q: query,
          patientId,
          lowGi,
          lowPotassium,
          lowSodium,
        });
        setFoods(res);
      } finally {
        setLoading(false);
      }
    }, 220);
    return () => clearTimeout(t);
  }, [query, patientId, lowGi, lowPotassium, lowSodium]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
          Tra cứu Thực phẩm & Quét Món ăn AI
        </h1>
      </div>

      {/* AI Any-Dish Vision & Formula Scanner */}
      <AnyDishScannerCard patientId={patientId} />

      {/* Search & Filters for 690 Standard Foods DB */}
      <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs">
        <div className="relative flex-1 min-w-0 w-full sm:w-auto sm:min-w-[220px]">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Tìm trong 690 nguyên liệu chuẩn CSDL (hỗ trợ không dấu: rau ngot, bi dao, gao lut...)"
            className="w-full rounded-xl border border-slate-200 bg-slate-50/70 py-2 pl-10 pr-4 text-sm outline-none focus:border-sky-500 focus:bg-white"
          />
        </div>
        <button
          onClick={() => setLowGi(!lowGi)}
          className={`rounded-full px-3.5 py-1.5 text-xs font-semibold transition ${
            lowGi ? 'bg-sky-600 text-white' : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
          }`}
        >
          GI Thấp
        </button>
        <button
          onClick={() => setLowPotassium(!lowPotassium)}
          className={`rounded-full px-3.5 py-1.5 text-xs font-semibold transition ${
            lowPotassium ? 'bg-sky-600 text-white' : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
          }`}
        >
          Ít Kali (≤ 200mg)
        </button>
        <button
          onClick={() => setLowSodium(!lowSodium)}
          className={`rounded-full px-3.5 py-1.5 text-xs font-semibold transition ${
            lowSodium ? 'bg-sky-600 text-white' : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
          }`}
        >
          Ít Natri (≤ 200mg)
        </button>
      </div>

      {/* Compact Results Grid (4 key nutrients outside, click for full modal) */}
      {loading ? (
        <div className="p-8 text-center text-sm text-slate-500">Đang truy vấn thực phẩm...</div>
      ) : (
        <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
          {foods.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setSelectedFood(f)}
              className="group rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-2xs transition hover:-translate-y-0.5 hover:border-sky-300 hover:shadow-md flex flex-col justify-between gap-3"
            >
              <div className="w-full">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-sm font-bold text-slate-900 group-hover:text-sky-700">{f.name}</h3>
                  <SafetyBadge action={f.safety_action} />
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
                  <div className="rounded-lg bg-slate-50 px-2.5 py-1.5">
                    Calo: <strong className="text-slate-900">{f.energy_kcal ?? '—'}</strong>
                  </div>
                  <div className="rounded-lg bg-slate-50 px-2.5 py-1.5">
                    Đạm: <strong className="text-slate-900">{f.protein_g ?? '—'}g</strong>
                  </div>
                  <div className="rounded-lg bg-slate-50 px-2.5 py-1.5">
                    Kali: <strong className="text-slate-900">{f.potassium_mg ?? '—'}</strong>
                  </div>
                  <div className="rounded-lg bg-slate-50 px-2.5 py-1.5">
                    GI: <strong className="text-slate-900">{f.gi || '—'}</strong>
                  </div>
                </div>
              </div>

              <div className="flex w-full items-center justify-between text-[11px] font-medium text-sky-700">
                <span className="truncate text-slate-400">
                  {f.safety_reasons?.[0] ? f.safety_reasons[0] : 'Nhấn để xem đầy đủ 15 chỉ số'}
                </span>
                <ChevronRight className="h-3.5 w-3.5 shrink-0 transition group-hover:translate-x-0.5" />
              </div>
            </button>
          ))}
        </div>
      )}

      <FoodDetailModal food={selectedFood} onClose={() => setSelectedFood(null)} />
    </div>
  );
}
