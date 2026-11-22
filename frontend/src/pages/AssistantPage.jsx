import { useState } from 'react';
import { BookOpen, Bot, Loader2, Send, ShieldAlert, ShieldCheck, User } from 'lucide-react';
import { api } from '../api';

const QUICK_PROMPTS = [
  '100g thịt gà ta có bao nhiêu đạm?',
  'Tôi ăn rau ngót được không?',
  'Người suy thận mạn có ăn được quả khế không?',
  'Cách luộc rau để giảm Kali cho người bệnh thận?',
];

function cleanMathAndSymbols(raw) {
  return String(raw || '')
    .replace(/\r\n/g, '\n')
    .replace(/\$\s*\\le\s*([^$]*)\$/g, '≤ $1')
    .replace(/\$\s*\\ge\s*([^$]*)\$/g, '≥ $1')
    .replace(/\$([^$\n]{1,30})\$/g, (_, inner) =>
      inner
        .replace(/\\le\b/g, '≤')
        .replace(/\\ge\b/g, '≥')
        .replace(/\\approx\b/g, '≈')
        .replace(/\\times\b/g, '×')
        .replace(/\\to\b/g, '→')
        .trim()
    )
    .replace(/\\le\b/g, '≤')
    .replace(/\\ge\b/g, '≥')
    .replace(/\\approx\b/g, '≈')
    .replace(/\\to\b/g, '→');
}

function renderInlineMarkdown(text) {
  const tokens = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\n]+\*)/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      tokens.push(text.slice(lastIndex, match.index));
    }
    const seg = match[0];
    if (seg.startsWith('**') && seg.endsWith('**')) {
      tokens.push(
        <strong key={match.index} className="font-bold text-slate-900">
          {seg.slice(2, -2)}
        </strong>
      );
    } else if (seg.startsWith('`') && seg.endsWith('`')) {
      tokens.push(
        <code key={match.index} className="rounded bg-slate-200/70 px-1.5 py-0.5 text-[12px] font-semibold text-slate-800">
          {seg.slice(1, -1)}
        </code>
      );
    } else if (seg.startsWith('*') && seg.endsWith('*')) {
      tokens.push(
        <em key={match.index} className="italic text-slate-700">
          {seg.slice(1, -1)}
        </em>
      );
    }
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) {
    tokens.push(text.slice(lastIndex));
  }
  return tokens;
}

function FormattedAssistantMessage({ text }) {
  const cleaned = cleanMathAndSymbols(text);
  const lines = cleaned.split('\n');

  return (
    <div className="space-y-1.5 text-sm leading-relaxed text-slate-800">
      {lines.map((rawLine, idx) => {
        const line = rawLine.trim();
        if (!line) {
          return <div key={idx} className="h-1" />;
        }

        // Headings (###, ##, #) -> strip # symbols and style nicely
        const headingMatch = line.match(/^(#{1,4})\s+(.+)$/);
        if (headingMatch) {
          const level = headingMatch[1].length;
          const content = headingMatch[2].replace(/\*\*/g, '');
          return (
            <div
              key={idx}
              className={`pt-2 font-extrabold text-slate-900 ${
                level <= 2 ? 'text-[15px]' : 'text-sm text-sky-900'
              }`}
            >
              {content}
            </div>
          );
        }

        // Bullet list (- item or * item) -> clean rounded dot bullet, indented
        const bulletMatch = rawLine.match(/^(\s*)[*-]\s+(.+)$/);
        if (bulletMatch) {
          const indentLevel = Math.min(2, Math.floor((bulletMatch[1]?.length || 0) / 2));
          return (
            <div
              key={idx}
              className="flex items-start gap-2"
              style={{ paddingLeft: `${indentLevel * 16 + 4}px` }}
            >
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-500" />
              <div className="flex-1">{renderInlineMarkdown(bulletMatch[2])}</div>
            </div>
          );
        }

        // Numbered list (1. item)
        const numMatch = rawLine.match(/^(\s*)(\d+)\.\s+(.+)$/);
        if (numMatch) {
          return (
            <div key={idx} className="flex items-start gap-2 pl-1">
              <span className="min-w-[18px] font-bold text-sky-700">{numMatch[2]}.</span>
              <div className="flex-1">{renderInlineMarkdown(numMatch[3])}</div>
            </div>
          );
        }

        return <p key={idx}>{renderInlineMarkdown(line)}</p>;
      })}
    </div>
  );
}

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
                {m.role === 'user' ? (
                  <div className="whitespace-pre-wrap">{m.content}</div>
                ) : (
                  <FormattedAssistantMessage text={m.content} />
                )}

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
