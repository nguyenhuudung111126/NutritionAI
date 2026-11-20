"""Hàng rào an toàn lâm sàng: kiểm tra dị ứng, ngưỡng chất (Kali, Natri, Phospho, GI)
dựa trên bảng `nutri.food_restriction_rules` và `nutri.nutrition_targets`."""
import json
from typing import Any, Dict, List, Optional

from src.db import get_conn
from src.tools.food_tool import _strip_accents, expand_allergens


def _eval_rule(food: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    """Trả về True nếu thực phẩm VI PHẠM luật."""
    if rule["food_id"] and food.get("id") == rule["food_id"]:
        return True

    col = rule["nutrient_column"]
    if not col:
        return False
    val = food.get(col)
    if val is None:
        return False

    op = rule["operator"]
    if op == "IN":
        allowed_list = rule.get("threshold_text") or []
        return str(val) in allowed_list

    thresh = rule.get("threshold_num")
    if thresh is None:
        return False
    fval = float(val)
    fthresh = float(thresh)
    if op == ">":
        return fval > fthresh
    if op == ">=":
        return fval >= fthresh
    if op == "<":
        return fval < fthresh
    if op == "<=":
        return fval <= fthresh
    if op == "=":
        return fval == fthresh
    return False


_PORTION_COLUMNS = {"glucid_g", "protein_g"}


def classify_food_with_rules(
    food: Dict[str, Any],
    rules: List[Dict[str, Any]],
    allergen_kws: List[str],
) -> Dict[str, Any]:
    """Đánh giá thực phẩm theo 4 cấp độ lâm sàng (`tier`):
    PASS (An toàn) | PORTION (Kiểm soát khẩu phần) | WARN (Hạn chế) | BLOCK (Cấm/Tránh).
    Trả kèm `action` (`PASS|WARN|BLOCK`) tương thích với enum `guardrail_action` trong DB."""
    food_norm = _strip_accents(food.get("name", ""))
    matched_allergens = [kw for kw in allergen_kws if kw in food_norm]
    if matched_allergens:
        return {
            "action": "BLOCK",
            "tier": "BLOCK",
            "reasons": [f"Món '{food.get('name')}' có chứa thành phần gây dị ứng ({', '.join(matched_allergens)})."],
            "rule_ids": [],
            "matched_allergens": matched_allergens,
        }

    worst_action = "PASS"
    has_clinical_warn = False
    has_portion_only = False
    reasons: List[str] = []
    rule_ids: List[int] = []
    violated_rules: List[Dict[str, Any]] = []

    for rule in rules:
        if _eval_rule(food, rule):
            act = rule["action"]
            reasons.append(rule["reason"])
            rule_ids.append(rule["id"])
            violated_rules.append(rule)
            if act == "BLOCK":
                worst_action = "BLOCK"
            elif act == "WARN":
                if worst_action == "PASS":
                    worst_action = "WARN"
                if rule.get("nutrient_column") in _PORTION_COLUMNS:
                    has_portion_only = True
                else:
                    has_clinical_warn = True

    if worst_action == "BLOCK":
        tier = "BLOCK"
    elif has_clinical_warn:
        tier = "WARN"
    elif has_portion_only:
        tier = "PORTION"
    else:
        tier = "PASS"

    return {
        "action": worst_action,
        "tier": tier,
        "reasons": reasons,
        "rule_ids": rule_ids,
        "violated_rules": violated_rules,
    }


def validate_food_for_patient(
    patient_id: str,
    food: Dict[str, Any],
    run_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Kiểm tra 1 thực phẩm có an toàn cho bệnh nhân không.

    Returns: {"action": "PASS"|"WARN"|"BLOCK", "tier": "PASS"|"PORTION"|"WARN"|"BLOCK", "reasons": [...], "rule_ids": [...]}
    """
    with get_conn() as conn:
        p = conn.execute(
            "SELECT food_allergies FROM patients WHERE id = %s;", (patient_id,)
        ).fetchone()
        allergies = expand_allergens(p["food_allergies"] if p else [])

        rules = [
            dict(r)
            for r in conn.execute(
                """
                SELECT frr.*
                FROM food_restriction_rules frr
                WHERE frr.condition_id IN (
                    SELECT condition_id FROM patient_conditions
                    WHERE patient_id = %s AND resolved_at IS NULL
                )
                OR frr.regime_id = (
                    SELECT regime_id FROM nutrition_targets
                    WHERE patient_id = %s AND is_current = TRUE
                    LIMIT 1
                );
                """,
                (patient_id, patient_id),
            ).fetchall()
        ]

        evaluated = classify_food_with_rules(food, rules, allergies)
        if run_id:
            if evaluated.get("matched_allergens"):
                _log_event(
                    conn, run_id, "OUTPUT", "allergy_guardrail", None, "BLOCK",
                    {"food": food.get("name"), "allergens": evaluated["matched_allergens"]},
                )
            else:
                for rule in evaluated.get("violated_rules", []):
                    _log_event(
                        conn, run_id, "OUTPUT", "food_restriction",
                        rule["id"], rule["action"],
                        {"food": food.get("name"), "column": rule["nutrient_column"], "value": str(food.get(rule["nutrient_column"]))},
                    )

    return {
        "action": evaluated["action"],
        "tier": evaluated["tier"],
        "reasons": evaluated["reasons"],
        "rule_ids": evaluated["rule_ids"],
    }


def validate_daily_totals(
    patient_id: str,
    totals: Dict[str, float],
    run_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Kiểm tra tổng dinh dưỡng 1 ngày so với `nutrition_targets`."""
    with get_conn() as conn:
        target = conn.execute(
            "SELECT * FROM nutrition_targets WHERE patient_id = %s AND is_current = TRUE;",
            (patient_id,),
        ).fetchone()
        if not target:
            return {"passed": True, "violations": []}

        violations: List[str] = []
        checks = [
            ("potassium_mg", "potassium_max_mg", "Kali", "mg"),
            ("sodium_mg", "sodium_max_mg", "Natri", "mg"),
            ("phosphorus_mg", "phosphate_max_mg", "Phospho", "mg"),
        ]
        for tot_key, lim_key, label, unit in checks:
            lim = target.get(lim_key)
            val = totals.get(tot_key, 0.0)
            if lim is not None and val > float(lim):
                violations.append(f"Tổng {label} ({val:.0f} {unit}) vượt ngưỡng tối đa ({float(lim):.0f} {unit}).")

        if target.get("protein_g") is not None:
            p_lim = float(target["protein_g"]) * 1.1
            p_val = totals.get("protein_g", 0.0)
            if p_val > p_lim:
                violations.append(f"Tổng Đạm ({p_val:.1f}g) vượt quá 10% mục tiêu ({float(target['protein_g']):.1f}g).")

        if violations and run_id:
            _log_event(conn, run_id, "OUTPUT", "daily_nutrient_limit", None, "BLOCK", {"violations": violations})

    return {"passed": len(violations) == 0, "violations": violations}


def _log_event(conn, run_id: int, stage: str, name: str, rule_id: Optional[int], action: str, detail: dict):
    conn.execute(
        """
        INSERT INTO guardrail_events (run_id, stage, guardrail_name, rule_id, action, detail)
        VALUES (%s, %s, %s, %s, %s::guardrail_action, %s::jsonb);
        """,
        (run_id, stage, name, rule_id, action, json.dumps(detail, ensure_ascii=False)),
    )
