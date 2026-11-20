"""Sinh file seed SQL cho PostgreSQL từ dữ liệu đã làm sạch.

Input : ../data/processed/thuc_pham_db_ready.csv (690 thực phẩm)
        ../data/raw/MaCheDoAn2006.xlsx            (phác đồ Bộ Y tế)
Output: 02_seed_foods.sql, 03_seed_regimes.sql

Chạy:  python build_seeds.py [đường_dẫn_MaCheDoAn2006.xlsx]
"""
import csv
import json
import re
import sys
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
FOODS_CSV = HERE.parent / "data" / "processed" / "thuc_pham_db_ready.csv"
REGIME_XLSX = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "data" / "raw" / "MaCheDoAn2006.xlsx"


def q(v):
    """SQL literal."""
    if v is None or v == "":
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


# ---------------------------------------------------------------- foods
FOOD_COLS = [  # csv column -> db column
    ("tt", "id"), ("ten_thuc_pham", "name"), ("don_vi_tinh", "unit"),
    ("thai_bo_pct", "waste_pct"), ("nang_luong_kcal", "energy_kcal"),
    ("nuoc_g", "water_g"), ("protein_g", "protein_g"), ("lipid_g", "lipid_g"),
    ("glucid_g", "glucid_g"), ("chat_xo_g", "fiber_g"), ("tro_tong_g", "ash_g"),
    ("calci_mg", "calcium_mg"), ("phospho_mg", "phosphorus_mg"), ("sat_mg", "iron_mg"),
    ("kem_mg", "zinc_mg"), ("natri_mg", "sodium_mg"), ("kali_mg", "potassium_mg"),
    ("magie_mg", "magnesium_mg"), ("retinol_mcg", "retinol_mcg"),
    ("beta_caroten_mcg", "beta_carotene_mcg"), ("vitamin_a_mcg", "vitamin_a_mcg"),
    ("vitamin_c_mg", "vitamin_c_mg"), ("vitamin_b1_mg", "vitamin_b1_mg"),
    ("vitamin_b2_mg", "vitamin_b2_mg"), ("niacin_mg", "niacin_mg"), ("gi", "gi"),
]
TEXT_COLS = {"name", "unit", "gi"}
NAME_FIXES = {"Gạo tẽ": "Gạo tẻ"}   # lỗi chính tả trong dữ liệu gốc


def fix_name(s):
    import unicodedata
    s = unicodedata.normalize("NFC", s)
    for bad, good in NAME_FIXES.items():
        s = s.replace(bad, good)
    return s


def build_foods():
    lines = ["SET search_path TO nutri, public;", "BEGIN;"]
    with open(FOODS_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    cols = ", ".join(db for _, db in FOOD_COLS)
    for r in rows:
        vals = []
        for src, db in FOOD_COLS:
            v = (r.get(src) or "").strip()
            if db == "name":
                v = fix_name(v)
            if db in TEXT_COLS:
                vals.append(q(v) if v else ("'g'" if db == "unit" else "NULL"))
            else:
                vals.append(v if v else "NULL")
        lines.append(f"INSERT INTO foods ({cols}) VALUES ({', '.join(vals)});")
    lines.append("COMMIT;")
    (HERE / "02_seed_foods.sql").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"foods: {len(rows)} rows")


# ---------------------------------------------------------------- regimes
NUM = r"(\d+(?:[.,]\d+)?)"


def num(s):
    return float(s.replace(",", "."))


def parse_range(raw, single_is_max=False):
    """'1800-1900' -> (1800,1900); '<33' -> (None,33); '40-<55' -> (40,55);
    '620' -> (620,620) hoặc (None,620) nếu single_is_max."""
    if raw is None:
        return None, None
    s = str(raw).strip().replace(" ", "").replace("≤", "<=").replace("≥", ">=")
    if not s:
        return None, None
    m = re.fullmatch(NUM + r"-(?:<=?)?" + NUM, s)
    if m:
        return num(m.group(1)), num(m.group(2))
    m = re.fullmatch(r"(<=?|>=?)" + NUM, s)
    if m:
        return (None, num(m.group(2))) if m.group(1).startswith("<") else (num(m.group(2)), None)
    m = re.fullmatch(NUM, s)
    if m:
        v = num(m.group(1))
        return (None, v) if single_is_max else (v, v)
    raise ValueError(f"Không parse được giá trị: {raw!r}")


def parse_notes(note):
    out = {}
    if not note:
        return out
    m = re.search(NUM + r"(?:-" + NUM + r")?\s*Kcal/kg", note)
    if m:
        out["energy_kcal_per_kg_min"] = num(m.group(1))
        out["energy_kcal_per_kg_max"] = num(m.group(2) or m.group(1))
    m = re.search(r"Protid\s*(<=?)?\s*" + NUM + r"(?:-<?" + NUM + r")?\s*g/kg", note)
    if m:
        lo, hi = num(m.group(2)), num(m.group(3)) if m.group(3) else None
        if m.group(1):          # "<0.6"
            out["protein_g_per_kg_max"] = lo
        else:
            out["protein_g_per_kg_min"] = lo
            out["protein_g_per_kg_max"] = hi if hi else lo
    m = re.search(r"ĐV\s*(?:>=?|≥)?\s*" + NUM + r"\s*%", note)
    if m:
        out["animal_protein_min_pct"] = num(m.group(1))
    m = re.search(r"Phosphat\s*(?:<=?)?\s*" + NUM + r"(?:-" + NUM + r")?\s*mg", note)
    if m:
        out["phosphate_max_mg"] = num(m.group(2) or m.group(1))
    m = re.search(r"Cholesterol\s*<=?\s*" + NUM + r"\s*mg", note)
    if m:
        out["cholesterol_max_mg"] = num(m.group(1))
    m = re.search(r"[Cc]hất xơ:?\s*" + NUM + r"-" + NUM + r"\s*g", note)
    if m:
        out["fiber_min_g"], out["fiber_max_g"] = num(m.group(1)), num(m.group(2))
    if re.search(r"GI\s*thấp", note, re.I):
        out["require_low_gi"] = True
    return out


REGIME_COLS = [
    "code", "group_name", "name",
    "energy_min_kcal", "energy_max_kcal", "protein_min_g", "protein_max_g",
    "lipid_min_g", "lipid_max_g", "glucid_min_g", "glucid_max_g",
    "sodium_min_mg", "sodium_max_mg", "potassium_min_mg", "potassium_max_mg",
    "phosphate_max_mg", "cholesterol_max_mg", "fiber_min_g", "fiber_max_g",
    "water_min_l", "water_max_l", "meals_min", "meals_max",
    "energy_kcal_per_kg_min", "energy_kcal_per_kg_max",
    "protein_g_per_kg_min", "protein_g_per_kg_max", "animal_protein_min_pct",
    "require_low_gi", "notes", "raw_source",
]


def build_regimes():
    wb = openpyxl.load_workbook(REGIME_XLSX, data_only=True)
    lines = ["SET search_path TO nutri, public;", "BEGIN;"]
    count, errors = 0, []
    for ws in wb:
        if "treem" in ws.title.lower():
            continue  # Chỉ dùng phác đồ người lớn (MCDAnguoilon)
        header = [str(c).strip() if c else "" for c in next(ws.iter_rows(max_row=1, values_only=True))]
        idx = {h: i for i, h in enumerate(header) if h}
        pos = {k: i for i, k in enumerate(
            ["MaCDA", "NhomBenh", "TenCheDoAn", "EKcal", "Pg", "L (g)", "Gg",
             "Natrimg", "Kalimg", "NuocLit", "sobua", "ghichu"])}
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue
            get = lambda k: row[pos[k]] if pos[k] < len(row) else None
            code = str(get("MaCDA")).strip()
            name = str(get("TenCheDoAn") or "").strip()
            note = str(get("ghichu") or "").strip()
            try:
                d = {"code": code, "group_name": str(get("NhomBenh")).strip(), "name": name,
                     "notes": note or None}
                d["energy_min_kcal"], d["energy_max_kcal"] = parse_range(get("EKcal"))
                d["protein_min_g"], d["protein_max_g"] = parse_range(get("Pg"))
                d["lipid_min_g"], d["lipid_max_g"] = parse_range(get("L (g)"))
                d["glucid_min_g"], d["glucid_max_g"] = parse_range(get("Gg"))
                d["sodium_min_mg"], d["sodium_max_mg"] = parse_range(get("Natrimg"), single_is_max=True)
                d["potassium_min_mg"], d["potassium_max_mg"] = parse_range(get("Kalimg"), single_is_max=True)
                d["water_min_l"], d["water_max_l"] = parse_range(get("NuocLit"))
                mmin, mmax = parse_range(get("sobua"))
                d["meals_min"] = int(mmin) if mmin else None
                d["meals_max"] = int(mmax) if mmax else None
                d.update(parse_notes(note))
                if d["group_name"] == "Đái tháo đường":   # mọi phác đồ ĐTĐ đều ưu tiên GI thấp
                    d["require_low_gi"] = True
                d["raw_source"] = json.dumps(
                    {h: (str(row[i]) if row[i] is not None else None)
                     for h, i in idx.items() if i < len(row)}, ensure_ascii=False)
            except ValueError as e:
                errors.append(f"{code}: {e}")
                continue
            vals = []
            for c in REGIME_COLS:
                v = d.get(c)
                if c == "require_low_gi":
                    vals.append("TRUE" if v else "FALSE")
                elif c == "raw_source":
                    vals.append(q(v) + "::jsonb")
                else:
                    vals.append(q(v))
            lines.append(f"INSERT INTO diet_regimes ({', '.join(REGIME_COLS)}) VALUES ({', '.join(vals)});")
            count += 1
    lines.append("COMMIT;")
    (HERE / "03_seed_regimes.sql").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"regimes: {count} rows")
    for e in errors:
        print("  LỖI", e)


def strip_bom():
    for p in HERE.glob("*.sql"):
        b = p.read_bytes()
        if b.startswith(b"\xef\xbb\xbf"):
            p.write_bytes(b[3:])


if __name__ == "__main__":
    build_foods()
    build_regimes()
    strip_bom()
