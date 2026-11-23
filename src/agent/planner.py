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
    cooking_method: str = Field(description="Ngắn gọn 1-2 từ: Luộc / Hấp / Kho nhạt / Nấu canh / Áp chảo")
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
        description="Viết ĐÚNG 1-2 câu ngắn (tối đa 40 từ): nêu cách đáp ứng sở thích hoặc lý do đổi món nếu xung đột bệnh lý/dị ứng.",
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
        limits.append(("protein_g", float(target["protein_g"]) * 1.06, 8.0, 15.0, True))
    if target.get("phosphate_max_mg") is not None:
        limits.append(("phosphorus_mg", float(target["phosphate_max_mg"]) * 0.97, 100.0, 15.0, True))
    if target.get("potassium_max_mg") is not None:
        limits.append(("potassium_mg", float(target["potassium_max_mg"]) * 0.97, 160.0, 20.0, False))
    if target.get("sodium_max_mg") is not None:
        limits.append(("sodium_mg", float(target["sodium_max_mg"]) * 0.97, 140.0, 10.0, False))

    def _trim_excess(allow_trim_carbs: bool = False):
        for _ in range(6):
            totals = _compute_day_totals(day, food_map)
            changed = False
            for key, max_allowed, high_thresh, min_grams, skip_high_carb in limits:
                cur_total = totals.get(key, 0.0)
                if cur_total <= max_allowed:
                    continue
                excess = cur_total - max_allowed
                eff_thresh = high_thresh * (0.5 if allow_trim_carbs else 1.0)
                rich_ings = []
                rich_contrib = 0.0
                for m in day.meals:
                    for d in m.dishes:
                        for ing in d.ingredients:
                            f = food_map.get(ing.food_id)
                            if not f:
                                continue
                            is_carb = float(f.get("glucid_g") or 0.0) >= 22.0
                            if not allow_trim_carbs and skip_high_carb and is_carb:
                                continue
                            floor_g = 40.0 if is_carb else min_grams
                            per100 = float(f.get(key) or 0.0)
                            if per100 >= eff_thresh and ing.grams > floor_g:
                                rich_ings.append((ing, floor_g))
                                rich_contrib += per100 * ing.grams / 100.0
                if rich_contrib <= 0:
                    continue
                scale = max(0.35, (rich_contrib - excess * 1.06) / rich_contrib)
                for ing, floor_g in rich_ings:
                    new_g = max(floor_g, round((ing.grams * scale) / 5.0) * 5.0)
                    if new_g < ing.grams:
                        ing.grams = new_g
                        changed = True
            if not changed:
                break

    # Vòng 1: ưu tiên giảm thịt/cá giàu đạm & phospho trước; Vòng 2: nếu vẫn vượt (VD: ăn nhiều gạo lứt) thì giảm nhẹ cả tinh bột giàu phospho
    _trim_excess(allow_trim_carbs=False)
    _trim_excess(allow_trim_carbs=True)

    # Nếu năng lượng bị hụt dưới ngưỡng tối thiểu, bù thông minh bằng tinh bột ít đạm/ít phospho (Miến dong / Khoai lang / Gạo lứt) trong giới hạn trần
    e_target = float(target.get("energy_kcal") or 0.0)
    min_kcal = max(1250.0, e_target * 0.76) if e_target > 0 else 0.0
    if e_target > 0:
        totals = _compute_day_totals(day, food_map)
        if totals["energy_kcal"] < min_kcal:
            p_cap = float(target["protein_g"]) * 1.06 if target.get("protein_g") is not None else 9999.0
            ph_cap = float(target["phosphate_max_mg"]) * 0.97 if target.get("phosphate_max_mg") is not None else 99999.0
            k_cap = float(target["potassium_max_mg"]) * 0.97 if target.get("potassium_max_mg") is not None else 99999.0
            na_cap = float(target["sodium_max_mg"]) * 0.97 if target.get("sodium_max_mg") is not None else 99999.0

            def _max_safe_add_grams(f_row: Dict[str, Any], cur_tot: Dict[str, float]) -> float:
                max_g = 220.0
                for col, cap_val in (
                    ("protein_g", p_cap),
                    ("phosphorus_mg", ph_cap),
                    ("potassium_mg", k_cap),
                    ("sodium_mg", na_cap),
                ):
                    per100 = float(f_row.get(col) or 0.0)
                    if per100 > 0:
                        headroom = max(0.0, cap_val - cur_tot.get(col, 0.0))
                        max_g = min(max_g, (headroom / per100) * 100.0)
                return max(0.0, round(max_g / 5.0) * 5.0)

            # Ưu tiên tăng gam các món tinh bột ít đạm/ít phospho đã có trong ngày
            carb_ings = []
            for m in day.meals:
                for d in m.dishes:
                    for ing in d.ingredients:
                        f = food_map.get(ing.food_id)
                        if f and float(f.get("glucid_g") or 0.0) >= 20.0 and float(f.get("protein_g") or 0.0) <= 8.5:
                            carb_ings.append((ing, f))
            # Sắp xếp ưu tiên tinh bột ít Phospho nhất (Khoai lang / Miến dong trước Gạo lứt)
            carb_ings.sort(key=lambda pair: float(pair[1].get("phosphorus_mg") or 0.0))
            for ing, f_row in carb_ings:
                totals = _compute_day_totals(day, food_map)
                if totals["energy_kcal"] >= e_target * 0.85:
                    break
                kcal100 = float(f_row.get("energy_kcal") or 0.0)
                if kcal100 <= 0:
                    continue
                need_g = ((e_target * 0.85 - totals["energy_kcal"]) / kcal100) * 100.0
                safe_add = min(need_g, _max_safe_add_grams(f_row, totals), max(0.0, 260.0 - ing.grams))
                add_g = round(safe_add / 5.0) * 5.0
                if add_g >= 10.0:
                    ing.grams += add_g

            # Nếu vẫn dưới min_kcal (VD: AI quên tinh bột ở bữa chính), tự động chèn thêm 1 món tinh bột ít Phospho có sẵn trong food_map
            totals = _compute_day_totals(day, food_map)
            if totals["energy_kcal"] < min_kcal and day.meals:
                for fallback_id, dish_title, method in (
                    (38, "Miến dong luộc/nấu", "Luộc"),
                    (31, "Khoai lang luộc", "Luộc"),
                    (5, "Cơm gạo lứt", "Nấu"),
                ):
                    f_row = food_map.get(fallback_id)
                    if not f_row:
                        continue
                    kcal100 = float(f_row.get("energy_kcal") or 0.0)
                    if kcal100 <= 0:
                        continue
                    need_g = ((e_target * 0.82 - totals["energy_kcal"]) / kcal100) * 100.0
                    safe_g = min(200.0, need_g, _max_safe_add_grams(f_row, totals))
                    add_g = round(safe_g / 5.0) * 5.0
                    if add_g >= 30.0:
                        target_meal = next((m for m in day.meals if m.meal in ("Trưa", "Tối")), day.meals[0])
                        target_meal.dishes.append(
                            DishSchema(
                                name=dish_title,
                                cooking_method=method,
                                ingredients=[DishIngredientSchema(food_id=fallback_id, grams=add_g)],
                            )
                        )
                        totals = _compute_day_totals(day, food_map)
                        if totals["energy_kcal"] >= min_kcal:
                            break

            _trim_excess(allow_trim_carbs=True)

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

    pool_limit = 48 if gen_days <= 1 else (64 if gen_days <= 3 else 84)
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

    # Vòng lặp tối đa 2 lần: nếu Lần 1 có ngày bị lỗi, Lần 2 CHỈ gọi AI sửa lại ĐÚNG các ngày bị lỗi (Partial-Day Retry) thay vì bỏ cả tuần
    failed_day_indices: List[int] = []
    for attempt in range(2):
        is_partial_retry = attempt > 0 and best_plan is not None and 0 < len(failed_day_indices) < len(best_plan.days)
        req_days = len(failed_day_indices) if is_partial_retry else gen_days
        day_scope_note = (
            f"CHỈ lập lại ĐÚNG {req_days} ngày bị lỗi (gán đúng `day_index` là {failed_day_indices})"
            if is_partial_retry
            else f"lập thực đơn {gen_days} ngày (đa dạng món, không lặp đạm/rau liên tiếp)"
        )
        prompt = f"""
Bạn là chuyên gia dinh dưỡng lâm sàng & đầu bếp Việt Nam.
Hãy {day_scope_note} CHỈ SỬ DỤNG `food_id` từ danh sách nguyên liệu an toàn dưới đây.

{profile_block}
MỤC TIÊU DINH DƯỠNG MỖI NGÀY (RÀNG BUỘC CỨNG Y KHOA):
- Phác đồ: {target['regime_code']} - {target['regime_name']}
- Năng lượng: ~{target['energy_kcal']} Kcal/ngày (BẮT BUỘC đủ tinh bột lành mạnh ở cả Trưa và Tối; phối hợp Miến dong / Khoai lang với Gạo lứt, không dùng quá 200g Gạo lứt/ngày để tránh vượt Phospho; tối thiểu ≥ 1300 kcal/ngày)
- Đạm: ~{target['protein_g']} g/ngày{prot_cap_note}
- Natri tối đa: {target['sodium_max_mg']} mg/ngày | Kali tối đa: {target['potassium_max_mg']} mg/ngày{phos_line}
- Tên món ăn (`name`) PHẢI khớp đúng tên nguyên liệu của `food_id` đã chọn (tuyệt đối không đặt tên 'Cháo thịt lợn' nếu chọn thịt khác hay Kê).
- Số bữa bắt buộc: ĐÚNG {target_meals} bữa/ngày, chỉ dùng tên bữa chính xác là: {', '.join(meal_slots)} (nếu số bữa là 3 thì không thêm bữa phụ; nếu người bệnh tiểu đường chỉ ăn 3 bữa, hãy dàn đều tinh bột GI thấp vào cả Sáng/Trưa/Tối).
- Lưu ý lâm sàng: {target.get('notes', '')}
{rag_block}{diversity_block}{pref_block}{feedback}

DANH SÁCH NGUYÊN LIỆU AN TOÀN (trên 100g, dùng đúng cột `id`):
{foods_table}
"""
        try:
            with trace_step(f"llm_meal_plan_attempt_{attempt + 1}", as_type="generation", input_data={"period": period, "attempt": attempt + 1, "req_days": req_days}) as gen_span:
                plan, used_model = generate_structured(prompt, MealPlanOutput, fast=True)
                if gen_span is not None:
                    gen_span.update(output={"model": used_model, "days": len(plan.days)})
        except Exception:
            if attempt > 0 and best_plan is not None:
                # Lần 2 gọi AI sửa lỗi gặp 503/timeout -> giữ nguyên phương án Lần 1 đã cân chỉnh gam, không làm sập trang
                break
            raise

        if is_partial_retry and best_plan is not None:
            # Ghép các ngày vừa sửa vào đúng vị trí trong thực đơn đã đạt chuẩn ở Lần 1
            fixed_by_idx = {}
            for pos, new_d in enumerate(plan.days):
                target_idx = new_d.day_index if new_d.day_index in failed_day_indices else (
                    failed_day_indices[pos] if pos < len(failed_day_indices) else new_d.day_index
                )
                new_d.day_index = target_idx
                fixed_by_idx[target_idx] = new_d
            merged_days = [fixed_by_idx.get(old_d.day_index, old_d) for old_d in best_plan.days]
            best_plan = MealPlanOutput(
                note_for_patient=plan.note_for_patient or best_plan.note_for_patient,
                days=merged_days,
            )
        else:
            best_plan = plan

        day_reports = []
        violations_all: List[str] = []
        failed_day_indices = []

        with trace_step(f"guardrail_daily_totals_attempt_{attempt + 1}", as_type="guardrail") as gr_span:
            for d in best_plan.days:
                _auto_balance_day_portions(d, food_map, target)
                totals = _compute_day_totals(d, food_map)
                check = validate_daily_totals(patient_id, totals, run_id=run_id)
                min_kcal = min(1080.0, float(target.get("energy_kcal") or 1600) * 0.62)
                if totals.get("energy_kcal", 0.0) < min_kcal:
                    check = {
                        "passed": False,
                        "violations": list(check.get("violations") or [])
                        + [f"Tổng năng lượng ({totals['energy_kcal']:.0f} kcal) quá thấp (< {min_kcal:.0f} kcal), hãy bổ sung miến dong/khoai lang/cơm gạo lứt vào bữa chính."],
                    }
                day_reports.append({"day_index": d.day_index, "totals": totals, "check": check})
                if not check["passed"]:
                    failed_day_indices.append(d.day_index)
                    violations_all.extend([f"Ngày {d.day_index}: {v}" for v in check["violations"]])
            if gr_span is not None:
                gr_span.update(output={"passed": len(violations_all) == 0, "failed_days": failed_day_indices, "violations": violations_all})

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
