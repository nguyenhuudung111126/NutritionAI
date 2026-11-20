-- =====================================================================
-- 04_seed_catalog.sql - Danh mục lâm sàng cho MVP (Đái tháo đường + Thận)
-- Thêm bệnh mới: INSERT vào conditions / biomarkers / regime_selection_rules
-- / food_restriction_rules. KHÔNG cần sửa code.
-- Chạy SAU 03_seed_regimes.sql (vì luật tham chiếu mã phác đồ).
-- =====================================================================
SET search_path TO nutri, public;

-- 1. Bệnh lý -----------------------------------------------------------
INSERT INTO conditions (code, name, group_name, icd10, is_enabled) VALUES
 ('DTD',           'Đái tháo đường',               'Đái tháo đường', 'E11',  TRUE),
 ('CKD',           'Bệnh thận mạn / Suy thận mạn', 'Thận-Tiết niệu', 'N18',  TRUE),
 ('AKI',           'Suy thận cấp',                 'Thận-Tiết niệu', 'N17',  TRUE),
 ('GN_ACUTE',      'Viêm cầu thận cấp',            'Thận-Tiết niệu', 'N00',  TRUE),
 ('GN_CHRONIC',    'Viêm cầu thận mạn',            'Thận-Tiết niệu', 'N03',  TRUE),
 ('NEPHROTIC',     'Hội chứng thận hư',            'Thận-Tiết niệu', 'N04',  TRUE),
 ('HTN',           'Tăng huyết áp',                'Tim mạch',       'I10',  TRUE),
 ('DYSLIPIDEMIA',  'Rối loạn mỡ máu',              'Chuyển hóa',     'E78',  TRUE),
 -- Chưa bật trong MVP - chỉ cần đổi is_enabled = TRUE khi mở rộng
 ('HEART_FAILURE', 'Suy tim',                      'Tim mạch',       'I50',  FALSE),
 ('GOUT',          'Gout',                         'Chuyển hóa',     'M10',  FALSE),
 ('CIRRHOSIS',     'Xơ gan',                       'Gan mật',        'K74',  FALSE);

-- 2. Chỉ số xét nghiệm (đơn vị chuẩn trong DB) ---------------------------
INSERT INTO biomarkers (code, name, unit, normal_min, normal_max, aliases) VALUES
 ('EGFR',         'Mức lọc cầu thận ước tính', 'mL/min/1.73m2', 90,   NULL, '{"eGFR","MLCT","GFR"}'),
 ('CREATININE',   'Creatinin máu',             'µmol/L',        62,   106,  '{"Creatinin","Cre","Creatinine"}'),
 ('UREA',         'Ure máu',                   'mmol/L',        2.5,  7.5,  '{"Urê","Ure","BUN"}'),
 ('GLUCOSE',      'Glucose máu lúc đói',       'mmol/L',        3.9,  6.4,  '{"Glucose","Đường huyết","GLU"}'),
 ('HBA1C',        'HbA1c',                     '%',             4.0,  5.6,  '{"HbA1c","A1C"}'),
 ('K',            'Kali máu',                  'mmol/L',        3.5,  5.0,  '{"K+","Kali","Potassium"}'),
 ('NA',           'Natri máu',                 'mmol/L',        135,  145,  '{"Na+","Natri","Sodium"}'),
 ('PHOSPHATE',    'Phospho máu',               'mmol/L',        0.81, 1.45, '{"Phospho","P"}'),
 ('ALBUMIN',      'Albumin máu',               'g/L',           35,   50,   '{"Albumin","ALB"}'),
 ('URINE_PROTEIN','Protein niệu 24h',          'g/24h',         0,    0.15, '{"Protein niệu","Đạm niệu"}'),
 ('CHOLESTEROL',  'Cholesterol toàn phần',     'mmol/L',        NULL, 5.2,  '{"Cholesterol","CHOL"}'),
 ('TRIGLYCERIDE', 'Triglycerid',               'mmol/L',        NULL, 1.7,  '{"Triglycerid","TG"}'),
 ('LDL',          'LDL-Cholesterol',           'mmol/L',        NULL, 3.4,  '{"LDL-C","LDL"}'),
 ('HDL',          'HDL-Cholesterol',           'mmol/L',        1.0,  NULL, '{"HDL-C","HDL"}'),
 ('URIC_ACID',    'Acid uric máu',             'µmol/L',        NULL, 420,  '{"Acid Uric","Uric"}');

-- 3. Giai đoạn bệnh thận mạn theo eGFR (KDIGO) ----------------------------
INSERT INTO condition_stages (condition_id, stage_code, stage_rank, biomarker_id, value_min, value_max, description)
SELECT c.id, s.stage_code, s.stage_rank, b.id, s.vmin, s.vmax, s.descr
FROM conditions c, biomarkers b,
 (VALUES ('1', 1, 90, NULL, 'eGFR >= 90'),
         ('2', 2, 60, 90,   'eGFR 60-89'),
         ('3a',3, 45, 60,   'eGFR 45-59'),
         ('3b',4, 30, 45,   'eGFR 30-44'),
         ('4', 5, 15, 30,   'eGFR 15-29'),
         ('5', 6, NULL, 15, 'eGFR < 15')) AS s(stage_code, stage_rank, vmin, vmax, descr)
WHERE c.code = 'CKD' AND b.code = 'EGFR';

-- 4. Luật chọn phác đồ (Agent đánh giá theo priority tăng dần, khớp đầu tiên thắng)
-- Ngữ nghĩa criteria (app/agent implement):
--   conditions_all : bệnh nhân phải có TẤT CẢ các bệnh
--   conditions_any : có ít nhất 1
--   stage          : {"CKD": {"min_rank":3,"max_rank":6}}
--   biomarkers     : {"K": {"gt":5.0}}   (gt, gte, lt, lte - lấy giá trị mới nhất)
--   bmi / systolic_bp : {"gt": 25}
--   dialysis_per_week : số buổi lọc máu / tuần (0 = không lọc)
--   any_of         : danh sách criteria con, chỉ cần 1 cái đúng
INSERT INTO regime_selection_rules (regime_id, priority, criteria, description)
SELECT r.id, x.priority, x.criteria::jsonb, x.descr
FROM diet_regimes r
JOIN (VALUES
  -- Đa bệnh lý: ưu tiên cao nhất
  ('DD07-X', 10, '{"conditions_all":["DTD","CKD"],"stage":{"CKD":{"min_rank":3,"max_rank":6}},"dialysis_per_week":0}', 'ĐTĐ + Suy thận mạn độ 3-4'),
  ('DD06-X', 11, '{"conditions_all":["DTD","CKD"],"stage":{"CKD":{"min_rank":1,"max_rank":2}}}', 'ĐTĐ + Suy thận mạn độ 1-2'),
  ('DD03-X', 12, '{"conditions_all":["DTD","GN_ACUTE"],"biomarkers":{"UREA":{"gt":7.5}}}', 'ĐTĐ + Viêm cầu thận, urê cao'),
  ('DD04-X', 13, '{"conditions_all":["DTD","GN_ACUTE"],"any_of":[{"conditions_any":["HTN"]},{"systolic_bp":{"gte":140}}]}', 'ĐTĐ + Viêm cầu thận, cao huyết áp'),
  ('DD05-X', 14, '{"conditions_all":["DTD","GN_ACUTE"]}', 'ĐTĐ + Viêm cầu thận giai đoạn hồi phục'),
  ('DD08-X', 15, '{"conditions_all":["DTD","HEART_FAILURE"]}', 'ĐTĐ + Suy tim độ 3-4'),
  -- Thận: lọc máu
  ('TN10-X', 20, '{"conditions_any":["CKD"],"dialysis_per_week":3}', 'Lọc máu 3 lần/tuần'),
  ('TN11-X', 21, '{"conditions_any":["CKD"],"dialysis_per_week":2}', 'Lọc máu 2 lần/tuần'),
  ('TN12-X', 22, '{"conditions_any":["CKD"],"dialysis_per_week":1}', 'Lọc máu 1 lần/tuần'),
  ('TN06-X', 23, '{"conditions_any":["AKI"],"dialysis_per_week":{"gte":1}}', 'Suy thận cấp có lọc máu'),
  ('TN05-X', 24, '{"conditions_any":["AKI"]}', 'Suy thận cấp trước lọc máu'),
  -- Thận mạn chưa lọc máu
  ('TN09-X', 30, '{"conditions_any":["CKD"],"stage":{"CKD":{"min_rank":3,"max_rank":6}},"biomarkers":{"K":{"gt":5.0}}}', 'Suy thận mạn 3-4 có tăng Kali'),
  ('TN08-X', 31, '{"conditions_any":["CKD"],"stage":{"CKD":{"min_rank":3,"max_rank":6}}}', 'Suy thận mạn 3-4 không tăng Kali'),
  ('TN07-X', 32, '{"conditions_any":["CKD"],"stage":{"CKD":{"min_rank":1,"max_rank":2}}}', 'Suy thận mạn 1-2'),
  -- Viêm cầu thận / thận hư
  ('TN01-X', 40, '{"conditions_any":["GN_ACUTE"],"biomarkers":{"UREA":{"gt":7.5}}}', 'Viêm cầu thận cấp, urê cao'),
  ('TN02-X', 41, '{"conditions_any":["GN_ACUTE"],"any_of":[{"conditions_any":["HTN"]},{"systolic_bp":{"gte":140}}]}', 'Viêm cầu thận cấp, cao huyết áp'),
  ('TN03-X', 42, '{"conditions_any":["GN_ACUTE"]}', 'Viêm cầu thận cấp hồi phục'),
  ('TN04-X', 43, '{"conditions_any":["GN_CHRONIC"]}', 'Viêm cầu thận mạn'),
  ('TN14-X', 44, '{"conditions_any":["NEPHROTIC"],"biomarkers":{"EGFR":{"lt":60}}}', 'Thận hư có tổn thương chức năng thận'),
  ('TN13-X', 45, '{"conditions_any":["NEPHROTIC"]}', 'Thận hư không tổn thương chức năng thận'),
  -- ĐTĐ đơn thuần
  ('DD02-X', 50, '{"conditions_all":["DTD"],"any_of":[{"bmi":{"gt":25}},{"conditions_any":["DYSLIPIDEMIA"]}]}', 'ĐTĐ thừa cân / rối loạn mỡ máu'),
  ('DD01-X', 60, '{"conditions_all":["DTD"]}', 'ĐTĐ đơn thuần'),
  -- Mặc định
  ('BT01-X', 999, '{}', 'Không có bệnh lý đặc biệt')
) AS x(code, priority, criteria, descr) ON x.code = r.code;

-- 5. Luật lọc thực phẩm (Guardrail + SQL Tool tìm món thay thế) -----------
-- Ngưỡng trên 100g thực phẩm ăn được.
INSERT INTO food_restriction_rules (condition_id, regime_id, nutrient_column, operator, threshold_num, threshold_text, action, reason)
SELECT c.id, NULL, x.col, x.op, x.num, x.txt::text[], x.act::nutri.guardrail_action, x.reason
FROM conditions c
JOIN (VALUES
  ('DTD', 'gi',            'IN', NULL::numeric, '{"Cao"}', 'WARN', 'Thực phẩm có chỉ số đường huyết (GI) cao, làm tăng đường máu nhanh. Nên chọn loại GI thấp hoặc ăn lượng nhỏ kèm rau.'),
  ('DTD', 'glucid_g',      '>',  70,            NULL,      'WARN', 'Hàm lượng glucid rất cao (>70g/100g), cần kiểm soát khẩu phần.'),
  ('CKD', 'potassium_mg',  '>',  300,           NULL,      'WARN', 'Thực phẩm giàu Kali (>300mg/100g) - thận suy giảm đào thải Kali, nguy cơ tăng Kali máu.'),
  ('CKD', 'phosphorus_mg', '>',  300,           NULL,      'WARN', 'Thực phẩm giàu Phospho (>300mg/100g), cần hạn chế ở bệnh nhân suy thận.'),
  ('CKD', 'sodium_mg',     '>',  400,           NULL,      'WARN', 'Thực phẩm nhiều Natri (>400mg/100g), gây giữ nước, tăng huyết áp.'),
  ('CKD', 'protein_g',     '>',  20,            NULL,      'WARN', 'Thực phẩm giàu đạm, cần tính chính xác khẩu phần theo g đạm/kg cân nặng.'),
  ('HTN', 'sodium_mg',     '>',  400,           NULL,      'WARN', 'Thực phẩm nhiều Natri (>400mg/100g), không phù hợp người tăng huyết áp.')
) AS x(ccode, col, op, num, txt, act, reason) ON x.ccode = c.code;

-- Luật siết theo phác đồ cụ thể (BLOCK = không được đưa vào thực đơn)
INSERT INTO food_restriction_rules (regime_id, nutrient_column, operator, threshold_num, action, reason)
SELECT r.id, x.col, x.op, x.num, x.act::nutri.guardrail_action, x.reason
FROM diet_regimes r
JOIN (VALUES
  ('TN09-X', 'potassium_mg',  '>', 250, 'BLOCK', 'Phác đồ suy thận có tăng Kali: loại thực phẩm Kali >250mg/100g.'),
  ('TN09-X', 'phosphorus_mg', '>', 250, 'BLOCK', 'Phác đồ TN09: Phosphat <600mg/ngày, loại thực phẩm Phospho >250mg/100g.'),
  ('TN05-X', 'potassium_mg',  '>', 250, 'BLOCK', 'Suy thận cấp trước lọc: Kali tối đa 1000mg/ngày.'),
  ('DD03-X', 'potassium_mg',  '>', 250, 'BLOCK', 'ĐTĐ + Viêm cầu thận urê cao: Kali <1000mg/ngày.'),
  ('DD07-X', 'gi',            'IN', NULL,'BLOCK', 'ĐTĐ + Suy thận 3-4: không dùng thực phẩm GI cao.')
) AS x(code, col, op, num, act, reason) ON x.code = r.code;

UPDATE food_restriction_rules SET threshold_text = '{"Cao"}'
WHERE nutrient_column = 'gi' AND threshold_text IS NULL;
