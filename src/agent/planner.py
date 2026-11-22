"""Meal Planner: Phối nguyên liệu an toàn từ `nutri.foods` thành thực đơn Việt Nam
cá nhân hóa theo Hồ sơ bệnh nhân, Phác đồ Bộ Y tế, RAG Guidelines và tự kiểm tra tổng vi chất qua Guardrail."""
import json
from datetime import date, timedelta
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from src.db import get_conn
from src.guardrails.clinical_validator import validate_daily_totals
from src.guardrails.pii_masker import mask_pii_text
from src.llm import DEFAULT_MODEL, generate_structured, has_api_key
from src.observability import log_pii_redaction, trace_step
from src.tools.food_tool import get_safe_foods


class DishIngredientSchema(BaseModel):
    food_id: int = Field(description="ID thực phẩm (cột id trong danh sách nguyên liệu an toàn)")
    grams: float = Field(description="Khối lượng ăn được tính bằng gam (> 0)")


class DishSchema(BaseModel):
    name: str = Field(description="Tên món ăn Việt Nam (VD: Cá quả hấp gừng, Canh bí đao)")
    cooking_method: str = Field(description="Cách chế biến: Luộc / Hấp / Kho nhạt / Nấu canh...")
    ingredients: List[DishIngredientSchema]


class MealSchema(BaseModel):
    meal: Literal["Sáng", "Phụ sáng", "Trưa", "Phụ chiều", "Tối", "Phụ tối"] = Field(
        description="Tên bữa ăn hợp lệ"
    )
    dishes: List[DishSchema]


class DayPlanSchema(BaseModel):
    day_index: int
    meals: List[MealSchema]


class MealPlanOutput(BaseModel):
    note_for_patient: str = Field(
        default="",
        description="Giải thích ngắn cách đáp ứng hồ sơ cá nhân, khẩu vị/món yêu thích của người dùng và lưu ý an toàn bệnh lý.",
    )
    days: List[DayPlanSchema]


def _compute_day_totals(day: DayPlanSchema, food_map: Dict[int, Dict[str, Any]]) -> Dict[str, float]:
    """Tính tổng dinh dưỡng thực tế 1 ngày bằng Python từ bảng `foods` (không để LLM nhẩm)."""
    totals = {
        "energy_kcal": 0.0, "protein_g": 0.0, "lipid_g": 0.0, "glucid_g": 0.0,
        "fiber_g": 0.0, "sodium_mg": 0.0, "potassium_mg": 0.0, "phosphorus_mg": 0.0,
    }
    for m in day.meals:
        for d in m.dishes:
            for ing in d.ingredients:
                f = food_map.get(ing.food_id)
                if not f:
                    continue
                ratio = ing.grams / 100.0
                for k in totals:
                    if f.get(k) is not None:
                        totals[k] += float(f[k]) * ratio
    return {k: round(v, 1) for k, v in totals.items()}


def _auto_balance_day_portions(
    day: DayPlanSchema,
    food_map: Dict[int, Dict[str, Any]],
    target: Dict[str, Any],
) -> DayPlanSchema:
    """Tự động cân chỉnh lại số gram của các nguyên liệu giàu Đạm/Phospho/Kali/Natri
    (ưu tiên giữ nguyên tinh bột để đảm bảo đủ năng lượng), tránh phải gọi AI sinh lại lần 2."""
    for m in day.meals:
        for d in m.dishes:
            d.ingredients = [ing for ing in d.ingredients if ing.food_id in food_map and ing.grams > 0]

    limits = []
    if target.get("protein_g") is not None:
        limits.append(("protein_g", float(target["protein_g"]) * 1.07, 11.0, 20.0, True))
    if target.get("phosphate_max_mg") is not None:
        limits.append(("phosphorus_mg", float(target["phosphate_max_mg"]) * 0.98, 130.0, 20.0, True))
    if target.get("potassium_max_mg") is not None:
        limits.append(("potassium_mg", float(target["potassium_max_mg"]) * 0.98, 180.0, 25.0, False))
    if target.get("sodium_max_mg") is not None:
        limits.append(("sodium_mg", float(target["sodium_max_mg"]) * 0.98, 150.0, 10.0, False))

    def _trim_excess():
        for _ in range(5):
            totals = _compute_day_totals(day, food_map)
            changed = False
            for key, max_allowed, high_thresh, min_grams, skip_high_carb in limits:
                cur_total = totals.get(key, 0.0)
                if cur_total <= max_allowed:
                    continue
                excess = cur_total - max_allowed
                rich_ings = []
                rich_contrib = 0.0
                for m in day.meals:
                    for d in m.dishes:
                        for ing in d.ingredients:
                            f = food_map.get(ing.food_id)
                            if not f:
                                continue
                            if skip_high_carb and float(f.get("glucid_g") or 0.0) >= 22.0:
                                continue
                            per100 = float(f.get(key) or 0.0)
                            if per100 >= high_thresh and ing.grams > min_grams:
                                rich_ings.append((ing, per100))
                                rich_contrib += per100 * ing.grams / 100.0
                if rich_contrib <= 0:
                    continue
                scale = max(0.35, (rich_contrib - excess * 1.05) / rich_contrib)
                for ing, _ in rich_ings:
                    new_g = max(min_grams, round((ing.grams * scale) / 5.0) * 5.0)
                    if new_g < ing.grams:
                        ing.grams = new_g
                        changed = True
            if not changed:
                break

    _trim_excess()

    # Nếu năng lượng bị hụt dưới 78% mục tiêu, bù nhẹ bằng tinh bột ít đạm/ít phospho sẵn có trong thực đơn
    e_target = float(target.get("energy_kcal") or 0.0)
    if e_target > 0:
        totals = _compute_day_totals(day, food_map)
        if totals["energy_kcal"] < e_target * 0.78:
            carb_ings = []
            carb_kcal = 0.0
            for m in day.meals:
                for d in m.dishes:
                    for ing in d.ingredients:
                        f = food_map.get(ing.food_id)
                        if not f:
                            continue
                        if (
                            float(f.get("glucid_g") or 0.0) >= 20.0
                            and float(f.get("protein_g") or 0.0) <= 9.0
                            and float(f.get("phosphorus_mg") or 0.0) <= 150.0
                            and float(f.get("potassium_mg") or 0.0) <= 220.0
                        ):
                            carb_ings.append(ing)
                            carb_kcal += float(f.get("energy_kcal") or 0.0) * ing.grams / 100.0
            if carb_kcal > 0:
                needed = e_target * 0.85 - totals["energy_kcal"]
                up_scale = min(1.8, (carb_kcal + max(0.0, needed)) / carb_kcal)
                for ing in carb_ings:
                    ing.grams = min(280.0, round((ing.grams * up_scale) / 5.0) * 5.0)
                _trim_excess()

    return day


def _resolve_plan_window(
    period: str,
    start_date: Optional[date] = None,
    num_days: Optional[int] = None,
) -> tuple[date, date, int, int, str, Optional[int]]:
    """Tính khung ngày thực đơn linh hoạt: (start_dt, end_dt, total_days, gen_days, db_period, rotation_days)."""
    start_dt = start_date or date.today()
    if num_days is not None and num_days >= 1:
        total_days = max(1, min(int(num_days), 31))
        db_period = "DAY" if total_days == 1 else ("WEEK" if total_days <= 7 else "MONTH")
        gen_days = total_days if total_days <= 7 else 7
        rotation_days = 7 if total_days > 7 else None
    else:
        db_period = period if period in ("DAY", "WEEK", "MONTH") else "DAY"
        total_days = 1 if db_period == "DAY" else (7 if db_period == "WEEK" else 30)
        gen_days = 1 if db_period == "DAY" else 7
        rotation_days = 7 if db_period == "MONTH" else None
    end_dt = start_dt + timedelta(days=total_days - 1)
    return start_dt, end_dt, total_days, gen_days, db_period, rotation_days


_MEAL_SLOTS_BY_COUNT = {
    3: ["Sáng", "Trưa", "Tối"],
    4: ["Sáng", "Trưa", "Phụ chiều", "Tối"],
    5: ["Sáng", "Phụ sáng", "Trưa", "Phụ chiều", "Tối"],
    6: ["Sáng", "Phụ sáng", "Trưa", "Phụ chiều", "Tối", "Phụ tối"],
}


def _get_recent_plan_foods(patient_id: str, limit: int = 12) -> List[str]:
    """Lấy danh sách nguyên liệu chính đã dùng trong thực đơn gần nhất để tránh lặp lại."""
    try:
        with get_conn() as conn:
            rows = conn.execute(
                """
                WITH latest_plan AS (
                    SELECT id FROM meal_plans WHERE patient_id = %s ORDER BY id DESC LIMIT 1
                )
                SELECT DISTINCT f.name
                FROM latest_plan lp
                JOIN meal_plan_days mpd ON mpd.meal_plan_id = lp.id
                JOIN meals m ON m.plan_day_id = mpd.id
                JOIN dishes d ON d.meal_id = m.id
                JOIN dish_ingredients di ON di.dish_id = d.id
                JOIN foods f ON f.id = di.food_id
                WHERE f.name NOT ILIKE '%%gạo tẻ%%' AND f.name NOT ILIKE '%%cơm%%'
                LIMIT %s;
                """,
                (patient_id, limit),
            ).fetchall()
        return [r["name"] for r in rows]
    except Exception:
        return []


def generate_meal_plan(
    patient_id: str,
    target: Dict[str, Any],
    period: str = "DAY",
    user_preferences: str = "",
    run_id: Optional[int] = None,
    patient_profile: Optional[Dict[str, Any]] = None,
    rag_guidelines: Optional[List[str]] = None,
    start_date: Optional[date] = None,
    num_days: Optional[int] = None,
    meals_per_day: Optional[int] = None,
) -> Dict[str, Any]:
    """Sinh thực đơn theo ngày/khoảng ngày tùy chỉnh (1..7 ngày chi tiết, >7 ngày dùng 7 ngày xoay vòng)
    dựa trên Hồ sơ cá nhân, Phác đồ mục tiêu, Tri thức RAG và Yêu cầu riêng của người dùng."""
    if not has_api_key():
        raise RuntimeError("Thiếu GEMINI_API_KEY hợp lệ trong file .env để lập thực đơn.")

    start_dt, end_dt, total_days, gen_days, db_period, rotation_days = _resolve_plan_window(
        period, start_date=start_date, num_days=num_days
    )
    target_meals = max(3, min(int(meals_per_day or target.get("meals_per_day") or 4), 6))
    meal_slots = _MEAL_SLOTS_BY_COUNT[target_meals]
    safe_preferences = mask_pii_text(user_preferences)
    log_pii_redaction(run_id, "user_preferences", user_preferences, safe_preferences)

    pool_limit = 64 if gen_days <= 1 else (80 if gen_days <= 3 else 96)
    with trace_step("tool_get_safe_foods", as_type="tool", input_data={"patient_id": patient_id, "period": period}):
        safe_foods = get_safe_foods(
            patient_id=patient_id,
            max_potassium_mg=250 if target.get("potassium_max_mg") and target["potassium_max_mg"] <= 1500 else 350,
            max_sodium_mg=400 if target.get("sodium_max_mg") else None,
            max_phosphorus_mg=300 if target.get("phosphate_max_mg") else None,
            require_low_gi=target.get("require_low_gi", False),
            limit=pool_limit,
            prefer_query=safe_preferences,
        )
    recent_foods = _get_recent_plan_foods(patient_id, limit=12)
    food_map = {f["id"]: f for f in safe_foods}

    # Bảng thu gọn (tiết kiệm ~65% token so với JSON đầy đủ -> AI lập thực đơn nhanh gấp ~2-3 lần)
    foods_table = "id|ten|kcal|p_g|k_mg|na_mg|ph_mg|gi\n" + "\n".join(
        f"{f['id']}|{f['name']}|{round(float(f['energy_kcal'] or 0))}|"
        f"{round(float(f['protein_g'] or 0), 1)}|{round(float(f['potassium_mg'] or 0))}|"
        f"{round(float(f['sodium_mg'] or 0))}|{round(float(f['phosphorus_mg'] or 0))}|{f['gi'] or ''}"
        for f in safe_foods
    )

    profile_block = ""
    if patient_profile:
        conds = ", ".join(patient_profile.get("conditions", [])) or "Không ghi nhận"
        allergies = ", ".join(patient_profile.get("food_allergies", [])) or "Không"
        labs = patient_profile.get("labs", {})
        profile_block = (
            f"HỒ SƠ CÁ NHÂN BỆNH NHÂN:\n"
            f"- Tuổi/Giới: {patient_profile.get('age')} tuổi, {patient_profile.get('gender')}\n"
            f"- Thể trạng: Cân nặng {patient_profile.get('weight_kg')} kg, BMI {patient_profile.get('bmi')}\n"
            f"- Bệnh lý đang mắc: {conds} (Giai đoạn thận: {patient_profile.get('ckd_stage') or 'Không'})\n"
            f"- Chỉ số xét nghiệm gần nhất: {json.dumps(labs, ensure_ascii=False)}\n"
            f"- Dị ứng thực phẩm (TUYỆT ĐỐI TRÁNH): {allergies}\n"
        )

    rag_block = ""
    if rag_guidelines:
        rag_block = "\nHƯỚNG DẪN Y KHOA BỔ TRỢ (RAG):\n- " + "\n- ".join(rag_guidelines[:2]) + "\n"

    pref_block = ""
    if safe_preferences.strip():
        pref_block = f"""
YÊU CẦU RIÊNG CỦA NGƯỜI DÙNG (ƯU TIÊN ĐÁP ỨNG NẾU KHÔNG VI PHẠM AN TOÀN BỆNH LÝ):
"{safe_preferences.strip()}"
- Ưu tiên lựa chọn thực phẩm hợp khẩu vị, món yêu thích và cách chế biến người dùng mong muốn từ danh sách nguyên liệu an toàn.
- Nếu yêu cầu riêng xung đột với bệnh lý/dị ứng hoặc làm vượt ngưỡng Kali/Natri/Đạm/GI: BẮT BUỘC giữ an toàn y khoa lên hàng đầu và giải thích rõ trong `note_for_patient`.
"""

    recent_avoid_line = (
        f"- Ưu tiên đổi món mới, TRÁNH lặp lại các nguyên liệu vừa ăn gần đây (trừ cơm/gạo tẻ): {', '.join(recent_foods)}.\n"
        if recent_foods
        else ""
    )
    diversity_block = f"""
QUY TẮC ĐA DẠNG MÓN ĂN (BẮT BUỘC):
- Không lặp lại cùng một loại thịt/cá/trứng/rau ở các ngày liên tiếp hoặc giữa bữa Trưa và bữa Tối trong cùng ngày.
- Luân phiên đa dạng nguồn đạm (thịt lợn, thịt gà, cá sông/cá biển, trứng, đậu phụ) và phương pháp chế biến (luộc, hấp, kho nhạt, nấu canh, áp chảo ít dầu).
{recent_avoid_line}"""

    feedback = ""
    best_plan: Optional[MealPlanOutput] = None
    day_reports: List[Dict[str, Any]] = []
    all_passed = False
    used_model = DEFAULT_MODEL

    prot_cap_note = (
        f" (TRẦN CỨNG: không vượt quá {round(float(target['protein_g']) * 1.08, 1)}g/ngày — chia gọn lượng thịt/cá/trứng mỗi bữa)"
        if target.get("protein_g") is not None
        else ""
    )
    phos_line = (
        f"\n- Phospho tối đa: {target['phosphate_max_mg']} mg/ngày"
        if target.get("phosphate_max_mg") is not None
        else ""
    )

    # Vòng lặp tối đa 2 lần nếu Guardrail phát hiện vượt ngưỡng chất
    for attempt in range(2):
        prompt = f"""
Bạn là chuyên gia dinh dưỡng lâm sàng & đầu bếp Việt Nam.
Hãy lập thực đơn {gen_days} ngày (đa dạng món, không lặp đạm/rau liên tiếp) CHỈ SỬ DỤNG `food_id` từ danh sách nguyên liệu an toàn dưới đây.

{profile_block}
MỤC TIÊU DINH DƯỠNG MỖI NGÀY (RÀNG BUỘC CỨNG Y KHOA):
- Phác đồ: {target['regime_code']} - {target['regime_name']}
- Năng lượng: ~{target['energy_kcal']} Kcal/ngày (đảm bảo đủ tinh bột lành mạnh, không lập thực đơn thiếu calo < 1300 kcal)
- Đạm: ~{target['protein_g']} g/ngày{prot_cap_note}
- Natri tối đa: {target['sodium_max_mg']} mg/ngày | Kali tối đa: {target['potassium_max_mg']} mg/ngày{phos_line}
- Số bữa bắt buộc: ĐÚNG {target_meals} bữa/ngày, chỉ dùng tên bữa chính xác là: {', '.join(meal_slots)} (nếu số bữa là 3 thì không thêm bữa phụ; nếu người bệnh tiểu đường chỉ ăn 3 bữa, hãy dàn đều tinh bột GI thấp và nhắc nhẹ trong `note_for_patient`).
- Lưu ý lâm sàng: {target.get('notes', '')}
{rag_block}{diversity_block}{pref_block}{feedback}

DANH SÁCH NGUYÊN LIỆU AN TOÀN (trên 100g, dùng đúng cột `id`):
{foods_table}
"""
        with trace_step(f"llm_meal_plan_attempt_{attempt + 1}", as_type="generation", input_data={"period": period, "attempt": attempt + 1}) as gen_span:
            plan, used_model = generate_structured(prompt, MealPlanOutput, fast=True)
            if gen_span is not None:
                gen_span.update(output={"model": used_model, "days": len(plan.days)})

        best_plan = plan
        day_reports = []
        violations_all: List[str] = []

        with trace_step(f"guardrail_daily_totals_attempt_{attempt + 1}", as_type="guardrail") as gr_span:
            for d in plan.days:
                _auto_balance_day_portions(d, food_map, target)
                totals = _compute_day_totals(d, food_map)
                check = validate_daily_totals(patient_id, totals, run_id=run_id)
                day_reports.append({"day_index": d.day_index, "totals": totals, "check": check})
                if not check["passed"]:
                    violations_all.extend([f"Ngày {d.day_index}: {v}" for v in check["violations"]])
            if gr_span is not None:
                gr_span.update(output={"passed": len(violations_all) == 0, "violations": violations_all})

        if not violations_all:
            all_passed = True
            break
        feedback = "\nCẢNH BÁO GUARDRAIL LẦN TRƯỚC (HÃY GIẢM GRAM HOẶC ĐỔI MÓN):\n" + "\n".join(violations_all)

    plan_id = _save_plan_to_db(
        patient_id, db_period, best_plan, all_passed, used_model,
        start_dt=start_dt, end_dt=end_dt, rotation_days=rotation_days,
    )
    return {
        "meal_plan_id": plan_id,
        "period": db_period,
        "start_date": start_dt.isoformat(),
        "end_date": end_dt.isoformat(),
        "total_days": total_days,
        "rotation_days": rotation_days,
        "guardrail_passed": all_passed,
        "model_used": used_model,
        "plan": best_plan.model_dump() if best_plan else {},
        "day_reports": day_reports,
        "food_map": {k: v["name"] for k, v in food_map.items()},
    }


def _save_plan_to_db(
    patient_id: str,
    period: str,
    plan: Optional[MealPlanOutput],
    passed: bool,
    model_used: str,
    start_dt: Optional[date] = None,
    end_dt: Optional[date] = None,
    rotation_days: Optional[int] = None,
) -> Optional[int]:
    if not plan:
        return None
    start_dt = start_dt or date.today()
    end_dt = end_dt or (start_dt if period == "DAY" else (start_dt + timedelta(days=6 if period == "WEEK" else 29)))
    with get_conn() as conn:
        target_row = conn.execute(
            "SELECT id FROM nutrition_targets WHERE patient_id = %s AND is_current = TRUE;",
            (patient_id,),
        ).fetchone()
        if not target_row:
            return None
        mp = conn.execute(
            """
            INSERT INTO meal_plans (patient_id, target_id, period, start_date, end_date,
                                    rotation_days, status, guardrail_passed, model_name)
            VALUES (%s, %s, %s::plan_period, %s, %s, %s, 'ACTIVE'::plan_status, %s, %s)
            RETURNING id;
            """,
            (patient_id, target_row["id"], period, start_dt, end_dt, rotation_days, passed, model_used),
        ).fetchone()
        mp_id = mp["id"]
        for d in plan.days:
            pd_row = conn.execute(
                "INSERT INTO meal_plan_days (meal_plan_id, day_index, plan_date) VALUES (%s, %s, %s) RETURNING id;",
                (mp_id, d.day_index, start_dt + timedelta(days=d.day_index - 1)),
            ).fetchone()
            for m in d.meals:
                m_row = conn.execute(
                    "INSERT INTO meals (plan_day_id, meal) VALUES (%s, %s::meal_type) "
                    "ON CONFLICT (plan_day_id, meal) DO UPDATE SET meal = EXCLUDED.meal RETURNING id;",
                    (pd_row["id"], m.meal),
                ).fetchone()
                for idx, dish in enumerate(m.dishes, start=1):
                    d_row = conn.execute(
                        "INSERT INTO dishes (meal_id, name, cooking_method, sort_order) VALUES (%s, %s, %s, %s) RETURNING id;",
                        (m_row["id"], dish.name, dish.cooking_method, idx),
                    ).fetchone()
                    for ing in dish.ingredients:
                        conn.execute(
                            "INSERT INTO dish_ingredients (dish_id, food_id, grams) VALUES (%s, %s, %s) "
                            "ON CONFLICT (dish_id, food_id) DO UPDATE SET grams = EXCLUDED.grams;",
                            (d_row["id"], ing.food_id, max(1.0, ing.grams)),
                        )
    return mp_id
