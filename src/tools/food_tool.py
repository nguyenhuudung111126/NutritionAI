"""Tool tra cứu 690 thực phẩm, lọc dị ứng và tìm món thay thế an toàn từ `nutri.foods`."""
import random
import re
import unicodedata
from typing import Any, Dict, List, Optional

from src.db import get_conn

# Từ điển mở rộng nhóm dị ứng -> các từ khóa nguyên liệu/chế phẩm liên quan
ALLERGEN_SYNONYMS: Dict[str, List[str]] = {
    "hải sản": [
        "tôm", "tép", "cua", "ghẹ", "mực", "bạch tuộc", "ốc", "sò",
        "ngao", "hến", "trai", "rươi", "hải sâm", "mắm tôm", "mắm ruốc",
    ],
    "tôm": ["tôm", "tép", "mắm tôm", "mắm ruốc", "bánh phồng tôm", "ruốc tôm"],
    "cua": ["cua", "ghẹ", "rạm"],
    "lạc": ["lạc", "đậu phộng"],
    "đậu phộng": ["lạc", "đậu phộng"],
    "sữa": ["sữa bò", "sữa dê", "sữa bột", "sữa chua", "sữa đặc", "pho mát", "caramen"],
    "trứng": ["trứng", "lòng đỏ", "lòng trắng", "mayonnaise"],
    "đậu nành": ["đậu nành", "đậu tương", "đậu phụ", "tàu hũ", "tào phớ", "xì dầu"],
}


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower().strip())
    return "".join(c for c in nfkd if not unicodedata.combining(c)).replace("đ", "d")


def expand_allergens(allergies: Optional[List[str]]) -> List[str]:
    """Mở rộng danh sách dị ứng thành các từ khóa không dấu để lọc trong SQL."""
    if not allergies:
        return []
    keywords = set()
    for item in allergies:
        clean = item.strip().lower()
        if not clean:
            continue
        keywords.add(_strip_accents(clean))
        for group, synonyms in ALLERGEN_SYNONYMS.items():
            if group in clean or clean in group:
                for syn in synonyms:
                    keywords.add(_strip_accents(syn))
    return sorted(keywords)


def search_food(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Tìm thực phẩm theo tên (hỗ trợ gõ không dấu hoặc gần đúng bằng pg_trgm)."""
    q_clean = query.strip()
    if not q_clean:
        return []
    sql = """
        SELECT id, name, unit, energy_kcal, protein_g, lipid_g, glucid_g, fiber_g,
               sodium_mg, potassium_mg, phosphorus_mg, calcium_mg, iron_mg, gi,
               similarity(f_unaccent(lower(name)), f_unaccent(lower(%s))) AS sim
        FROM foods
        WHERE f_unaccent(lower(name)) ILIKE '%%' || f_unaccent(lower(%s)) || '%%'
           OR f_unaccent(lower(name)) %% f_unaccent(lower(%s))
        ORDER BY
            (f_unaccent(lower(name)) ILIKE '%%' || f_unaccent(lower(%s)) || '%%') DESC,
            sim DESC,
            length(name) ASC
        LIMIT %s;
    """
    with get_conn() as conn:
        rows = conn.execute(sql, (q_clean, q_clean, q_clean, q_clean, limit)).fetchall()
    return [dict(r) for r in rows]


def _get_patient_allergen_patterns(conn, patient_id: str) -> List[str]:
    row = conn.execute(
        "SELECT food_allergies FROM patients WHERE id = %s;", (patient_id,)
    ).fetchone()
    if not row:
        return []
    keywords = expand_allergens(row["food_allergies"])
    return [f"%{kw}%" for kw in keywords]


def get_safe_foods(
    patient_id: str,
    max_potassium_mg: Optional[float] = None,
    max_sodium_mg: Optional[float] = None,
    max_phosphorus_mg: Optional[float] = None,
    require_low_gi: bool = False,
    limit: int = 120,
    prefer_query: str = "",
) -> List[Dict[str, Any]]:
    """Lọc pool nguyên liệu cân đối & ngẫu nhiên đa dạng (tinh bột + đạm + rau củ quả) an toàn cho bệnh nhân."""
    with get_conn() as conn:
        allergen_patterns = _get_patient_allergen_patterns(conn, patient_id)
        conditions = ["energy_kcal IS NOT NULL", "energy_kcal > 0"]
        params: List[Any] = []

        if allergen_patterns:
            conditions.append("NOT (f_unaccent(lower(name)) LIKE ANY(%s))")
            params.append(allergen_patterns)
        if max_potassium_mg is not None:
            conditions.append("(potassium_mg IS NULL OR potassium_mg <= %s)")
            params.append(max_potassium_mg)
        if max_sodium_mg is not None:
            conditions.append("(sodium_mg IS NULL OR sodium_mg <= %s)")
            params.append(max_sodium_mg)
        if max_phosphorus_mg is not None:
            conditions.append("(phosphorus_mg IS NULL OR phosphorus_mg <= %s)")
            params.append(max_phosphorus_mg)
        if require_low_gi:
            conditions.append("(gi IS NULL OR gi <> 'Cao'::gi_level)")

        where_clause = " AND ".join(conditions)
        n_carb = max(18, limit // 5)
        n_meat = max(18, limit // 5)
        n_fish_egg = max(22, limit // 4)
        n_veg = max(30, limit - n_carb - n_meat - n_fish_egg)

        # Lấy ngẫu nhiên trong từng nhóm đạt chuẩn an toàn để tránh lặp món đầu bảng
        sql = f"""
            WITH safe AS (
                SELECT id, name, unit, energy_kcal, water_g, protein_g, lipid_g, glucid_g,
                       fiber_g, sodium_mg, potassium_mg, phosphorus_mg, gi
                FROM foods
                WHERE {where_clause}
                  AND f_unaccent(lower(name)) NOT LIKE ALL(ARRAY['%%ruou%%','%%bia%%','%%sua me%%','%%thit cho%%','%%co nhac%%','%%coc tain%%'])
            )
            (SELECT * FROM safe
             WHERE COALESCE(glucid_g, 0) >= 15 AND energy_kcal BETWEEN 80 AND 400
               AND COALESCE(fiber_g, 0) <= 10 AND COALESCE(sodium_mg, 0) <= 400
             ORDER BY random() LIMIT %s)
            UNION
            (SELECT * FROM safe
             WHERE id BETWEEN 280 AND 373
               AND COALESCE(protein_g, 0) >= 12 AND COALESCE(lipid_g, 0) <= 20
             ORDER BY random() LIMIT %s)
            UNION
            (SELECT * FROM safe
             WHERE id BETWEEN 374 AND 460
               AND COALESCE(protein_g, 0) >= 10 AND COALESCE(lipid_g, 0) <= 20
             ORDER BY random() LIMIT %s)
            UNION
            (SELECT * FROM safe
             WHERE COALESCE(water_g, 0) >= 82 AND energy_kcal <= 85
               AND COALESCE(sodium_mg, 0) <= 100
             ORDER BY (COALESCE(potassium_mg, 999) <= 220) DESC, random() LIMIT %s);
        """
        rows = conn.execute(sql, tuple(params + [n_carb, n_meat, n_fish_egg, n_veg])).fetchall()

        result_map: Dict[int, Dict[str, Any]] = {r["id"]: dict(r) for r in rows}

        # Đảm bảo nếu người dùng nêu tên món cụ thể (an toàn) trong sở thích thì vẫn có mặt trong pool
        if prefer_query and prefer_query.strip():
            pref_tokens = [
                _strip_accents(w)
                for w in re.findall(r"[0-9A-Za-zÀ-ỹ]{2,}", prefer_query)
                if _strip_accents(w) not in {"thich", "mon", "luoc", "hap", "xao", "nau", "tu", "va", "cho", "an", "nhieu", "it"}
            ]
            pref_patterns = [f"%{t}%" for t in pref_tokens[:6]]
            if pref_patterns:
                pref_sql = f"""
                    SELECT id, name, unit, energy_kcal, water_g, protein_g, lipid_g, glucid_g,
                           fiber_g, sodium_mg, potassium_mg, phosphorus_mg, gi
                    FROM foods
                    WHERE {where_clause}
                      AND f_unaccent(lower(name)) LIKE ANY(%s)
                    ORDER BY COALESCE(potassium_mg, 999) ASC, id ASC
                    LIMIT 10;
                """
                pref_rows = conn.execute(pref_sql, tuple(params + [pref_patterns])).fetchall()
                for pr in pref_rows:
                    result_map.setdefault(pr["id"], dict(pr))

    result = list(result_map.values())
    random.shuffle(result)
    return result


def find_alternatives(
    patient_id: str,
    max_potassium_mg: Optional[float] = 200,
    max_sodium_mg: Optional[float] = 200,
    require_low_gi: bool = False,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Gợi ý thực phẩm thay thế an toàn (ít Kali, ít Natri, GI thấp, không dị ứng)."""
    with get_conn() as conn:
        allergen_patterns = _get_patient_allergen_patterns(conn, patient_id)
        conditions = ["potassium_mg IS NOT NULL"]
        params: List[Any] = []

        if allergen_patterns:
            conditions.append("NOT (f_unaccent(lower(name)) LIKE ANY(%s))")
            params.append(allergen_patterns)
        if max_potassium_mg is not None:
            conditions.append("potassium_mg <= %s")
            params.append(max_potassium_mg)
        if max_sodium_mg is not None:
            conditions.append("(sodium_mg IS NULL OR sodium_mg <= %s)")
            params.append(max_sodium_mg)
        if require_low_gi:
            conditions.append("gi = 'Thấp'::gi_level")

        sql = f"""
            SELECT id, name, energy_kcal, protein_g, potassium_mg, sodium_mg, gi
            FROM foods
            WHERE {' AND '.join(conditions)}
            ORDER BY potassium_mg ASC, energy_kcal DESC
            LIMIT %s;
        """
        params.append(limit)
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(r) for r in rows]
