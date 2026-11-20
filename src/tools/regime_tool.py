"""Tool so khớp hồ sơ bệnh nhân với phác đồ Bộ Y tế (`regime_selection_rules`)
và tính mục tiêu dinh dưỡng cá nhân hóa (`nutrition_targets`)."""
import json
from typing import Any, Dict, Optional

from src.db import get_conn


def _infer_ckd_stage(egfr: Optional[float]) -> tuple[int, str]:
    if egfr is None:
        return 1, "1"
    if egfr >= 90:
        return 1, "1"
    if egfr >= 60:
        return 2, "2"
    if egfr >= 45:
        return 3, "3a"
    if egfr >= 30:
        return 4, "3b"
    if egfr >= 15:
        return 5, "4"
    return 6, "5"


def get_patient_context(patient_id: str) -> Dict[str, Any]:
    """Tổng hợp hồ sơ, bệnh lý đang mắc, giai đoạn và chỉ số XN mới nhất."""
    with get_conn() as conn:
        profile = conn.execute(
            """
            SELECT p.id, p.nickname, p.gender, p.birth_year,
                   EXTRACT(YEAR FROM now())::int - p.birth_year AS age,
                   p.height_cm, p.activity_level, p.food_allergies, p.food_dislikes
            FROM patients p
            WHERE p.id = %s;
            """,
            (patient_id,),
        ).fetchone()
        if not profile:
            raise ValueError(f"Không tìm thấy bệnh nhân id={patient_id}")

        last_checkup = conn.execute(
            """
            SELECT id AS checkup_id, checkup_date, weight_kg, systolic_bp, diastolic_bp,
                   COALESCE(dialysis_per_week, 0) AS dialysis_per_week
            FROM checkups
            WHERE patient_id = %s
            ORDER BY checkup_date DESC, id DESC
            LIMIT 1;
            """,
            (patient_id,),
        ).fetchone()

        cond_rows = conn.execute(
            """
            SELECT cd.code, cs.stage_code, cs.stage_rank
            FROM patient_conditions pc
            JOIN conditions cd ON cd.id = pc.condition_id
            LEFT JOIN condition_stages cs ON cs.id = pc.stage_id
            WHERE pc.patient_id = %s AND pc.resolved_at IS NULL;
            """,
            (patient_id,),
        ).fetchall()

        lab_rows = conn.execute(
            "SELECT biomarker_code, value FROM v_latest_lab_results WHERE patient_id = %s;",
            (patient_id,),
        ).fetchall()

    weight_kg = float(last_checkup["weight_kg"]) if last_checkup and last_checkup["weight_kg"] else None
    height_cm = float(profile["height_cm"]) if profile["height_cm"] else None
    bmi = round(weight_kg / ((height_cm / 100) ** 2), 1) if (weight_kg and height_cm) else None

    conditions = {r["code"] for r in cond_rows}
    stages = {r["code"]: r["stage_rank"] for r in cond_rows if r["stage_rank"] is not None}
    stage_codes = {r["code"]: r["stage_code"] for r in cond_rows if r["stage_code"]}
    biomarkers = {r["biomarker_code"]: float(r["value"]) for r in lab_rows}

    if "CKD" in conditions and "CKD" not in stages:
        inferred_rank, inferred_code = _infer_ckd_stage(biomarkers.get("EGFR"))
        stages["CKD"] = inferred_rank
        stage_codes["CKD"] = inferred_code

    return {
        **dict(profile),
        "weight_kg": weight_kg,
        "bmi": bmi,
        "checkup_id": last_checkup["checkup_id"] if last_checkup else None,
        "systolic_bp": last_checkup["systolic_bp"] if last_checkup else None,
        "diastolic_bp": last_checkup["diastolic_bp"] if last_checkup else None,
        "dialysis_per_week": last_checkup["dialysis_per_week"] if last_checkup else 0,
        "conditions": conditions,
        "stages": stages,
        "ckd_stage": stage_codes.get("CKD"),
        "biomarkers": biomarkers,
        "labs": biomarkers,
    }


def _check_numeric(val: Optional[float], spec: Any) -> bool:
    if val is None:
        return False
    if isinstance(spec, (int, float)):
        return val == spec
    if isinstance(spec, dict):
        if "gt" in spec and not (val > spec["gt"]):
            return False
        if "gte" in spec and not (val >= spec["gte"]):
            return False
        if "lt" in spec and not (val < spec["lt"]):
            return False
        if "lte" in spec and not (val <= spec["lte"]):
            return False
        return True
    return False


def match_criteria(criteria: Dict[str, Any], ctx: Dict[str, Any]) -> bool:
    """Đánh giá JSONB criteria trong `regime_selection_rules` với hồ sơ bệnh nhân."""
    if not criteria:
        return True

    if "conditions_all" in criteria:
        if not set(criteria["conditions_all"]).issubset(ctx["conditions"]):
            return False

    if "conditions_any" in criteria:
        if not (set(criteria["conditions_any"]) & ctx["conditions"]):
            return False

    if "stage" in criteria:
        for cond_code, bounds in criteria["stage"].items():
            rank = ctx["stages"].get(cond_code)
            if rank is None:
                return False
            if "min_rank" in bounds and rank < bounds["min_rank"]:
                return False
            if "max_rank" in bounds and rank > bounds["max_rank"]:
                return False

    if "biomarkers" in criteria:
        for bm_code, spec in criteria["biomarkers"].items():
            if not _check_numeric(ctx["biomarkers"].get(bm_code), spec):
                return False

    for field in ("bmi", "systolic_bp", "dialysis_per_week"):
        if field in criteria and not _check_numeric(ctx.get(field), criteria[field]):
            return False

    if "any_of" in criteria:
        if not any(match_criteria(sub, ctx) for sub in criteria["any_of"]):
            return False

    return True


def _midpoint(lo: Optional[float], hi: Optional[float]) -> Optional[float]:
    if lo is not None and hi is not None:
        return round((float(lo) + float(hi)) / 2, 1)
    return float(hi if hi is not None else lo) if (lo is not None or hi is not None) else None


def match_and_compute_target(patient_id: str, save_to_db: bool = True) -> Dict[str, Any]:
    """Khớp đúng phác đồ Bộ Y tế và tính mục tiêu dinh dưỡng ngày theo cân nặng."""
    ctx = get_patient_context(patient_id)

    with get_conn() as conn:
        rules = conn.execute(
            """
            SELECT rsr.id AS rule_id, rsr.priority, rsr.criteria, rsr.description,
                   dr.*
            FROM regime_selection_rules rsr
            JOIN diet_regimes dr ON dr.id = rsr.regime_id
            WHERE rsr.is_enabled = TRUE AND dr.is_enabled = TRUE
            ORDER BY rsr.priority ASC;
            """
        ).fetchall()

        matched = None
        for r in rules:
            if match_criteria(r["criteria"], ctx):
                matched = dict(r)
                break

        if not matched:
            raise RuntimeError("Không tìm thấy phác đồ phù hợp (thiếu luật mặc định BT01-X).")

        weight = ctx["weight_kg"]
        if weight and (matched["energy_kcal_per_kg_min"] or matched["energy_kcal_per_kg_max"]):
            kcal_per_kg = _midpoint(matched["energy_kcal_per_kg_min"], matched["energy_kcal_per_kg_max"])
            energy_kcal = round(weight * kcal_per_kg, 1)
        else:
            kcal_per_kg = None
            energy_kcal = _midpoint(matched["energy_min_kcal"], matched["energy_max_kcal"]) or 1800.0

        if weight and (matched["protein_g_per_kg_min"] or matched["protein_g_per_kg_max"]):
            prot_per_kg = _midpoint(matched["protein_g_per_kg_min"], matched["protein_g_per_kg_max"])
            protein_g = round(weight * prot_per_kg, 1)
        else:
            prot_per_kg = None
            protein_g = _midpoint(matched["protein_min_g"], matched["protein_max_g"])

        lipid_g = _midpoint(matched["lipid_min_g"], matched["lipid_max_g"])
        glucid_g = _midpoint(matched["glucid_min_g"], matched["glucid_max_g"])
        meals_per_day = matched["meals_max"] or matched["meals_min"] or 4

        target = {
            "patient_id": patient_id,
            "regime_code": matched["code"],
            "regime_name": matched["name"],
            "rule_description": matched["description"],
            "energy_kcal": energy_kcal,
            "protein_g": protein_g,
            "lipid_g": lipid_g,
            "glucid_g": glucid_g,
            "sodium_max_mg": float(matched["sodium_max_mg"]) if matched["sodium_max_mg"] else None,
            "potassium_max_mg": float(matched["potassium_max_mg"]) if matched["potassium_max_mg"] else None,
            "phosphate_max_mg": float(matched["phosphate_max_mg"]) if matched["phosphate_max_mg"] else None,
            "fiber_min_g": float(matched["fiber_min_g"]) if matched["fiber_min_g"] else None,
            "water_max_l": float(matched["water_max_l"]) if matched["water_max_l"] else None,
            "meals_per_day": meals_per_day,
            "require_low_gi": bool(matched["require_low_gi"]),
            "notes": matched["notes"],
            "calculation_detail": {
                "weight_kg": weight,
                "kcal_per_kg": kcal_per_kg,
                "protein_g_per_kg": prot_per_kg,
                "regime_code": matched["code"],
            },
        }

        if save_to_db:
            conn.execute(
                "UPDATE nutrition_targets SET is_current = FALSE, valid_to = now() "
                "WHERE patient_id = %s AND is_current = TRUE;",
                (patient_id,),
            )
            conn.execute(
                """
                INSERT INTO nutrition_targets (
                    patient_id, checkup_id, regime_id, selection_rule_id,
                    energy_kcal, protein_g, lipid_g, glucid_g,
                    sodium_max_mg, potassium_max_mg, phosphate_max_mg,
                    fiber_min_g, water_max_l, meals_per_day, require_low_gi,
                    calculation_detail, is_current
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,TRUE);
                """,
                (
                    patient_id, ctx["checkup_id"], matched["id"], matched["rule_id"],
                    energy_kcal, protein_g, lipid_g, glucid_g,
                    target["sodium_max_mg"], target["potassium_max_mg"], target["phosphate_max_mg"],
                    target["fiber_min_g"], target["water_max_l"], meals_per_day,
                    target["require_low_gi"], json.dumps(target["calculation_detail"]),
                ),
            )

    return target
