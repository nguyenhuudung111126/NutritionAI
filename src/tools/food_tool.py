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


BROAD_CATEGORY_PREFIXES: Dict[str, List[str]] = {
    "ca": ["ca %"],
    "thit": ["thit %"],
    "rau": ["rau %", "cai %", "bi %", "bau%", "su su%", "muop%"],
    "trai cay": ["tao %", "le", "cam", "buoi", "chuoi%", "oi", "dua hau%", "xoai%", "nho %"],
    "hoa qua": ["tao %", "le", "cam", "buoi", "chuoi%", "oi", "dua hau%", "xoai%", "nho %"],
    "hai san": ["tom%", "cua%", "ghe%", "muc%", "oc%", "ngao%", "hen%", "so%"],
    "sua": ["sua %"],
    "trung": ["trung %", "long trang trung%"],
}


def get_category_key(food_name: str) -> Optional[str]:
    norm = _strip_accents(food_name or "").strip()
    return norm if norm in BROAD_CATEGORY_PREFIXES else None


def search_category_foods(cat_key: str, limit: int = 18) -> List[Dict[str, Any]]:
    """Lấy danh sách thực phẩm tươi phổ biến thuộc 1 nhóm chung (VD: 'cá', 'thịt', 'rau', 'trái cây')."""
    patterns = BROAD_CATEGORY_PREFIXES.get(cat_key)
    if not patterns:
        return []
    sql = """
        SELECT id, name, unit, energy_kcal, protein_g, lipid_g, glucid_g, fiber_g,
               sodium_mg, potassium_mg, phosphorus_mg, calcium_mg, iron_mg, gi
        FROM foods
        WHERE f_unaccent(lower(name)) LIKE ANY(%s)
          AND f_unaccent(lower(name)) NOT LIKE ALL(ARRAY[
              '%% hop%%','%% kho','%% kho %%','%% muoi%%','%% say%%','%%ruou%%','%%bia%%',
              '%%sua me%%','%%thit cho%%','%%thit huou%%','%%thit ngua%%','%%thit trau%%',
              '%%thit cuu%%','%%thit de%%','%%thit tho%%','%%bau duc%%','%%gan %%','%%long %%'
          ])
        ORDER BY COALESCE(potassium_mg, 999) ASC, id ASC
        LIMIT %s;
    """
    with get_conn() as conn:
        rows = conn.execute(sql, (patterns, limit)).fetchall()
    return [dict(r) for r in rows]


def search_food(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Tìm thực phẩm theo tên (hỗ trợ gõ không dấu / pg_trgm, ưu tiên thực phẩm tươi sống trừ khi người dùng hỏi đồ hộp/khô/mỡ)."""
    q_clean = query.strip()
    if not q_clean:
        return []
    q_norm = _strip_accents(q_clean)
    wants_processed = any(k in q_norm for k in ("hop", "kho", "muoi", "say", "xong khoi", "hun khoi", "mo"))
    fresh_order = (
        ""
        if wants_processed
        else """(f_unaccent(lower(name)) NOT LIKE ALL(ARRAY[
            '%% hop%%','%% kho','%% kho %%','%% muoi%%','%% say%%','%% xong khoi%%','%% hun khoi%%','%% mo'
        ])) DESC, """
    )
    sql = f"""
        SELECT id, name, unit, energy_kcal, protein_g, lipid_g, glucid_g, fiber_g,
               sodium_mg, potassium_mg, phosphorus_mg, calcium_mg, iron_mg, gi,
               similarity(f_unaccent(lower(name)), f_unaccent(lower(%s))) AS sim
        FROM foods
        WHERE f_unaccent(lower(name)) ILIKE '%%' || f_unaccent(lower(%s)) || '%%'
           OR f_unaccent(lower(name)) %% f_unaccent(lower(%s))
        ORDER BY
            (f_unaccent(lower(name)) = f_unaccent(lower(%s))) DESC,
            (f_unaccent(lower(name)) ILIKE '%%' || f_unaccent(lower(%s)) || '%%') DESC,
            {fresh_order}
            sim DESC,
            length(name) ASC
        LIMIT %s;
    """
    with get_conn() as conn:
        rows = conn.execute(sql, (q_clean, q_clean, q_clean, q_clean, q_clean, limit)).fetchall()
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
        n_carb = max(6, round(limit * 0.20))
        n_meat = max(7, round(limit * 0.22))
        n_fish_egg = max(7, round(limit * 0.22))
        n_veg = max(10, limit - n_carb - n_meat - n_fish_egg)

        # Lấy ngẫu nhiên trong từng nhóm đạt chuẩn an toàn + luôn giữ các nguyên liệu nền tảng cơm nhà Việt Nam
        sql = f"""
            WITH safe AS (
                SELECT id, name, unit, energy_kcal, water_g, protein_g, lipid_g, glucid_g,
                       fiber_g, sodium_mg, potassium_mg, phosphorus_mg, gi
                FROM foods
                WHERE {where_clause}
                  AND f_unaccent(lower(name)) NOT LIKE ALL(ARRAY[
                      '%%ruou%%','%%bia%%','%%sua me%%','%%thit cho%%','%%co nhac%%','%%coc tain%%',
                      '%%thit huou%%','%%thit ngua%%','%%thit cuu%%','%%thit de%%','%%thit tho%%',
                      '%%thit ngong%%','%%ga rung%%','%%bo cau%%','%%thit trau%%',
                      '%%bau duc%%','%%da day%%','%%dau bo%%','%%dau lon%%','%%duoi bo%%','%%duoi lon%%',
                      '%%gan %%','%%luoi %%','%%long %%','%%bi lon%%','%%gan chan%%'
                  ])
            )
            (SELECT * FROM safe WHERE id IN (5, 31, 38, 74, 295, 299, 440))
            UNION
            (SELECT * FROM safe
             WHERE COALESCE(glucid_g, 0) >= 15 AND energy_kcal BETWEEN 80 AND 400
               AND COALESCE(fiber_g, 0) <= 10 AND COALESCE(sodium_mg, 0) <= 400
               AND id NOT IN (41, 42, 43)
             ORDER BY random() LIMIT %s)
            UNION
            (SELECT * FROM safe
             WHERE id BETWEEN 283 AND 310
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
    source_food: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Gợi ý thực phẩm thay thế an toàn cùng nhóm thực phẩm (loại dầu ăn, mỡ, gia vị, nội tạng)."""
    with get_conn() as conn:
        allergen_patterns = _get_patient_allergen_patterns(conn, patient_id)
        conditions = [
            "potassium_mg IS NOT NULL",
            "energy_kcal IS NOT NULL",
            "energy_kcal BETWEEN 10 AND 400",
            "COALESCE(lipid_g, 0) <= 25",
            """f_unaccent(lower(name)) NOT LIKE ALL(ARRAY[
                '%%dau %%','%%mo %%','%%bo thuc vat%%','%%bo dong vat%%','%%magarin%%',
                '%%duong %%','%%muoi %%','%%nuoc mam%%','%%mam %%','%%tuong %%','%%xi dau%%',
                '%%bot ngot%%','%%hat nem%%','%%tieu %%','%%ot bot%%','%%ruou%%','%%bia%%',
                '%%coc tain%%','%%co nhac%%','%%con %%','%%hop%%','%%nem %%','%%gio %%',
                '%% kho','%%sua me%%','%%sua %%','%%bot %%','%%thit cho%%','%%thit huou%%',
                '%%thit ngua%%','%%thit trau%%','%%thit cuu%%','%%thit de%%','%%thit tho%%',
                '%%bau duc%%','%%gan %%','%%long %%','%%tim %%','%%da day%%','%%dau bo%%','%%dau lon%%',
                '%%duoi bo%%','%%duoi lon%%','%%tai lon%%','%%chan gio%%','%%bi lon%%','%%tao pho%%'
            ])""",
        ]
        params: List[Any] = []

        if source_food and source_food.get("id") is not None:
            conditions.append("id <> %s")
            params.append(source_food["id"])

        is_carb_source = bool(
            source_food
            and float(source_food.get("glucid_g") or 0) >= 25
            and float(source_food.get("energy_kcal") or 0) >= 90
        )
        eff_max_k = max(float(max_potassium_mg), 260.0) if (max_potassium_mg is not None and is_carb_source) else max_potassium_mg

        if allergen_patterns:
            conditions.append("NOT (f_unaccent(lower(name)) LIKE ANY(%s))")
            params.append(allergen_patterns)
        if eff_max_k is not None:
            conditions.append("potassium_mg <= %s")
            params.append(eff_max_k)
        if max_sodium_mg is not None:
            conditions.append("(sodium_mg IS NULL OR sodium_mg <= %s)")
            params.append(max_sodium_mg)
        if require_low_gi:
            conditions.append("gi = 'Thấp'::gi_level")

        # Ưu tiên cùng nhóm thực phẩm tươi sống phổ biến với món gốc (rau củ / đạm / tinh bột)
        if source_food:
            src_kcal = float(source_food.get("energy_kcal") or 0)
            src_prot = float(source_food.get("protein_g") or 0)
            src_carb = float(source_food.get("glucid_g") or 0)
            if src_prot >= 10 and src_carb < 25:
                # Nhóm đạm (thịt nạc, cá, trứng, đậu phụ)
                order_prefix = (
                    "(id IN (74, 295, 299, 440, 442) OR "
                    "(id BETWEEN 284 AND 445 AND COALESCE(protein_g, 0) >= 10 AND COALESCE(lipid_g, 0) <= 18)) DESC, "
                )
            elif src_carb >= 25 and src_kcal >= 90:
                # Nhóm tinh bột lành mạnh (gạo lứt, khoai lang, miến dong)
                order_prefix = (
                    "(id IN (5, 31, 32, 38) OR "
                    "(COALESCE(glucid_g, 0) >= 18 AND energy_kcal BETWEEN 80 AND 380)) DESC, "
                )
            else:
                # Nhóm rau củ quả tươi ít Kali (loại hải sản/nhuyễn thể có water_g cao)
                order_prefix = (
                    "(COALESCE(water_g, 0) >= 84 AND COALESCE(protein_g, 0) < 4 "
                    "AND energy_kcal <= 85 AND COALESCE(sodium_mg, 0) <= 100) DESC, "
                )
        else:
            order_prefix = (
                "(COALESCE(water_g, 0) >= 84 AND COALESCE(protein_g, 0) < 4 "
                "OR id IN (5, 31, 32, 38, 74, 295, 440, 442)) DESC, "
            )

        sql = f"""
            SELECT id, name, energy_kcal, protein_g, potassium_mg, sodium_mg, gi
            FROM foods
            WHERE {' AND '.join(conditions)}
            ORDER BY {order_prefix}potassium_mg ASC, COALESCE(phosphorus_mg, 999) ASC
            LIMIT %s;
        """
        params.append(limit)
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(r) for r in rows]
