"""Xác thực & phân quyền (Admin vs Bệnh nhân) bằng PBKDF2 + HMAC-SHA256 Bearer Token."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException

from src.db import get_conn
from src.tools.food_tool import _strip_accents

ROOT_DIR = Path(__file__).resolve().parent.parent
_SECRET_FILE = ROOT_DIR / ".auth_secret"
_TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 7 ngày


def _get_auth_secret() -> bytes:
    env_sec = os.getenv("AUTH_SECRET", "").strip()
    if env_sec:
        return env_sec.encode("utf-8")
    if _SECRET_FILE.exists():
        sec = _SECRET_FILE.read_text(encoding="utf-8").strip()
        if sec:
            return sec.encode("utf-8")
    new_sec = secrets.token_urlsafe(48)
    _SECRET_FILE.write_text(new_sec, encoding="utf-8")
    return new_sec.encode("utf-8")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"pbkdf2_sha256${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored_hash: Optional[str]) -> bool:
    if not stored_hash or "$" not in stored_hash:
        return False
    parts = stored_hash.split("$")
    if len(parts) != 3 or parts[0] != "pbkdf2_sha256":
        return False
    try:
        salt = bytes.fromhex(parts[1])
        expected = bytes.fromhex(parts[2])
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return hmac.compare_digest(actual, expected)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def create_access_token(user: Dict[str, Any], ttl_seconds: int = _TOKEN_TTL_SECONDS) -> str:
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    now = int(time.time())
    payload_obj = {
        "sub": str(user["id"]),
        "username": user.get("username"),
        "role": user.get("role", "PATIENT"),
        "patient_id": str(user["patient_id"]) if user.get("patient_id") else None,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    payload = _b64url_encode(json.dumps(payload_obj, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    sig = hmac.new(_get_auth_secret(), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64url_encode(sig)}"


def decode_access_token(token: str) -> Dict[str, Any]:
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="Token đăng nhập không hợp lệ.")
    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(_get_auth_secret(), signing_input, hashlib.sha256).digest()
    try:
        actual_sig = _b64url_decode(sig_b64)
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=401, detail="Token đăng nhập bị hỏng.")

    if not hmac.compare_digest(actual_sig, expected_sig):
        raise HTTPException(status_code=401, detail="Chữ ký token không hợp lệ.")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=401, detail="Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.")
    return payload


def _slugify_username(text: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "", _strip_accents(text))
    return clean[:30] or "benhnhan"


def ensure_auth_schema_and_seed() -> None:
    """Idempotent migration: nâng cấp `app_users` hỗ trợ role + tài khoản mặc định."""
    with get_conn() as conn:
        conn.execute("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS username VARCHAR(100);")
        conn.execute("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'PATIENT';")
        conn.execute("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS patient_id UUID;")
        conn.execute("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;")

        # Unique index cho username & constraint role / FK patient_id (an toàn chạy lại)
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_app_users_username ON app_users (username) WHERE username IS NOT NULL;"
        )
        conn.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_app_users_role') THEN
                    ALTER TABLE app_users ADD CONSTRAINT chk_app_users_role CHECK (role IN ('ADMIN', 'PATIENT'));
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_app_users_patient') THEN
                    ALTER TABLE app_users ADD CONSTRAINT fk_app_users_patient
                        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE SET NULL;
                END IF;
            END $$;
            """
        )

        # 1. Seed tài khoản ADMIN mặc định nếu chưa có tài khoản ADMIN nào
        admin_exists = conn.execute("SELECT id FROM app_users WHERE role = 'ADMIN' LIMIT 1;").fetchone()
        if not admin_exists:
            conn.execute(
                """
                INSERT INTO app_users (username, email, password_hash, display_name, role, is_active)
                VALUES (%s, %s, %s, %s, 'ADMIN', TRUE)
                ON CONFLICT (email) DO UPDATE
                SET username = EXCLUDED.username,
                    password_hash = EXCLUDED.password_hash,
                    display_name = EXCLUDED.display_name,
                    role = 'ADMIN',
                    is_active = TRUE;
                """,
                ("admin", "admin@nutriguard.ai", hash_password("admin123"), "Quản trị viên (Admin)"),
            )

        # 2. Bảo đảm mỗi bệnh nhân hiện có đều có 1 tài khoản PATIENT mặc định (mật khẩu 123456) nếu chưa gán
        patients = conn.execute(
            """
            SELECT p.id::text AS id, p.nickname
            FROM patients p
            LEFT JOIN app_users u ON u.patient_id = p.id
            WHERE u.id IS NULL
            ORDER BY p.created_at ASC;
            """
        ).fetchall()

        for p in patients:
            base_slug = _slugify_username(p["nickname"])
            # Rút gọn biệt danh Eval dài thành 'bacnam' nếu phù hợp
            if p["id"] == "00000000-0000-0000-0000-0000000000a1":
                base_slug = "bacnam"
            candidate = base_slug
            suffix = 1
            while conn.execute(
                "SELECT 1 FROM app_users WHERE username = %s OR email = %s;",
                (candidate, f"{candidate}@patient.nutriguard.ai"),
            ).fetchone():
                suffix += 1
                candidate = f"{base_slug}{suffix}"

            conn.execute(
                """
                INSERT INTO app_users (username, email, password_hash, display_name, role, patient_id, is_active)
                VALUES (%s, %s, %s, %s, 'PATIENT', %s, TRUE);
                """,
                (
                    candidate,
                    f"{candidate}@patient.nutriguard.ai",
                    hash_password("123456"),
                    p["nickname"],
                    p["id"],
                ),
            )


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT u.id::text AS id, u.username, u.email, u.display_name,
                   u.role, u.patient_id::text AS patient_id, u.is_active, u.created_at
            FROM app_users u
            WHERE u.id = %s;
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def authenticate_user(username_or_email: str, password: str) -> Optional[Dict[str, Any]]:
    ident = username_or_email.strip().lower()
    if not ident or not password:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT u.id::text AS id, u.username, u.email, u.password_hash, u.display_name,
                   u.role, u.patient_id::text AS patient_id, u.is_active
            FROM app_users u
            WHERE lower(COALESCE(u.username, '')) = %s OR lower(u.email) = %s
            LIMIT 1;
            """,
            (ident, ident),
        ).fetchone()
    if not row:
        return None
    if not row["is_active"]:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa. Vui lòng liên hệ Quản trị viên.")
    if not verify_password(password, row["password_hash"]):
        return None
    return {
        "id": row["id"],
        "username": row["username"] or row["email"],
        "email": row["email"],
        "display_name": row["display_name"],
        "role": row["role"],
        "patient_id": row["patient_id"],
        "is_active": row["is_active"],
    }


def get_current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Vui lòng đăng nhập để tiếp tục.")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    user = get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="Tài khoản không tồn tại.")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị vô hiệu hóa.")
    return user


def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if user.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="Chức năng này chỉ dành cho Quản trị viên (Admin).")
    return user


def verify_patient_access(patient_id: str, user: Dict[str, Any]) -> None:
    if user.get("role") == "ADMIN":
        return
    if str(user.get("patient_id") or "") != str(patient_id):
        raise HTTPException(status_code=403, detail="Bạn chỉ được phép truy cập hồ sơ của chính mình.")
