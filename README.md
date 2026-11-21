# NutriGuard AI – Trợ lý Dinh dưỡng Lâm sàng Cá nhân hóa

Hệ thống AI Agent hỗ trợ bệnh nhân quản lý dinh dưỡng theo **24 phác đồ Bộ Y tế (QĐ 2879/QĐ-BYT)**, tích hợp **LangGraph**, **RAG (`pgvector`)**, **Gemini Vision OCR** đọc phiếu xét nghiệm đa ảnh và **Clinical Guardrails** tự động kiểm duyệt an toàn thực đơn (hỗ trợ **Đái tháo đường**, **Bệnh thận mạn**, , **Tăng huyết áp** (kèm với **Rối loạn mỡ máu**, **Suy tim**...)).

> 🌐 **Bản Demo Online:** [https://nutriguard-ai-api.onrender.com](https://nutriguard-ai-api.onrender.com)  
> 👤 **Tài khoản dùng thử:** Bệnh nhân (`dung` / `123456`) | Quản trị viên (`admin` / `admin123`)

## Cấu trúc dự án

- `data/`: Dữ liệu gốc (`raw/`), dữ liệu đã làm sạch (`processed/` - 690 thực phẩm Việt Nam) và tài liệu y khoa Bộ Y tế (`knowledge/`).
- `Database/`: Schema PostgreSQL (`nutri`), script sinh và nạp dữ liệu (`build_seeds.py`, `00_all_in_one.sql`, `enrich_usda_minerals.py`).
- `src/`: Mã nguồn ứng dụng (`agent/`, `tools/`, `guardrails/`, `rag/`, `vision/`, `api.py`, `auth.py`, `observability.py`, `app.py`).
- `frontend/`: Giao diện Web React + Vite + Tailwind CSS (build thành `frontend/dist/` để FastAPI phục vụ trực tiếp, deploy trên **Render** qua `render.yaml`).
- `evals/`: Bộ kiểm thử đánh giá chất lượng và độ an toàn y khoa gồm **30 Golden Cases** (`test_safety.py`).
- `docs/`: Bộ sơ đồ thiết kế hệ thống (`uc_*.png`, `act_*.png`, `agent_workflow_*.png`).

## Khởi chạy nhanh (Local)

1. Cài thư viện Python:
   ```bash
   pip install -r requirements.txt
   ```
2. Khởi tạo CSDL PostgreSQL (cần cài extension `pgvector`) theo hướng dẫn trong [`Database/README.md`](Database/README.md).
3. Cấu hình `.env` dựa trên `.env.example` (`DATABASE_URL`, `GEMINI_API_KEY`, và tùy chọn `LANGFUSE_*`).
4. Nạp tài liệu y khoa vào kho tri thức RAG (`pgvector`):
   ```bash
   python -m src.rag.ingest
   ```
5. Build Frontend và chạy Backend FastAPI:
   ```bash
   cd frontend && npm install && npm run build && cd ..
   uvicorn src.api:app --host 127.0.0.1 --port 8000
   ```
   Sau đó truy cập `http://127.0.0.1:8000`. *(Hoặc chạy giao diện Streamlit dự phòng: `streamlit run src/app.py`)*

## Chạy bộ kiểm thử đánh giá (30 Golden Cases)

```bash
python -m evals.test_safety
```
