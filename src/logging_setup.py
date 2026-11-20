"""Structured JSON logging: mỗi dòng log là 1 JSON có `trace_id` / `request_id` và đã che PII.

- Ghi ra stdout + file xoay vòng `logs/app.jsonl` (đọc lại được trên trang Admin Observability).
- `trace_id`, `request_id`, `user_role` lấy tự động từ ContextVar (gán bởi HTTP middleware & agent run).
"""
import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.guardrails.pii_masker import mask_pii_dict, mask_pii_text

ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT_DIR / "logs"
LOG_FILE = LOG_DIR / "app.jsonl"

trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_role_var: ContextVar[Optional[str]] = ContextVar("user_role", default=None)

_RESERVED = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime"}


class JsonPiiFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": mask_pii_text(record.getMessage()),
            "trace_id": getattr(record, "trace_id", None) or trace_id_var.get(),
            "request_id": getattr(record, "request_id", None) or request_id_var.get(),
            "user_role": user_role_var.get(),
        }
        extras = {k: v for k, v in record.__dict__.items() if k not in _RESERVED and k not in payload}
        if extras:
            payload.update(mask_pii_dict({k: (v if isinstance(v, (str, int, float, bool, dict, type(None))) else str(v)) for k, v in extras.items()}))
        if record.exc_info:
            payload["error"] = mask_pii_text(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = JsonPiiFormatter()

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)

    root = logging.getLogger("nutriguard")
    root.setLevel(level)
    root.handlers = [file_handler, stream_handler]
    root.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"nutriguard.{name}")


def read_recent_logs(limit: int = 200, level: Optional[str] = None, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Đọc N dòng log JSON mới nhất (mới -> cũ) để hiển thị trên dashboard."""
    if not LOG_FILE.exists():
        return []
    with LOG_FILE.open("r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()[-max(limit * 5, 500):]
    out: List[Dict[str, Any]] = []
    for line in reversed(lines):
        try:
            item = json.loads(line)
        except Exception:
            continue
        if level and item.get("level") != level.upper():
            continue
        if trace_id and item.get("trace_id") != trace_id:
            continue
        out.append(item)
        if len(out) >= limit:
            break
    return out
