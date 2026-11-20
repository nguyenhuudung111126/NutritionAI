-- =====================================================================
-- 99_demo_patient.sql - Ca bệnh mẫu để demo / test (có thể bỏ qua)
-- Bác Nam, 58 tuổi, ĐTĐ type 2 + Suy thận mạn 3b, 65kg, 168cm
-- =====================================================================
SET search_path TO nutri, public;

INSERT INTO app_users (id, email, display_name)
VALUES ('00000000-0000-0000-0000-000000000001', 'demo@nutriguard.ai', 'Demo');

INSERT INTO patients (id, user_id, nickname, gender, birth_year, height_cm, activity_level)
VALUES ('00000000-0000-0000-0000-0000000000a1', '00000000-0000-0000-0000-000000000001',
        'Bác Nam', 'Nam', 1968, 168, 'Ít vận động');

-- Lần khám 1 (tháng 8)
INSERT INTO checkups (id, patient_id, checkup_date, weight_kg, systolic_bp, diastolic_bp, is_on_dialysis, dialysis_per_week, source)
VALUES (1, '00000000-0000-0000-0000-0000000000a1', '2026-08-15', 68, 145, 90, FALSE, 0, 'MANUAL');
INSERT INTO lab_results (checkup_id, biomarker_id, value)
SELECT 1, id, v FROM biomarkers b JOIN (VALUES ('EGFR',42),('CREATININE',160),('HBA1C',8.2),('K',4.8),('GLUCOSE',9.1)) x(c,v) ON x.c=b.code;

-- Lần khám 2 (tháng 11) - cập nhật sau tái khám
INSERT INTO checkups (id, patient_id, checkup_date, weight_kg, systolic_bp, diastolic_bp, is_on_dialysis, dialysis_per_week, source)
VALUES (2, '00000000-0000-0000-0000-0000000000a1', '2026-11-15', 65, 135, 85, FALSE, 0, 'UPLOAD');
INSERT INTO lab_results (checkup_id, biomarker_id, value)
SELECT 2, id, v FROM biomarkers b JOIN (VALUES ('EGFR',39),('CREATININE',165),('HBA1C',7.1),('K',4.9),('GLUCOSE',7.4)) x(c,v) ON x.c=b.code;
SELECT setval(pg_get_serial_sequence('nutri.checkups','id'), 2);

INSERT INTO patient_conditions (patient_id, condition_id, stage_id, diagnosed_at, source_checkup_id)
SELECT '00000000-0000-0000-0000-0000000000a1', c.id, NULL, '2020-01-01', 1 FROM conditions c WHERE c.code = 'DTD';
INSERT INTO patient_conditions (patient_id, condition_id, stage_id, diagnosed_at, source_checkup_id)
SELECT '00000000-0000-0000-0000-0000000000a1', c.id, s.id, '2025-06-01', 2
FROM conditions c JOIN condition_stages s ON s.condition_id = c.id AND s.stage_code = '3b' WHERE c.code = 'CKD';

-- Mục tiêu dinh dưỡng (app tính: phác đồ DD07-X, 30 kcal/kg, 0.6 g đạm/kg)
INSERT INTO nutrition_targets (id, patient_id, checkup_id, regime_id, energy_kcal, protein_g, sodium_max_mg,
                               potassium_max_mg, phosphate_max_mg, fiber_min_g, water_max_l, meals_per_day,
                               require_low_gi, calculation_detail)
SELECT 1, '00000000-0000-0000-0000-0000000000a1', 2, r.id, 65*30, 65*0.6, r.sodium_max_mg, r.potassium_max_mg,
       r.phosphate_max_mg, r.fiber_min_g, r.water_max_l, 5, r.require_low_gi,
       '{"weight_kg":65,"kcal_per_kg":30,"protein_g_per_kg":0.6,"regime":"DD07-X"}'
FROM diet_regimes r WHERE r.code = 'DD07-X';
SELECT setval(pg_get_serial_sequence('nutri.nutrition_targets','id'), 1);

-- Thực đơn 1 ngày (bữa trưa) để test view tính dinh dưỡng
INSERT INTO meal_plans (id, patient_id, target_id, period, start_date, end_date, status)
VALUES (1, '00000000-0000-0000-0000-0000000000a1', 1, 'DAY', '2026-11-20', '2026-11-20', 'DRAFT');
INSERT INTO meal_plan_days (id, meal_plan_id, day_index, plan_date) VALUES (1, 1, 1, '2026-11-20');
INSERT INTO meals (id, plan_day_id, meal) VALUES (1, 1, 'Trưa');
INSERT INTO dishes (id, meal_id, name, cooking_method) VALUES
 (1, 1, 'Cơm gạo tẻ', 'Nấu'), (2, 1, 'Canh bí đao', 'Luộc');
INSERT INTO dish_ingredients (dish_id, food_id, grams)
SELECT 1, id, 120 FROM foods WHERE name = 'Gạo tẻ máy'
UNION ALL
SELECT 2, id, 150 FROM foods WHERE name = 'Bí đao';
SELECT setval(pg_get_serial_sequence('nutri.meal_plans','id'), 1);
SELECT setval(pg_get_serial_sequence('nutri.meal_plan_days','id'), 1);
SELECT setval(pg_get_serial_sequence('nutri.meals','id'), 1);
SELECT setval(pg_get_serial_sequence('nutri.dishes','id'), 2);
