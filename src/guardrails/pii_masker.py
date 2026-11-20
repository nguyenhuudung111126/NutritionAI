"""Hàng rào bảo mật thông tin cá nhân (PII Redaction) cho dữ liệu y tế."""
import re
from typing import Any, Dict

_PATTERNS = [
    # Số CCCD / CMND (9 hoặc 12 chữ số)
    (re.compile(r"\b\d{9}\b|\b\d{12}\b"), "[CCCD_REDACTED]"),
    # Số điện thoại Việt Nam
    (re.compile(r"(?:\+84|0)(?:3|5|7|8|9)\d{8}\b"), "[PHONE_REDACTED]"),
    # Mã thẻ BHYT (2 chữ + 1 số + 12 số)
    (re.compile(r"\b[A-Z]{2}\d{13}\b"), "[BHYT_REDACTED]"),
    # Email
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL_REDACTED]"),
]


def mask_pii_text(text: str) -> str:
    """Ẩn CCCD, SĐT, mã BHYT, email trong văn bản trước khi lưu log hoặc gửi trace."""
    if not text:
        return text
    masked = text
    for pattern, repl in _PATTERNS:
        masked = pattern.sub(repl, masked)
    return masked


def mask_pii_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Loại bỏ hoặc che các trường định danh cá nhân trong dict JSON."""
    sensitive_keys = {"full_name", "ho_ten", "cccd", "cmnd", "phone", "sdt", "address", "dia_chi", "bhyt"}
    cleaned: Dict[str, Any] = {}
    for k, v in data.items():
        if k.lower() in sensitive_keys:
            cleaned[k] = "[REDACTED]"
        elif isinstance(v, str):
            cleaned[k] = mask_pii_text(v)
        elif isinstance(v, dict):
            cleaned[k] = mask_pii_dict(v)
        else:
            cleaned[k] = v
    return cleaned
