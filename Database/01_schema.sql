-- =====================================================================
-- NutriGuard AI - PostgreSQL schema (PostgreSQL 15+, tested target: 18)
-- Kiến trúc: data-driven -> thêm bệnh mới chỉ cần INSERT dữ liệu,
-- không phải sửa code.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- tìm tên món gần đúng ("rau ngot")
CREATE EXTENSION IF NOT EXISTS unaccent;   -- tìm không dấu
-- (gen_random_uuid() có sẵn từ PostgreSQL 13, không cần pgcrypto)
-- RAG + pgvector nằm riêng ở 05_rag_pgvector.sql (cần cài extension pgvector).

CREATE SCHEMA IF NOT EXISTS nutri;
SET search_path TO nutri, public;

-- ---------------------------------------------------------------------
-- 0. ENUM
-- ---------------------------------------------------------------------
CREATE TYPE gi_level        AS ENUM ('Thấp', 'Trung bình', 'Cao');
CREATE TYPE gender_type     AS ENUM ('Nam', 'Nữ');
CREATE TYPE activity_type   AS ENUM ('Nằm tại giường', 'Ít vận động', 'Vận động vừa', 'Vận động nhiều');
CREATE TYPE meal_type       AS ENUM ('Sáng', 'Phụ sáng', 'Trưa', 'Phụ chiều', 'Tối', 'Phụ tối');
CREATE TYPE plan_period     AS ENUM ('DAY', 'WEEK', 'MONTH');
CREATE TYPE plan_status     AS ENUM ('DRAFT', 'ACTIVE', 'ARCHIVED', 'REJECTED');
CREATE TYPE doc_status      AS ENUM ('UPLOADED', 'EXTRACTED', 'CONFIRMED', 'FAILED');
CREATE TYPE guardrail_action AS ENUM ('PASS', 'WARN', 'BLOCK', 'REWRITE');

-- Hàm tự cập nhật updated_at
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN NEW.updated_at := now(); RETURN NEW; END; $$ LANGUAGE plpgsql;

-- Hàm unaccent IMMUTABLE để dùng được trong index
CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS
$$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $$;

-- =====================================================================
-- 1. DỮ LIỆU THỰC PHẨM (690 nguyên liệu - Viện Dinh dưỡng)
-- =====================================================================
CREATE TABLE food_groups (
    id          SMALLSERIAL PRIMARY KEY,
    name        VARCHAR(120) UNIQUE NOT NULL     -- "Nhóm rau củ", "Nhóm thịt, cá"...
);

CREATE TABLE foods (
    id                  INTEGER PRIMARY KEY,      -- = cột TT (1..690)
    name                VARCHAR(255) NOT NULL,
    unit                VARCHAR(10)  NOT NULL DEFAULT 'g' CHECK (unit IN ('g','ml')),
    food_group_id       SMALLINT REFERENCES food_groups(id),   -- để NULL, bổ sung sau
    waste_pct           NUMERIC(5,2),
    -- Giá trị trên 100g ăn được. NULL = chưa có số liệu, 0 = không có.
    energy_kcal         NUMERIC(8,2),
    water_g             NUMERIC(8,2),
    protein_g           NUMERIC(8,2),
    lipid_g             NUMERIC(8,2),
    glucid_g            NUMERIC(8,2),
    fiber_g             NUMERIC(8,2),
    ash_g               NUMERIC(8,2),
    calcium_mg          NUMERIC(10,2),
    phosphorus_mg       NUMERIC(10,2),
    iron_mg             NUMERIC(10,2),
    zinc_mg             NUMERIC(10,2),
    sodium_mg           NUMERIC(10,2),
    potassium_mg        NUMERIC(10,2),
    magnesium_mg        NUMERIC(10,2),
    retinol_mcg         NUMERIC(10,2),
    beta_carotene_mcg   NUMERIC(10,2),
    vitamin_a_mcg       NUMERIC(10,2),
    vitamin_c_mg        NUMERIC(10,2),
    vitamin_b1_mg       NUMERIC(10,3),
    vitamin_b2_mg       NUMERIC(10,3),
    niacin_mg           NUMERIC(10,2),
    gi                  gi_level,
    is_animal_protein   BOOLEAN,                  -- phục vụ ràng buộc "Protid ĐV >= 60%"
    aliases             TEXT[] DEFAULT '{}',      -- tên gọi khác: {"rau bồ ngót"}
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (energy_kcal  IS NULL OR energy_kcal  >= 0),
    CHECK (protein_g    IS NULL OR protein_g    >= 0),
    CHECK (glucid_g     IS NULL OR glucid_g     >= 0),
    CHECK (potassium_mg IS NULL OR potassium_mg >= 0),
    CHECK (sodium_mg    IS NULL OR sodium_mg    >= 0)
);
CREATE INDEX idx_foods_name_trgm ON foods USING gin (f_unaccent(lower(name)) gin_trgm_ops);
CREATE INDEX idx_foods_potassium ON foods (potassium_mg);
CREATE INDEX idx_foods_gi        ON foods (gi);
CREATE TRIGGER trg_foods_updated BEFORE UPDATE ON foods FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- 2. DANH MỤC LÂM SÀNG (mở rộng bệnh = thêm dòng)
-- =====================================================================
-- 2.1 Bệnh lý
CREATE TABLE conditions (
    id          SMALLSERIAL PRIMARY KEY,
    code        VARCHAR(30) UNIQUE NOT NULL,      -- 'DTD', 'CKD', 'AKI', 'GN_ACUTE', 'NEPHROTIC', 'HTN'...
    name        VARCHAR(150) NOT NULL,
    group_name  VARCHAR(60) NOT NULL,             -- 'Đái tháo đường', 'Thận-Tiết niệu', 'Tim mạch'...
    icd10       VARCHAR(20),
    is_enabled  BOOLEAN NOT NULL DEFAULT TRUE,    -- MVP: chỉ bật 2 nhóm
    description TEXT
);

-- 2.2 Chỉ số xét nghiệm (biomarker) - thêm chỉ số mới = thêm dòng
CREATE TABLE biomarkers (
    id          SMALLSERIAL PRIMARY KEY,
    code        VARCHAR(30) UNIQUE NOT NULL,      -- 'EGFR','CREATININE','HBA1C','GLUCOSE','K','NA','URIC_ACID'...
    name        VARCHAR(120) NOT NULL,
    unit        VARCHAR(30) NOT NULL,             -- đơn vị chuẩn hóa lưu trong DB
    normal_min  NUMERIC(10,3),
    normal_max  NUMERIC(10,3),
    aliases     TEXT[] DEFAULT '{}'               -- tên trên phiếu BV: {"Cre","Creatinin"}
);

-- 2.3 Giai đoạn bệnh xác định bằng chỉ số (VD: CKD stage theo eGFR)
CREATE TABLE condition_stages (
    id            SERIAL PRIMARY KEY,
    condition_id  SMALLINT NOT NULL REFERENCES conditions(id) ON DELETE CASCADE,
    stage_code    VARCHAR(20) NOT NULL,           -- '1','2','3a','3b','4','5'
    stage_rank    SMALLINT NOT NULL,              -- để so sánh nặng/nhẹ
    biomarker_id  SMALLINT REFERENCES biomarkers(id),
    value_min     NUMERIC(10,3),                  -- inclusive
    value_max     NUMERIC(10,3),                  -- exclusive
    description   TEXT,
    UNIQUE (condition_id, stage_code)
);

-- =====================================================================
-- 3. PHÁC ĐỒ CHẾ ĐỘ ĂN BỘ Y TẾ (MaCheDoAn2006)
-- =====================================================================
CREATE TABLE diet_regimes (
    id                      SERIAL PRIMARY KEY,
    code                    VARCHAR(20) UNIQUE NOT NULL,   -- 'DD07-X', 'TN08-X'
    group_name              VARCHAR(60) NOT NULL,          -- 'Đái tháo đường', 'Thận-Tiết niệu'
    name                    VARCHAR(255) NOT NULL,
    -- Khung dinh dưỡng / ngày (NULL = không giới hạn)
    energy_min_kcal         NUMERIC(8,1),
    energy_max_kcal         NUMERIC(8,1),
    protein_min_g           NUMERIC(6,1),
    protein_max_g           NUMERIC(6,1),
    lipid_min_g             NUMERIC(6,1),
    lipid_max_g             NUMERIC(6,1),
    glucid_min_g            NUMERIC(6,1),
    glucid_max_g            NUMERIC(6,1),
    sodium_min_mg           NUMERIC(8,1),
    sodium_max_mg           NUMERIC(8,1),
    potassium_min_mg        NUMERIC(8,1),
    potassium_max_mg        NUMERIC(8,1),
    phosphate_max_mg        NUMERIC(8,1),
    cholesterol_max_mg      NUMERIC(8,1),
    fiber_min_g             NUMERIC(6,1),
    fiber_max_g             NUMERIC(6,1),
    water_min_l             NUMERIC(4,2),
    water_max_l             NUMERIC(4,2),
    meals_min               SMALLINT,
    meals_max               SMALLINT,
    -- Công thức theo cân nặng (cá nhân hóa): "35 Kcal/kg", "Protid 0.6-0.8 g/kg"
    energy_kcal_per_kg_min  NUMERIC(5,1),
    energy_kcal_per_kg_max  NUMERIC(5,1),
    protein_g_per_kg_min    NUMERIC(4,2),
    protein_g_per_kg_max    NUMERIC(4,2),
    animal_protein_min_pct  NUMERIC(5,1),                  -- "ĐV >= 60%"
    require_low_gi          BOOLEAN NOT NULL DEFAULT FALSE,
    notes                   TEXT,                          -- ghi chú gốc Bộ Y tế
    raw_source              JSONB,                         -- dòng Excel gốc (truy vết)
    is_enabled              BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX idx_regimes_group ON diet_regimes (group_name);

-- 3.1 Luật chọn phác đồ (data-driven matching) - Agent đọc bảng này
--   criteria JSONB ví dụ:
--   {"conditions_all":["DTD","CKD"], "stage":{"CKD":{"min_rank":3,"max_rank":4}},
--    "biomarkers":{"K":{"lte":5.0}}}
CREATE TABLE regime_selection_rules (
    id          SERIAL PRIMARY KEY,
    regime_id   INTEGER NOT NULL REFERENCES diet_regimes(id) ON DELETE CASCADE,
    priority    SMALLINT NOT NULL DEFAULT 100,    -- số nhỏ = ưu tiên cao (ca đa bệnh lý đặt nhỏ hơn)
    criteria    JSONB NOT NULL,
    description TEXT,
    is_enabled  BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX idx_rsr_criteria ON regime_selection_rules USING gin (criteria);

-- 3.2 Luật lọc thực phẩm theo phác đồ (dùng cho Guardrail + SQL Tool)
--   VD: TN09-X: potassium_mg per 100g > 300 -> BLOCK; DD*: gi = 'Cao' -> WARN
CREATE TABLE food_restriction_rules (
    id              SERIAL PRIMARY KEY,
    regime_id       INTEGER REFERENCES diet_regimes(id) ON DELETE CASCADE,
    condition_id    SMALLINT REFERENCES conditions(id) ON DELETE CASCADE,
    nutrient_column VARCHAR(40),                  -- tên cột trong foods: 'potassium_mg','gi'...
    operator        VARCHAR(5) NOT NULL CHECK (operator IN ('>','>=','<','<=','=','IN')),
    threshold_num   NUMERIC(10,2),
    threshold_text  TEXT[],                       -- cho gi: {'Cao'}
    food_id         INTEGER REFERENCES foods(id), -- luật cấm đích danh 1 món (tùy chọn)
    action          guardrail_action NOT NULL DEFAULT 'WARN',
    reason          TEXT NOT NULL,                -- câu giải thích hiển thị cho người dùng
    CHECK (regime_id IS NOT NULL OR condition_id IS NOT NULL),
    CHECK (nutrient_column IS NOT NULL OR food_id IS NOT NULL)
);

-- =====================================================================
-- 4. NGƯỜI DÙNG & HỒ SƠ BỆNH NHÂN
-- =====================================================================
CREATE TABLE app_users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username      VARCHAR(100) UNIQUE,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT,
    display_name  VARCHAR(120),
    role          VARCHAR(20) NOT NULL DEFAULT 'PATIENT' CHECK (role IN ('ADMIN', 'PATIENT')),
    patient_id    UUID REFERENCES patients(id) ON DELETE SET NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 1 tài khoản quản lý nhiều hồ sơ (Bố, Mẹ, Bản thân)
CREATE TABLE patients (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    nickname        VARCHAR(100) NOT NULL,       -- "Bố Nam" (không bắt buộc tên thật - privacy)
    gender          gender_type NOT NULL,
    birth_year      SMALLINT CHECK (birth_year BETWEEN 1900 AND 2100),
    height_cm       NUMERIC(5,1) CHECK (height_cm BETWEEN 40 AND 250),
    activity_level  activity_type NOT NULL DEFAULT 'Ít vận động',
    food_allergies  TEXT[] DEFAULT '{}',
    food_dislikes   TEXT[] DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_patients_user ON patients (user_id);
CREATE TRIGGER trg_patients_updated BEFORE UPDATE ON patients FOR EACH ROW EXECUTE FUNCTION set_updated_at();
-- Lưu năm sinh thay vì tuổi -> tuổi luôn đúng theo thời gian.

-- Bệnh lý hiện tại của bệnh nhân (có lịch sử: resolved_at)
CREATE TABLE patient_conditions (
    id              BIGSERIAL PRIMARY KEY,
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    condition_id    SMALLINT NOT NULL REFERENCES conditions(id),
    stage_id        INTEGER REFERENCES condition_stages(id),
    diagnosed_at    DATE,
    resolved_at     DATE,                          -- NULL = đang mắc
    source_checkup_id BIGINT,                      -- FK thêm ở dưới
    notes           TEXT
);
CREATE UNIQUE INDEX uq_patient_active_condition
    ON patient_conditions (patient_id, condition_id) WHERE resolved_at IS NULL;

-- =====================================================================
-- 5. TÀI LIỆU UPLOAD & LỊCH SỬ KHÁM (cập nhật nhiều lần)
-- =====================================================================
CREATE TABLE medical_documents (
    id              BIGSERIAL PRIMARY KEY,
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    file_path       TEXT NOT NULL,                 -- đường dẫn object storage / local
    mime_type       VARCHAR(80),
    file_sha256     VARCHAR(64),                   -- hash file để chống upload trùng
    status          doc_status NOT NULL DEFAULT 'UPLOADED',
    extracted_json  JSONB,                         -- output Pydantic của Vision model (đã xóa PII)
    model_name      VARCHAR(80),
    trace_id        VARCHAR(100),                  -- Langfuse trace
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_at    TIMESTAMPTZ
);

-- Mỗi lần khám = 1 dòng. Không ghi đè -> giữ timeline tiến triển.
CREATE TABLE checkups (
    id              BIGSERIAL PRIMARY KEY,
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    document_id     BIGINT REFERENCES medical_documents(id) ON DELETE SET NULL,
    checkup_date    DATE NOT NULL,
    weight_kg       NUMERIC(5,1) CHECK (weight_kg BETWEEN 2 AND 400),
    systolic_bp     SMALLINT,
    diastolic_bp    SMALLINT,
    is_on_dialysis  BOOLEAN,
    dialysis_per_week SMALLINT,
    source          VARCHAR(20) NOT NULL DEFAULT 'MANUAL' CHECK (source IN ('MANUAL','UPLOAD')),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_checkups_patient_date ON checkups (patient_id, checkup_date DESC);

ALTER TABLE patient_conditions
    ADD CONSTRAINT fk_pc_checkup FOREIGN KEY (source_checkup_id) REFERENCES checkups(id) ON DELETE SET NULL;

-- Kết quả xét nghiệm dạng dọc (EAV) -> thêm chỉ số mới không đổi schema
CREATE TABLE lab_results (
    id              BIGSERIAL PRIMARY KEY,
    checkup_id      BIGINT NOT NULL REFERENCES checkups(id) ON DELETE CASCADE,
    biomarker_id    SMALLINT NOT NULL REFERENCES biomarkers(id),
    value           NUMERIC(12,3) NOT NULL,
    raw_value_text  VARCHAR(60),                   -- giá trị gốc trên phiếu
    raw_unit        VARCHAR(30),                   -- đơn vị gốc (đã quy đổi sang biomarkers.unit)
    UNIQUE (checkup_id, biomarker_id)
);

-- =====================================================================
-- 6. MỤC TIÊU DINH DƯỠNG ĐÃ TÍNH (có lịch sử, 1 bản current / bệnh nhân)
-- =====================================================================
CREATE TABLE nutrition_targets (
    id                  BIGSERIAL PRIMARY KEY,
    patient_id          UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    checkup_id          BIGINT REFERENCES checkups(id) ON DELETE SET NULL,
    regime_id           INTEGER REFERENCES diet_regimes(id),
    selection_rule_id   INTEGER REFERENCES regime_selection_rules(id),
    bmr_kcal            NUMERIC(8,1),
    tdee_kcal           NUMERIC(8,1),
    energy_kcal         NUMERIC(8,1) NOT NULL,
    protein_g           NUMERIC(6,1),
    lipid_g             NUMERIC(6,1),
    glucid_g            NUMERIC(6,1),
    sodium_max_mg       NUMERIC(8,1),
    potassium_max_mg    NUMERIC(8,1),
    phosphate_max_mg    NUMERIC(8,1),
    fiber_min_g         NUMERIC(6,1),
    water_max_l         NUMERIC(4,2),
    meals_per_day       SMALLINT,
    require_low_gi      BOOLEAN NOT NULL DEFAULT FALSE,
    calculation_detail  JSONB,                     -- công thức + giá trị đầu vào (giải thích được)
    is_current          BOOLEAN NOT NULL DEFAULT TRUE,
    valid_from          TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to            TIMESTAMPTZ
);
CREATE UNIQUE INDEX uq_targets_current ON nutrition_targets (patient_id) WHERE is_current;

-- =====================================================================
-- 7. THỰC ĐƠN NGÀY / TUẦN / THÁNG
--    meal_plans -> meal_plan_days -> meals -> dishes -> dish_ingredients(food)
-- =====================================================================
CREATE TABLE meal_plans (
    id              BIGSERIAL PRIMARY KEY,
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    target_id       BIGINT NOT NULL REFERENCES nutrition_targets(id),
    period          plan_period NOT NULL,
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    rotation_days   SMALLINT,                      -- tháng = chu kỳ 7 ngày xoay vòng
    status          plan_status NOT NULL DEFAULT 'DRAFT',
    guardrail_passed BOOLEAN,
    model_name      VARCHAR(80),
    trace_id        VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (end_date >= start_date)
);
CREATE INDEX idx_meal_plans_patient ON meal_plans (patient_id, start_date DESC);

CREATE TABLE meal_plan_days (
    id              BIGSERIAL PRIMARY KEY,
    meal_plan_id    BIGINT NOT NULL REFERENCES meal_plans(id) ON DELETE CASCADE,
    day_index       SMALLINT NOT NULL,             -- 1..7 (hoặc 1..30)
    plan_date       DATE,
    UNIQUE (meal_plan_id, day_index)
);

CREATE TABLE meals (
    id              BIGSERIAL PRIMARY KEY,
    plan_day_id     BIGINT NOT NULL REFERENCES meal_plan_days(id) ON DELETE CASCADE,
    meal            meal_type NOT NULL,
    UNIQUE (plan_day_id, meal)
);

CREATE TABLE dishes (
    id              BIGSERIAL PRIMARY KEY,
    meal_id         BIGINT NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
    name            VARCHAR(200) NOT NULL,         -- "Cá quả hấp gừng"
    cooking_method  VARCHAR(50),                   -- Luộc / Hấp / Kho nhạt...
    instructions    TEXT,
    sort_order      SMALLINT NOT NULL DEFAULT 1
);

CREATE TABLE dish_ingredients (
    id              BIGSERIAL PRIMARY KEY,
    dish_id         BIGINT NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
    food_id         INTEGER NOT NULL REFERENCES foods(id),
    grams           NUMERIC(7,1) NOT NULL CHECK (grams > 0),   -- gram ăn được
    UNIQUE (dish_id, food_id)
);

-- =====================================================================
-- 8. CHAT / AGENT MEMORY
-- =====================================================================
CREATE TABLE chat_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    title           VARCHAR(200),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chat_messages (
    id              BIGSERIAL PRIMARY KEY,
    session_id      UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role            VARCHAR(12) NOT NULL CHECK (role IN ('user','assistant','tool','system')),
    content         TEXT NOT NULL,
    intent          VARCHAR(30),                   -- NUTRITION_LOOKUP / SAFETY_CHECK / MEAL_PLANNING
    tool_calls      JSONB,
    trace_id        VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chat_messages_session ON chat_messages (session_id, created_at);

-- 9. RAG -> xem 05_rag_pgvector.sql

-- =====================================================================
-- 10. OBSERVABILITY - GUARDRAILS - EVALS
-- =====================================================================
CREATE TABLE agent_runs (
    id              BIGSERIAL PRIMARY KEY,
    trace_id        VARCHAR(100) UNIQUE,           -- Langfuse trace id
    patient_id      UUID REFERENCES patients(id) ON DELETE SET NULL,
    workflow        VARCHAR(50) NOT NULL,          -- 'qa', 'meal_plan', 'doc_extract'
    model_name      VARCHAR(80),
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    cost_usd        NUMERIC(10,6),
    latency_ms      INTEGER,
    status          VARCHAR(20) NOT NULL DEFAULT 'SUCCESS',
    error           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE guardrail_events (
    id              BIGSERIAL PRIMARY KEY,
    run_id          BIGINT REFERENCES agent_runs(id) ON DELETE CASCADE,
    stage           VARCHAR(10) NOT NULL CHECK (stage IN ('INPUT','OUTPUT')),
    guardrail_name  VARCHAR(60) NOT NULL,          -- 'pii_redaction','off_topic','nutrient_limit','food_restriction'
    rule_id         INTEGER REFERENCES food_restriction_rules(id) ON DELETE SET NULL,
    action          guardrail_action NOT NULL,
    detail          JSONB,                         -- {"food":"Rau ngót","potassium_mg":457,"limit":300}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_guardrail_events_name ON guardrail_events (guardrail_name, action);

CREATE TABLE eval_cases (
    id              SERIAL PRIMARY KEY,
    category        VARCHAR(40) NOT NULL,          -- 'safety_check','lookup','meal_plan','extraction'
    input           JSONB NOT NULL,                -- câu hỏi + hồ sơ bệnh nhân giả lập
    expected        JSONB NOT NULL,                -- {"verdict":"KHÔNG NÊN","must_mention":["kali"]}
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE eval_runs (
    id              SERIAL PRIMARY KEY,
    git_commit      VARCHAR(40),
    model_name      VARCHAR(80),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    summary         JSONB                          -- {"adherence":0.98,"hallucination":0.0}
);

CREATE TABLE eval_results (
    id              BIGSERIAL PRIMARY KEY,
    eval_run_id     INTEGER NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    case_id         INTEGER NOT NULL REFERENCES eval_cases(id) ON DELETE CASCADE,
    output          JSONB,
    metrics         JSONB,                         -- {"medical_adherence":1,"faithfulness":0.92}
    passed          BOOLEAN NOT NULL,
    trace_id        VARCHAR(100)
);

-- =====================================================================
-- 11. VIEWS tiện dụng cho Agent / App
-- =====================================================================
-- Chỉ số xét nghiệm mới nhất của từng bệnh nhân
CREATE VIEW v_latest_lab_results AS
SELECT DISTINCT ON (c.patient_id, lr.biomarker_id)
       c.patient_id, b.code AS biomarker_code, b.name AS biomarker_name,
       lr.value, b.unit, c.checkup_date
FROM lab_results lr
JOIN checkups c   ON c.id = lr.checkup_id
JOIN biomarkers b ON b.id = lr.biomarker_id
ORDER BY c.patient_id, lr.biomarker_id, c.checkup_date DESC, c.id DESC;

-- Hồ sơ tổng hợp để nạp vào context Agent
CREATE VIEW v_patient_profile AS
SELECT p.id AS patient_id, p.nickname, p.gender,
       EXTRACT(YEAR FROM now())::int - p.birth_year AS age,
       p.height_cm, p.activity_level,
       lc.weight_kg, lc.checkup_date AS last_checkup,
       ROUND(lc.weight_kg / NULLIF((p.height_cm/100)^2, 0), 1) AS bmi,
       (SELECT array_agg(cd.code || COALESCE(':' || cs.stage_code, ''))
          FROM patient_conditions pc
          JOIN conditions cd ON cd.id = pc.condition_id
          LEFT JOIN condition_stages cs ON cs.id = pc.stage_id
         WHERE pc.patient_id = p.id AND pc.resolved_at IS NULL) AS active_conditions,
       nt.energy_kcal, nt.protein_g, nt.sodium_max_mg, nt.potassium_max_mg,
       dr.code AS regime_code, dr.name AS regime_name
FROM patients p
LEFT JOIN LATERAL (SELECT weight_kg, checkup_date FROM checkups
                   WHERE patient_id = p.id AND weight_kg IS NOT NULL
                   ORDER BY checkup_date DESC, id DESC LIMIT 1) lc ON TRUE
LEFT JOIN nutrition_targets nt ON nt.patient_id = p.id AND nt.is_current
LEFT JOIN diet_regimes dr ON dr.id = nt.regime_id;

-- Dinh dưỡng thực tế của từng món / bữa / ngày (tính bằng SQL, không để LLM tính)
CREATE VIEW v_dish_nutrition AS
SELECT d.id AS dish_id, d.meal_id,
       ROUND(SUM(f.energy_kcal   * di.grams / 100), 1) AS energy_kcal,
       ROUND(SUM(f.protein_g     * di.grams / 100), 1) AS protein_g,
       ROUND(SUM(f.lipid_g       * di.grams / 100), 1) AS lipid_g,
       ROUND(SUM(f.glucid_g      * di.grams / 100), 1) AS glucid_g,
       ROUND(SUM(f.fiber_g       * di.grams / 100), 1) AS fiber_g,
       ROUND(SUM(f.sodium_mg     * di.grams / 100), 0) AS sodium_mg,
       ROUND(SUM(f.potassium_mg  * di.grams / 100), 0) AS potassium_mg,
       ROUND(SUM(f.phosphorus_mg * di.grams / 100), 0) AS phosphorus_mg,
       COUNT(*) FILTER (WHERE f.potassium_mg IS NULL OR f.sodium_mg IS NULL) AS missing_data_count
FROM dishes d
JOIN dish_ingredients di ON di.dish_id = d.id
JOIN foods f ON f.id = di.food_id
GROUP BY d.id, d.meal_id;

CREATE VIEW v_day_nutrition AS
SELECT pd.meal_plan_id, pd.day_index, pd.plan_date,
       SUM(v.energy_kcal) AS energy_kcal, SUM(v.protein_g) AS protein_g,
       SUM(v.lipid_g) AS lipid_g, SUM(v.glucid_g) AS glucid_g, SUM(v.fiber_g) AS fiber_g,
       SUM(v.sodium_mg) AS sodium_mg, SUM(v.potassium_mg) AS potassium_mg,
       SUM(v.phosphorus_mg) AS phosphorus_mg
FROM meal_plan_days pd
JOIN meals m ON m.plan_day_id = pd.id
JOIN v_dish_nutrition v ON v.meal_id = m.id
GROUP BY pd.meal_plan_id, pd.day_index, pd.plan_date;

-- Ngày nào vượt ngưỡng -> Guardrail đọc view này
CREATE VIEW v_day_violations AS
SELECT dn.*, nt.energy_kcal AS target_kcal, nt.protein_g AS target_protein,
       nt.sodium_max_mg, nt.potassium_max_mg, nt.phosphate_max_mg,
       (nt.sodium_max_mg    IS NOT NULL AND dn.sodium_mg    > nt.sodium_max_mg)    AS sodium_exceeded,
       (nt.potassium_max_mg IS NOT NULL AND dn.potassium_mg > nt.potassium_max_mg) AS potassium_exceeded,
       (nt.phosphate_max_mg IS NOT NULL AND dn.phosphorus_mg > nt.phosphate_max_mg) AS phosphate_exceeded,
       (nt.protein_g IS NOT NULL AND dn.protein_g > nt.protein_g * 1.1)            AS protein_exceeded,
       (ABS(dn.energy_kcal - nt.energy_kcal) > nt.energy_kcal * 0.1)               AS energy_off_target
FROM v_day_nutrition dn
JOIN meal_plans mp ON mp.id = dn.meal_plan_id
JOIN nutrition_targets nt ON nt.id = mp.target_id;
