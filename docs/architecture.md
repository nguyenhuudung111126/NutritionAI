# Kiến trúc kỹ thuật & Workflow Agent – NutriGuard AI

Tài liệu mô tả kiến trúc hệ thống **NutriGuard AI** (Trợ lý Dinh dưỡng Lâm sàng cho bệnh nhân Đái tháo đường, Bệnh thận mạn & Đa bệnh lý) theo đúng 6 trụ cột: **Model**, **Workflow Agent**, **RAG & SQL Tooling**, **Guardrails**, **Observability** và **Evals**.

---

## 1. Luồng tổng thể theo trình tự lâm sàng (Hồ sơ trước $\to$ Yêu cầu sau)

1. **Bước 1 — Thiết lập Hồ sơ & Khung mục tiêu y khoa:**
   - Bệnh nhân nhập thông tin cơ bản (Tuổi, Giới, Chiều cao, Cân nặng, Bệnh lý, Dị ứng) hoặc tải ảnh/PDF phiếu xét nghiệm qua **Vision Extractor** (`src/vision/lab_extractor.py`).
   - Dữ liệu lưu vào PostgreSQL (`patients`, `checkups`, `lab_results`) và được `src/tools/regime_tool.py` đối chiếu bảng luật Bộ Y tế (QĐ 2879/QĐ-BYT) để tính ra **Khung dinh dưỡng mục tiêu** (`nutrition_targets`: mã phác đồ `DD01-X..DD08-X`, `TN01-X..TN14-X`, calo, đạm, natri, kali, phospho, GI).
2. **Bước 2 — Tiếp nhận Yêu cầu người dùng:**
   - Người dùng đặt câu hỏi / thẩm định món ở **Tab 1** hoặc yêu cầu lập thực đơn kèm ngân sách/khẩu vị ở **Tab 2** (`src/app.py`).
3. **Bước 3 — LangGraph Workflow Agent điều phối:**
   - Mọi yêu cầu đi qua cùng một đồ thị thống nhất tại `src/agent/graph.py`:
     `START` $\to$ `load_context` $\to$ `input_guardrail` $\to$ `route` $\to$ (`lookup` | `safety` | `meal_plan` | `general`) $\to$ `output_guardrail` $\to$ `END`.
4. **Bước 4 — Observability & Evals:**
   - **Observability** (`src/observability.py`): Bọc ngoài toàn bộ lượt chạy để ghi `trace_id`, `latency_ms`, `model_name` thực tế vào `agent_runs`, ghi vi phạm vào `guardrail_events`, và đẩy trace lên **Langfuse** (khi có API key).
   - **Evals** (`evals/test_safety.py`): Chạy kiểm thử định kỳ với bộ ca bệnh chuẩn trong `eval_cases` và lưu kết quả vào `eval_runs` / `eval_results`.

---

## 2. Sơ đồ LangGraph Workflow Agent (`src/agent/graph.py`)

```mermaid
flowchart TD
    START((START)) --> N1["1. load_context: Nạp Hồ sơ cá nhân, Xét nghiệm, Dị ứng & Phác đồ Bộ Y tế (regime_tool)"]
    N1 --> N2["2. input_guardrail: Tiếp nhận yêu cầu & Che PII đầu vào (SĐT, CCCD, BHYT, Email)"]
    N2 --> N3{"3. route: Phân loại thành 2 nhóm yêu cầu chính"}

    N3 -->|"Yêu cầu 1: HỎI ĐÁP & THẨM ĐỊNH (Tab 1)"| QA{"Xử lý theo loại câu hỏi"}
    QA -->|"Tra cứu số liệu"| Q1["lookup: Trả thẳng số liệu chuẩn từ 690 món (0 gọi LLM)"]
    QA -->|"Kiểm tra món ăn"| Q2["safety: RAG (pgvector) + Guardrail + Món thay thế + Gemini"]
    QA -->|"Hỏi kiến thức bệnh lý"| Q3["general: RAG (pgvector) + Gemini tư vấn theo bệnh án"]

    N3 -->|"Yêu cầu 2: LẬP THỰC ĐƠN (Tab 2 / Chat)"| B3["meal_plan: RAG (pgvector) + get_safe_foods (lọc dị ứng & bệnh lý)"]
    B3 --> GEN["Gemini sinh thực đơn JSON (Hồ sơ + Phác đồ + RAG + Ngân sách/Khẩu vị)"]
    GEN --> CALC["Python tính tổng dinh dưỡng thực tế (_compute_day_totals)"]
    CALC --> GR{"validate_daily_totals (Guardrail tổng ngày)"}
    GR -->|"Vượt ngưỡng (Tự sửa tối đa 2 vòng)"| GEN
    GR -->|"Đạt chuẩn / Hết 2 vòng"| SAVE["Lưu vào meal_plans & meal_plan_items"]

    Q1 --> OUT["4. output_guardrail: Kiểm tra & lọc PII đầu ra"]
    Q2 --> OUT
    Q3 --> OUT
    SAVE --> OUT

    OUT --> END((END))

    OBS["Observability bọc ngoài (observability.py): start_run_log -> trace_step / Langfuse -> finish_run_log (agent_runs & guardrail_events)"] -.-> START
    OBS -.-> END
```

---

## 3. Thành phần kỹ thuật chính

| Trụ cột | Công nghệ & File triển khai | Vai trò |
| :--- | :--- | :--- |
| **Model** | Google Gemini (`src/llm.py`) | Đa model fallback (`gemini-3.5-flash-lite`, `gemini-3-flash-preview`...), Structured Output JSON, Vision OCR phiếu xét nghiệm, `gemini-embedding-001` (768 chiều). |
| **Workflow Agent** | LangGraph (`src/agent/`) | `state.py`, `router.py`, `planner.py`, `graph.py` — điều phối 8 nodes kèm vòng lặp tự sửa thực đơn 2 vòng. |
| **RAG & SQL Tooling** | PostgreSQL 18 + `pgvector` (`src/rag/ingest.py`, `src/tools/`) | RAG nạp PDF/Markdown bằng `pymupdf` (chunking theo đề mục + overlap 120 ký tự); SQL Tool truy vấn 690 món ăn & 24 phác đồ Bộ Y tế. |
| **Guardrails** | `src/guardrails/` | `pii_masker.py` (che PII đầu vào/ra) + `clinical_validator.py` (chặn dị ứng & ngưỡng Kali/Natri/Phospho/GI/Đạm). |
| **Observability** | `src/observability.py` + Langfuse v5 | Ghi `agent_runs`, `guardrail_events` trong PostgreSQL và đẩy trace/span lên Langfuse. |
| **Evals** | `evals/test_safety.py` | Kiểm thử tự động độ khớp phác đồ và khả năng chặn món nguy hiểm. |
