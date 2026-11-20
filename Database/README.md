# NutriGuard AI – Cơ sở dữ liệu PostgreSQL

## Thứ tự chạy

| File | Nội dung |
|---|---|
| `01_schema.sql` | Toàn bộ bảng, enum, index, view (schema `nutri`) |
| `02_seed_foods.sql` | 690 thực phẩm (sinh từ `thuc_pham_db_ready.csv`) |
| `03_seed_regimes.sql` | 24 phác đồ chế độ ăn người lớn Bộ Y tế (`MCDAnguoilon`), đã tách min/max |
| `04_seed_catalog.sql` | Bệnh lý, chỉ số xét nghiệm, giai đoạn CKD, luật chọn phác đồ, luật lọc thực phẩm |
| `05_rag_pgvector.sql` | Kho tri thức RAG (**cần cài extension pgvector**, có thể chạy sau) |
| `99_demo_patient.sql` | Ca bệnh mẫu “Bác Nam” (ĐTĐ + Suy thận 3b) để demo (không bắt buộc) |

```powershell
$env:Path += ";C:\Program Files\PostgreSQL\18\bin"
createdb -U postgres nutriguard
psql -U postgres -d nutriguard -f 01_schema.sql
psql -U postgres -d nutriguard -f 02_seed_foods.sql
psql -U postgres -d nutriguard -f 03_seed_regimes.sql
psql -U postgres -d nutriguard -f 04_seed_catalog.sql
psql -U postgres -d nutriguard -f 99_demo_patient.sql   # tùy chọn
psql -U postgres -d nutriguard -f 05_rag_pgvector.sql   # khi đã cài pgvector
```

Sinh lại file seed khi dữ liệu thay đổi: `python build_seeds.py` (cần `openpyxl`).

## Thêm bệnh mới (không sửa code)
1. `UPDATE nutri.conditions SET is_enabled = TRUE WHERE code = 'GOUT';` (hoặc INSERT bệnh mới)
2. Thêm chỉ số cần thiết vào `biomarkers` (VD `URIC_ACID` đã có sẵn)
3. Thêm luật vào `regime_selection_rules` (bệnh → mã phác đồ)
4. Thêm luật vào `food_restriction_rules` (ngưỡng chất trên 100g → WARN/BLOCK)
