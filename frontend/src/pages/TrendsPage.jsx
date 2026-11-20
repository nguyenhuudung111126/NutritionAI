import { useEffect, useState } from 'react';
import { Activity, Loader2, Trash2, TrendingUp } from 'lucide-react';
import { api } from '../api';

function parseDateParts(rawDate) {
  const s = String(rawDate || '').trim();
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) {
    return { dayMonth: s, year: '', full: s };
  }
  const [, year, month, day] = m;
  return {
    dayMonth: `${day}/${month}`,
    year,
    full: `${day}/${month}/${year}`,
  };
}

function formatRefRange(minVal, maxVal, unit) {
  if (minVal != null && maxVal != null) return `${minVal} – ${maxVal} ${unit}`;
  if (minVal != null) return `≥ ${minVal} ${unit}`;
  if (maxVal != null) return `≤ ${maxVal} ${unit}`;
  return unit || '';
}

function MiniLineChart({ series }) {
  const [hoveredIdx, setHoveredIdx] = useState(null);
  const pts = series.points || [];
  const w = 320;
  const h = 124;
  const padX = 20;
  const padTop = 14;
  const padBottom = 30;

  if (pts.length === 0) return null;
  const values = pts.map((p) => Number(p.value));
  const allBounds = [...values];
  if (series.normal_min != null) allBounds.push(Number(series.normal_min));
  if (series.normal_max != null) allBounds.push(Number(series.normal_max));
  const minVal = Math.min(...allBounds) * 0.9;
  const maxVal = Math.max(...allBounds) * 1.1 || 1;
  const span = maxVal - minVal || 1;

  const toX = (idx) => (pts.length === 1 ? w / 2 : padX + (idx / (pts.length - 1)) * (w - padX * 2));
  const toY = (val) => h - padBottom - ((val - minVal) / span) * (h - padTop - padBottom);

  const polyPoints = pts.map((p, i) => `${toX(i)},${toY(Number(p.value))}`).join(' ');
  const latest = values[values.length - 1];
  const outOfRange =
    (series.normal_min != null && latest < series.normal_min) ||
    (series.normal_max != null && latest > series.normal_max);

  const plotTop = padTop;
  const plotBot = h - padBottom;
  const rawTopY = series.normal_max != null ? toY(Number(series.normal_max)) : plotTop;
  const rawBotY = series.normal_min != null ? toY(Number(series.normal_min)) : plotBot;
  const bandTopY = Math.max(plotTop, Math.min(plotBot, Math.min(rawTopY, rawBotY)));
  const bandBotY = Math.max(plotTop, Math.min(plotBot, Math.max(rawTopY, rawBotY)));
  const showBand = series.normal_min != null || series.normal_max != null;

  const parsedDates = pts.map((p) => parseDateParts(p.date));
  const hoveredPoint = hoveredIdx != null ? pts[hoveredIdx] : null;
  const hoveredDate = hoveredIdx != null ? parsedDates[hoveredIdx] : null;
  const hoveredPctX = hoveredIdx != null ? Math.min(82, Math.max(18, (toX(hoveredIdx) / w) * 100)) : 50;

  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-xs transition hover:border-sky-200 hover:shadow-md">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-xs font-bold text-slate-900">{series.name}</div>
          <div className="text-[11px] text-slate-400">
            Ngưỡng chuẩn: {formatRefRange(series.normal_min, series.normal_max, series.unit)}
          </div>
        </div>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
            outOfRange ? 'bg-amber-100 text-amber-800' : 'bg-emerald-50 text-emerald-700'
          }`}
        >
          {latest} {series.unit}
        </span>
      </div>

      <div className="relative mt-2" onMouseLeave={() => setHoveredIdx(null)}>
        {hoveredPoint && hoveredDate && (
          <div
            style={{ left: `${hoveredPctX}%`, transform: 'translateX(-50%)' }}
            className="pointer-events-none absolute -top-2 z-10 whitespace-nowrap rounded-lg bg-slate-900 px-2.5 py-1 text-[11px] font-medium text-white shadow-md"
          >
            <span className="text-slate-300">{hoveredDate.full}</span>
            <span className="mx-1.5 text-slate-500">•</span>
            <span className="font-bold text-sky-300">
              {hoveredPoint.value} {series.unit}
            </span>
          </div>
        )}

        <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
          {showBand && bandBotY > bandTopY && (
            <rect
              x={padX}
              y={bandTopY}
              width={w - padX * 2}
              height={Math.max(4, bandBotY - bandTopY)}
              fill="rgba(16, 185, 129, 0.12)"
              rx="4"
            />
          )}
          {hoveredIdx != null && (
            <line
              x1={toX(hoveredIdx)}
              y1={padTop}
              x2={toX(hoveredIdx)}
              y2={h - padBottom}
              stroke="#94a3b8"
              strokeWidth="1"
              strokeDasharray="3 3"
            />
          )}
          {pts.length > 1 && (
            <polyline fill="none" stroke="#0284c7" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" points={polyPoints} />
          )}
          {pts.map((p, idx) => {
            const d = parsedDates[idx];
            const hideDensity = pts.length > 7 && idx !== 0 && idx !== pts.length - 1 && idx % 2 === 1;
            const showYear = !hideDensity && Boolean(d.year);
            const isHovered = hoveredIdx === idx;

            return (
              <g
                key={idx}
                className="cursor-pointer"
                onMouseEnter={() => setHoveredIdx(idx)}
                onClick={() => setHoveredIdx(isHovered ? null : idx)}
              >
                <circle cx={toX(idx)} cy={toY(Number(p.value))} r="12" fill="transparent" />
                <circle
                  cx={toX(idx)}
                  cy={toY(Number(p.value))}
                  r={isHovered ? '5.5' : '4'}
                  fill={isHovered ? '#0284c7' : '#0369a1'}
                  stroke="#fff"
                  strokeWidth={isHovered ? '2' : '1.5'}
                />
                {!hideDensity && (
                  <text
                    x={toX(idx)}
                    y={h - 14}
                    textAnchor="middle"
                    className={`text-[9px] ${isHovered ? 'fill-sky-700 font-bold' : 'fill-slate-500 font-medium'}`}
                  >
                    {d.dayMonth}
                  </text>
                )}
                {showYear && (
                  <text
                    x={toX(idx)}
                    y={h - 3}
                    textAnchor="middle"
                    className="fill-slate-400 text-[8px] font-semibold"
                  >
                    {d.year}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

export default function TrendsPage({ patientId, onDeletedCheckup }) {
  const [data, setData] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [actionMsg, setActionMsg] = useState('');

  const loadTrends = () => {
    if (!patientId) return;
    api.getTrends(patientId).then(setData).catch(() => {});
  };

  useEffect(() => {
    setActionMsg('');
    loadTrends();
  }, [patientId]);

  const handleDelete = async (checkup) => {
    const labelDate = parseDateParts(checkup.checkup_date).full;
    if (!window.confirm(`Xóa đợt khám #${checkup.id} (${labelDate})? Mọi chỉ số xét nghiệm thuộc đợt này sẽ bị gỡ khỏi biểu đồ.`)) {
      return;
    }
    setDeletingId(checkup.id);
    setActionMsg('');
    try {
      await api.deleteCheckup(patientId, checkup.id);
      setActionMsg(`Đã xóa đợt khám #${checkup.id} (${labelDate}) khỏi lịch sử.`);
      loadTrends();
      onDeletedCheckup?.();
    } catch (err) {
      setActionMsg(`Lỗi xóa đợt khám: ${err.message}`);
    } finally {
      setDeletingId(null);
    }
  };

  if (!data) {
    return <div className="p-8 text-center text-sm text-slate-500">Đang tải biểu đồ xét nghiệm...</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
          Xu hướng Chỉ số Xét nghiệm & Tái khám
        </h1>
      </div>

      {/* Biomarker Charts */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(data.lab_series || []).map((s) => (
          <MiniLineChart key={s.code} series={s} />
        ))}
      </div>

      {/* Checkups Table */}
      <div className="rounded-xl border border-slate-200/80 bg-white/95 p-6 shadow-xs">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-sky-50 text-sky-600">
              <Activity className="h-4 w-4" />
            </span>
            <h2 className="text-base font-bold text-slate-900">Các đợt khám đã lưu ({data.checkups?.length || 0})</h2>
          </div>
          {actionMsg && (
            <span className="rounded-xl bg-sky-50 px-3 py-1 text-xs font-medium text-sky-800">{actionMsg}</span>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500">
                <th className="py-2 pr-4">ID</th>
                <th className="py-2 pr-4">Ngày khám</th>
                <th className="py-2 pr-4">Cân nặng (kg)</th>
                <th className="py-2 pr-4">Huyết áp</th>
                <th className="py-2 pr-4">Nguồn</th>
                <th className="py-2 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(data.checkups || []).map((c) => (
                <tr key={c.id}>
                  <td className="py-2 pr-4 font-semibold">#{c.id}</td>
                  <td className="py-2 pr-4">{parseDateParts(c.checkup_date).full}</td>
                  <td className="py-2 pr-4">{c.weight_kg ?? '—'}</td>
                  <td className="py-2 pr-4">
                    {c.systolic_bp ? `${c.systolic_bp}/${c.diastolic_bp} mmHg` : '—'}
                  </td>
                  <td className="py-2 pr-4">
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium">{c.source}</span>
                  </td>
                  <td className="py-2 text-right">
                    <button
                      type="button"
                      disabled={deletingId === c.id}
                      onClick={() => handleDelete(c)}
                      className="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-rose-50/70 px-2.5 py-1 text-[11px] font-semibold text-rose-700 transition hover:bg-rose-100 disabled:opacity-50"
                      title="Xóa đợt khám này"
                    >
                      {deletingId === c.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
                      Xóa
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Labs Detail Table */}
      <div className="rounded-xl border border-slate-200/80 bg-white/95 p-6 shadow-xs">
        <div className="mb-3 flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-teal-50 text-teal-600">
            <TrendingUp className="h-4 w-4" />
          </span>
          <h2 className="text-base font-bold text-slate-900">Chi tiết chỉ số xét nghiệm</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500">
                <th className="py-2 pr-4">Ngày</th>
                <th className="py-2 pr-4">Chỉ số</th>
                <th className="py-2 pr-4">Giá trị</th>
                <th className="py-2 pr-4">Đơn vị</th>
                <th className="py-2 pr-4">Ngưỡng chuẩn</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(data.labs_table || []).map((r, idx) => (
                <tr key={idx}>
                  <td className="py-2 pr-4">{parseDateParts(r.checkup_date).full}</td>
                  <td className="py-2 pr-4 font-semibold">{r.name} ({r.code})</td>
                  <td className="py-2 pr-4 font-bold text-slate-900">{r.value}</td>
                  <td className="py-2 pr-4 text-slate-500">{r.unit}</td>
                  <td className="py-2 pr-4 text-slate-500">{formatRefRange(r.normal_min, r.normal_max, '')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
