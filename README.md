# NutriGuard AI – Trợ lý Dinh dưỡng Lâm sàng Cá nhân hóa

Hệ thống AI Agent hỗ trợ bệnh nhân quản lý dinh dưỡng theo phác đồ Bộ Y tế (tập trung MVP vào **Đái tháo đường** & **Thận – Tiết niệu**, dễ dàng mở rộng thêm bệnh mới qua CSDL).

## Cấu trúc dự án

- `data/`: Dữ liệu gốc (`raw/`), dữ liệu đã làm sạch (`processed/` - 690 thực phẩm Việt Nam) và tài liệu y khoa (`knowledge/`).
- `Database/`: Schema PostgreSQL (`nutri`), script sinh và nạp dữ liệu (`build_seeds.py`, `00_all_in_one.sql`).
- `src/`: Mã nguồn ứng dụng (`agent/`, `tools/`, `guardrails/`, `rag/`, `vision/`, `api.py`, `app.py`).
- `frontend/`: Giao diện Web React + Vite + Tailwind CSS (deploy trên Vercel).
- `evals/`: Bộ kiểm thử đánh giá chất lượng và độ an toàn y khoa (`test_safety.py`).
- `docs/`: Tài liệu kiến trúc kỹ thuật, sơ đồ Draw.io và kịch bản quay video demo.

## Khởi chạy nhanh (Local)

1. Cài thư viện Python:
   ```bash
   pip install -r requirements.txt
   ```
2. Khởi tạo CSDL PostgreSQL theo hướng dẫn trong [`Database/README.md`](Database/README.md).
3. Cấu hình `.env` dựa trên `.env.example`.
4. Chạy Backend + React UI (build sẵn hoặc dev mode):
   ```bash
   cd frontend && npm install && npm run build && cd ..
   uvicorn src.api:app --host 127.0.0.1 --port 8000
   ```
   *(Hoặc chạy giao diện Streamlit dự phòng: `streamlit run src/app.py`)*
