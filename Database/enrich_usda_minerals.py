"""Bổ sung các vi chất còn thiếu (Kali, Natri, Phospho, Canxi, Sắt, Kẽm, Magie)
trong `nutri.foods` từ bộ dữ liệu chuẩn quốc tế USDA SR28 (`usda.sql3`),
kèm kiểm tra chéo Calo/Đạm để đảm bảo không ghép nhầm thực phẩm tươi/khô."""
import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from src.db import get_conn
from src.llm import generate_structured

DEFAULT_USDA_PATH = Path(
    r"C:\Users\Lenovo\.gemini\antigravity\brain\a89a584f-080c-437e-b276-ee709ec44d61\scratch\usda.sql3"
)
LOG_PATH = ROOT / "data" / "processed" / "usda_enrichment_log.json"


class FoodTranslationItem(BaseModel):
    food_id: int
    english_queries: List[str] = Field(
        description="2-3 cụm từ tìm kiếm tiếng Anh chuẩn kiểu USDA SR28 (VD: ['taro, raw', 'taro'])"
    )


class FoodTranslationBatch(BaseModel):
    items: List[FoodTranslationItem]


def load_usda_sr28(usda_path: Path) -> List[Dict[str, Any]]:
    """Đọc ~8,789 thực phẩm chuẩn từ USDA SR28 SQLite."""
    con = sqlite3.connect(str(usda_path))
    foods = {}
    for fid, desc in con.execute("SELECT id, long_desc FROM food;"):
        foods[fid] = {
            "usda_id": fid,
            "desc": desc,
            "desc_low": desc.lower(),
            "tokens": set(re.findall(r"[a-z0-9]+", desc.lower())),
        }

    nid_map = {
        203: "protein_g",
        204: "lipid_g",
        205: "glucid_g",
        208: "energy_kcal",
        291: "fiber_g",
        301: "calcium_mg",
        303: "iron_mg",
        304: "magnesium_mg",
        305: "phosphorus_mg",
        306: "potassium_mg",
        307: "sodium_mg",
        309: "zinc_mg",
    }
    for fid, nid, amt in con.execute(
        "SELECT food_id, nutrient_id, amount FROM nutrition WHERE nutrient_id IN (203,204,205,208,291,301,303,304,305,306,307,309);"
    ):
        if fid in foods and nid in nid_map:
            foods[fid][nid_map[nid]] = float(amt)
    con.close()
    return list(foods.values())


def _is_cooked_or_dried_vn(vn_name: str) -> str:
    low = vn_name.lower()
    if any(k in low for k in ("khô", "bột", "rang", "sấy", "chiên")):
        return "processed"
    if any(k in low for k in ("luộc", "nấu", "hấp", "hộp", "muối")):
        return "cooked"
    return "raw"


def _best_usda_match(
    vn_food: Dict[str, Any],
    queries: List[str],
    usda_foods: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Tìm món USDA SR28 khớp nhất có kiểm tra chéo năng lượng & đạm."""
    vn_kcal = float(vn_food["energy_kcal"] or 0)
    vn_prot = float(vn_food["protein_g"] or 0)
    vn_state = _is_cooked_or_dried_vn(vn_food["name"])

    best_score = -1.0
    best_item = None

    for q_idx, q in enumerate(queries):
        q_tokens = [t for t in re.findall(r"[a-z0-9]+", q.lower()) if len(t) >= 2]
        if not q_tokens:
            continue

        for u in usda_foods:
            if u.get("potassium_mg") is None and u.get("sodium_mg") is None:
                continue
            u_tokens = u["tokens"]
            overlap = sum(1 for t in q_tokens if t in u_tokens)
            if overlap == 0:
                continue
            # Bảo đảm danh từ chính khớp phần tên đầu của USDA (trước dấu phẩy thứ nhất/hai)
            head_part = u["desc_low"].split(",")[0]
            head_tokens = set(re.findall(r"[a-z0-9]+", head_part))
            # Hỗ trợ số ít/số nhiều đơn giản (vd tamarind <-> tamarinds)
            expanded_head = head_tokens | {t.rstrip("s") for t in head_tokens} | {t + "s" for t in head_tokens}
            first_q = q_tokens[0]
            first_variants = {first_q, first_q.rstrip("s"), first_q + "s"}
            if not (first_variants & expanded_head) and first_q not in ("fish", "meat", "oil"):
                continue

            # Yêu cầu khớp ít nhất toàn bộ token nếu query ngắn (<=2 từ) hoặc >=2/3 số từ
            expanded_u = u_tokens | {t.rstrip("s") for t in u_tokens}
            overlap = sum(1 for t in q_tokens if t in expanded_u or t.rstrip("s") in expanded_u)
            min_req = len(q_tokens) if len(q_tokens) <= 2 else max(2, int(len(q_tokens) * 0.65))
            if overlap < min_req:
                continue

            # Kiểm tra chéo Calo để tránh ghép nhầm tươi/khô
            u_kcal = u.get("energy_kcal")
            if vn_kcal >= 25 and u_kcal is not None and u_kcal > 0:
                ratio = u_kcal / vn_kcal
                if ratio < 0.45 or ratio > 2.2:
                    continue

            # Kiểm tra chéo Đạm nếu là thực phẩm giàu đạm
            u_prot = u.get("protein_g")
            if vn_prot >= 10 and u_prot is not None and u_prot > 0:
                p_ratio = u_prot / vn_prot
                if p_ratio < 0.4 or p_ratio > 2.5:
                    continue

            score = (overlap / len(q_tokens)) * 10.0 - q_idx * 1.5
            desc_low = u["desc_low"]
            if desc_low.startswith(q_tokens[0]):
                score += 2.0
            if vn_state == "raw" and ", raw" in desc_low:
                score += 2.0
            elif vn_state == "cooked" and ("cooked" in desc_low or "boiled" in desc_low or "canned" in desc_low):
                score += 1.5
            elif vn_state == "processed" and ("dried" in desc_low or "flour" in desc_low or "fried" in desc_low or "powder" in desc_low):
                score += 1.5
            # Tránh khớp nhầm đồ babyfood hoặc fastfood nếu tên VN không nhắc tới
            if "babyfood" in desc_low or "restaurant" in desc_low or "infant formula" in desc_low:
                score -= 5.0
            # Thưởng nếu khớp sát Calo
            if vn_kcal > 0 and u_kcal is not None:
                score -= abs(u_kcal - vn_kcal) / max(vn_kcal, 50.0)

            if score > best_score:
                best_score = score
                best_item = u

    if best_score < 6.0:
        return None
    return best_item


def translate_batch(batch: List[Dict[str, Any]]) -> Dict[int, List[str]]:
    payload = [{"id": r["id"], "name": r["name"], "kcal": float(r["energy_kcal"] or 0)} for r in batch]
    prompt = f"""
Bạn là chuyên gia dữ liệu dinh dưỡng. Hãy dịch danh sách thực phẩm Việt Nam sau sang 2-3 cụm từ tìm kiếm tiếng Anh chuẩn của bảng USDA SR28 để tra hàm lượng khoáng chất (Kali, Natri, Phospho).
Quy tắc:
- Giữ đúng trạng thái tươi/khô/bột/luộc/chiên (VD: "Khoai môn" -> ["taro, raw", "taro"]; "Bánh mỳ" -> ["bread, white", "bread, french"]; "Miến dong" -> ["noodles, glass, dry", "vermicelli, dry"]; "Cà tím" -> ["eggplant, raw"]; "Cá mỡ" -> ["fish, bass, raw", "fish, mackerel, raw"]; "Bún" -> ["noodles, rice, cooked"]).
- Nếu trong tên đã có tiếng Anh trong ngoặc, ưu tiên dùng chính cụm tiếng Anh đó.

DANH SÁCH:
{json.dumps(payload, ensure_ascii=False)}
"""
    parsed, _ = generate_structured(prompt, FoodTranslationBatch, fast=True)
    return {item.food_id: item.english_queries for item in parsed.items}


def run_enrichment(usda_path: Path = DEFAULT_USDA_PATH, apply_db: bool = True) -> None:
    if not usda_path.exists():
        raise FileNotFoundError(f"Không tìm thấy USDA SQLite tại: {usda_path}")

    usda_foods = load_usda_sr28(usda_path)
    print(f"Đã nạp {len(usda_foods)} thực phẩm chuẩn từ USDA SR28.")

    with get_conn() as conn:
        missing_rows = conn.execute(
            """
            SELECT id, name, energy_kcal, protein_g, lipid_g, glucid_g, fiber_g,
                   potassium_mg, sodium_mg, phosphorus_mg, calcium_mg, iron_mg, zinc_mg, magnesium_mg
            FROM foods
            WHERE potassium_mg IS NULL OR sodium_mg IS NULL OR phosphorus_mg IS NULL
               OR lipid_g IS NULL OR fiber_g IS NULL OR protein_g IS NULL
            ORDER BY id;
            """
        ).fetchall()

    print(f"Tìm thấy {len(missing_rows)} món thiếu vi chất/đa lượng. Bắt đầu dịch & đối chiếu USDA...")

    translations: Dict[int, List[str]] = {}
    batch_size = 45
    for i in range(0, len(missing_rows), batch_size):
        chunk = [dict(r) for r in missing_rows[i : i + batch_size]]
        print(f" - Đang dịch batch {i // batch_size + 1}/{(len(missing_rows) - 1) // batch_size + 1}...")
        translations.update(translate_batch(chunk))

    matched_logs = []
    unmatched_logs = []
    target_cols = [
        "protein_g", "lipid_g", "glucid_g", "fiber_g",
        "potassium_mg", "sodium_mg", "phosphorus_mg", "calcium_mg", "iron_mg", "zinc_mg", "magnesium_mg",
    ]

    with get_conn() as conn:
        for row in missing_rows:
            queries = translations.get(row["id"], [])
            # Thêm cụm tiếng Anh trong ngoặc nếu có
            paren = re.search(r"\(([^)]+)\)", row["name"])
            if paren:
                queries = [paren.group(1)] + queries

            match = _best_usda_match(dict(row), queries, usda_foods)
            if not match:
                unmatched_logs.append({"id": row["id"], "name": row["name"], "queries": queries})
                continue

            updates: Dict[str, float] = {}
            for col in target_cols:
                if row[col] is None and match.get(col) is not None:
                    updates[col] = round(float(match[col]), 2)

            if not updates:
                unmatched_logs.append({"id": row["id"], "name": row["name"], "queries": queries, "reason": "USDA match lacks missing cols"})
                continue

            if apply_db:
                set_clause = ", ".join(f"{col} = %s" for col in updates)
                conn.execute(
                    f"UPDATE foods SET {set_clause} WHERE id = %s;",
                    tuple(updates.values()) + (row["id"],),
                )

            matched_logs.append({
                "id": row["id"],
                "name": row["name"],
                "usda_id": match["usda_id"],
                "usda_desc": match["desc"],
                "filled": updates,
            })

    LOG_PATH.write_text(
        json.dumps(
            {
                "matched_count": len(matched_logs),
                "unmatched_count": len(unmatched_logs),
                "matched": matched_logs,
                "unmatched": unmatched_logs,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"HOÀN TẤT! Đã khớp USDA: {len(matched_logs)} món | Chưa khớp: {len(unmatched_logs)} món.")
    print(f"Chi tiết đối chiếu đã lưu tại: {LOG_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bù vi chất thiếu từ USDA SR28")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ đối chiếu và xuất log, chưa ghi vào DB")
    args = parser.parse_args()
    run_enrichment(apply_db=not args.dry_run)
