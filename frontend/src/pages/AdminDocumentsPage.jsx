import { useEffect, useState } from 'react';
import { BookOpen, FileText, Loader2, Search, Trash2, Upload } from 'lucide-react';
import { api } from '../api';

export default function AdminDocumentsPage() {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [ragFiles, setRagFiles] = useState([]);
  const [ragSource, setRagSource] = useState('Bộ Y tế / Phác đồ lâm sàng');
  const [ragGroup, setRagGroup] = useState('Chung');
  const [publishedYear, setPublishedYear] = useState(2024);
  const [maxChars, setMaxChars] = useState(800);
  const [overlap, setOverlap] = useState(120);
  const [uploadingRag, setUploadingRag] = useState(false);
  const [ragMsg, setRagMsg] = useState('');
  const [ragErr, setRagErr] = useState('');
  const [ragQuery, setRagQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [ragHits, setRagHits] = useState([]);

  const loadDocs = async () => {
    setLoading(true);
    try {
      const list = await api.getRagDocuments();
      setDocs(list);
    } catch (err) {
      setRagErr(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocs();
  }, []);

  const handleUploadRag = async (e) => {
    e.preventDefault();
    if (!ragFiles.length) return;
    setUploadingRag(true);
    setRagMsg('');
    setRagErr('');
    try {
      const res = await api.uploadRagDocuments(ragFiles, {
        source: ragSource,
        group_name: ragGroup,
        published_year: Number(publishedYear) || 2024,
        max_chars: Number(maxChars) || 800,
        overlap: Number(overlap) || 120,
      });
      const totalChunks = res.reduce((acc, item) => acc + (item.chunk_count || 0), 0);
      setRagMsg(`Đã nạp thành công ${res.length} tài liệu (${totalChunks} chunks) vào pgvector.`);
      setRagFiles([]);
      await loadDocs();
    } catch (err) {
      setRagErr(`Lỗi nạp tài liệu: ${err.message}`);
    } finally {
      setUploadingRag(false);
    }
  };

  const handleDeleteDoc = async (docId) => {
    setRagErr('');
    try {
      await api.deleteRagDocument(docId);
      await loadDocs();
    } catch (err) {
      setRagErr(err.message);
    }
  };

  const handleSearchRag = async (e) => {
    e.preventDefault();
    if (!ragQuery.trim()) return;
    setSearching(true);
    setRagErr('');
    try {
      const hits = await api.searchRag(ragQuery);
      setRagHits(hits);
    } catch (err) {
      setRagErr(err.message);
    } finally {
      setSearching(false);
    }
  };

  const totalChunks = docs.reduce((acc, d) => acc + Number(d.chunk_count || 0), 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-teal-100 px-3 py-0.5 text-[11px] font-bold text-teal-800">
            <FileText className="h-3.5 w-3.5" /> Dữ liệu & Phác đồ Lâm sàng
          </div>
          <h1 className="mt-1.5 text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
            Quản lý Tài liệu
          </h1>
          <p className="mt-1 text-xs text-slate-600">
            Nạp tài liệu phác đồ Bộ Y tế (.pdf, .md, .txt) để tách vector chunks trong PostgreSQL pgvector và kiểm thử truy xuất ngữ nghĩa.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs font-bold">
          <span className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-800 shadow-2xs">
            {docs.length} tài liệu
          </span>
          <span className="rounded-xl border border-teal-200 bg-teal-50 px-3.5 py-2 text-teal-800">
            {totalChunks} chunks pgvector
          </span>
        </div>
      </div>

      {/* Upload & Chunk Config */}
      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-teal-50 text-teal-600">
            <BookOpen className="h-4 w-4" />
          </span>
          <h2 className="text-base font-bold text-slate-900">
            Kho tri thức RAG
          </h2>
        </div>

        <form onSubmit={handleUploadRag} className="space-y-3 rounded-xl border border-sky-100 bg-sky-50/40 p-4">
          <div className="grid gap-3 md:grid-cols-4 items-end">
            <div className="md:col-span-2">
              <label className="mb-1 block text-xs font-semibold text-slate-700">
                Chọn 1 hoặc nhiều file (.pdf, .md, .txt)
              </label>
              <input
                type="file"
                multiple
                accept=".pdf,.md,.txt"
                onChange={(e) => setRagFiles(Array.from(e.target.files || []))}
                className="w-full text-xs text-slate-700 file:mr-3 file:rounded-xl file:border-0 file:bg-sky-600 file:px-3.5 file:py-2 file:text-xs file:font-semibold file:text-white hover:file:bg-sky-700"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">Nhóm bệnh</label>
              <select
                value={ragGroup}
                onChange={(e) => setRagGroup(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-sky-500"
              >
                {['Chung', 'Đái tháo đường', 'Thận-Tiết niệu', 'Tim mạch', 'Chuyển hóa', 'Gan mật'].map((g) => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
            </div>
            <button
              type="submit"
              disabled={!ragFiles.length || uploadingRag}
              className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-sky-500 to-teal-500 px-4 py-2.5 text-xs font-bold text-white shadow-sm shadow-sky-500/20 hover:brightness-105 disabled:opacity-50"
            >
              {uploadingRag ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
              Nạp ({ragFiles.length}) file
            </button>
          </div>

          <div className="grid gap-3 sm:grid-cols-4">
            <div className="sm:col-span-2">
              <label className="mb-1 block text-[11px] font-semibold text-slate-600">Nguồn tài liệu</label>
              <input
                type="text"
                value={ragSource}
                onChange={(e) => setRagSource(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs outline-none focus:border-sky-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-[11px] font-semibold text-slate-600">Năm ban hành</label>
              <input
                type="number"
                value={publishedYear}
                onChange={(e) => setPublishedYear(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs outline-none focus:border-sky-500"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="mb-1 block text-[11px] font-semibold text-slate-600">Chunk</label>
                <input
                  type="number"
                  value={maxChars}
                  onChange={(e) => setMaxChars(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-xs outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-semibold text-slate-600">Overlap</label>
                <input
                  type="number"
                  value={overlap}
                  onChange={(e) => setOverlap(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-xs outline-none"
                />
              </div>
            </div>
          </div>
        </form>

        {ragErr && <div className="rounded-xl bg-rose-50 px-3.5 py-2 text-xs font-medium text-rose-700">{ragErr}</div>}
        {ragMsg && <div className="rounded-xl bg-emerald-50 px-3.5 py-2 text-xs font-semibold text-emerald-800">{ragMsg}</div>}

        {loading ? (
          <div className="flex items-center gap-2 py-6 text-xs text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin text-sky-600" /> Đang tải tài liệu...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500">
                  <th className="py-2 pr-4">ID</th>
                  <th className="py-2 pr-4">Tên tài liệu</th>
                  <th className="py-2 pr-4">Nhóm bệnh</th>
                  <th className="py-2 pr-4">Nguồn</th>
                  <th className="py-2 pr-4">Chunks</th>
                  <th className="py-2 pr-4 text-right">Xóa</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {docs.map((d) => (
                  <tr key={d.id} className="hover:bg-sky-50/30">
                    <td className="py-2.5 pr-4 font-semibold text-slate-700">#{d.id}</td>
                    <td className="py-2.5 pr-4 font-semibold text-slate-900">{d.title}</td>
                    <td className="py-2.5 pr-4">{d.group_name}</td>
                    <td className="py-2.5 pr-4 text-slate-500">{d.source || '—'}</td>
                    <td className="py-2.5 pr-4 font-bold text-emerald-700">{d.chunk_count}</td>
                    <td className="py-2.5 pr-4 text-right">
                      <button
                        onClick={() => handleDeleteDoc(d.id)}
                        className="rounded-lg p-1.5 text-rose-500 hover:bg-rose-50"
                        title="Xóa tài liệu"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Semantic Search Tester */}
      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-6 shadow-xs space-y-4">
        <div>
          <h2 className="text-base font-bold text-slate-900">Kiểm thử Truy xuất Ngữ nghĩa (pgvector Search)</h2>
          <p className="text-xs text-slate-500">Nhập câu hỏi lâm sàng để kiểm tra đoạn văn bản (chunks) nào được AI Agent truy xuất</p>
        </div>

        <form onSubmit={handleSearchRag} className="flex gap-2">
          <input
            type="text"
            value={ragQuery}
            onChange={(e) => setRagQuery(e.target.value)}
            placeholder="Thử tìm kiếm ngữ nghĩa trong pgvector (VD: Bệnh thận có ăn được quả khế không?)..."
            className="flex-1 rounded-xl border border-slate-200 px-4 py-2.5 text-xs outline-none focus:border-sky-500"
          />
          <button
            type="submit"
            disabled={searching}
            className="inline-flex items-center gap-1.5 rounded-xl bg-sky-600 px-4 py-2.5 text-xs font-bold text-white shadow-2xs hover:bg-sky-700 disabled:opacity-50"
          >
            {searching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
            Tìm RAG
          </button>
        </form>

        {ragHits.length > 0 && (
          <div className="space-y-2.5">
            {ragHits.map((h, i) => (
              <div key={i} className="rounded-xl border border-sky-100 bg-sky-50/40 p-3.5 text-xs">
                <div className="font-bold text-sky-900">
                  Top {i + 1} • Độ tương đồng {Number(h.similarity).toFixed(3)} • {h.title} ({h.section})
                </div>
                <p className="mt-1 leading-relaxed text-slate-700">{h.content}</p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
