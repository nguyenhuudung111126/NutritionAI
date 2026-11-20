import { useEffect, useState } from 'react';
import {
  Activity,
  Apple,
  ArrowRight,
  BookOpen,
  Cpu,
  FileText,
  FlaskConical,
  Loader2,
  ScrollText,
  ShieldAlert,
  ShieldCheck,
  Stethoscope,
  Users,
} from 'lucide-react';
import { api } from '../api';

export default function AdminOverviewPage({ onNavigate }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .adminGetOverview()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-12 text-xs font-semibold text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin text-sky-600" /> Đang tải tổng quan hệ thống...
      </div>
    );
  }

  const stats = data?.stats || {};
  const evalSummary = data?.latest_eval?.summary || {};
  const passPct =
    evalSummary.pass_rate != null ? `${Math.round(Number(evalSummary.pass_rate) * 100)}%` : '—';

  const quickCards = [
    {
      tab: 'admin-documents',
      title: 'Quản lý Tài liệu',
      desc: `${stats.rag_docs_count || 0} tài liệu • ${stats.rag_chunks_count || 0} vector chunks`,
      icon: FileText,
      tone: 'bg-teal-50 text-teal-700',
    },
    {
      tab: 'admin-foods',
      title: 'Kho Thực phẩm',
      desc: `${stats.foods_count || 0} thực phẩm chuẩn Viện Dinh dưỡng`,
      icon: Apple,
      tone: 'bg-sky-50 text-sky-700',
    },
    {
      tab: 'admin-diseases',
      title: 'Danh mục Bệnh lý & Phác đồ',
      desc: `${stats.conditions_count || 0} nhóm bệnh • ${stats.regimes_count || 0} phác đồ BYT`,
      icon: Stethoscope,
      tone: 'bg-indigo-50 text-indigo-700',
    },
    {
      tab: 'admin-patients',
      title: 'Quản lý Tài khoản',
      desc: `${stats.active_users_count || 0} tài khoản đang hoạt động`,
      icon: Users,
      tone: 'bg-emerald-50 text-emerald-700',
    },
    {
      tab: 'admin-audit',
      title: 'Giám sát Vận hành',
      desc: `${stats.agent_runs_count || 0} traces AI • ${stats.guardrail_blocks_count || 0} cảnh báo/chặn`,
      icon: ScrollText,
      tone: 'bg-amber-50 text-amber-700',
    },
    {
      tab: 'admin-evals',
      title: 'Đánh giá Hệ thống',
      desc: `Tỷ lệ an toàn y khoa gần nhất: ${passPct}`,
      icon: Cpu,
      tone: 'bg-violet-50 text-violet-700',
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-sky-100 px-3 py-0.5 text-[11px] font-bold text-sky-800">
            <ShieldCheck className="h-3.5 w-3.5" /> Trung tâm Quản trị Hệ thống
          </div>
          <h1 className="mt-1.5 text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
            Tổng quan Dữ liệu & Vận hành AI
          </h1>
          <p className="mt-1 text-xs text-slate-600">
            Theo dõi toàn diện dữ liệu lâm sàng, kho tri thức RAG pgvector, người dùng và độ an toàn của Agent.
          </p>
        </div>

        <span
          className={`rounded-full px-3.5 py-1.5 text-xs font-bold ${
            data?.langfuse_enabled ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
          }`}
        >
          {data?.langfuse_enabled ? 'Langfuse Cloud: ĐANG BẬT' : 'Audit Log: PostgreSQL Local'}
        </span>
      </div>

      {/* Top 4 KPI Cards */}
      <div className="grid grid-cols-2 gap-3.5 lg:grid-cols-4">
        <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-xs">
          <div className="flex items-center justify-between text-[11px] font-bold uppercase text-slate-400">
            <span>Kho Thực phẩm</span>
            <Apple className="h-4 w-4 text-sky-600" />
          </div>
          <div className="mt-2 text-2xl font-extrabold text-slate-900 tabular-nums">
            {stats.foods_count || 0}
          </div>
          <div className="text-xs text-slate-500">nguyên liệu chuẩn hóa</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-xs">
          <div className="flex items-center justify-between text-[11px] font-bold uppercase text-slate-400">
            <span>Tài liệu RAG</span>
            <BookOpen className="h-4 w-4 text-teal-600" />
          </div>
          <div className="mt-2 text-2xl font-extrabold text-teal-700 tabular-nums">
            {stats.rag_docs_count || 0}
          </div>
          <div className="text-xs text-slate-500">{stats.rag_chunks_count || 0} vector chunks</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-xs">
          <div className="flex items-center justify-between text-[11px] font-bold uppercase text-slate-400">
            <span>Bệnh nhân & Thực đơn</span>
            <Users className="h-4 w-4 text-indigo-600" />
          </div>
          <div className="mt-2 text-2xl font-extrabold text-slate-900 tabular-nums">
            {stats.patients_count || 0}
          </div>
          <div className="text-xs text-slate-500">{stats.meal_plans_count || 0} thực đơn đã lập</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-4 shadow-xs">
          <div className="flex items-center justify-between text-[11px] font-bold uppercase text-slate-400">
            <span>Safety Evals</span>
            <FlaskConical className="h-4 w-4 text-emerald-600" />
          </div>
          <div className="mt-2 text-2xl font-extrabold text-emerald-700 tabular-nums">{passPct}</div>
          <div className="text-xs text-slate-500">
            {evalSummary.passed ?? 0}/{evalSummary.total ?? 0} ca đạt gần nhất
          </div>
        </div>
      </div>

      {/* Quick Module Directory */}
      <section className="space-y-3">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500">
          Phân hệ Quản trị Chuyên biệt
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {quickCards.map(({ tab, title, desc, icon: Icon, tone }) => (
            <button
              key={tab}
              type="button"
              onClick={() => onNavigate(tab)}
              className="group flex items-start justify-between gap-3 rounded-2xl border border-slate-200/80 bg-white/95 p-4 text-left shadow-xs transition hover:-translate-y-0.5 hover:border-sky-300 hover:shadow-md"
            >
              <div className="flex items-start gap-3">
                <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${tone}`}>
                  <Icon className="h-5 w-5" />
                </span>
                <div>
                  <div className="text-sm font-bold text-slate-900 group-hover:text-sky-700">{title}</div>
                  <div className="mt-0.5 text-xs text-slate-500">{desc}</div>
                </div>
              </div>
              <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-sky-600" />
            </button>
          ))}
        </div>
      </section>

      {/* Recent AI Activity */}
      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-xs space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-sky-600" />
            <h2 className="text-base font-bold text-slate-900">Hoạt động AI Agent gần nhất</h2>
          </div>
          <button
            type="button"
            onClick={() => onNavigate('admin-audit')}
            className="text-xs font-bold text-sky-600 hover:underline"
          >
            Xem toàn bộ Audit →
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-[11px] font-bold uppercase text-slate-400">
                <th className="py-2 pr-3">ID</th>
                <th className="py-2 px-3">Workflow</th>
                <th className="py-2 px-3">Model</th>
                <th className="py-2 px-3">Độ trễ</th>
                <th className="py-2 pl-3">Trạng thái</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(data?.recent_runs || []).map((r) => (
                <tr key={r.id}>
                  <td className="py-2 pr-3 font-semibold text-slate-700">#{r.id}</td>
                  <td className="py-2 px-3 font-medium text-slate-900">{r.workflow}</td>
                  <td className="py-2 px-3 text-slate-500">{r.model_name || '—'}</td>
                  <td className="py-2 px-3 tabular-nums">{r.latency_ms ?? '—'} ms</td>
                  <td className="py-2 pl-3">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                        r.status === 'SUCCESS'
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-rose-100 text-rose-800'
                      }`}
                    >
                      {r.status}
                    </span>
                  </td>
                </tr>
              ))}
              {(data?.recent_runs || []).length === 0 && (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-slate-400">
                    Chưa có lượt chạy Agent nào được ghi nhận.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
