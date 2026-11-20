"""Đọc ảnh/PDF phiếu khám hoặc kết quả xét nghiệm bằng Gemini Vision + Structured Output."""
import io
import json
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from google.genai import types
from PIL import Image
from pydantic import BaseModel, Field

from src.db import get_conn
from src.guardrails.pii_masker import mask_pii_dict
from src.llm import generate_structured
from src.tools.regime_tool import match_and_compute_target


class ExtractedLabItem(BaseModel):
    biomarker_name: str = Field(description="Tên chỉ số trên phiếu (VD: eGFR, Creatinin, HbA1c, K+, Glucose)")
    value: float = Field(description="Giá trị số đo được")
    unit: str = Field(default="", description="Đơn vị trên phiếu (VD: mmol/L, %, umol/L)")


class ExtractedMedicalRecord(BaseModel):
    gender: Optional[str] = Field(None, description="Nam hoặc Nữ")
    age: Optional[int] = Field(None, description="Tuổi bệnh nhân")
    weight_kg: Optional[float] = Field(None, description="Cân nặng (kg) nếu có ghi")
    height_cm: Optional[float] = Field(None, description="Chiều cao (cm) nếu có ghi")
    systolic_bp: Optional[int] = Field(None, description="Huyết áp tâm thu (số trên)")
    diastolic_bp: Optional[int] = Field(None, description="Huyết áp tâm trương (số dưới)")
    checkup_date: Optional[str] = Field(None, description="Ngày khám định dạng YYYY-MM-DD")
    diagnosed_diseases: List[str] = Field(default=[], description="Chẩn đoán bệnh lý (VD: Đái tháo đường, Suy thận mạn)")
    allergies: List[str] = Field(default=[], description="Tiền sử dị ứng thuốc/thức ăn nếu có")
    lab_results: List[ExtractedLabItem] = Field(default=[], description="Các chỉ số xét nghiệm sinh hóa đọc được")


def _compress_image_if_needed(file_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
    """Thu gọn ảnh chụp dung lượng lớn (tối đa 1600px) để Gemini Vision đọc nhanh, không timeout."""
    if not mime_type.startswith("image/"):
        return file_bytes, mime_type
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.thumbnail((1600, 1600))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue(), "image/jpeg"
    except Exception:
        return file_bytes, mime_type


def extract_medical_record_multi(files: List[Tuple[bytes, str]]) -> ExtractedMedicalRecord:
    """Gọi Gemini Vision đọc cùng lúc 1 hoặc nhiều ảnh/PDF phiếu khám (VD: 2 mặt/2 tờ) và gộp vào 1 JSON chuẩn (đã bỏ PII)."""
    if not files:
        raise ValueError("Chưa có tệp ảnh/PDF nào để phân tích.")
    prompt = (
        "Bạn là chuyên gia trích xuất dữ liệu bệnh án tiếng Việt. "
        "Hãy đọc TẤT CẢ các ảnh/tài liệu phiếu khám hoặc kết quả xét nghiệm kèm theo (có thể gồm nhiều trang hoặc nhiều tờ chụp khác nhau trong cùng một đợt khám) "
        "và tổng hợp đầy đủ thành một hồ sơ thống nhất: "
        "giới tính, tuổi, cân nặng, chiều cao, huyết áp, ngày khám, chẩn đoán bệnh, "
        "tiền sử dị ứng và toàn bộ các chỉ số xét nghiệm trên mọi trang (eGFR, Creatinin, Ure, Glucose, HbA1c, Kali K+, Natri Na+, Phospho...). "
        "TUYỆT ĐỐI KHÔNG trích xuất họ tên thật, số CCCD, số điện thoại hay địa chỉ. "
        "Trả về đúng JSON schema."
    )
    parts = []
    for raw_bytes, mime_type in files:
        opt_bytes, opt_mime = _compress_image_if_needed(raw_bytes, mime_type)
        parts.append(types.Part.from_bytes(data=opt_bytes, mime_type=opt_mime))
    parsed, _ = generate_structured([*parts, prompt], ExtractedMedicalRecord, fast=True)
    return parsed


def extract_medical_record(file_bytes: bytes, mime_type: str = "image/jpeg") -> ExtractedMedicalRecord:
    """Gọi Gemini Vision đọc 1 ảnh/PDF phiếu khám và trả về JSON có cấu trúc (đã bỏ PII)."""
    return extract_medical_record_multi([(file_bytes, mime_type)])


class DuplicateCheckupError(ValueError):
    """Ném ra khi người dùng tải lên lại phiếu xét nghiệm đã tồn tại cho bệnh nhân."""


def _format_vn_date(iso_date: str) -> str:
    parts = str(iso_date).split("-")
    if len(parts) == 3:
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return str(iso_date)


def find_duplicate_document(patient_id: str, file_sha256: str) -> Optional[Dict[str, Any]]:
    """Kiểm tra file (theo SHA-256) đã từng được dùng để tạo đợt khám cho bệnh nhân này chưa."""
    if not file_sha256:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT md.id AS doc_id, c.id AS checkup_id, c.checkup_date
            FROM medical_documents md
            JOIN checkups c ON c.document_id = md.id
            WHERE md.patient_id = %s AND md.file_sha256 = %s
            ORDER BY c.id DESC
            LIMIT 1;
            """,
            (patient_id, file_sha256),
        ).fetchone()
    return dict(row) if row else None


def save_extracted_checkup(
    patient_id: str,
    record: ExtractedMedicalRecord,
    file_path: str = "uploaded_in_memory",
    mime_type: str = "image/jpeg",
    checkup_date_override: Optional[str] = None,
    file_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    """Lưu hoặc gộp đợt khám + chỉ số xét nghiệm vào PostgreSQL (chống trùng theo ngày & giá trị)."""
    safe_json = mask_pii_dict(record.model_dump())
    check_date = checkup_date_override or record.checkup_date or date.today().isoformat()

    with get_conn() as conn:
        biomarkers = conn.execute("SELECT id, code, name, aliases FROM biomarkers;").fetchall()
        matched_entries = []
        matched_labs = []
        egfr_val: Optional[float] = None
        for item in record.lab_results:
            q_name = item.biomarker_name.strip().lower()
            bm_id = None
            bm_code = None
            for bm in biomarkers:
                candidates = [bm["code"].lower(), bm["name"].lower()] + [a.lower() for a in (bm["aliases"] or [])]
                if any(c == q_name or c in q_name or q_name in c for c in candidates):
                    bm_id = bm["id"]
                    bm_code = bm["code"]
                    break
            if bm_id:
                if bm_code == "EGFR":
                    egfr_val = item.value
                matched_entries.append((bm_id, bm_code, item))
                matched_labs.append(item.biomarker_name)

        existing = conn.execute(
            """
            SELECT id, weight_kg, systolic_bp, diastolic_bp
            FROM checkups
            WHERE patient_id = %s AND checkup_date = %s::date AND source = 'UPLOAD'
            ORDER BY id DESC
            LIMIT 1;
            """,
            (patient_id, check_date),
        ).fetchone()

        merged = False
        if existing:
            existing_cid = existing["id"]
            existing_labs_rows = conn.execute(
                "SELECT biomarker_id, value FROM lab_results WHERE checkup_id = %s;",
                (existing_cid,),
            ).fetchall()
            existing_labs = {r["biomarker_id"]: float(r["value"]) for r in existing_labs_rows}

            has_new_or_changed_lab = any(
                bm_id not in existing_labs or abs(float(item.value) - existing_labs[bm_id]) > 1e-3
                for bm_id, _, item in matched_entries
            )
            has_new_vitals = (
                (record.weight_kg is not None and existing["weight_kg"] is None)
                or (record.systolic_bp is not None and existing["systolic_bp"] is None)
                or (record.diastolic_bp is not None and existing["diastolic_bp"] is None)
            )
            if not has_new_or_changed_lab and not has_new_vitals:
                raise DuplicateCheckupError(
                    f"Đợt khám ngày {_format_vn_date(check_date)} đã có sẵn đầy đủ các chỉ số giống hệt phiếu này "
                    f"(đợt #{existing_cid}). Hệ thống giữ nguyên bản cũ để tránh trùng trên biểu đồ."
                )

            doc_row = conn.execute(
                """
                INSERT INTO medical_documents (patient_id, file_path, mime_type, file_sha256, status, extracted_json, model_name, confirmed_at)
                VALUES (%s, %s, %s, %s, 'CONFIRMED'::doc_status, %s::jsonb, 'gemini-vision', now())
                RETURNING id;
                """,
                (patient_id, file_path, mime_type, file_sha256, json.dumps(safe_json, ensure_ascii=False)),
            ).fetchone()

            conn.execute(
                """
                UPDATE checkups
                SET document_id = %s,
                    weight_kg = COALESCE(%s, weight_kg),
                    systolic_bp = COALESCE(%s, systolic_bp),
                    diastolic_bp = COALESCE(%s, diastolic_bp)
                WHERE id = %s;
                """,
                (doc_row["id"], record.weight_kg, record.systolic_bp, record.diastolic_bp, existing_cid),
            )
            checkup_id = existing_cid
            merged = True
        else:
            doc_row = conn.execute(
                """
                INSERT INTO medical_documents (patient_id, file_path, mime_type, file_sha256, status, extracted_json, model_name, confirmed_at)
                VALUES (%s, %s, %s, %s, 'CONFIRMED'::doc_status, %s::jsonb, 'gemini-vision', now())
                RETURNING id;
                """,
                (patient_id, file_path, mime_type, file_sha256, json.dumps(safe_json, ensure_ascii=False)),
            ).fetchone()

            checkup_row = conn.execute(
                """
                INSERT INTO checkups (patient_id, document_id, checkup_date, weight_kg, systolic_bp, diastolic_bp, source)
                VALUES (%s, %s, %s::date, %s, %s, %s, 'UPLOAD')
                RETURNING id;
                """,
                (patient_id, doc_row["id"], check_date, record.weight_kg, record.systolic_bp, record.diastolic_bp),
            ).fetchone()
            checkup_id = checkup_row["id"]

        for bm_id, _, item in matched_entries:
            conn.execute(
                """
                INSERT INTO lab_results (checkup_id, biomarker_id, value, raw_value_text, raw_unit)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (checkup_id, biomarker_id) DO UPDATE
                SET value = EXCLUDED.value,
                    raw_value_text = EXCLUDED.raw_value_text,
                    raw_unit = EXCLUDED.raw_unit;
                """,
                (checkup_id, bm_id, item.value, str(item.value), item.unit),
            )

        # Tự động thêm/cập nhật bệnh lý & giai đoạn CKD theo chẩn đoán hoặc eGFR
        disease_keywords = {
            "DTD": ["đái tháo đường", "tiểu đường", "dtd", "diabetes"],
            "CKD": ["suy thận mạn", "bệnh thận mạn", "ckd", "suy thận"],
            "AKI": ["suy thận cấp", "aki"],
            "GN_ACUTE": ["viêm cầu thận cấp"],
            "GN_CHRONIC": ["viêm cầu thận mạn"],
            "NEPHROTIC": ["hội chứng thận hư"],
            "HTN": ["tăng huyết áp", "cao huyết áp"],
            "DYSLIPIDEMIA": ["rối loạn mỡ máu", "rối loạn lipid"],
        }
        detected_codes = set()
        for diag in record.diagnosed_diseases:
            d_low = diag.lower()
            for code, kws in disease_keywords.items():
                if any(kw in d_low for kw in kws):
                    detected_codes.add(code)
        if egfr_val is not None and egfr_val < 90 and "AKI" not in detected_codes:
            detected_codes.add("CKD")

        for code in detected_codes:
            cond = conn.execute("SELECT id FROM conditions WHERE code = %s AND is_enabled = TRUE;", (code,)).fetchone()
            if not cond:
                continue
            stage_id = None
            if code == "CKD" and egfr_val is not None:
                st_row = conn.execute(
                    """
                    SELECT id FROM condition_stages
                    WHERE condition_id = %s
                      AND (value_min IS NULL OR %s >= value_min)
                      AND (value_max IS NULL OR %s < value_max)
                    LIMIT 1;
                    """,
                    (cond["id"], egfr_val, egfr_val),
                ).fetchone()
                stage_id = st_row["id"] if st_row else None
            conn.execute(
                """
                INSERT INTO patient_conditions (patient_id, condition_id, stage_id, diagnosed_at, source_checkup_id)
                VALUES (%s, %s, %s, %s::date, %s)
                ON CONFLICT (patient_id, condition_id) WHERE resolved_at IS NULL
                DO UPDATE SET stage_id = COALESCE(EXCLUDED.stage_id, patient_conditions.stage_id),
                              source_checkup_id = EXCLUDED.source_checkup_id;
                """,
                (patient_id, cond["id"], stage_id, check_date, checkup_id),
            )

        if record.allergies:
            conn.execute(
                """
                UPDATE patients
                SET food_allergies = (SELECT ARRAY(SELECT DISTINCT unnest(food_allergies || %s::text[])))
                WHERE id = %s;
                """,
                (record.allergies, patient_id),
            )

    new_target = match_and_compute_target(patient_id, save_to_db=True)
    return {"checkup_id": checkup_id, "merged": merged, "matched_labs": matched_labs, "new_target": new_target}
