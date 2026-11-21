"""Quản lý kết nối PostgreSQL (schema `nutri`) với Connection Pool tái sử dụng."""
import os
from contextlib import contextmanager
from pathlib import Path
from queue import Empty, Full, LifoQueue

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

# Tự động nạp .env ở thư mục gốc dự án
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

_POOL: LifoQueue = LifoQueue(maxsize=6)


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("Thiếu biến môi trường DATABASE_URL trong file .env")
    return url


def _acquire_conn() -> psycopg.Connection:
    url = get_database_url()
    while True:
        try:
            conn = _POOL.get_nowait()
            if conn.closed:
                continue
            try:
                conn.execute("SET search_path TO nutri, public;")
                return conn
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                continue
        except Empty:
            conn = psycopg.connect(url, row_factory=dict_row)
            conn.execute("SET search_path TO nutri, public;")
            return conn


def _release_conn(conn: psycopg.Connection) -> None:
    if conn.closed:
        return
    try:
        _POOL.put_nowait(conn)
    except Full:
        try:
            conn.close()
        except Exception:
            pass


@contextmanager
def get_conn():
    """Mượn kết nối PostgreSQL từ pool (dict_row, search_path = nutri, public)."""
    conn = _acquire_conn()
    broken = False
    try:
        yield conn
        conn.commit()
    except Exception:
        broken = True
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        if broken:
            try:
                conn.close()
            except Exception:
                pass
        else:
            _release_conn(conn)
