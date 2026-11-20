"""Input Guardrail rule-based: chặn Prompt Injection / Jailbreak và câu hỏi lạc đề (Off-topic).

Thiết kế ưu tiên GIẢM FALSE POSITIVE:
- Injection: chỉ chặn khi có mẫu câu điều khiển mô hình rõ ràng (bỏ qua *hướng dẫn/chỉ thị*, lộ *system prompt*,
  đổi vai không giới hạn...). Câu "bỏ qua bữa sáng", "hướng dẫn nấu canh" KHÔNG bị chặn.
- Off-topic: chỉ chặn khi có từ khóa lạc đề VÀ hoàn toàn không có từ khóa sức khỏe/dinh dưỡng.
"""
import re
import unicodedata
from typing import Any, Dict, List


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFD", (text or "").lower().replace("đ", "d"))
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


# Mẫu injection (đã bỏ dấu, chữ thường)
_INJECTION_PATTERNS: List[re.Pattern] = [re.compile(p) for p in [
    r"(bo qua|phot lo|quen|lo di|vo hieu)\s+(het\s+|moi\s+|tat ca\s+|toan bo\s+|cac\s+)*(huong dan|chi thi|quy tac|lenh|rang buoc|gioi han|nguyen tac)\s*(truoc|phia tren|ben tren|he thong|an toan)?",
    r"ignore\s+(all\s+|any\s+|the\s+)*(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)",
    r"disregard\s+(all\s+|the\s+)*(previous|prior|above|system)\s+",
    r"(system\s*prompt|prompt\s*he\s*thong|developer\s*message|chi thi he thong)",
    r"(tiet lo|in ra|hien thi|cho (toi|minh) xem|reveal|print|show)\s+.{0,25}(prompt|chi thi|cau hinh an|instructions?)",
    r"\b(jailbreak|dan mode|dan jailbreak|che do dan|developer mode|che do nha phat trien|god mode)\b",
    r"(dong vai|gia vo la|you are now|act as|pretend to be|tu gio ban la|bay gio ban la).{0,60}(khong (con )?gioi han|khong bi rang buoc|bo qua|unrestricted|no rules|without restrictions|khong can tuan thu)",
    r"(khong can|dung) tuan thu .{0,20}(quy tac|nguyen tac|an toan|phac do)",
    r"</?\s*(system|assistant|instruction)\s*>",
]]

_OFFTOPIC_KEYWORDS = [
    "code python", "viet code", "lap trinh", "javascript", "sql injection", "hack", "crack phan mem",
    "bitcoin", "crypto", "tien ao", "chung khoan", "co phieu", "forex", "xo so", "lo de", "ca do",
    "bong da", "ngoai hang anh", "ket qua tran", "world cup", "chinh tri", "bau cu", "tong thong",
    "viet bai tho", "lam tho", "viet van", "dich sang tieng", "giai toan", "bai tap ve nha",
    "thoi tiet", "phim", "game", "choi game", "du lich", "dat ve may bay", "tinh yeu", "tan gai",
]

_HEALTH_KEYWORDS = [
    "an uong", "bua an", "mon an", "thuc pham", "thuc don", "dinh duong", "calo", "kcal", "dam", "protein",
    "kali", "natri", "muoi", "duong huyet", "tinh bot", "chi so gi", "chat beo", "chat xo", "vitamin", "khoang chat",
    "benh", "than", "tieu duong", "dai thao duong", "huyet ap", "mo mau", "gout", "suy than", "ckd",
    "xet nghiem", "egfr", "creatinin", "hba1c", "glucose", "can nang", "bmi", "bac si", "suc khoe",
    "rau", "trai cay", "hoa qua", "thit", "trung", "sua", "gao", "com", "chao", "canh", "nau", "che bien",
]


def check_input_safety(text: str) -> Dict[str, Any]:
    """Trả về {action: PASS|BLOCK, category: none|prompt_injection|off_topic, matched: [...]}."""
    q = _norm(text)
    if not q:
        return {"action": "PASS", "category": "none", "matched": []}

    inj = [p.pattern[:40] for p in _INJECTION_PATTERNS if p.search(q)]
    if inj:
        return {"action": "BLOCK", "category": "prompt_injection", "matched": inj[:3]}

    padded = f" {q} "
    off = [k for k in _OFFTOPIC_KEYWORDS if k in q]
    has_health = any(re.search(rf"(?<![a-z]){re.escape(k.strip())}(?![a-z])", padded) for k in _HEALTH_KEYWORDS)
    if off and not has_health:
        return {"action": "BLOCK", "category": "off_topic", "matched": off[:3]}

    return {"action": "PASS", "category": "none", "matched": []}


REFUSAL_MESSAGES = {
    "prompt_injection": (
        "⚠️ Yêu cầu của bạn có dấu hiệu cố gắng thay đổi quy tắc an toàn của hệ thống nên đã bị từ chối. "
        "NutriGuard AI chỉ tư vấn dinh dưỡng theo phác đồ Bộ Y tế và không thể bỏ qua các nguyên tắc an toàn lâm sàng."
    ),
    "off_topic": (
        "Xin lỗi, câu hỏi này nằm ngoài phạm vi hỗ trợ. NutriGuard AI chỉ tư vấn về dinh dưỡng, thực đơn "
        "và an toàn thực phẩm theo hồ sơ bệnh lý của bạn. Bạn có thể hỏi ví dụ: \"Tôi ăn chuối được không?\""
    ),
}
