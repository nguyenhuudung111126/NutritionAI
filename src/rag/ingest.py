"""Nạp tài liệu hướng dẫn y khoa (Markdown, TXT, PDF) vào PostgreSQL (`pgvector`) và tìm kiếm RAG."""
import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from google.genai import types

from src.db import get_conn
from src.llm import embed_text, embed_texts, generate_text, has_api_key

DEFAULT_DOC_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge" / "clinical_guidelines.md"

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def _split_long_block(block: str, max_chars: int, overlap: int) -> List[str]:
    """Chia nhỏ một khối văn bản dài theo ranh giới câu/dòng, giữ lại phần overlap."""
    if len(block) <= max_chars:
        return [block]

    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(block) if p.strip()]
    if len(parts) <= 1:
        step = max(1, max_chars - overlap)
        return [block[i : i + max_chars].strip() for i in range(0, len(block), step) if block[i : i + max_chars].strip()]

    out: List[str] = []
    cur = ""
    for part in parts:
        candidate = f"{cur} {part}".strip() if cur else part
        if len(candidate) <= max_chars:
            cur = candidate
        else:
            if cur:
                out.append(cur)
                tail = cur[-overlap:].strip() if overlap > 0 else ""
                cur = f"{tail} {part}".strip() if tail else part
            else:
                out.extend(_split_long_block(part, max_chars, overlap))
                cur = ""
    if cur:
        out.append(cur)
    return out


def chunk_markdown(text: str, max_chars: int = 800, overlap: int = 120) -> List[Dict[str, str]]:
    """Cắt tài liệu Markdown/văn bản theo đề mục & đoạn văn, có overlap để không đứt ý y khoa."""
    normalized = unicodedata.normalize("NFC", text).replace("\r\n", "\n")
    sections: List[Tuple[str, List[str]]] = []
    current_section = "Chung"
    current_lines: List[str] = []

    for line in normalized.splitlines():
        stripped = line.strip()
        m = _HEADING_RE.match(stripped)
        if m:
            if current_lines:
                sections.append((current_section, current_lines))
                current_lines = []
            current_section = m.group(2).strip("* ").strip() or "Chung"
            continue
        current_lines.append(line.rstrip())

    if current_lines:
        sections.append((current_section, current_lines))

    chunks: List[Dict[str, str]] = []
    for section, lines in sections:
        body = "\n".join(lines).strip()
        if not body:
            continue
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        buffer = ""
        for para in paragraphs:
            if len(para) > max_chars:
                if buffer:
                    chunks.append({"section": section, "content": buffer})
                    buffer = ""
                for sub in _split_long_block(para, max_chars, overlap):
                    chunks.append({"section": section, "content": sub})
                continue

            candidate = f"{buffer}\n\n{para}".strip() if buffer else para
            if len(candidate) <= max_chars:
                buffer = candidate
            else:
                chunks.append({"section": section, "content": buffer})
                tail = buffer[-overlap:].strip() if overlap > 0 else ""
                buffer = f"{tail}\n\n{para}".strip() if tail and len(tail) + len(para) + 2 <= max_chars else para

        if buffer:
            chunks.append({"section": section, "content": buffer})

    return chunks


def extract_pdf_markdown(pdf_bytes: bytes, use_ocr_fallback: bool = True) -> Tuple[str, Dict[str, Any]]:
    """Trích xuất văn bản từ file PDF bằng PyMuPDF (cực nhanh) + Gemini OCR nếu là PDF scan."""
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("Thiếu thư viện `pymupdf`. Hãy chạy: pip install pymupdf") from exc

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    num_pages = len(doc)
    pages_txt = []
    for idx, page in enumerate(doc):
        page_txt = page.get_text("text").strip()
        if page_txt:
            pages_txt.append(f"## Trang {idx + 1}\n\n{page_txt}")
    doc.close()

    extracted = "\n\n".join(pages_txt)
    extractor_used = "pymupdf_text"

    non_ws_chars = len(re.sub(r"\s+", "", extracted))
    avg_chars_per_page = non_ws_chars / max(num_pages, 1)

    if use_ocr_fallback and avg_chars_per_page < 50 and has_api_key():
        prompt = (
            "Hãy trích xuất toàn bộ nội dung tài liệu y khoa/dinh dưỡng trong file PDF này sang định dạng Markdown tiếng Việt chuẩn. "
            "Giữ nguyên các tiêu đề bằng #, ##, ### và chuyển đầy đủ bảng biểu thành bảng Markdown. "
            "Không tóm tắt, không bỏ sót số liệu lâm sàng."
        )
        part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        extracted, model_used = generate_text([prompt, part], fast=False)
        extractor_used = f"gemini_ocr ({model_used})"

    normalized = unicodedata.normalize("NFC", extracted or "").strip()
    meta = {
        "pages": num_pages,
        "extractor": extractor_used,
        "chars": len(normalized),
    }
    return normalized, meta


def ingest_text(
    text: str,
    title: str,
    source: str,
    group_name: Optional[str] = None,
    published_year: int = 2024,
    max_chars: int = 800,
    overlap: int = 120,
    source_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Cắt chunk văn bản, tạo vector 768 chiều theo batch và lưu vào PostgreSQL (`pgvector`)."""
    chunks = chunk_markdown(text, max_chars=max_chars, overlap=overlap)
    if not chunks:
        raise ValueError("Không trích xuất được nội dung văn bản hợp lệ để nạp vào RAG.")

    group_label = (group_name or "Chung").strip() or "Chung"
    embed_inputs = [
        f"Tài liệu: {title} | Nhóm bệnh: {group_label} | Đề mục: {ch['section']}\n{ch['content']}"
        for ch in chunks
    ]
    embeddings = embed_texts(embed_inputs, task_type="retrieval_document")

    with get_conn() as conn:
        doc = conn.execute(
            """
            INSERT INTO knowledge_documents (title, source, group_name, published_year)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
            """,
            (title, source, None if group_label == "Chung" else group_label, published_year),
        ).fetchone()
        doc_id = doc["id"]

        for idx, (ch, emb) in enumerate(zip(chunks, embeddings)):
            vec_str = "[" + ",".join(str(x) for x in emb) + "]"
            meta_json = json.dumps(
                {
                    "section": ch["section"],
                    "source_file": source_filename or source,
                    "group_name": group_label,
                },
                ensure_ascii=False,
            )
            conn.execute(
                """
                INSERT INTO knowledge_chunks (document_id, chunk_index, content, metadata, embedding)
                VALUES (%s, %s, %s, %s::jsonb, %s::vector);
                """,
                (doc_id, idx, ch["content"], meta_json, vec_str),
            )

    return {
        "document_id": doc_id,
        "title": title,
        "chunk_count": len(chunks),
        "sample_chunks": chunks[:3],
    }


def ingest_pdf_bytes(
    pdf_bytes: bytes,
    filename: str,
    title: str,
    source: str = "Tài liệu PDF tải lên",
    group_name: Optional[str] = None,
    published_year: int = 2024,
    max_chars: int = 800,
    overlap: int = 120,
) -> Dict[str, Any]:
    """Trích xuất PDF từ bytes, chunking và nạp vào kho tri thức `pgvector`."""
    markdown_text, extract_meta = extract_pdf_markdown(pdf_bytes)
    result = ingest_text(
        text=markdown_text,
        title=title.strip() or Path(filename).stem,
        source=source.strip() or filename,
        group_name=group_name,
        published_year=published_year,
        max_chars=max_chars,
        overlap=overlap,
        source_filename=filename,
    )
    result["extract_meta"] = extract_meta
    return result


def ingest_file(
    file_path: Path,
    title: Optional[str] = None,
    source: Optional[str] = None,
    group_name: Optional[str] = None,
    published_year: int = 2024,
    max_chars: int = 800,
    overlap: int = 120,
) -> Dict[str, Any]:
    """Nạp file `.pdf`, `.md` hoặc `.txt` từ đường dẫn ổ đĩa vào PostgreSQL (`pgvector`)."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {path}")

    doc_title = title or path.stem
    doc_source = source or path.name

    if path.suffix.lower() == ".pdf":
        return ingest_pdf_bytes(
            pdf_bytes=path.read_bytes(),
            filename=path.name,
            title=doc_title,
            source=doc_source,
            group_name=group_name,
            published_year=published_year,
            max_chars=max_chars,
            overlap=overlap,
        )

    text = path.read_text(encoding="utf-8")
    res = ingest_text(
        text=text,
        title=doc_title,
        source=doc_source,
        group_name=group_name,
        published_year=published_year,
        max_chars=max_chars,
        overlap=overlap,
        source_filename=path.name,
    )
    res["extract_meta"] = {"pages": 1, "extractor": "markdown/text", "chars": len(text)}
    return res


def ingest_document(
    file_path: Path = DEFAULT_DOC_PATH,
    title: str = "Hướng dẫn Dinh dưỡng Lâm sàng (ĐTĐ & Thận)",
    source: str = "Bộ Y tế / KDIGO / ADA (Tổng hợp MVP)",
    group_name: Optional[str] = None,
    published_year: int = 2024,
) -> int:
    """Nạp tài liệu vào `nutri.knowledge_documents` & `nutri.knowledge_chunks` (trả về số chunk)."""
    res = ingest_file(
        file_path=file_path,
        title=title,
        source=source,
        group_name=group_name,
        published_year=published_year,
    )
    return int(res["chunk_count"])


_FOLDER_GROUP_HINTS = {
    "ckd": "Thận-Tiết niệu",
    "than": "Thận-Tiết niệu",
    "renal": "Thận-Tiết niệu",
    "kidney": "Thận-Tiết niệu",
    "dtd": "Đái tháo đường",
    "diabetes": "Đái tháo đường",
    "tieu_duong": "Đái tháo đường",
    "thao_duong": "Đái tháo đường",
    "thao duong": "Đái tháo đường",
    "htn": "Tim mạch",
    "tha": "Tim mạch",
    "tim_mach": "Tim mạch",
    "huyet_ap": "Tim mạch",
    "huyet ap": "Tim mạch",
    "gout": "Chuyển hóa",
    "chuyen_hoa": "Chuyển hóa",
    "gan": "Gan mật",
}


def _strip_accents(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def _infer_group_from_path(file_path: Path, root_dir: Path, fallback_group: Optional[str]) -> Optional[str]:
    if fallback_group:
        return fallback_group
    rel_text = _strip_accents(" / ".join(file_path.relative_to(root_dir).parts))
    for key, group in _FOLDER_GROUP_HINTS.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", rel_text):
            return group
    return None


def ingest_directory(
    dir_path: Path,
    source: Optional[str] = None,
    group_name: Optional[str] = None,
    published_year: int = 2024,
    max_chars: int = 800,
    overlap: int = 120,
    skip_existing: bool = True,
) -> List[Dict[str, Any]]:
    """Quét và nạp hàng loạt toàn bộ file `.pdf`, `.md`, `.txt` trong một thư mục (kể cả thư mục con)."""
    root = Path(dir_path)
    if not root.is_dir():
        raise NotADirectoryError(f"Không phải thư mục hợp lệ: {root}")

    supported_exts = {".pdf", ".md", ".txt"}
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in supported_exts)
    if not files:
        raise ValueError(f"Không tìm thấy file .pdf/.md/.txt nào trong {root}")

    existing_sources = set()
    if skip_existing:
        existing_sources = {d["source"] for d in list_knowledge_documents()}

    results: List[Dict[str, Any]] = []
    for idx, fpath in enumerate(files, 1):
        if skip_existing and (fpath.name in existing_sources or fpath.stem in existing_sources):
            results.append({"file": str(fpath), "status": "SKIPPED", "reason": "Đã tồn tại trong DB"})
            continue
        inferred_group = _infer_group_from_path(fpath, root, group_name)
        print(f"[{idx}/{len(files)}] Đang xử lý '{fpath.name}' (nhóm: {inferred_group or 'Chung'})...")
        try:
            res = ingest_file(
                file_path=fpath,
                title=fpath.stem,
                source=source or fpath.name,
                group_name=inferred_group,
                published_year=published_year,
                max_chars=max_chars,
                overlap=overlap,
            )
            results.append({"file": str(fpath), "status": "INGESTED", **res})
        except Exception as exc:
            results.append({"file": str(fpath), "status": "ERROR", "reason": str(exc)})
    return results


def list_knowledge_documents() -> List[Dict[str, Any]]:
    """Liệt kê các tài liệu đã nạp vào kho tri thức RAG kèm số lượng chunk."""
    sql = """
        SELECT d.id, d.title, d.source, COALESCE(d.group_name, 'Chung') AS group_name,
               d.published_year, COUNT(c.id) AS chunk_count, d.created_at
        FROM knowledge_documents d
        LEFT JOIN knowledge_chunks c ON c.document_id = d.id
        GROUP BY d.id
        ORDER BY d.id DESC;
    """
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql).fetchall()]


def delete_knowledge_document(document_id: int) -> None:
    """Xóa một tài liệu (và toàn bộ chunk vector liên quan) khỏi kho RAG."""
    with get_conn() as conn:
        conn.execute("DELETE FROM knowledge_documents WHERE id = %s;", (document_id,))


def _keyword_fallback_knowledge(
    query: str,
    top_k: int = 3,
    group_names: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Fallback tìm đoạn tài liệu theo từ khóa trong PostgreSQL khi Embedding API lỗi/timeout."""
    tokens = [w for w in re.findall(r"[0-9A-Za-zÀ-ỹ]{3,}", query or "") if w.lower() not in {"bệnh", "người", "được", "không", "những", "nhiều"}]
    patterns = [f"%{t}%" for t in tokens[:5]] or [f"%{(query or '').strip()[:40]}%"]
    where_grp = "AND (d.group_name IS NULL OR d.group_name = ANY(%s))" if group_names else ""
    sql = f"""
        SELECT c.content, c.metadata->>'section' AS section, d.title, d.source,
               COALESCE(d.group_name, 'Chung') AS group_name,
               0.5::float AS similarity
        FROM knowledge_chunks c
        JOIN knowledge_documents d ON d.id = c.document_id
        WHERE c.content ILIKE ANY(%s) {where_grp}
        ORDER BY c.id ASC
        LIMIT %s;
    """
    params: Tuple[Any, ...] = (patterns, group_names, top_k) if group_names else (patterns, top_k)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def search_knowledge(
    query: str,
    top_k: int = 3,
    group_names: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Tìm top-k đoạn hướng dẫn y khoa liên quan nhất từ `pgvector` (có fallback từ khóa nếu embedding timeout)."""
    try:
        emb = embed_text(query, task_type="retrieval_query")
    except Exception:
        return _keyword_fallback_knowledge(query, top_k=top_k, group_names=group_names)

    vec_str = "[" + ",".join(str(x) for x in emb) + "]"

    if group_names:
        sql = """
            SELECT c.content, c.metadata->>'section' AS section, d.title, d.source,
                   COALESCE(d.group_name, 'Chung') AS group_name,
                   1 - (c.embedding <=> %s::vector) AS similarity
            FROM knowledge_chunks c
            JOIN knowledge_documents d ON d.id = c.document_id
            WHERE d.group_name IS NULL OR d.group_name = ANY(%s)
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s;
        """
        params: Tuple[Any, ...] = (vec_str, group_names, vec_str, top_k)
    else:
        sql = """
            SELECT c.content, c.metadata->>'section' AS section, d.title, d.source,
                   COALESCE(d.group_name, 'Chung') AS group_name,
                   1 - (c.embedding <=> %s::vector) AS similarity
            FROM knowledge_chunks c
            JOIN knowledge_documents d ON d.id = c.document_id
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s;
        """
        params = (vec_str, vec_str, top_k)

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nạp 1 file hoặc cả thư mục PDF/Markdown vào PostgreSQL pgvector")
    parser.add_argument("target", nargs="?", default=str(DEFAULT_DOC_PATH), help="Đường dẫn tới 1 file (.pdf/.md/.txt) HOẶC 1 thư mục")
    parser.add_argument("--title", default=None, help="Tên tài liệu hiển thị (khi nạp 1 file)")
    parser.add_argument("--source", default=None, help="Nguồn tài liệu (VD: Bộ Y tế, KDIGO 2024)")
    parser.add_argument("--group", default=None, help="Nhóm bệnh (VD: Đái tháo đường, Thận-Tiết niệu, Gout)")
    parser.add_argument("--year", type=int, default=2024, help="Năm xuất bản")
    parser.add_argument("--max-chars", type=int, default=800, help="Độ dài tối đa mỗi chunk (ký tự)")
    parser.add_argument("--overlap", type=int, default=120, help="Số ký tự overlap giữa các chunk")
    parser.add_argument("--force", action="store_true", help="Nạp lại cả những file đã có trong DB (khi nạp thư mục)")
    args = parser.parse_args()

    target_path = Path(args.target)
    if target_path.is_dir():
        summary = ingest_directory(
            dir_path=target_path,
            source=args.source,
            group_name=args.group,
            published_year=args.year,
            max_chars=args.max_chars,
            overlap=args.overlap,
            skip_existing=not args.force,
        )
        for item in summary:
            if item["status"] == "INGESTED":
                print(f"[OK] {item['title']} -> {item['chunk_count']} chunks (ID={item['document_id']})")
            elif item["status"] == "SKIPPED":
                print(f"[SKIP] {item['file']} ({item['reason']})")
            else:
                print(f"[ERR] {item['file']}: {item['reason']}")
    else:
        res = ingest_file(
            file_path=target_path,
            title=args.title,
            source=args.source,
            group_name=args.group,
            published_year=args.year,
            max_chars=args.max_chars,
            overlap=args.overlap,
        )
        print(f"Đã nạp thành công '{res['title']}' ({res['chunk_count']} chunks, ID={res['document_id']}) vào PostgreSQL pgvector!")
