import { useState } from 'react';
import { BookOpen, Bot, Loader2, Send, ShieldAlert, ShieldCheck, User } from 'lucide-react';
import { api } from '../api';

const QUICK_PROMPTS = [
  '100g thịt gà ta có bao nhiêu đạm?',
  'Tôi ăn rau ngót được không?',
  'Người suy thận mạn có ăn được quả khế không?',
  'Cách luộc rau để giảm Kali cho người bệnh thận?',
];

export default function AssistantPage({ patientId, patientName }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const sendMessage = async (text) => {
    const q = text.trim();
    if (!q || !patientId || loading) return;
    setMessages((prev) => [...prev, { role: 'user', content: q }]);
    setInput('');
    setLoading(true);
    try {
      const res = await api.chat(patientId, q);
      setMessages((prev) => [...prev, { role: 'assistant', content: res.final_response, meta: res }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', content: `Lỗi xử lý: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
          Trợ lý Dinh dưỡng AI
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Tư vấn theo hồ sơ bệnh nhân <strong className="text-slate-900">{patientName}</strong>
        </p>
      </div>

      {/* Quick Prompt Chips */}
      <div className="flex flex-wrap gap-2">
        {QUICK_PROMPTS.map((q) => (
          <button
            key={q}
            onClick={() => sendMessage(q)}
            disabled={loading}
            className="rounded-xl border border-sky-200 bg-white px-3.5 py-1.5 text-xs font-medium text-sky-900 shadow-2xs transition hover:bg-sky-50 disabled:opacity-50"
          >
            {q}
          </button>
        ))}
      </div>

      {/* Chat Box */}
      <div className="flex h-[560px] flex-col rounded-xl border border-sky-100 bg-white/95 shadow-sm overflow-hidden">
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center text-center text-slate-400">
              <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-lg bg-sky-50 text-sky-600">
                <Bot className="h-6 w-6" />
              </span>
              <p className="text-sm font-medium text-slate-600">Chọn 1 câu hỏi gợi ý hoặc nhập câu hỏi của bạn</p>
            </div>
          )}

          {messages.map((m, idx) => (
            <div key={idx} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {m.role === 'assistant' && (
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500 to-teal-400 text-white shadow-2xs">
                  <Bot className="h-4 w-4" />
                </span>
              )}
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-gradient-to-r from-sky-500 to-sky-600 text-white shadow-sm shadow-sky-500/20'
                    : 'border border-sky-100 bg-sky-50/35 text-slate-800'
                }`}
              >
                <div className="whitespace-pre-wrap">{m.content}</div>

                {m.meta && (
                  <div className="mt-3 space-y-2 border-t border-slate-200/80 pt-2.5 text-[11px]">
                    <div className="flex flex-wrap gap-1.5">
                      {m.meta.guardrail_passed ? (
                        <span className="inline-flex items-center gap-1 rounded-md bg-emerald-100 px-2 py-0.5 font-bold text-emerald-800">
                          <ShieldCheck className="h-3 w-3" /> Phù hợp với hồ sơ
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-md bg-rose-100 px-2 py-0.5 font-bold text-rose-800">
                          <ShieldAlert className="h-3 w-3" /> Cần lưu ý / Hạn chế
                        </span>
                      )}
                      {m.meta.safe_alternatives?.length > 0 && (
                        <span className="rounded-md bg-sky-100 px-2 py-0.5 font-semibold text-sky-900">
                          Gợi ý thay thế: {m.meta.safe_alternatives.map((a) => a.name).join(', ')}
                        </span>
                      )}
                    </div>

                    {m.meta.rag_context?.length > 0 && (
                      <details className="rounded-xl bg-white p-2.5 border border-slate-200">
                        <summary className="flex cursor-pointer items-center gap-1 font-semibold text-sky-800">
                          <BookOpen className="h-3.5 w-3.5" /> Tài liệu tham chiếu ({m.meta.rag_context.length} đoạn)
                        </summary>
                        <div className="mt-2 space-y-1.5 text-slate-600">
                          {m.meta.rag_context.map((snippet, si) => (
                            <p key={si} className="border-l-2 border-sky-500 pl-2">{snippet}</p>
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                )}
              </div>
              {m.role === 'user' && (
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-200 text-slate-700">
                  <User className="h-4 w-4" />
                </span>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin text-sky-600" />
              Đang tra cứu dữ liệu và kiểm tra độ an toàn...
            </div>
          )}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage(input);
          }}
          className="flex items-center gap-2 border-t border-slate-200 bg-white p-3"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Nhập câu hỏi dinh dưỡng hoặc tên món ăn cần kiểm tra..."
            className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm outline-none focus:border-sky-500 focus:bg-white"
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-r from-sky-500 to-teal-500 text-white shadow-sm shadow-sky-500/20 transition hover:brightness-105 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
