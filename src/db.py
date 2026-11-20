"""Quản lý kết nối PostgreSQL (schema `nutri`)."""
import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

# Tự động nạp .env ở thư mục gốc dự án
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("Thiếu biến môi trường DATABASE_URL trong file .env")
    return url


@contextmanager
def get_conn():
    """Mở kết nối PostgreSQL với dict_row và search_path = nutri, public."""
    conn = psycopg.connect(get_database_url(), row_factory=dict_row)
    try:
        conn.execute("SET search_path TO nutri, public;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
