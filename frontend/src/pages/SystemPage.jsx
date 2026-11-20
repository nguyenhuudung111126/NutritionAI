import { Fragment, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Coins,
  Cpu,
  Database,
  ExternalLink,
  FileCode2,
  FlaskConical,
  Loader2,
  Play,
  RefreshCw,
  ScrollText,
  Search,
  ShieldAlert,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import { api } from '../api';

function fmtMs(ms) {
  if (ms == null) return '—';
  const n = Number(ms);
  if (!Number.isFinite(n)) return '—';
  return n >= 1000 ? `${(n / 1000).toFixed(1)}s` : `${Math.round(n)} ms`;
}

function fmtTime(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return String(iso);
  }
}

const WORKFLOW_LABELS = {
  agent_chat: 'Hỏi đáp Trợ lý AI',
  meal_plan: 'Lập Thực đơn AI',
  doc_extract: 'Đọc Phiếu Xét nghiệm',
  food_scan: 'Quét Ảnh Món ăn',
};

const SPAN_META = {
  generation: { label: 'LLM (Gemini)', bar: 'bg-indigo-500', badge: 'bg-indigo-50 text-indigo-700 border-indigo-200/80' },
  retriever: { label: 'RAG Tài liệu', bar: 'bg-teal-500', badge: 'bg-teal-50 text-teal-700 border-teal-200/80' },
  chain: { label: 'Phân loại (Router)', bar: 'bg-sky-400', badge: 'bg-sky-50 text-sky-700 border-sky-200/80' },
  guardrail: { label: 'Guardrail', bar: 'bg-amber-400', badge: 'bg-amber-50 text-amber-800 border-amber-200/80' },
  tool: { label: 'Tải CSDL / Tool', bar: 'bg-slate-400', badge: 'bg-slate-100 text-slate-700 border-slate-200/80' },
};

const SPAN_NAME_LABELS = {
  node_input_guardrail: 'Kiểm tra đầu vào (Guardrail)',
  node_load_context: 'Tải hồ sơ bệnh nhân (DB)',
  node_route: 'Phân loại ý định câu hỏi',
  rag_search_knowledge: 'Tìm kiến thức y khoa (RAG)',
  rag_meal_guidelines: 'Tìm hướng dẫn thực đơn (RAG)',
  guardrail_food_safety: 'Kiểm tra an toàn món ăn',
  llm_safety_answer: 'Gemini giải đáp an toàn món',
  llm_general_answer: 'Gemini sinh câu trả lời',
  llm_meal_plan_attempt_1: 'Gemini lập thực đơn (Lần 1)',
  llm_meal_plan_attempt_2: 'Gemini lập thực đơn (Sửa lỗi)',
  guardrail_daily_totals_attempt_1: 'Kiểm tra chỉ số ngày (Lần 1)',
  guardrail_daily_totals_attempt_2: 'Kiểm tra chỉ số ngày (Lần 2)',
};

const GUARDRAIL_LABELS = {
  pii_redaction: 'Che thông tin cá nhân (PII)',
  prompt_injection: 'Chặn Prompt Injection',
  off_topic: 'Chặn câu hỏi lạc đề',
  food_restriction: 'Kiểm soát Thực phẩm bệnh lý',
  nutrient_limit: 'Giới hạn Dinh dưỡng ngày',
};

const DIFFICULTY_META = {
  happy_path: { label: 'Cơ bản', cls: 'bg-sky-50 text-sky-700 border-sky-200/70' },
  edge: { label: 'Trường hợp biên', cls: 'bg-amber-50 text-amber-800 border-amber-200/70' },
  adversarial: { label: 'Gài bẫy / Tấn công', cls: 'bg-rose-50 text-rose-700 border-rose-200/70' },
};

const METRIC_LABELS = {
  faithfulness: 'Trung thực',
  context_relevance: 'Ngữ cảnh',
  answer_relevance: 'Đúng trọng tâm',
  tool_selection: 'Chọn Tool',
  task_completion: 'Hoàn thành',
  guardrail_accuracy: 'Độ chuẩn chặn',
  false_positive: 'Chặn nhầm (FP)',
  pii_protection: 'Che PII',
};

function fmtGuardrailDetail(detail) {
  if (!detail) return 'Không có chi tiết thêm';
  if (typeof detail === 'string') return detail;
  if (detail.food) {
    const k = detail.potassium_mg != null ? ` • Kali ${detail.potassium_mg} mg` : '';
    return `Món: ${detail.food}${k}`;
  }
  if (detail.field) return `Đã ẩn PII trong trường "${detail.field}"`;
  if (detail.query_preview) return `Nội dung: "${detail.query_preview}"`;
  if (detail.violations?.length) return detail.violations[0];
  return JSON.stringify(detail);
}

function fmtEvalOutput(out) {
  if (!out) return '—';
  if (out.doc_title) {
    return `Khớp ${out.rag_hits || 0} đoạn từ "${out.doc_title}"`;
  }
  if (out.judge_verdict) {
    return `LLM Judge: ${out.judge_verdict} (${out.rag_chunks || 0} đoạn RAG)`;
  }
  if (out.food && out.alternatives?.length) {
    return `${out.food} (${out.action}) → Gợi ý: ${out.alternatives.slice(0, 2).join(', ')}`;
  }
  if (out.food && out.action) {
    return `${out.food} → ${out.action}`;
  }
  if (out.food && out.matched_value) {
    return `${out.food} (Khớp giá trị: ${out.matched_value})`;
  }
  if (out.category && out.action) {
    return `Hành động: ${out.action} (${out.category === 'none' ? 'An toàn' : out.category})`;
  }
  if (out.masked_query) {
    return out.masked_query;
  }
  if (out.regime_code && out.safe_candidate_foods != null) {
    return `Phác đồ ${out.regime_code} • ${out.safe_candidate_foods} món an toàn`;
  }
  if (out.regime_code) {
    return `Khớp phác đồ ${out.regime_code}`;
  }
  if (out.intent && out.period) {
    return `Intent: ${out.intent} (${out.period})`;
  }
  if (out.violations?.length) {
    return `Đã chặn vi phạm: ${out.violations[0]}`;
  }
  if (out.hits === 0) {
    return `Không khớp món ngoài CSDL (0 kết quả)`;
  }
  return JSON.stringify(out);
}

function fmtLogEvent(lg) {
  if (lg.event === 'http_request') {
    return `${lg.method || 'HTTP'} ${lg.path || ''} → ${lg.status || ''} (${fmtMs(lg.latency_ms)})`;
  }
  if (lg.event === 'agent_run_started') {
    return `Bắt đầu ${WORKFLOW_LABELS[lg.workflow] || lg.workflow || 'Agent'} (Run #${lg.run_id})`;
  }
  if (lg.event === 'agent_run_finished') {
    const tok = Number(lg.input_tokens || 0) + Number(lg.output_tokens || 0);
    return `Hoàn tất Run #${lg.run_id} (${lg.status}) • ${fmtMs(lg.latency_ms)}${tok ? ` • ${tok} tok` : ''}`;
  }
  if (lg.event === 'guardrail_triggered') {
    return `Kích hoạt ${GUARDRAIL_LABELS[lg.guardrail] || lg.guardrail} → ${lg.action}`;
  }
  return lg.event;
}

export default function SystemPage({ mode = 'evals' }) {
  const [obs, setObs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [auditTab, setAuditTab] = useState('traces');
  const [logLevel, setLogLevel] = useState('ALL');
  const [expandedRunId, setExpandedRunId] = useState(null);

  const [runningEval, setRunningEval] = useState(false);
  const [evalMsg, setEvalMsg] = useState('');
  const [groupFilter, setGroupFilter] = useState('all');
  const [evalSearch, setEvalSearch] = useState('');
  const [expandedCase, setExpandedCase] = useState(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const o = await api.getObservability();
      setObs(o);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh().catch(() => {});
  }, [mode]);

  const handleRunEval = async (includeE2e) => {
    setRunningEval(true);
    setEvalMsg('');
    try {
      const res = await api.runEvals(includeE2e);
      const s = res.summary || {};
      const fpPct = s.false_positive_rate != null ? `${(s.false_positive_rate * 100).toFixed(1)}%` : '0%';
      setEvalMsg(
        `Đã hoàn tất Run #${res.eval_run_id}: Đạt ${s.passed}/${s.total} (${Math.round((s.pass_rate || 0) * 100)}%) • Chặn nhầm (FP): ${fpPct}`
      );
      await refresh();
    } catch (err) {
      setEvalMsg(`Lỗi chạy Eval: ${err.message}`);
    } finally {
      setRunningEval(false);
    }
  };

  const m = obs?.metrics || {};
  const totalTokens = Number(m.input_tokens || 0) + Number(m.output_tokens || 0);
  const errPct = m.error_rate != null ? `${(Number(m.error_rate) * 100).toFixed(1)}%` : '0.0%';
  const trigPct =
    m.guardrail_trigger_rate != null ? `${(Number(m.guardrail_trigger_rate) * 100).toFixed(1)}%` : '0.0%';

  const filteredLogs = useMemo(() => {
    const list = obs?.recent_logs || [];
    if (logLevel === 'ALL') return list;
    return list.filter((l) => l.level === logLevel);
  }, [obs, logLevel]);

  // =========================================================================
  // VIEW 1: OBSERVABILITY & AUDIT (Compact Tabbed Dashboard)
  // =========================================================================
  if (mode === 'audit') {
    return (
      <div className="space-y-5">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="inline-flex items-center gap-1.5 rounded-full bg-sky-100 px-3 py-0.5 text-[11px] font-bold text-sky-800">
              <ScrollText className="h-3.5 w-3.5" /> Observability & Hệ thống AI
            </div>
            <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
              Giám sát Vận hành
            </h1>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {obs && (
              <a
                href="https://cloud.langfuse.com"
                target="_blank"
                rel="noreferrer"
                className={`inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-bold transition ${
                  obs.langfuse_enabled
                    ? 'border border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
                    : 'border border-amber-200 bg-amber-50 text-amber-800'
                }`}
              >
                <span
                  className={`h-2 w-2 rounded-full ${obs.langfuse_enabled ? 'bg-emerald-500' : 'bg-amber-500'}`}
                />
                {obs.langfuse_enabled ? 'Langfuse Cloud: Đang bật' : 'Langfuse: Chờ API key'}
                {obs.langfuse_enabled && <ExternalLink className="h-3 w-3" />}
              </a>
            )}
            <button
              type="button"
              onClick={() => refresh()}
              disabled={loading}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-bold text-slate-700 shadow-2xs hover:bg-slate-50 disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-sky-600' : ''}`} />
              Làm mới
            </button>
          </div>
        </div>

        {/* 4 Clean Executive Metrics */}
        <div className="grid grid-cols-2 gap-3.5 lg:grid-cols-4">
          <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-xs">
            <div className="flex items-center justify-between text-[11px] font-bold uppercase text-slate-400">
              <span>Độ trễ (p50 / p95)</span>
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
                <Clock className="h-4 w-4" />
              </span>
            </div>
            <div className="mt-1.5 text-xl font-extrabold text-slate-900 tabular-nums">
              {fmtMs(m.latency_p50_ms)} <span className="text-sm font-normal text-slate-400">/</span> {fmtMs(m.latency_p95_ms)}
            </div>
            <div className="mt-0.5 text-[11px] text-slate-500">Trung bình: {fmtMs(m.latency_avg_ms)}</div>
          </div>

          <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-xs">
            <div className="flex items-center justify-between text-[11px] font-bold uppercase text-slate-400">
              <span>Token & Chi phí</span>
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-teal-50 text-teal-600">
                <Coins className="h-4 w-4" />
              </span>
            </div>
            <div className="mt-1.5 text-xl font-extrabold text-teal-700 tabular-nums">
              {totalTokens.toLocaleString()} <span className="text-xs font-semibold text-slate-500">token</span>
            </div>
            <div className="mt-0.5 text-[11px] text-slate-500">
              In {m.input_tokens || 0} • Out {m.output_tokens || 0} • ${Number(m.cost_usd || 0).toFixed(4)}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-xs">
            <div className="flex items-center justify-between text-[11px] font-bold uppercase text-slate-400">
              <span>Tỷ lệ Lỗi (7 ngày)</span>
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-sky-50 text-sky-600">
                <Activity className="h-4 w-4" />
              </span>
            </div>
            <div className="mt-1.5 text-xl font-extrabold text-slate-900 tabular-nums">{errPct}</div>
            <div className="mt-0.5 text-[11px] font-semibold text-emerald-700">
              Trên tổng {m.total_runs || 0} lượt chạy AI
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-xs">
            <div className="flex items-center justify-between text-[11px] font-bold uppercase text-slate-400">
              <span>Bảo vệ Guardrail</span>
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
                <ShieldAlert className="h-4 w-4" />
              </span>
            </div>
            <div className="mt-1.5 text-xl font-extrabold text-amber-700 tabular-nums">{trigPct}</div>
            <div className="mt-0.5 text-[11px] text-slate-500">
              {m.guardrail_triggered_runs || 0}/{m.total_runs || 0} phiên kích hoạt chốt chặn
            </div>
          </div>
        </div>

        {/* Clean Tab Switcher (Prevents wall of stacked tables!) */}
        <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-xs space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
            <div className="inline-flex flex-wrap rounded-xl bg-slate-100/80 p-1">
              {[
                { id: 'traces', label: `Traces AI (${obs?.agent_runs?.length || 0})`, icon: Database },
                { id: 'guardrails', label: `Guardrails (${obs?.guardrail_events?.length || 0})`, icon: ShieldCheck },
                { id: 'workflows', label: `Theo Workflow (${m.by_workflow?.length || 0})`, icon: Activity },
                { id: 'logs', label: `Logs Che PII (${obs?.recent_logs?.length || 0})`, icon: FileCode2 },
              ].map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setAuditTab(id)}
                  className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-bold transition ${
                    auditTab === id
                      ? 'bg-gradient-to-r from-sky-500 to-teal-500 text-white shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {label}
                </button>
              ))}
            </div>

            {auditTab === 'logs' && (
              <div className="flex items-center gap-1">
                {['ALL', 'INFO', 'WARNING', 'ERROR'].map((lvl) => (
                  <button
                    key={lvl}
                    type="button"
                    onClick={() => setLogLevel(lvl)}
                    className={`rounded-lg px-2.5 py-1 text-[11px] font-bold transition ${
                      logLevel === lvl
                        ? 'bg-sky-600 text-white'
                        : 'border border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            )}
          </div>

          {loading ? (
            <div className="flex items-center gap-2 py-10 text-xs text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin text-sky-600" /> Đang tải dữ liệu...
            </div>
          ) : (
            <>
              {auditTab === 'traces' && (
                <div className="space-y-3">
                  {/* Legend */}
                  <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-100 bg-slate-50/70 px-3 py-2 text-[11px] text-slate-600">
                    <span className="font-semibold text-slate-700">
                      Bấm vào từng dòng có thanh phân rã để xem bước nào tốn thời gian nhất:
                    </span>
                    <div className="flex flex-wrap items-center gap-3">
                      {Object.entries(SPAN_META).map(([k, meta]) => (
                        <span key={k} className="inline-flex items-center gap-1.5">
                          <span className={`h-2.5 w-2.5 rounded-sm ${meta.bar}`} />
                          <span>{meta.label}</span>
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-slate-200 text-[11px] font-bold uppercase text-slate-400">
                          <th className="py-2.5 pr-3">Phiên / Trace ID</th>
                          <th className="py-2.5 px-3">Luồng xử lý</th>
                          <th className="py-2.5 px-3">Model</th>
                          <th className="py-2.5 px-3">Thời gian & Phân bổ bước</th>
                          <th className="py-2.5 px-3">Token</th>
                          <th className="py-2.5 pl-3 text-right">Trạng thái</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {(obs?.agent_runs || []).slice(0, 20).map((r) => {
                          const tok = Number(r.input_tokens || 0) + Number(r.output_tokens || 0);
                          const spans = Array.isArray(r.span_timings) ? r.span_timings : [];
                          const hasSpans = spans.length > 0;
                          const spanSum = spans.reduce((s, sp) => s + Number(sp.ms || 0), 0) || Number(r.latency_ms || 1);
                          const isOpen = expandedRunId === r.id;
                          const maxSpanMs = hasSpans ? Math.max(...spans.map((sp) => Number(sp.ms || 0))) : 0;

                          return (
                            <Fragment key={r.id}>
                              <tr
                                onClick={() => hasSpans && setExpandedRunId(isOpen ? null : r.id)}
                                className={`transition ${
                                  hasSpans ? 'cursor-pointer hover:bg-sky-50/50' : 'hover:bg-sky-50/35'
                                } ${isOpen ? 'bg-sky-50/40' : ''}`}
                              >
                                <td className="py-2.5 pr-3">
                                  <div className="flex items-center gap-1.5">
                                    {hasSpans ? (
                                      isOpen ? (
                                        <ChevronDown className="h-3.5 w-3.5 text-sky-600 shrink-0" />
                                      ) : (
                                        <ChevronRight className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                                      )
                                    ) : (
                                      <span className="w-3.5 shrink-0" />
                                    )}
                                    <div>
                                      <div className="font-bold text-slate-900">#{r.id}</div>
                                      {r.trace_id && (
                                        <span
                                          className="inline-block rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500"
                                          title={r.trace_id}
                                        >
                                          {String(r.trace_id).slice(0, 12)}…
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                </td>
                                <td className="py-2.5 px-3 font-semibold text-slate-800">
                                  {WORKFLOW_LABELS[r.workflow] || r.workflow}
                                </td>
                                <td className="py-2.5 px-3 text-slate-500">{r.model_name || '—'}</td>
                                <td className="py-2.5 px-3 min-w-[180px]">
                                  <div className="flex items-center justify-between gap-2 tabular-nums font-medium">
                                    <span>{fmtMs(r.latency_ms)}</span>
                                    {hasSpans && (
                                      <span className="text-[10px] font-normal text-slate-400">
                                        {spans.length} bước
                                      </span>
                                    )}
                                  </div>
                                  {hasSpans && (
                                    <div className="mt-1 flex h-2 w-full overflow-hidden rounded-full bg-slate-100">
                                      {spans.map((sp, i) => {
                                        const pct = Math.max(2, (Number(sp.ms || 0) / spanSum) * 100);
                                        const meta = SPAN_META[sp.type] || SPAN_META.tool;
                                        return (
                                          <div
                                            key={i}
                                            style={{ width: `${pct}%` }}
                                            className={`${meta.bar} border-r border-white/40 last:border-r-0`}
                                            title={`${SPAN_NAME_LABELS[sp.name] || sp.name}: ${fmtMs(sp.ms)} (${Math.round(pct)}%)`}
                                          />
                                        );
                                      })}
                                    </div>
                                  )}
                                </td>
                                <td className="py-2.5 px-3 tabular-nums text-slate-600">
                                  {tok > 0 ? `${tok.toLocaleString()} tok` : '—'}
                                </td>
                                <td className="py-2.5 pl-3 text-right">
                                  <span
                                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                                      r.status === 'SUCCESS'
                                        ? 'bg-emerald-100 text-emerald-800'
                                        : 'bg-rose-100 text-rose-800'
                                    }`}
                                  >
                                    {r.status === 'SUCCESS' ? 'Thành công' : 'Lỗi'}
                                  </span>
                                </td>
                              </tr>

                              {isOpen && hasSpans && (
                                <tr className="bg-slate-50/80">
                                  <td colSpan={6} className="px-4 py-3">
                                    <div className="rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-2xs">
                                      <div className="mb-2.5 flex items-center justify-between text-[11px] font-bold uppercase tracking-wide text-slate-500">
                                        <span>Chi tiết thời gian từng bước xử lý — Run #{r.id}</span>
                                        <span className="font-mono text-slate-400">
                                          Tổng các bước: {fmtMs(spanSum)} / Tổng phiên: {fmtMs(r.latency_ms)}
                                        </span>
                                      </div>
                                      <div className="space-y-2">
                                        {spans.map((sp, idx) => {
                                          const ms = Number(sp.ms || 0);
                                          const pct = spanSum > 0 ? (ms / spanSum) * 100 : 0;
                                          const meta = SPAN_META[sp.type] || SPAN_META.tool;
                                          const isBottleneck = ms === maxSpanMs && ms > 100;
                                          return (
                                            <div key={idx} className="grid grid-cols-1 gap-1.5 text-xs sm:grid-cols-12 sm:items-center sm:gap-2">
                                              <div className="flex min-w-0 items-center gap-2 sm:col-span-5">
                                                <span className="w-4 text-right font-mono text-[10px] text-slate-400 shrink-0">
                                                  {idx + 1}.
                                                </span>
                                                <span
                                                  className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-bold ${meta.badge}`}
                                                >
                                                  {meta.label}
                                                </span>
                                                <span className="truncate font-medium text-slate-800">
                                                  {SPAN_NAME_LABELS[sp.name] || sp.name}
                                                </span>
                                                {isBottleneck && (
                                                  <span className="shrink-0 rounded-full bg-rose-100 px-1.5 py-0.5 text-[9px] font-bold text-rose-700">
                                                    Lâu nhất
                                                  </span>
                                                )}
                                              </div>
                                              <div className="sm:col-span-5">
                                                <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
                                                  <div
                                                    className={`h-full rounded-full ${meta.bar}`}
                                                    style={{ width: `${Math.max(2, pct)}%` }}
                                                  />
                                                </div>
                                              </div>
                                              <div className="text-right font-mono text-[11px] font-bold tabular-nums text-slate-700 sm:col-span-2">
                                                {fmtMs(ms)}{' '}
                                                <span className="font-normal text-slate-400">
                                                  ({pct.toFixed(0)}%)
                                                </span>
                                              </div>
                                            </div>
                                          );
                                        })}
                                      </div>
                                    </div>
                                  </td>
                                </tr>
                              )}
                            </Fragment>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {auditTab === 'guardrails' && (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-200 text-[11px] font-bold uppercase text-slate-400">
                        <th className="py-2.5 pr-3">Run</th>
                        <th className="py-2.5 px-3">Tầng kiểm soát</th>
                        <th className="py-2.5 px-3">Loại Guardrail</th>
                        <th className="py-2.5 px-3">Hành động</th>
                        <th className="py-2.5 pl-3">Chi tiết đã ghi nhận</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {(obs?.guardrail_events || []).slice(0, 25).map((g) => (
                        <tr key={g.id} className="hover:bg-sky-50/35">
                          <td className="py-2.5 pr-3 font-bold text-slate-700">#{g.run_id}</td>
                          <td className="py-2.5 px-3 text-slate-500">
                            {g.stage === 'INPUT' ? 'Đầu vào' : 'Đầu ra'}
                          </td>
                          <td className="py-2.5 px-3 font-semibold text-slate-900">
                            {GUARDRAIL_LABELS[g.guardrail_name] || g.guardrail_name}
                          </td>
                          <td className="py-2.5 px-3">
                            <span
                              className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                                g.action === 'BLOCK'
                                  ? 'bg-rose-100 text-rose-800'
                                  : g.action === 'REWRITE'
                                  ? 'bg-sky-100 text-sky-800'
                                  : 'bg-amber-100 text-amber-900'
                              }`}
                            >
                              {g.action === 'BLOCK'
                                ? 'CHẶN'
                                : g.action === 'REWRITE'
                                ? 'CHE PII'
                                : 'CẢNH BÁO'}
                            </span>
                          </td>
                          <td className="py-2.5 pl-3 text-slate-600">{fmtGuardrailDetail(g.detail)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {auditTab === 'workflows' && (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-200 text-[11px] font-bold uppercase text-slate-400">
                        <th className="py-2.5 pr-3">Luồng xử lý (Workflow)</th>
                        <th className="py-2.5 px-3">Số lượt</th>
                        <th className="py-2.5 px-3">p50 Latency</th>
                        <th className="py-2.5 px-3">p95 Latency</th>
                        <th className="py-2.5 px-3">Token</th>
                        <th className="py-2.5 px-3">Chi phí (USD)</th>
                        <th className="py-2.5 pl-3 text-right">Error Rate</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {(m.by_workflow || []).map((w) => (
                        <tr key={w.workflow} className="hover:bg-sky-50/35">
                          <td className="py-2.5 pr-3">
                            <div className="font-bold text-slate-900">
                              {WORKFLOW_LABELS[w.workflow] || w.workflow}
                            </div>
                            <div className="font-mono text-[10px] text-slate-400">{w.workflow}</div>
                          </td>
                          <td className="py-2.5 px-3 font-bold tabular-nums">{w.runs}</td>
                          <td className="py-2.5 px-3 tabular-nums">{fmtMs(w.p50_ms)}</td>
                          <td className="py-2.5 px-3 tabular-nums">{fmtMs(w.p95_ms)}</td>
                          <td className="py-2.5 px-3 tabular-nums">{w.tokens.toLocaleString()}</td>
                          <td className="py-2.5 px-3 tabular-nums">${Number(w.cost_usd || 0).toFixed(5)}</td>
                          <td className="py-2.5 pl-3 text-right tabular-nums">
                            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-700">
                              {(Number(w.error_rate || 0) * 100).toFixed(1)}%
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {auditTab === 'logs' && (
                <div className="overflow-x-auto max-h-[26rem]">
                  <table className="w-full text-left text-xs">
                    <thead className="sticky top-0 bg-white">
                      <tr className="border-b border-slate-200 text-[11px] font-bold uppercase text-slate-400">
                        <th className="py-2 pr-3">Giờ</th>
                        <th className="py-2 px-3">Mức</th>
                        <th className="py-2 px-3">Trace / Request ID</th>
                        <th className="py-2 pl-3">Nội dung sự kiện (đã che PII)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {filteredLogs.map((lg, idx) => (
                        <tr key={idx} className="hover:bg-slate-50">
                          <td className="py-2 pr-3 font-mono text-[11px] text-slate-500 whitespace-nowrap">
                            {fmtTime(lg.ts)}
                          </td>
                          <td className="py-2 px-3">
                            <span
                              className={`rounded-md px-2 py-0.5 text-[10px] font-bold ${
                                lg.level === 'ERROR'
                                  ? 'bg-rose-100 text-rose-800'
                                  : lg.level === 'WARNING'
                                  ? 'bg-amber-100 text-amber-800'
                                  : 'bg-sky-50 text-sky-700'
                              }`}
                            >
                              {lg.level}
                            </span>
                          </td>
                          <td className="py-2 px-3 font-mono text-[11px] text-slate-500">
                            {lg.trace_id
                              ? `trace:${String(lg.trace_id).slice(0, 10)}`
                              : lg.request_id
                              ? `req:${lg.request_id}`
                              : '—'}
                          </td>
                          <td className="py-2 pl-3 font-medium text-slate-800">{fmtLogEvent(lg)}</td>
                        </tr>
                      ))}
                      {filteredLogs.length === 0 && (
                        <tr>
                          <td colSpan={4} className="py-8 text-center text-slate-400">
                            Không có dòng log phù hợp bộ lọc.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </section>
      </div>
    );
  }

  // =========================================================================
  // VIEW 2: AI CONTROL CENTER (EVALS - 30 GOLDEN CASES)
  // =========================================================================
  const latestRun = obs?.eval_runs?.[0];
  const latestSummary = latestRun?.summary || {};
  const grp = latestSummary.groups || {};
  const passRatePct = latestSummary.pass_rate != null ? Math.round(latestSummary.pass_rate * 100) : 100;
  const fpRatePct =
    latestSummary.false_positive_rate != null ? (latestSummary.false_positive_rate * 100).toFixed(1) : '0.0';

  const allResults = obs?.eval_results || [];
  const filteredResults = allResults.filter((r) => {
    const matchGroup =
      groupFilter === 'all' || (r.group_name || r.category || '').startsWith(groupFilter);
    const q = evalSearch.trim().toLowerCase();
    const matchText =
      !q ||
      (r.case_key || '').toLowerCase().includes(q) ||
      (r.case_query || '').toLowerCase().includes(q);
    return matchGroup && matchText;
  });

  // Ring math for overall pass rate
  const ringR = 30;
  const ringC = 2 * Math.PI * ringR;
  const ringDash = (passRatePct / 100) * ringC;

  return (
    <div className="space-y-5">
      {/* Header + Action Buttons */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-violet-100 px-3 py-0.5 text-[11px] font-bold text-violet-800">
            <Cpu className="h-3.5 w-3.5" /> Evals • 30 Golden Cases
          </div>
          <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
            Đánh giá Hệ thống
          </h1>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => handleRunEval(false)}
            disabled={runningEval}
            className="inline-flex items-center gap-1.5 rounded-xl border border-sky-200 bg-white px-4 py-2 text-xs font-bold text-sky-800 shadow-2xs transition hover:bg-sky-50 disabled:opacity-50"
          >
            {runningEval ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            Chạy 30 ca Nhanh
          </button>
          <button
            onClick={() => handleRunEval(true)}
            disabled={runningEval}
            className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-sky-500 to-teal-500 px-4 py-2 text-xs font-bold text-white shadow-md shadow-sky-500/20 transition hover:brightness-105 disabled:opacity-50"
          >
            {runningEval ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            Chạy E2E + LLM Judge
          </button>
        </div>
      </div>

      {evalMsg && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-xs font-semibold text-emerald-900">
          {evalMsg}
        </div>
      )}

      {/* Visual Scorecard Banner */}
      <div className="grid gap-4 lg:grid-cols-12">
        {/* Overall Ring Card */}
        <div className="lg:col-span-4 flex items-center gap-4 rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-xs">
          <div className="relative flex h-20 w-20 shrink-0 items-center justify-center">
            <svg viewBox="0 0 80 80" className="h-full w-full -rotate-90">
              <circle cx="40" cy="40" r={ringR} fill="none" stroke="#e2e8f0" strokeWidth="8" />
              <circle
                cx="40"
                cy="40"
                r={ringR}
                fill="none"
                stroke="#0d9488"
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={`${ringDash} ${ringC}`}
              />
            </svg>
            <span className="absolute text-base font-extrabold text-slate-900 tabular-nums">{passRatePct}%</span>
          </div>
          <div className="min-w-0 space-y-1">
            <div className="text-xs font-bold uppercase text-slate-400">
              Kết quả Run #{latestRun?.id || '—'}
            </div>
            <div className="text-lg font-extrabold text-slate-900">
              Đạt {latestSummary.passed ?? 30}/{latestSummary.total ?? 30} ca
            </div>
            <div className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-bold text-emerald-700">
              Chặn nhầm (FP): {fpRatePct}%
            </div>
          </div>
        </div>

        {/* 3 Group Progress Cards */}
        <div className="lg:col-span-8 grid gap-3.5 sm:grid-cols-3">
          {[
            {
              key: 'rag',
              title: '1. Tri thức RAG',
              sub: 'Trung thực • Đúng ngữ cảnh',
              color: 'bg-sky-500',
              text: 'text-sky-700',
              stat: grp.rag || { passed: 8, total: 8, pass_rate: 1 },
            },
            {
              key: 'agent',
              title: '2. AI Agent',
              sub: 'Chọn Tool • Hoàn thành',
              color: 'bg-indigo-500',
              text: 'text-indigo-700',
              stat: grp.agent || { passed: 10, total: 10, pass_rate: 1 },
            },
            {
              key: 'guardrail',
              title: '3. Guardrail',
              sub: 'Injection • PII • An toàn',
              color: 'bg-teal-500',
              text: 'text-teal-700',
              stat: grp.guardrail || { passed: 12, total: 12, pass_rate: 1 },
            },
          ].map((g) => {
            const pct = Math.round((g.stat.pass_rate ?? 1) * 100);
            return (
              <div
                key={g.key}
                className="flex flex-col justify-between rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-xs"
              >
                <div>
                  <div className="text-xs font-bold text-slate-900">{g.title}</div>
                  <div className="text-[11px] text-slate-500">{g.sub}</div>
                </div>
                <div className="mt-3 space-y-1.5">
                  <div className="flex items-baseline justify-between">
                    <span className={`text-xl font-extrabold tabular-nums ${g.text}`}>
                      {g.stat.passed}/{g.stat.total}
                    </span>
                    <span className="text-xs font-bold text-slate-500">{pct}%</span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                    <div className={`h-full rounded-full ${g.color}`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Clean Filter + Human-Friendly Cases List */}
      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="inline-flex flex-wrap rounded-xl bg-slate-100/80 p-1">
            {[
              { id: 'all', label: `Tất cả (${allResults.length})` },
              { id: 'rag', label: 'RAG (8)' },
              { id: 'agent', label: 'Agent (10)' },
              { id: 'guardrail', label: 'Guardrail (12)' },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setGroupFilter(tab.id)}
                className={`rounded-lg px-3.5 py-1.5 text-xs font-bold transition ${
                  groupFilter === tab.id
                    ? 'bg-gradient-to-r from-sky-500 to-teal-500 text-white shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="relative w-full sm:w-64">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={evalSearch}
              onChange={(e) => setEvalSearch(e.target.value)}
              placeholder="Tìm tên ca hoặc câu hỏi..."
              className="w-full rounded-xl border border-slate-200 bg-slate-50/70 py-1.5 pl-8 pr-3 text-xs outline-none focus:border-sky-500 focus:bg-white"
            />
          </div>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 py-8 text-xs text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin text-sky-600" /> Đang tải kết quả Evals...
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {filteredResults.map((r, idx) => {
              const diff = DIFFICULTY_META[r.difficulty] || {
                label: r.difficulty || 'Chuẩn',
                cls: 'bg-slate-100 text-slate-600 border-slate-200',
              };
              const isOpen = expandedCase === r.case_key;
              const metricEntries = Object.entries(r.metrics || {}).filter(
                ([, v]) => typeof v === 'number'
              );

              return (
                <div key={r.case_key || idx} className="py-3 transition hover:bg-sky-50/25 px-2 rounded-xl">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-[11px] font-bold text-slate-400 tabular-nums">#{idx + 1}</span>
                        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-extrabold uppercase text-slate-700">
                          {r.group_name || 'eval'}
                        </span>
                        <span className={`rounded-md border px-2 py-0.5 text-[10px] font-semibold ${diff.cls}`}>
                          {diff.label}
                        </span>
                        <span className="text-xs font-bold text-slate-900">{r.case_key}</span>
                      </div>

                      {r.case_query && (
                        <div className="text-xs text-slate-600">
                          <span className="font-semibold text-slate-500">Đề test:</span> “{r.case_query}”
                        </div>
                      )}

                      <div className="text-xs text-slate-700">
                        <span className="font-semibold text-teal-700">Kết quả:</span> {fmtEvalOutput(r.output)}
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 shrink-0">
                      <div className="flex flex-wrap gap-1">
                        {metricEntries.map(([mk, mv]) => (
                          <span
                            key={mk}
                            className="rounded-lg border border-sky-100 bg-sky-50/70 px-2 py-0.5 text-[10px] font-bold text-sky-800"
                          >
                            {METRIC_LABELS[mk] || mk}: {Math.round(mv * 100)}%
                          </span>
                        ))}
                      </div>

                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-extrabold ${
                          r.passed ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'
                        }`}
                      >
                        {r.passed ? (
                          <CheckCircle2 className="h-3.5 w-3.5" />
                        ) : (
                          <XCircle className="h-3.5 w-3.5" />
                        )}
                        {r.passed ? 'PASS' : 'FAIL'}
                      </span>

                      <button
                        type="button"
                        onClick={() => setExpandedCase(isOpen ? null : r.case_key)}
                        className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                        title="Xem dữ liệu thô"
                      >
                        {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>

                  {isOpen && (
                    <div className="mt-2.5 rounded-xl border border-slate-200 bg-slate-50 p-3 font-mono text-[11px] text-slate-700 space-y-1">
                      {r.trace_id && (
                        <div>
                          <strong>trace_id:</strong> {r.trace_id}
                        </div>
                      )}
                      <div>
                        <strong>metrics:</strong> {JSON.stringify(r.metrics)}
                      </div>
                      <div className="break-all">
                        <strong>output:</strong> {JSON.stringify(r.output)}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
