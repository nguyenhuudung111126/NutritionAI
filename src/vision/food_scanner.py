"""Quét ảnh hoặc phân tích món ăn bất kỳ (kể cả món hỗn hợp ngoài CSDL như Phở, Bún, Bánh mì...).
Kết hợp Gemini Vision/LLM (bóc tách công thức & khẩu phần) + Đối chiếu CSDL 690 thực phẩm chuẩn
+ Chấm điểm Guardrail 4 mức theo hồ sơ bệnh án của bệnh nhân."""
from typing import Any, Dict, List, Optional

from google.genai import types
from pydantic import BaseModel, Field

from src.db import get_conn
from src.guardrails.clinical_validator import classify_food_with_rules
from src.llm import generate_structured
from src.tools.food_tool import _strip_accents, expand_allergens
from src.vision.lab_extractor import _compress_image_if_needed

NUTRIENT_KEYS = [
    "energy_kcal",
    "protein_g",
    "lipid_g",
    "glucid_g",
    "fiber_g",
    "water_g",
    "sodium_mg",
    "potassium_mg",
    "phosphorus_mg",
    "calcium_mg",
    "iron_mg",
    "zinc_mg",
    "magnesium_mg",
    "vitamin_c_mg",
]

# Các từ khóa nguyên liệu hỗn hợp/pha chế không nên khớp cưỡng bức vào nguyên liệu đơn thô trong bảng foods
_COMPOSITE_KEYWORDS = {
    "nuoc dung",
    "nuoc leo",
    "nuoc pho",
    "nuoc bun",
    "nuoc ham",
    "nuoc sot",
    "sot",
    "com trang",
    "com chin",
    "tra sua",
    "tran chau",
    "kem",
    "pate",
    "xuc xich",
    "cha lua",
    "gio lua",
    "cha",
    "bi",
    "suon nuong",
    "thit nguoi",
}


class NutrientPer100gEstimate(BaseModel):
    energy_kcal: float = Field(description="Năng lượng (kcal) trên 100g thành phần này")
    protein_g: float = Field(description="Chất đạm - Protein (g) trên 100g")
    lipid_g: float = Field(description="Chất béo - Lipid (g) trên 100g")
    glucid_g: float = Field(description="Chất bột đường - Glucid/Carb (g) trên 100g")
    fiber_g: float = Field(default=0.0, description="Chất xơ (g) trên 100g")
    water_g: float = Field(default=70.0, description="Nước (g) trên 100g")
    sodium_mg: float = Field(default=0.0, description="Natri - Na (mg) trên 100g (chú ý nước dùng/gia vị mặn có Na cao)")
    potassium_mg: float = Field(default=0.0, description="Kali - K (mg) trên 100g")
    phosphorus_mg: float = Field(default=0.0, description="Phospho - P (mg) trên 100g")
    calcium_mg: float = Field(default=0.0, description="Canxi - Ca (mg) trên 100g")
    iron_mg: float = Field(default=0.0, description="Sắt - Fe (mg) trên 100g")
    zinc_mg: float = Field(default=0.0, description="Kẽm - Zn (mg) trên 100g")
    magnesium_mg: float = Field(default=0.0, description="Magie - Mg (mg) trên 100g")
    vitamin_c_mg: float = Field(default=0.0, description="Vitamin C (mg) trên 100g")


class DecomposedIngredient(BaseModel):
    name: str = Field(description="Tên thành phần hiển thị tiếng Việt (VD: 'Bánh phở tươi', 'Thịt bò tái', 'Nước dùng phở ninh xương')")
    db_lookup_keyword: Optional[str] = Field(
        default=None,
        description=(
            "Tên nguyên liệu đơn chuẩn trong Bảng Thành phần Thực phẩm Việt Nam để tra CSDL "
            "(VD: 'Bánh phở', 'Bún', 'Miến dong', 'Bánh mì', 'Thịt bò loại 1', 'Thịt lợn nạc', 'Thịt gà ta', "
            "'Tôm biển', 'Trứng gà', 'Đậu phụ', 'Hành lá', 'Giá đỗ', 'Dưa chuột', 'Cà chua', 'Rau muống'). "
            "ĐỂ TRỐNG (null) nếu là nước dùng/nước lèo đã pha, cơm chín, sốt, trà sữa, trân châu hoặc đồ chế biến sẵn phức hợp."
        ),
    )
    weight_g: float = Field(description="Khối lượng ước tính (gram hoặc ml) của thành phần này trong 1 suất ăn")
    role: str = Field(
        default="Khác",
        description="Phân nhóm thành phần: 'Tinh bột' | 'Đạm' | 'Rau củ' | 'Nước dùng / Sốt' | 'Khác'",
    )
    per_100g: NutrientPer100gEstimate = Field(
        description="Ước tính hàm lượng dinh dưỡng trên 100g (hoặc 100ml) của riêng thành phần này"
    )


class DishDecomposition(BaseModel):
    dish_name: str = Field(description="Tên món ăn nhận diện được bằng tiếng Việt (VD: 'Phở bò tái chín')")
    serving_description: str = Field(description="Mô tả 1 suất ăn tiêu chuẩn (VD: '1 tô vừa (~550g cả nước dùng)')")
    estimated_gi: str = Field(
        default="Trung bình",
        description="Mức chỉ số đường huyết (GI) ước tính của món ăn: chỉ nhận 'Thấp', 'Trung bình', hoặc 'Cao'",
    )
    confidence_note: str = Field(
        default="Phân tích công thức & định lượng khẩu phần bằng Gemini Vision/LLM",
        description="Mô tả ngắn cách nhận diện món và khẩu phần",
    )
    clinical_tips: List[str] = Field(
        default_factory=list,
        description=(
            "2-3 lời khuyên thực tế giúp người bệnh Đái tháo đường / Suy thận / Tăng huyết áp ăn món này an toàn hơn "
            "(VD: bỏ 2/3 nước dùng để giảm Natri, giảm 1/3 bánh phở/cơm, ăn rau trước...)"
        ),
    )
    ingredients: List[DecomposedIngredient] = Field(
        description="Danh sách 3-6 thành phần chính cấu thành 1 suất món ăn này"
    )


def _match_db_food(conn, keyword: Optional[str]) -> Optional[Dict[str, Any]]:
    """Tìm nguyên liệu đơn trong bảng `nutri.foods` nếu khớp đáng tin cậy."""
    if not keyword or not keyword.strip():
        return None
    kw_norm = _strip_accents(keyword.strip())
    if not kw_norm or kw_norm in _COMPOSITE_KEYWORDS:
        return None
    if any(comp in kw_norm for comp in ("nuoc dung", "nuoc leo", "nuoc pho", "nuoc ham", "tra sua", "tran chau", "com ")):
        return None

    row = conn.execute(
        """
        SELECT id, name, unit, water_g, energy_kcal, protein_g, lipid_g, glucid_g, fiber_g,
               sodium_mg, potassium_mg, phosphorus_mg, calcium_mg, iron_mg, zinc_mg,
               magnesium_mg, vitamin_c_mg, gi,
               similarity(f_unaccent(lower(name)), f_unaccent(lower(%s))) AS sim
        FROM foods
        WHERE f_unaccent(lower(name)) = f_unaccent(lower(%s))
           OR similarity(f_unaccent(lower(name)), f_unaccent(lower(%s))) >= 0.58
        ORDER BY
            (f_unaccent(lower(name)) = f_unaccent(lower(%s))) DESC,
            sim DESC,
            length(name) ASC
        LIMIT 1;
        """,
        (keyword.strip(), keyword.strip(), keyword.strip(), keyword.strip()),
    ).fetchone()
    return dict(row) if row else None


def _decompose_with_gemini(
    dish_query: str = "",
    file_bytes: Optional[bytes] = None,
    mime_type: str = "image/jpeg",
    patient_context_summary: str = "",
) -> tuple[DishDecomposition, str]:
    """Gọi Gemini Vision / LLM để bóc tách món ăn bất kỳ thành nguyên liệu + định lượng gram."""
    prompt = (
        "Bạn là chuyên gia Dinh dưỡng Lâm sàng Việt Nam. "
        "Hãy nhận diện món ăn từ ảnh chụp và/hoặc tên món người dùng cung cấp, sau đó:\n"
        "1. Bóc tách 1 suất ăn tiêu chuẩn thành 3 đến 6 thành phần nguyên liệu chính kèm khối lượng gram (hoặc ml).\n"
        "   - Lưu ý: Với món nước (Phở, Bún, Miến, Hủ tiếu...), BẮT BUỘC tách riêng phần 'Nước dùng/Nước lèo' (thường 280-350ml, "
        "chứa khoảng 320-450mg Natri/100ml do nêm muối/nước mắm/hạt nêm, và 30-60mg Kali/100ml từ xương hầm).\n"
        "   - Với món có cơm chín, để `db_lookup_keyword` là null và ghi thành phần là 'Cơm trắng chín' (~130 kcal, 28.2g glucid, 2.7g đạm / 100g) "
        "để không bị nhầm với gạo khô sống.\n"
        "2. Với mỗi thành phần, nếu là nguyên liệu thô/cơ bản có trong Bảng Thành phần Thực phẩm Việt Nam "
        "(như 'Bánh phở', 'Bún', 'Bánh mì', 'Thịt bò loại 1', 'Thịt lợn nạc', 'Thịt gà ta', 'Tôm biển', 'Trứng gà', 'Đậu phụ', 'Hành lá', 'Giá đỗ'), "
        "hãy điền `db_lookup_keyword` chính xác. Nếu là nước dùng, sốt, cơm chín hoặc đồ chế biến hỗn hợp thì để `db_lookup_keyword` là null.\n"
        "3. Luôn ước tính đầy đủ 14 chỉ số dinh dưỡng trên 100g trong `per_100g` cho mọi thành phần (đặc biệt là energy_kcal, protein_g, lipid_g, glucid_g, fiber_g, sodium_mg, potassium_mg, phosphorus_mg).\n"
        "4. Đánh giá chỉ số đường huyết `estimated_gi` của cả món ('Thấp', 'Trung bình', hoặc 'Cao') và đưa ra 2-3 mẹo ăn thực tế "
        "(cách bớt nước dùng, điều chỉnh khẩu phần bánh phở/cơm, thứ tự ăn rau-đạm-bột) phù hợp với bệnh nhân.\n"
    )
    if dish_query.strip():
        prompt += f"\nThông tin món người dùng nhập: '{dish_query.strip()}'."
    if patient_context_summary:
        prompt += f"\nBối cảnh bệnh nhân đang kiểm tra: {patient_context_summary}."

    contents: List[Any] = []
    if file_bytes:
        opt_bytes, opt_mime = _compress_image_if_needed(file_bytes, mime_type)
        contents.append(types.Part.from_bytes(data=opt_bytes, mime_type=opt_mime))
    contents.append(prompt)

    parsed, model_used = generate_structured(contents, DishDecomposition, fast=True)
    return parsed, model_used


def analyze_any_dish(
    dish_query: str = "",
    file_bytes: Optional[bytes] = None,
    mime_type: str = "image/jpeg",
    patient_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Phân tích món ăn bất kỳ từ ảnh và/hoặc tên món, ghép CSDL 690 món + chấm Guardrail 4 mức."""
    if not file_bytes and not dish_query.strip():
        raise ValueError("Vui lòng tải ảnh món ăn hoặc nhập tên món cần phân tích.")

    patient_summary = ""
    allergen_kws: List[str] = []
    raw_allergies: List[str] = []
    dict_rules: List[Dict[str, Any]] = []
    target_info: Optional[Dict[str, Any]] = None

    with get_conn() as conn:
        if patient_id:
            p = conn.execute(
                "SELECT nickname, food_allergies FROM patients WHERE id = %s;",
                (patient_id,),
            ).fetchone()
            if p:
                raw_allergies = list(p["food_allergies"] or [])
                allergen_kws = expand_allergens(raw_allergies)

            cond_rows = conn.execute(
                """
                SELECT c.code, c.name, cs.stage_code
                FROM patient_conditions pc
                JOIN conditions c ON c.id = pc.condition_id
                LEFT JOIN condition_stages cs ON cs.id = pc.stage_id
                WHERE pc.patient_id = %s AND pc.resolved_at IS NULL;
                """,
                (patient_id,),
            ).fetchall()
            cond_names = [
                f"{r['name']}" + (f" (giai đoạn {r['stage_code']})" if r.get("stage_code") else "")
                for r in cond_rows
            ]

            t_row = conn.execute(
                """
                SELECT nt.*, dr.code AS regime_code, dr.name AS regime_name
                FROM nutrition_targets nt
                LEFT JOIN diet_regimes dr ON dr.id = nt.regime_id
                WHERE nt.patient_id = %s AND nt.is_current = TRUE
                LIMIT 1;
                """,
                (patient_id,),
            ).fetchone()
            if t_row:
                target_info = {
                    "regime_code": t_row["regime_code"],
                    "regime_name": t_row["regime_name"],
                    "energy_kcal": float(t_row["energy_kcal"]) if t_row["energy_kcal"] is not None else None,
                    "protein_g": float(t_row["protein_g"]) if t_row["protein_g"] is not None else None,
                    "glucid_g": float(t_row["glucid_g"]) if t_row["glucid_g"] is not None else None,
                    "lipid_g": float(t_row["lipid_g"]) if t_row["lipid_g"] is not None else None,
                    "sodium_max_mg": float(t_row["sodium_max_mg"]) if t_row["sodium_max_mg"] is not None else None,
                    "potassium_max_mg": float(t_row["potassium_max_mg"]) if t_row["potassium_max_mg"] is not None else None,
                    "phosphate_max_mg": float(t_row["phosphate_max_mg"]) if t_row["phosphate_max_mg"] is not None else None,
                    "require_low_gi": bool(t_row["require_low_gi"]),
                }

            if cond_names or raw_allergies:
                patient_summary = f"Bệnh lý: {', '.join(cond_names) or 'Không'}. Dị ứng: {', '.join(raw_allergies) or 'Không'}."

            rules = conn.execute(
                """
                SELECT frr.*
                FROM food_restriction_rules frr
                WHERE frr.condition_id IN (
                    SELECT condition_id FROM patient_conditions WHERE patient_id = %s AND resolved_at IS NULL
                )
                OR frr.regime_id = (
                    SELECT regime_id FROM nutrition_targets WHERE patient_id = %s AND is_current = TRUE LIMIT 1
                );
                """,
                (patient_id, patient_id),
            ).fetchall()
            dict_rules = [dict(r) for r in rules]

        decomp, model_used = _decompose_with_gemini(
            dish_query=dish_query,
            file_bytes=file_bytes,
            mime_type=mime_type,
            patient_context_summary=patient_summary,
        )

        gi_norm = decomp.estimated_gi if decomp.estimated_gi in ("Thấp", "Trung bình", "Cao") else "Trung bình"
        enriched_ingredients: List[Dict[str, Any]] = []

        for idx, ing in enumerate(decomp.ingredients):
            w_g = max(0.0, float(ing.weight_g or 0.0))
            db_food = _match_db_food(conn, ing.db_lookup_keyword)
            ai_100g = ing.per_100g.model_dump()

            merged_100g: Dict[str, float] = {}
            for k in NUTRIENT_KEYS:
                if db_food and db_food.get(k) is not None:
                    merged_100g[k] = round(float(db_food[k]), 2)
                else:
                    merged_100g[k] = round(max(0.0, float(ai_100g.get(k) or 0.0)), 2)

            ing_amount: Dict[str, float] = {
                k: round(merged_100g[k] * w_g / 100.0, 1) for k in NUTRIENT_KEYS
            }

            enriched_ingredients.append(
                {
                    "id": idx + 1,
                    "name": ing.name,
                    "role": ing.role,
                    "weight_g": round(w_g, 0),
                    "default_weight_g": round(w_g, 0),
                    "source": "DB" if db_food else "AI",
                    "matched_food_id": db_food["id"] if db_food else None,
                    "matched_food_name": db_food["name"] if db_food else None,
                    "per_100g": merged_100g,
                    "amount": ing_amount,
                }
            )

    total_weight_g = round(sum(item["weight_g"] for item in enriched_ingredients), 0) or 100.0
    serving_totals: Dict[str, float] = {}
    per_100g_totals: Dict[str, float] = {}

    for k in NUTRIENT_KEYS:
        tot = sum(item["per_100g"][k] * item["weight_g"] / 100.0 for item in enriched_ingredients)
        serving_totals[k] = round(tot, 1)
        per_100g_totals[k] = round(tot * 100.0 / total_weight_g, 1)

    # Đánh giá an toàn kết hợp:
    # 1) Kiểm tra dị ứng trên tên món + toàn bộ tên nguyên liệu thành phần
    combined_name_for_allergy = f"{decomp.dish_name} (" + ", ".join(
        f"{i['name']} {i.get('matched_food_name') or ''}" for i in enriched_ingredients
    ) + ")"
    synthetic_food_100g = {
        "id": None,
        "name": combined_name_for_allergy,
        "gi": gi_norm,
        **per_100g_totals,
    }

    safety_action = "PASS"
    safety_reasons: List[str] = []

    if patient_id:
        ev = classify_food_with_rules(synthetic_food_100g, dict_rules, allergen_kws)
        safety_action = ev["tier"]
        safety_reasons = list(ev["reasons"])

        tier_rank = {"PASS": 0, "PORTION": 1, "WARN": 2, "BLOCK": 3}

        def _escalate(new_tier: str, reason: str):
            nonlocal safety_action
            if reason not in safety_reasons:
                safety_reasons.append(reason)
            if tier_rank[new_tier] > tier_rank[safety_action]:
                safety_action = new_tier

        # 2) Đánh giá theo tổng 1 suất ăn thực tế so với ngân sách mục tiêu ngày của bệnh nhân
        if target_info:
            na_max = target_info.get("sodium_max_mg")
            if na_max and serving_totals["sodium_mg"] > na_max * 0.45:
                pct = round(serving_totals["sodium_mg"] * 100.0 / na_max)
                _escalate(
                    "WARN",
                    f"1 suất chứa {serving_totals['sodium_mg']:.0f}mg Natri (chiếm {pct}% giới hạn Natri cả ngày {na_max:.0f}mg).",
                )

            k_max = target_info.get("potassium_max_mg")
            if k_max and serving_totals["potassium_mg"] > k_max * 0.42:
                pct = round(serving_totals["potassium_mg"] * 100.0 / k_max)
                _escalate(
                    "WARN",
                    f"1 suất chứa {serving_totals['potassium_mg']:.0f}mg Kali (chiếm {pct}% giới hạn Kali cả ngày {k_max:.0f}mg).",
                )

            p_max = target_info.get("phosphate_max_mg")
            if p_max and serving_totals["phosphorus_mg"] > p_max * 0.45:
                pct = round(serving_totals["phosphorus_mg"] * 100.0 / p_max)
                _escalate(
                    "WARN",
                    f"1 suất chứa {serving_totals['phosphorus_mg']:.0f}mg Phospho (chiếm {pct}% giới hạn Phospho cả ngày {p_max:.0f}mg).",
                )

            if target_info.get("require_low_gi"):
                if gi_norm == "Cao":
                    _escalate(
                        "WARN",
                        "Món ăn có chỉ số đường huyết (GI) Cao, dễ gây tăng đường huyết đột ngột sau ăn.",
                    )
                if serving_totals["glucid_g"] >= 40:
                    _escalate(
                        "PORTION",
                        f"1 suất cung cấp {serving_totals['glucid_g']:.1f}g tinh bột (Glucid), cần kiểm soát lượng bánh phở/bún/cơm trong bữa.",
                    )

            prot_target = target_info.get("protein_g")
            if prot_target and serving_totals["protein_g"] > prot_target * 0.50:
                pct = round(serving_totals["protein_g"] * 100.0 / prot_target)
                _escalate(
                    "PORTION",
                    f"1 suất cung cấp {serving_totals['protein_g']:.1f}g Đạm (chiếm {pct}% tổng đạm cả ngày {prot_target:.0f}g).",
                )

    db_matched_count = sum(1 for i in enriched_ingredients if i["source"] == "DB")

    return {
        "dish_name": decomp.dish_name,
        "serving_description": decomp.serving_description,
        "total_weight_g": total_weight_g,
        "estimated_gi": gi_norm,
        "confidence_note": decomp.confidence_note,
        "model_used": model_used,
        "db_matched_count": db_matched_count,
        "total_ingredients_count": len(enriched_ingredients),
        "safety_action": safety_action,
        "safety_reasons": safety_reasons,
        "clinical_tips": decomp.clinical_tips,
        "serving_totals": serving_totals,
        "per_100g_totals": per_100g_totals,
        "ingredients": enriched_ingredients,
        "patient_target": target_info,
        "patient_allergen_keywords": allergen_kws,
    }
