"""FastAPI Backend cho NutriGuard AI – phục vụ giao diện React SPA hiện đại
và nối trực tiếp vào LangGraph Agent, RAG pgvector, Guardrails, Vision OCR & Evals."""
import hashlib
import threading
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from evals.test_safety import run_evals
from src.agent.graph import run_agent
from src.auth import (
    authenticate_user,
    create_access_token,
    ensure_auth_schema_and_seed,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
    verify_patient_access,
)
from src.db import get_conn
from src.guardrails.clinical_validator import classify_food_with_rules
from src.llm import warmup_gemini_client
from src.logging_setup import get_logger, read_recent_logs, request_id_var
from src.observability import compute_agent_metrics, has_langfuse_config
from src.rag.ingest import (
    delete_knowledge_document,
    ingest_pdf_bytes,
    ingest_text,
    list_knowledge_documents,
    search_knowledge,
)
from src.tools.food_tool import _strip_accents, expand_allergens
from src.tools.regime_tool import get_patient_context, match_and_compute_target
from src.vision.food_scanner import analyze_any_dish
from src.vision.lab_extractor import (
    DuplicateCheckupError,
    extract_medical_record,
    extract_medical_record_multi,
    find_duplicate_document,
    save_extracted_checkup,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

app = FastAPI(title="NutriGuard AI API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
http_log = get_logger("http")


@app.on_event("startup")
def _warmup_on_startup():
    threading.Thread(target=warmup_gemini_client, daemon=True).start()


@app.middleware("http")
async def structured_http_logging_middleware(request: Request, call_next):
    req_id = uuid.uuid4().hex[:12]
    tok = request_id_var.set(req_id)
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
        if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/observability"):
            lat = int((time.perf_counter() - t0) * 1000)
            http_log.info(
                "http_request",
                extra={"method": request.method, "path": request.url.path, "status": response.status_code, "latency_ms": lat},
            )
        return response
    finally:
        request_id_var.reset(tok)


def _to_json_safe(obj: Any) -> Any:
    """Chuyển Decimal / date / datetime về kiểu JSON chuẩn."""
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json_safe(v) for v in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if type(obj).__name__ == "Decimal":
        return float(obj)
    return obj


# ----------------- SCHEMAS -----------------

class LoginPayload(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class ChangePasswordPayload(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=4)


class PatientAccountPayload(BaseModel):
    username: str = Field(..., min_length=2)
    password: Optional[str] = None
    display_name: Optional[str] = None
    is_active: bool = True


class AdminUserCreatePayload(BaseModel):
    username: str = Field(..., min_length=2)
    password: str = Field(..., min_length=4)
    display_name: str = Field(..., min_length=1)
    email: Optional[str] = None
    role: str = "PATIENT"
    patient_id: Optional[str] = None


class AdminUserUpdatePayload(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    patient_id: Optional[str] = None


class FoodAdminPayload(BaseModel):
    name: str = Field(..., min_length=1)
    unit: str = "g"
    energy_kcal: Optional[float] = 0.0
    protein_g: Optional[float] = 0.0
    lipid_g: Optional[float] = 0.0
    glucid_g: Optional[float] = 0.0
    fiber_g: Optional[float] = 0.0
    sodium_mg: Optional[float] = 0.0
    potassium_mg: Optional[float] = 0.0
    phosphorus_mg: Optional[float] = 0.0
    gi: Optional[str] = None


class PatientCreatePayload(BaseModel):
    nickname: str = Field(..., min_length=1)
    gender: str = "Nam"
    birth_year: int = 1968
    height_cm: float = 168.0
    weight_kg: float = 65.0
    diseases: List[str] = Field(default_factory=list)   # ["DTD", "CKD", "HTN", "DYSLIPIDEMIA"]
    ckd_stage: Optional[str] = None
    food_allergies: List[str] = Field(default_factory=list)
    activity_level: str = "Ít vận động"
    account_username: Optional[str] = None
    account_password: Optional[str] = None


class PatientUpdatePayload(BaseModel):
    nickname: Optional[str] = None
    gender: Optional[str] = None
    birth_year: Optional[int] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    diseases: Optional[List[str]] = None
    ckd_stage: Optional[str] = None
    dialysis_per_week: Optional[int] = None
    food_allergies: Optional[List[str]] = None


class ChatPayload(BaseModel):
    query: str = Field(..., min_length=1)


class MealPlanPayload(BaseModel):
    num_days: int = Field(default=1, ge=1, le=7)
    meals_per_day: Optional[int] = Field(default=None, ge=3, le=6)
    user_preferences: str = ""


class EvalRunPayload(BaseModel):
    include_e2e: bool = False


@app.on_event("startup")
def _startup_init_auth():
    ensure_auth_schema_and_seed()


# ----------------- AUTHENTICATION -----------------

@app.post("/api/auth/login")
def login(payload: LoginPayload):
    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu.")
    token = create_access_token(user)
    return _to_json_safe({"token": token, "user": user})


@app.get("/api/auth/me")
def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    return _to_json_safe({"user": current_user})


@app.post("/api/auth/change-password")
def change_password(
    payload: ChangePasswordPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT password_hash FROM app_users WHERE id = %s;",
            (current_user["id"],),
        ).fetchone()
        if not row or not verify_password(payload.old_password, row["password_hash"]):
            raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng.")
        conn.execute(
            "UPDATE app_users SET password_hash = %s WHERE id = %s;",
            (hash_password(payload.new_password), current_user["id"]),
        )
    return {"ok": True, "message": "Đã đổi mật khẩu thành công."}


# ----------------- HEALTH & PATIENTS -----------------

@app.get("/api/health")
def health_check():
    with get_conn() as conn:
        foods_cnt = conn.execute("SELECT count(*) AS c FROM foods;").fetchone()["c"]
        rag_cnt = conn.execute("SELECT count(*) AS c FROM knowledge_chunks;").fetchone()["c"]
    return {
        "status": "ok",
        "foods_count": foods_cnt,
        "rag_chunks": rag_cnt,
        "langfuse_enabled": has_langfuse_config(),
    }


@app.get("/api/patients")
def get_patients(current_user: Dict[str, Any] = Depends(get_current_user)):
    with get_conn() as conn:
        if current_user["role"] == "ADMIN":
            rows = conn.execute(
                """
                SELECT p.id::text AS id, p.nickname, p.gender,
                       EXTRACT(YEAR FROM now())::int - p.birth_year AS age,
                       p.height_cm, p.food_allergies, p.created_at
                FROM patients p
                ORDER BY p.created_at ASC;
                """
            ).fetchall()
        elif current_user.get("patient_id"):
            rows = conn.execute(
                """
                SELECT p.id::text AS id, p.nickname, p.gender,
                       EXTRACT(YEAR FROM now())::int - p.birth_year AS age,
                       p.height_cm, p.food_allergies, p.created_at
                FROM patients p
                WHERE p.id = %s;
                """,
                (current_user["patient_id"],),
            ).fetchall()
        else:
            rows = []
    return _to_json_safe(rows)


@app.post("/api/patients")
def create_patient(
    payload: PatientCreatePayload,
    _admin: Dict[str, Any] = Depends(require_admin),
):
    acc_user = (payload.account_username or "").strip().lower()
    acc_pass = (payload.account_password or "").strip()
    if acc_user and len(acc_pass) < 4:
        raise HTTPException(status_code=400, detail="Mật khẩu tài khoản bệnh nhân cần ít nhất 4 ký tự.")

    with get_conn() as conn:
        if acc_user:
            dup_u = conn.execute(
                "SELECT 1 FROM app_users WHERE lower(COALESCE(username, '')) = %s OR lower(email) = %s;",
                (acc_user, f"{acc_user}@patient.nutriguard.ai"),
            ).fetchone()
            if dup_u:
                raise HTTPException(status_code=409, detail=f"Tên đăng nhập '{acc_user}' đã tồn tại.")

        u = conn.execute(
            "INSERT INTO app_users (email, display_name) VALUES ('default@nutriguard.ai', 'Default') "
            "ON CONFLICT (email) DO UPDATE SET display_name = EXCLUDED.display_name RETURNING id;"
        ).fetchone()
        p = conn.execute(
            """
            INSERT INTO patients (user_id, nickname, gender, birth_year, height_cm, activity_level, food_allergies)
            VALUES (%s, %s, %s::gender_type, %s, %s, %s::activity_type, %s::text[])
            RETURNING id::text AS id;
            """,
            (
                u["id"],
                payload.nickname.strip(),
                payload.gender,
                payload.birth_year,
                payload.height_cm,
                payload.activity_level,
                [a.strip() for a in payload.food_allergies if a.strip()],
            ),
        ).fetchone()
        pid = p["id"]
        conn.execute(
            "INSERT INTO checkups (patient_id, checkup_date, weight_kg, source) VALUES (%s, CURRENT_DATE, %s, 'MANUAL');",
            (pid, payload.weight_kg),
        )
        for d_code in payload.diseases:
            stage_id = None
            if d_code == "CKD" and payload.ckd_stage and payload.ckd_stage != "Không":
                s_row = conn.execute(
                    "SELECT cs.id FROM condition_stages cs JOIN conditions c ON c.id = cs.condition_id "
                    "WHERE c.code = 'CKD' AND cs.stage_code = %s;",
                    (payload.ckd_stage,),
                ).fetchone()
                stage_id = s_row["id"] if s_row else None
            conn.execute(
                "INSERT INTO patient_conditions (patient_id, condition_id, stage_id) "
                "SELECT %s, id, %s FROM conditions WHERE code = %s AND is_enabled = TRUE;",
                (pid, stage_id, d_code),
            )
        if acc_user:
            conn.execute(
                """
                INSERT INTO app_users (username, email, password_hash, display_name, role, patient_id, is_active)
                VALUES (%s, %s, %s, %s, 'PATIENT', %s, TRUE);
                """,
                (acc_user, f"{acc_user}@patient.nutriguard.ai", hash_password(acc_pass), payload.nickname.strip(), pid),
            )
    target = match_and_compute_target(pid, save_to_db=True)
    return _to_json_safe({"id": pid, "target": target})


@app.delete("/api/patients/{patient_id}")
def delete_patient(
    patient_id: str,
    _admin: Dict[str, Any] = Depends(require_admin),
):
    with get_conn() as conn:
        conn.execute("DELETE FROM app_users WHERE patient_id = %s AND role = 'PATIENT';", (patient_id,))
        row = conn.execute("DELETE FROM patients WHERE id = %s RETURNING id::text AS id;", (patient_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy bệnh nhân.")
    return {"deleted_id": row["id"]}


@app.put("/api/patients/{patient_id}")
def update_patient(
    patient_id: str,
    payload: PatientUpdatePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    verify_patient_access(patient_id, current_user)
    with get_conn() as conn:
        p = conn.execute("SELECT id FROM patients WHERE id = %s;", (patient_id,)).fetchone()
        if not p:
            raise HTTPException(status_code=404, detail="Không tìm thấy bệnh nhân")
        if payload.nickname is not None and payload.nickname.strip():
            clean_nick = payload.nickname.strip()
            conn.execute("UPDATE patients SET nickname = %s WHERE id = %s;", (clean_nick, patient_id))
            conn.execute("UPDATE app_users SET display_name = %s WHERE patient_id = %s AND role = 'PATIENT';", (clean_nick, patient_id))
        if payload.gender is not None and payload.gender.strip() in ("Nam", "Nữ"):
            conn.execute("UPDATE patients SET gender = %s::gender_type WHERE id = %s;", (payload.gender.strip(), patient_id))
        if payload.birth_year is not None and 1910 <= int(payload.birth_year) <= 2026:
            conn.execute("UPDATE patients SET birth_year = %s WHERE id = %s;", (int(payload.birth_year), patient_id))
        if payload.height_cm is not None:
            conn.execute("UPDATE patients SET height_cm = %s WHERE id = %s;", (payload.height_cm, patient_id))
        if payload.food_allergies is not None:
            clean_all = [a.strip() for a in payload.food_allergies if a.strip()]
            conn.execute("UPDATE patients SET food_allergies = %s::text[] WHERE id = %s;", (clean_all, patient_id))
        if payload.weight_kg is not None or payload.dialysis_per_week is not None:
            last_ck = conn.execute(
                "SELECT weight_kg, dialysis_per_week FROM checkups WHERE patient_id = %s ORDER BY checkup_date DESC, id DESC LIMIT 1;",
                (patient_id,),
            ).fetchone()
            w_val = payload.weight_kg if payload.weight_kg is not None else (last_ck["weight_kg"] if last_ck else None)
            d_val = (
                int(payload.dialysis_per_week)
                if payload.dialysis_per_week is not None
                else int((last_ck["dialysis_per_week"] if last_ck else 0) or 0)
            )
            conn.execute(
                "INSERT INTO checkups (patient_id, checkup_date, weight_kg, dialysis_per_week, source) VALUES (%s, CURRENT_DATE, %s, %s, 'MANUAL');",
                (patient_id, w_val, d_val),
            )
        if payload.diseases is not None:
            conn.execute("UPDATE patient_conditions SET resolved_at = CURRENT_DATE WHERE patient_id = %s AND resolved_at IS NULL;", (patient_id,))
            for d_code in payload.diseases:
                stage_id = None
                if d_code == "CKD" and payload.ckd_stage and payload.ckd_stage != "Không":
                    s_row = conn.execute(
                        "SELECT cs.id FROM condition_stages cs JOIN conditions c ON c.id = cs.condition_id "
                        "WHERE c.code = 'CKD' AND cs.stage_code = %s;",
                        (payload.ckd_stage,),
                    ).fetchone()
                    stage_id = s_row["id"] if s_row else None
                conn.execute(
                    "INSERT INTO patient_conditions (patient_id, condition_id, stage_id) "
                    "SELECT %s, id, %s FROM conditions WHERE code = %s AND is_enabled = TRUE;",
                    (patient_id, stage_id, d_code),
                )
    target = match_and_compute_target(patient_id, save_to_db=True)
    return _to_json_safe({"id": patient_id, "target": target})


@app.get("/api/patients/{patient_id}/overview")
def get_patient_overview(
    patient_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    verify_patient_access(patient_id, current_user)
    ctx = get_patient_context(patient_id)
    target = match_and_compute_target(patient_id, save_to_db=False)
    with get_conn() as conn:
        rules = conn.execute(
            """
            SELECT frr.id, frr.nutrient_column, frr.operator, frr.threshold_num,
                   frr.threshold_text, frr.action, frr.reason,
                   COALESCE(c.name, dr.name) AS source_name,
                   COALESCE(c.code, dr.code) AS source_code
            FROM food_restriction_rules frr
            LEFT JOIN conditions c ON c.id = frr.condition_id
            LEFT JOIN diet_regimes dr ON dr.id = frr.regime_id
            WHERE frr.condition_id IN (
                SELECT condition_id FROM patient_conditions
                WHERE patient_id = %s AND resolved_at IS NULL
            )
            OR frr.regime_id = (
                SELECT id FROM diet_regimes WHERE code = %s LIMIT 1
            )
            ORDER BY frr.action DESC, frr.id ASC;
            """,
            (patient_id, target.get("regime_code")),
        ).fetchall()

        all_conditions = conn.execute(
            "SELECT code, name, group_name, is_enabled FROM conditions ORDER BY id;"
        ).fetchall()
        recent_docs = conn.execute(
            "SELECT id, file_path, status, uploaded_at FROM medical_documents WHERE patient_id = %s ORDER BY id DESC LIMIT 3;",
            (patient_id,),
        ).fetchall()
        plans_cnt = conn.execute(
            "SELECT count(*) AS c FROM meal_plans WHERE patient_id = %s;", (patient_id,)
        ).fetchone()["c"]
        lab_items = conn.execute(
            """
            SELECT v.biomarker_code AS code, b.name, v.value, b.unit,
                   b.normal_min, b.normal_max, v.checkup_date
            FROM v_latest_lab_results v
            JOIN biomarkers b ON b.code = v.biomarker_code
            WHERE v.patient_id = %s
            ORDER BY b.id ASC;
            """,
            (patient_id,),
        ).fetchall()
        latest_plan_row = conn.execute(
            """
            SELECT mp.id, mp.period, mp.guardrail_passed, mp.model_name, mp.created_at,
                   COALESCE(SUM(f.energy_kcal * di.grams / 100.0), 0) AS energy_kcal,
                   COALESCE(SUM(f.protein_g * di.grams / 100.0), 0) AS protein_g,
                   COALESCE(SUM(f.lipid_g * di.grams / 100.0), 0) AS lipid_g,
                   COALESCE(SUM(f.glucid_g * di.grams / 100.0), 0) AS glucid_g,
                   COALESCE(SUM(f.fiber_g * di.grams / 100.0), 0) AS fiber_g,
                   COALESCE(SUM(f.sodium_mg * di.grams / 100.0), 0) AS sodium_mg,
                   COALESCE(SUM(f.potassium_mg * di.grams / 100.0), 0) AS potassium_mg,
                   COALESCE(SUM(f.phosphorus_mg * di.grams / 100.0), 0) AS phosphorus_mg
            FROM meal_plans mp
            JOIN meal_plan_days mpd ON mpd.meal_plan_id = mp.id AND mpd.day_index = 1
            JOIN meals m ON m.plan_day_id = mpd.id
            JOIN dishes d ON d.meal_id = m.id
            JOIN dish_ingredients di ON di.dish_id = d.id
            JOIN foods f ON f.id = di.food_id
            WHERE mp.patient_id = %s
            GROUP BY mp.id
            ORDER BY mp.id DESC
            LIMIT 1;
            """,
            (patient_id,),
        ).fetchone()

    active_rules = [r for r in rules if r["action"] == "BLOCK"]
    watch_rules = [r for r in rules if r["action"] != "BLOCK"]
    return _to_json_safe({
        "profile": ctx,
        "target": target,
        "clinical_matrix": {
            "blocking_rules": active_rules,
            "warning_rules": watch_rules,
            "allergies": ctx.get("food_allergies") or [],
        },
        "lab_items": lab_items,
        "latest_plan_summary": latest_plan_row,
        "available_conditions": all_conditions,
        "recent_documents": recent_docs,
        "meal_plans_count": plans_cnt,
    })


@app.get("/api/patients/{patient_id}/trends")
def get_patient_trends(
    patient_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    verify_patient_access(patient_id, current_user)
    with get_conn() as conn:
        checkups = conn.execute(
            """
            SELECT id, checkup_date, weight_kg, systolic_bp, diastolic_bp, source
            FROM checkups
            WHERE patient_id = %s
            ORDER BY checkup_date ASC, id ASC;
            """,
            (patient_id,),
        ).fetchall()
        labs = conn.execute(
            """
            SELECT c.checkup_date, b.code, b.name, lr.value, b.unit, b.normal_min, b.normal_max
            FROM lab_results lr
            JOIN checkups c ON c.id = lr.checkup_id
            JOIN biomarkers b ON b.id = lr.biomarker_id
            WHERE c.patient_id = %s
            ORDER BY c.checkup_date ASC, c.id ASC, b.code;
            """,
            (patient_id,),
        ).fetchall()

    series: Dict[str, Dict[str, Any]] = {}
    for row in labs:
        code = row["code"]
        if code not in series:
            series[code] = {
                "code": code,
                "name": row["name"],
                "unit": row["unit"],
                "normal_min": row["normal_min"],
                "normal_max": row["normal_max"],
                "points": [],
            }
        series[code]["points"].append({
            "date": row["checkup_date"],
            "value": row["value"],
        })
    return _to_json_safe({"checkups": checkups, "lab_series": list(series.values()), "labs_table": list(reversed(labs))})


@app.get("/api/patients/{patient_id}/meal-plans")
def list_meal_plans(
    patient_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    verify_patient_access(patient_id, current_user)
    with get_conn() as conn:
        plans = conn.execute(
            """
            SELECT mp.id, mp.period, mp.start_date, mp.end_date, mp.guardrail_passed, mp.model_name, mp.created_at,
                   dr.code AS regime_code, dr.name AS regime_name
            FROM meal_plans mp
            JOIN nutrition_targets nt ON nt.id = mp.target_id
            JOIN diet_regimes dr ON dr.id = nt.regime_id
            WHERE mp.patient_id = %s
            ORDER BY mp.id DESC
            LIMIT 15;
            """,
            (patient_id,),
        ).fetchall()

        detailed_plans = []
        for p in plans:
            days = conn.execute(
                "SELECT id, day_index, plan_date FROM meal_plan_days WHERE meal_plan_id = %s ORDER BY day_index;",
                (p["id"],),
            ).fetchall()
            day_items = []
            for d in days:
                meals = conn.execute(
                    "SELECT id, meal FROM meals WHERE plan_day_id = %s ORDER BY id;", (d["id"],)
                ).fetchall()
                meals_out = []
                totals = {"energy_kcal": 0.0, "protein_g": 0.0, "lipid_g": 0.0, "glucid_g": 0.0, "fiber_g": 0.0, "potassium_mg": 0.0, "sodium_mg": 0.0}
                for m in meals:
                    dishes = conn.execute(
                        "SELECT id, name, cooking_method FROM dishes WHERE meal_id = %s ORDER BY sort_order, id;",
                        (m["id"],),
                    ).fetchall()
                    dishes_out = []
                    for dish in dishes:
                        ings = conn.execute(
                            """
                            SELECT di.food_id, di.grams, f.name, f.energy_kcal, f.protein_g, f.lipid_g, f.glucid_g, f.fiber_g, f.potassium_mg, f.sodium_mg
                            FROM dish_ingredients di
                            JOIN foods f ON f.id = di.food_id
                            WHERE di.dish_id = %s;
                            """,
                            (dish["id"],),
                        ).fetchall()
                        for ing in ings:
                            ratio = float(ing["grams"]) / 100.0
                            for k in totals:
                                if ing[k] is not None:
                                    totals[k] += float(ing[k]) * ratio
                        dishes_out.append({
                            "name": dish["name"],
                            "cooking_method": dish["cooking_method"],
                            "ingredients": [
                                {"food_id": i["food_id"], "name": i["name"], "grams": float(i["grams"])}
                                for i in ings
                            ],
                        })
                    meals_out.append({"meal": m["meal"], "dishes": dishes_out})
                day_items.append({
                    "day_index": d["day_index"],
                    "plan_date": d["plan_date"],
                    "totals": {k: round(v, 1) for k, v in totals.items()},
                    "meals": meals_out,
                })
            detailed_plans.append({**p, "days": day_items})

    return _to_json_safe(detailed_plans)


@app.post("/api/patients/{patient_id}/meal-plans")
def create_meal_plan(
    patient_id: str,
    payload: MealPlanPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    verify_patient_access(patient_id, current_user)
    period_code = "DAY" if payload.num_days == 1 else "WEEK"
    out = run_agent(
        patient_id=patient_id,
        user_query=payload.user_preferences,
        forced_intent="MEAL_PLANNING",
        period=period_code,
        user_preferences=payload.user_preferences,
        num_days=payload.num_days,
        meals_per_day=payload.meals_per_day,
    )
    return _to_json_safe(out.get("draft_plan") or {})


@app.post("/api/patients/{patient_id}/chat")
def chat_with_agent(
    patient_id: str,
    payload: ChatPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    verify_patient_access(patient_id, current_user)
    out = run_agent(patient_id=patient_id, user_query=payload.query)
    return _to_json_safe({
        "final_response": out.get("final_response", ""),
        "intent": out.get("intent"),
        "pii_redacted": out.get("pii_redacted", False),
        "guardrail_passed": out.get("guardrail_passed", True),
        "guardrail_warnings": out.get("guardrail_warnings", []),
        "rag_context": out.get("rag_context", []),
        "retrieved_foods": out.get("retrieved_foods", []),
        "safe_alternatives": out.get("safe_alternatives", []),
        "model_used": out.get("model_used"),
        "trace_id": out.get("trace_id"),
        "draft_plan": out.get("draft_plan"),
    })


@app.post("/api/patients/{patient_id}/checkups/upload")
async def upload_checkup(
    patient_id: str,
    file: Optional[UploadFile] = File(default=None),
    files: Optional[List[UploadFile]] = File(default=None),
    checkup_date: Optional[str] = Form(default=None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    verify_patient_access(patient_id, current_user)
    upload_list: List[UploadFile] = []
    if files:
        upload_list.extend(f for f in files if f and f.filename)
    if file and file.filename:
        upload_list.append(file)
    if not upload_list:
        raise HTTPException(status_code=400, detail="Vui lòng chọn ít nhất 1 ảnh hoặc tệp PDF phiếu khám.")

    file_items = []
    hashes = []
    for uf in upload_list:
        raw = await uf.read()
        if not raw:
            continue
        mime = uf.content_type or "image/jpeg"
        file_items.append((raw, mime, uf.filename or "uploaded_lab"))
        hashes.append(hashlib.sha256(raw).hexdigest())

    if not file_items:
        raise HTTPException(status_code=400, detail="Tệp tải lên rỗng.")

    file_sha256 = (
        hashes[0]
        if len(hashes) == 1
        else hashlib.sha256("|".join(sorted(hashes)).encode("utf-8")).hexdigest()
    )

    dup = find_duplicate_document(patient_id, file_sha256)
    if dup:
        cdate = dup["checkup_date"].strftime("%d/%m/%Y") if hasattr(dup["checkup_date"], "strftime") else str(dup["checkup_date"])
        raise HTTPException(
            status_code=409,
            detail=f"Phiếu xét nghiệm này đã được tải lên trước đó (đợt khám #{dup['checkup_id']} ngày {cdate}). Không cần tải lại.",
        )

    try:
        rec = extract_medical_record_multi([(raw, mime) for raw, mime, _ in file_items])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI đọc phiếu thất bại: {exc}")
    combined_names = ", ".join(name for _, _, name in file_items)
    primary_mime = file_items[0][1]
    try:
        res = save_extracted_checkup(
            patient_id,
            rec,
            file_path=combined_names[:500],
            mime_type=primary_mime,
            checkup_date_override=(checkup_date.strip() if checkup_date and checkup_date.strip() else None),
            file_sha256=file_sha256,
        )
    except DuplicateCheckupError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi lưu đợt khám vào CSDL: {exc}")
    return _to_json_safe({"extracted": rec.model_dump(), "files_count": len(file_items), **res})


@app.delete("/api/patients/{patient_id}/checkups/{checkup_id}")
def delete_checkup(
    patient_id: str,
    checkup_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    verify_patient_access(patient_id, current_user)
    with get_conn() as conn:
        row = conn.execute(
            "DELETE FROM checkups WHERE id = %s AND patient_id = %s RETURNING id, document_id;",
            (checkup_id, patient_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy đợt khám cần xóa.")
        if row["document_id"]:
            conn.execute("DELETE FROM medical_documents WHERE id = %s;", (row["document_id"],))
    new_target = match_and_compute_target(patient_id, save_to_db=True)
    return _to_json_safe({"deleted_id": checkup_id, "new_target": new_target})


# ----------------- FOODS DB EXPLORER -----------------

@app.get("/api/foods")
def list_foods(
    q: str = "",
    patient_id: Optional[str] = None,
    low_gi: bool = False,
    low_potassium: bool = False,
    low_sodium: bool = False,
    limit: int = 60,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    effective_pid = patient_id
    if current_user["role"] == "PATIENT":
        if patient_id:
            verify_patient_access(patient_id, current_user)
        effective_pid = current_user.get("patient_id")
    patient_id = effective_pid

    with get_conn() as conn:
        clauses = ["energy_kcal IS NOT NULL"]
        params: List[Any] = []
        if q.strip():
            clauses.append("(f_unaccent(lower(name)) ILIKE '%%' || f_unaccent(lower(%s)) || '%%' OR f_unaccent(lower(name)) %% f_unaccent(lower(%s)))")
            params.extend([q.strip(), q.strip()])
        if low_gi:
            clauses.append("gi = 'Thấp'")
        if low_potassium:
            clauses.append("(potassium_mg IS NOT NULL AND potassium_mg <= 200)")
        if low_sodium:
            clauses.append("(sodium_mg IS NOT NULL AND sodium_mg <= 200)")

        where_sql = " AND ".join(clauses)
        order_sql = (
            "similarity(f_unaccent(lower(name)), f_unaccent(lower(%s))) DESC, length(name) ASC"
            if q.strip()
            else "id ASC"
        )
        if q.strip():
            params.append(q.strip())
        params.append(min(limit, 150))

        rows = conn.execute(
            f"""
            SELECT id, name, unit, water_g, energy_kcal, protein_g, lipid_g, glucid_g, fiber_g,
                   sodium_mg, potassium_mg, phosphorus_mg, calcium_mg, iron_mg, zinc_mg,
                   magnesium_mg, vitamin_c_mg, gi
            FROM foods
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT %s;
            """,
            tuple(params),
        ).fetchall()

        allergen_kws: List[str] = []
        rules: List[Dict[str, Any]] = []
        if patient_id:
            p = conn.execute("SELECT food_allergies FROM patients WHERE id = %s;", (patient_id,)).fetchone()
            allergen_kws = expand_allergens(p["food_allergies"] if p else [])
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

    out = []
    dict_rules = [dict(r) for r in rules]
    for f in rows:
        item = dict(f)
        if patient_id:
            ev = classify_food_with_rules(item, dict_rules, allergen_kws)
            item["safety_action"] = ev["tier"]
            item["safety_reasons"] = ev["reasons"]
        else:
            item["safety_action"] = "PASS"
            item["safety_reasons"] = []
        out.append(item)
    return _to_json_safe(out)


@app.post("/api/foods/analyze")
async def analyze_dish_endpoint(
    dish_query: str = Form(default=""),
    patient_id: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    effective_pid = patient_id.strip() if patient_id and patient_id.strip() else None
    if current_user["role"] == "PATIENT":
        if effective_pid:
            verify_patient_access(effective_pid, current_user)
        effective_pid = current_user.get("patient_id")

    raw_bytes: Optional[bytes] = None
    mime_type = "image/jpeg"
    if file and file.filename:
        raw_bytes = await file.read()
        mime_type = file.content_type or "image/jpeg"

    if not raw_bytes and not dish_query.strip():
        raise HTTPException(status_code=400, detail="Vui lòng tải ảnh món ăn hoặc nhập tên món cần phân tích.")

    try:
        res = analyze_any_dish(
            dish_query=dish_query.strip(),
            file_bytes=raw_bytes,
            mime_type=mime_type,
            patient_id=effective_pid,
        )
        return _to_json_safe(res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích món ăn: {e}")


# ----------------- ADMIN MANAGEMENT (PATIENTS & ACCOUNTS) -----------------

@app.get("/api/admin/patients")
def admin_list_patients(_admin: Dict[str, Any] = Depends(require_admin)):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT p.id::text AS id, p.nickname, p.gender,
                   EXTRACT(YEAR FROM now())::int - p.birth_year AS age,
                   p.birth_year, p.height_cm, p.food_allergies, p.created_at,
                   lc.weight_kg, lc.checkup_date AS last_checkup,
                   ROUND(lc.weight_kg / NULLIF((p.height_cm/100)^2, 0), 1) AS bmi,
                   dr.code AS regime_code,
                   nt.energy_kcal, nt.protein_g,
                   (SELECT COALESCE(array_agg(cd.code || COALESCE(' ' || cs.stage_code, '')), '{}')
                      FROM patient_conditions pc
                      JOIN conditions cd ON cd.id = pc.condition_id
                      LEFT JOIN condition_stages cs ON cs.id = pc.stage_id
                     WHERE pc.patient_id = p.id AND pc.resolved_at IS NULL) AS active_conditions,
                   (SELECT count(*) FROM meal_plans mp WHERE mp.patient_id = p.id) AS meal_plans_count,
                   (SELECT count(*) FROM checkups c WHERE c.patient_id = p.id) AS checkups_count,
                   u.id::text AS account_user_id,
                   u.username AS account_username,
                   u.is_active AS account_active
            FROM patients p
            LEFT JOIN LATERAL (
                SELECT weight_kg, checkup_date FROM checkups
                WHERE patient_id = p.id AND weight_kg IS NOT NULL
                ORDER BY checkup_date DESC, id DESC LIMIT 1
            ) lc ON TRUE
            LEFT JOIN nutrition_targets nt ON nt.patient_id = p.id AND nt.is_current = TRUE
            LEFT JOIN diet_regimes dr ON dr.id = nt.regime_id
            LEFT JOIN LATERAL (
                SELECT id, username, is_active FROM app_users
                WHERE patient_id = p.id AND role = 'PATIENT'
                ORDER BY created_at ASC LIMIT 1
            ) u ON TRUE
            ORDER BY p.created_at ASC;
            """
        ).fetchall()
    return _to_json_safe(rows)


@app.post("/api/admin/patients/{patient_id}/account")
def admin_upsert_patient_account(
    patient_id: str,
    payload: PatientAccountPayload,
    _admin: Dict[str, Any] = Depends(require_admin),
):
    uname = payload.username.strip().lower()
    with get_conn() as conn:
        p = conn.execute("SELECT id, nickname FROM patients WHERE id = %s;", (patient_id,)).fetchone()
        if not p:
            raise HTTPException(status_code=404, detail="Không tìm thấy bệnh nhân.")

        existing = conn.execute(
            "SELECT id::text AS id FROM app_users WHERE patient_id = %s AND role = 'PATIENT' LIMIT 1;",
            (patient_id,),
        ).fetchone()

        conflict = conn.execute(
            "SELECT id::text AS id FROM app_users WHERE lower(COALESCE(username, '')) = %s;",
            (uname,),
        ).fetchone()
        if conflict and (not existing or conflict["id"] != existing["id"]):
            raise HTTPException(status_code=409, detail=f"Tên đăng nhập '{uname}' đã có người sử dụng.")

        disp = (payload.display_name or p["nickname"]).strip()
        if existing:
            if payload.password and payload.password.strip():
                if len(payload.password.strip()) < 4:
                    raise HTTPException(status_code=400, detail="Mật khẩu tối thiểu 4 ký tự.")
                conn.execute(
                    """
                    UPDATE app_users
                    SET username = %s, email = %s, display_name = %s, is_active = %s, password_hash = %s
                    WHERE id = %s;
                    """,
                    (uname, f"{uname}@patient.nutriguard.ai", disp, payload.is_active, hash_password(payload.password.strip()), existing["id"]),
                )
            else:
                conn.execute(
                    """
                    UPDATE app_users
                    SET username = %s, email = %s, display_name = %s, is_active = %s
                    WHERE id = %s;
                    """,
                    (uname, f"{uname}@patient.nutriguard.ai", disp, payload.is_active, existing["id"]),
                )
            return {"ok": True, "user_id": existing["id"], "username": uname}
        else:
            pwd = (payload.password or "").strip()
            if len(pwd) < 4:
                raise HTTPException(status_code=400, detail="Vui lòng nhập mật khẩu (tối thiểu 4 ký tự) khi cấp tài khoản mới.")
            row = conn.execute(
                """
                INSERT INTO app_users (username, email, password_hash, display_name, role, patient_id, is_active)
                VALUES (%s, %s, %s, %s, 'PATIENT', %s, %s)
                RETURNING id::text AS id;
                """,
                (uname, f"{uname}@patient.nutriguard.ai", hash_password(pwd), disp, patient_id, payload.is_active),
            ).fetchone()
            return {"ok": True, "user_id": row["id"], "username": uname}


@app.get("/api/admin/users")
def admin_list_users(_admin: Dict[str, Any] = Depends(require_admin)):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT u.id::text AS id, u.username, u.email, u.display_name, u.role,
                   u.patient_id::text AS patient_id, p.nickname AS patient_nickname,
                   u.is_active, u.created_at
            FROM app_users u
            LEFT JOIN patients p ON p.id = u.patient_id
            WHERE u.username IS NOT NULL
            ORDER BY CASE WHEN u.role = 'ADMIN' THEN 0 ELSE 1 END, u.created_at ASC;
            """
        ).fetchall()
    return _to_json_safe(rows)


@app.post("/api/admin/users")
def admin_create_user(
    payload: AdminUserCreatePayload,
    _admin: Dict[str, Any] = Depends(require_admin),
):
    uname = payload.username.strip().lower()
    role = payload.role.upper()
    if role not in ("ADMIN", "PATIENT"):
        raise HTTPException(status_code=400, detail="Vai trò phải là ADMIN hoặc PATIENT.")

    with get_conn() as conn:
        dup = conn.execute(
            "SELECT 1 FROM app_users WHERE lower(COALESCE(username, '')) = %s;", (uname,)
        ).fetchone()
        if dup:
            raise HTTPException(status_code=409, detail=f"Tên đăng nhập '{uname}' đã tồn tại.")
        patient_id = payload.patient_id if role == "PATIENT" else None
        created_blank_patient = False
        if role == "PATIENT" and not patient_id:
            owner = conn.execute(
                "INSERT INTO app_users (email, display_name) VALUES ('default@nutriguard.ai', 'Default') "
                "ON CONFLICT (email) DO UPDATE SET display_name = EXCLUDED.display_name RETURNING id;"
            ).fetchone()
            p_row = conn.execute(
                "INSERT INTO patients (user_id, nickname, gender, birth_year, height_cm, activity_level) "
                "VALUES (%s, %s, 'Nam'::gender_type, 1985, 165.0, 'Ít vận động'::activity_type) RETURNING id::text AS id;",
                (owner["id"], payload.display_name.strip()),
            ).fetchone()
            patient_id = p_row["id"]
            conn.execute(
                "INSERT INTO checkups (patient_id, checkup_date, weight_kg, source) VALUES (%s, CURRENT_DATE, 60.0, 'MANUAL');",
                (patient_id,),
            )
            created_blank_patient = True
        email = (payload.email or "").strip() or f"{uname}@{'admin' if role == 'ADMIN' else 'patient'}.nutriguard.ai"
        row = conn.execute(
            """
            INSERT INTO app_users (username, email, password_hash, display_name, role, patient_id, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, TRUE)
            RETURNING id::text AS id, username, email, display_name, role, patient_id::text AS patient_id, is_active;
            """,
            (uname, email, hash_password(payload.password), payload.display_name.strip(), role, patient_id),
        ).fetchone()
    if created_blank_patient and patient_id:
        match_and_compute_target(patient_id, save_to_db=True)
    return _to_json_safe(row)


@app.patch("/api/admin/users/{user_id}")
def admin_update_user(
    user_id: str,
    payload: AdminUserUpdatePayload,
    admin: Dict[str, Any] = Depends(require_admin),
):
    if user_id == admin["id"] and payload.is_active is False:
        raise HTTPException(status_code=400, detail="Không thể tự khóa chính tài khoản Admin đang đăng nhập.")
    with get_conn() as conn:
        u = conn.execute("SELECT id, role FROM app_users WHERE id = %s;", (user_id,)).fetchone()
        if not u:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
        if payload.display_name is not None:
            conn.execute("UPDATE app_users SET display_name = %s WHERE id = %s;", (payload.display_name.strip(), user_id))
        if payload.email is not None:
            conn.execute("UPDATE app_users SET email = %s WHERE id = %s;", (payload.email.strip(), user_id))
        if payload.role is not None:
            new_role = payload.role.strip().upper()
            if new_role not in ("ADMIN", "PATIENT"):
                raise HTTPException(status_code=400, detail="Vai trò phải là ADMIN hoặc PATIENT.")
            conn.execute("UPDATE app_users SET role = %s WHERE id = %s;", (new_role, user_id))
        if payload.is_active is not None:
            conn.execute("UPDATE app_users SET is_active = %s WHERE id = %s;", (payload.is_active, user_id))
        if payload.password and payload.password.strip():
            if len(payload.password.strip()) < 4:
                raise HTTPException(status_code=400, detail="Mật khẩu tối thiểu 4 ký tự.")
            conn.execute("UPDATE app_users SET password_hash = %s WHERE id = %s;", (hash_password(payload.password.strip()), user_id))
        if payload.patient_id is not None:
            conn.execute("UPDATE app_users SET patient_id = %s WHERE id = %s;", (payload.patient_id or None, user_id))
    return {"ok": True}


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(
    user_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Không thể xóa tài khoản Admin đang đăng nhập.")
    with get_conn() as conn:
        row = conn.execute("DELETE FROM app_users WHERE id = %s RETURNING id::text AS id;", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
    return {"deleted_id": row["id"]}


@app.get("/api/admin/overview")
def admin_overview(_admin: Dict[str, Any] = Depends(require_admin)):
    with get_conn() as conn:
        stats = {
            "patients_count": conn.execute("SELECT count(*) AS c FROM patients;").fetchone()["c"],
            "active_users_count": conn.execute("SELECT count(*) AS c FROM app_users WHERE username IS NOT NULL AND is_active = TRUE;").fetchone()["c"],
            "foods_count": conn.execute("SELECT count(*) AS c FROM foods;").fetchone()["c"],
            "rag_docs_count": conn.execute("SELECT count(*) AS c FROM knowledge_documents;").fetchone()["c"],
            "rag_chunks_count": conn.execute("SELECT count(*) AS c FROM knowledge_chunks;").fetchone()["c"],
            "conditions_count": conn.execute("SELECT count(*) AS c FROM conditions WHERE is_enabled = TRUE;").fetchone()["c"],
            "regimes_count": conn.execute("SELECT count(*) AS c FROM diet_regimes WHERE is_enabled = TRUE;").fetchone()["c"],
            "meal_plans_count": conn.execute("SELECT count(*) AS c FROM meal_plans;").fetchone()["c"],
            "agent_runs_count": conn.execute("SELECT count(*) AS c FROM agent_runs;").fetchone()["c"],
            "guardrail_blocks_count": conn.execute("SELECT count(*) AS c FROM guardrail_events WHERE action IN ('BLOCK', 'REWRITE');").fetchone()["c"],
        }
        latest_eval = conn.execute(
            "SELECT id, model_name, summary, started_at FROM eval_runs ORDER BY id DESC LIMIT 1;"
        ).fetchone()
        recent_runs = conn.execute(
            "SELECT id, workflow, model_name, latency_ms, status, created_at FROM agent_runs ORDER BY id DESC LIMIT 8;"
        ).fetchall()
    return _to_json_safe({
        "stats": stats,
        "latest_eval": latest_eval,
        "recent_runs": recent_runs,
        "langfuse_enabled": has_langfuse_config(),
    })


@app.get("/api/admin/catalog")
def admin_catalog(_admin: Dict[str, Any] = Depends(require_admin)):
    with get_conn() as conn:
        conditions = conn.execute(
            "SELECT id, code, name, group_name, icd10, is_enabled, description FROM conditions ORDER BY id;"
        ).fetchall()
        regimes = conn.execute(
            """
            SELECT id, code, group_name, name, energy_min_kcal, energy_max_kcal,
                   protein_min_g, protein_max_g, sodium_max_mg, potassium_max_mg,
                   phosphate_max_mg, fiber_min_g, meals_min, meals_max,
                   energy_kcal_per_kg_min, energy_kcal_per_kg_max,
                   protein_g_per_kg_min, protein_g_per_kg_max,
                   require_low_gi, is_enabled, notes
            FROM diet_regimes
            ORDER BY id;
            """
        ).fetchall()
        rules = conn.execute(
            """
            SELECT frr.id, frr.nutrient_column, frr.operator, frr.threshold_num,
                   frr.threshold_text, frr.action, frr.reason,
                   COALESCE(c.code, dr.code) AS source_code,
                   COALESCE(c.name, dr.name) AS source_name
            FROM food_restriction_rules frr
            LEFT JOIN conditions c ON c.id = frr.condition_id
            LEFT JOIN diet_regimes dr ON dr.id = frr.regime_id
            ORDER BY frr.action DESC, frr.id ASC;
            """
        ).fetchall()
    return _to_json_safe({"conditions": conditions, "regimes": regimes, "rules": rules})


@app.patch("/api/admin/conditions/{code}/toggle")
def admin_toggle_condition(code: str, _admin: Dict[str, Any] = Depends(require_admin)):
    with get_conn() as conn:
        row = conn.execute(
            "UPDATE conditions SET is_enabled = NOT is_enabled WHERE code = %s RETURNING code, is_enabled;",
            (code,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy mã bệnh lý.")
    return _to_json_safe(row)


@app.post("/api/admin/foods")
def admin_create_food(payload: FoodAdminPayload, _admin: Dict[str, Any] = Depends(require_admin)):
    gi_val = payload.gi if payload.gi in ("Thấp", "Trung bình", "Cao") else None
    unit_val = payload.unit if payload.unit in ("g", "ml") else "g"
    with get_conn() as conn:
        next_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS nid FROM foods;").fetchone()["nid"]
        row = conn.execute(
            """
            INSERT INTO foods (
                id, name, unit, energy_kcal, protein_g, lipid_g, glucid_g, fiber_g,
                sodium_mg, potassium_mg, phosphorus_mg, gi
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::gi_level)
            RETURNING id, name, unit, energy_kcal, protein_g, lipid_g, glucid_g, fiber_g,
                      sodium_mg, potassium_mg, phosphorus_mg, gi;
            """,
            (
                next_id,
                payload.name.strip(),
                unit_val,
                payload.energy_kcal,
                payload.protein_g,
                payload.lipid_g,
                payload.glucid_g,
                payload.fiber_g,
                payload.sodium_mg,
                payload.potassium_mg,
                payload.phosphorus_mg,
                gi_val,
            ),
        ).fetchone()
    return _to_json_safe(row)


@app.put("/api/admin/foods/{food_id}")
def admin_update_food(food_id: int, payload: FoodAdminPayload, _admin: Dict[str, Any] = Depends(require_admin)):
    gi_val = payload.gi if payload.gi in ("Thấp", "Trung bình", "Cao") else None
    unit_val = payload.unit if payload.unit in ("g", "ml") else "g"
    with get_conn() as conn:
        row = conn.execute(
            """
            UPDATE foods
            SET name = %s, unit = %s, energy_kcal = %s, protein_g = %s, lipid_g = %s,
                glucid_g = %s, fiber_g = %s, sodium_mg = %s, potassium_mg = %s,
                phosphorus_mg = %s, gi = %s::gi_level
            WHERE id = %s
            RETURNING id, name, unit, energy_kcal, protein_g, lipid_g, glucid_g, fiber_g,
                      sodium_mg, potassium_mg, phosphorus_mg, gi;
            """,
            (
                payload.name.strip(),
                unit_val,
                payload.energy_kcal,
                payload.protein_g,
                payload.lipid_g,
                payload.glucid_g,
                payload.fiber_g,
                payload.sodium_mg,
                payload.potassium_mg,
                payload.phosphorus_mg,
                gi_val,
                food_id,
            ),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy thực phẩm.")
    return _to_json_safe(row)


@app.delete("/api/admin/foods/{food_id}")
def admin_delete_food(food_id: int, _admin: Dict[str, Any] = Depends(require_admin)):
    with get_conn() as conn:
        try:
            row = conn.execute("DELETE FROM foods WHERE id = %s RETURNING id;", (food_id,)).fetchone()
        except Exception as e:
            raise HTTPException(status_code=409, detail=f"Không thể xóa món đang được sử dụng trong thực đơn: {e}")
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy thực phẩm.")
    return {"deleted_id": row["id"]}


# ----------------- OBSERVABILITY, EVALS & RAG PDF (ADMIN ONLY) -----------------

@app.get("/api/observability")
def get_observability(_admin: Dict[str, Any] = Depends(require_admin)):
    with get_conn() as conn:
        runs = conn.execute(
            """
            SELECT id, trace_id, workflow, model_name, latency_ms,
                   input_tokens, output_tokens, cost_usd, status, error, created_at,
                   COALESCE(span_timings, '[]'::jsonb) AS span_timings
            FROM agent_runs
            ORDER BY id DESC LIMIT 40;
            """
        ).fetchall()
        events = conn.execute(
            "SELECT id, run_id, stage, guardrail_name, action, detail, created_at FROM guardrail_events ORDER BY id DESC LIMIT 40;"
        ).fetchall()
        eval_runs = conn.execute(
            "SELECT id, model_name, summary, started_at FROM eval_runs ORDER BY id DESC LIMIT 10;"
        ).fetchall()
        eval_results = conn.execute(
            """
            SELECT er.eval_run_id, ec.category, ec.input->>'case_key' AS case_key,
                   ec.input->>'group' AS group_name, ec.input->>'difficulty' AS difficulty,
                   ec.input->>'query' AS case_query,
                   er.passed, er.metrics, er.output, er.trace_id
            FROM eval_results er
            JOIN eval_cases ec ON ec.id = er.case_id
            WHERE er.eval_run_id = (SELECT COALESCE(MAX(id), 0) FROM eval_runs)
            ORDER BY er.id ASC;
            """
        ).fetchall()
    return _to_json_safe({
        "langfuse_enabled": has_langfuse_config(),
        "metrics": compute_agent_metrics(),
        "recent_logs": read_recent_logs(limit=60),
        "agent_runs": runs,
        "guardrail_events": events,
        "eval_runs": eval_runs,
        "eval_results": eval_results,
    })


@app.post("/api/evals/run")
def trigger_evals(payload: EvalRunPayload, _admin: Dict[str, Any] = Depends(require_admin)):
    res = run_evals(include_e2e=payload.include_e2e)
    return _to_json_safe(res)


@app.get("/api/rag/documents")
def get_rag_documents(_admin: Dict[str, Any] = Depends(require_admin)):
    return _to_json_safe(list_knowledge_documents())


@app.post("/api/rag/documents")
async def upload_rag_documents(
    files: List[UploadFile] = File(...),
    source: str = Form(default="Bộ Y tế / Phác đồ lâm sàng"),
    group_name: str = Form(default="Chung"),
    published_year: int = Form(default=2024),
    max_chars: int = Form(default=800),
    overlap: int = Form(default=120),
    _admin: Dict[str, Any] = Depends(require_admin),
):
    results = []
    for f in files:
        raw = await f.read()
        fname = f.filename or "document.pdf"
        title = Path(fname).stem
        if fname.lower().endswith(".pdf"):
            res = ingest_pdf_bytes(
                pdf_bytes=raw,
                filename=fname,
                title=title,
                source=source,
                group_name=group_name,
                published_year=published_year,
                max_chars=max_chars,
                overlap=overlap,
            )
        else:
            res = ingest_text(
                text=raw.decode("utf-8"),
                title=title,
                source=source,
                group_name=group_name,
                published_year=published_year,
                max_chars=max_chars,
                overlap=overlap,
                source_filename=fname,
            )
        results.append(res)
    return _to_json_safe(results)


@app.delete("/api/rag/documents/{doc_id}")
def remove_rag_document(doc_id: int, _admin: Dict[str, Any] = Depends(require_admin)):
    delete_knowledge_document(doc_id)
    return {"deleted": doc_id}


@app.get("/api/rag/search")
def query_rag(q: str, top_k: int = 4, _admin: Dict[str, Any] = Depends(require_admin)):
    if not q.strip():
        return []
    return _to_json_safe(search_knowledge(q, top_k=top_k))


# ----------------- SERVE BUILT REACT SPA -----------------

if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        target_file = FRONTEND_DIST / full_path
        if full_path and target_file.is_file():
            return FileResponse(target_file)
        return FileResponse(FRONTEND_DIST / "index.html")
