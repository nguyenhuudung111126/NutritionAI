"""Intent Router: Phân loại câu hỏi của người dùng sang đúng nhánh xử lý.

Chiến lược Hybrid Fast-Path:
- Các câu hỏi rõ ràng (lập thực đơn, hỏi ăn món X được không, tra cứu calo/đạm/kali món X,
  hỏi kiến thức chung/chào hỏi) được phân loại ngay bằng Rule/Từ khóa trong < 1ms.
- Chỉ gọi Gemini Structured Output khi câu hỏi mơ hồ / đa nghĩa để tránh tốn ~3s độ trễ không cần thiết.
"""
import re
import unicodedata
from typing import Literal, Optional

from pydantic import BaseModel, Field

from src.llm import generate_structured, has_api_key


class IntentClassification(BaseModel):
    intent: Literal["NUTRITION_LOOKUP", "SAFETY_CHECK", "MEAL_PLANNING", "GENERAL"] = Field(
        description=(
            "NUTRITION_LOOKUP: hỏi thành phần dinh dưỡng của 1 món ăn. "
            "SAFETY_CHECK: hỏi bệnh nhân có ăn món nào đó được không. "
            "MEAL_PLANNING: yêu cầu lập thực đơn theo ngày/tuần/tháng. "
            "GENERAL: câu hỏi chung về dinh dưỡng bệnh lý hoặc chào hỏi."
        )
    )
    food_name: str = Field(default="", description="Tên thực phẩm được nhắc đến (nếu có).")
    period: Literal["DAY", "WEEK", "MONTH", "NONE"] = Field(
        default="NONE", description="Khoảng thời gian lập thực đơn nếu là MEAL_PLANNING, ngược lại là NONE."
    )


def _norm(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower().strip())
    return "".join(c for c in nfkd if not unicodedata.combining(c)).replace("đ", "d")


_NOISE_PHRASES_RE = re.compile(
    r"\b("
    r"bệnh nhân|người bị|người bệnh|tôi bị|tôi là|mình bị|em bị|bác sĩ|cho hỏi|xin hỏi|"
    r"suy thận mạn|bệnh thận mạn|suy thận|thận mạn|tiểu đường|đái tháo đường|tăng huyết áp|huyết áp cao|"
    r"rối loạn mỡ máu|mỡ máu|lọc máu|chạy thận|thai kỳ|"
    r"benh nhan|nguoi bi|nguoi benh|toi bi|toi la|minh bi|em bi|bac si|cho hoi|xin hoi|"
    r"suy than man|benh than man|suy than|than man|tieu duong|dai thao duong|tang huyet ap|huyet ap cao|"
    r"roi loan mo mau|mo mau|loc mau|chay than|thai ky|"
    r"thành phần dinh dưỡng|hàm lượng dinh dưỡng|giá trị dinh dưỡng|"
    r"thanh phan dinh duong|ham luong dinh duong|gia tri dinh duong|"
    r"ăn gì|có ăn được không|ăn được không|uống được không|có ăn được|có uống được|"
    r"được không|có sao không|có tốt không|nên ăn không|có nên ăn|nên kiêng|"
    r"an gi|co an duoc khong|an duoc khong|uong duoc khong|co an duoc|co uong duoc|"
    r"duoc khong|co sao khong|co tot khong|nen an khong|co nen an|nen kieng|"
    r"có bao nhiêu|bao nhiêu|là bao nhiêu|như thế nào|"
    r"co bao nhieu|bao nhieu|la bao nhieu|nhu the nao|"
    r"món nào thay thế|thay thế|gợi ý|mon nao thay the|thay the|goi y|"
    r"100g|100ml|100 g|100 ml"
    r")\b"
)

_ACCENTED_STOPWORDS_RE = re.compile(
    r"\b("
    r"tôi|mình|chúng tôi|bị|bệnh|có|ăn|uống|món|được|không|nên|kiêng|hãy|"
    r"sao|nhỉ|ạ|và|của|cho|với|về|là|nhiều|ít|lượng|calo|kcal|kali|đạm|protein|"
    r"natri|muối|phospho|photpho|chất xơ|chất béo|đường bột|đường huyết|gi|dinh dưỡng|hàm lượng|"
    r"hay|luộc|hấp|xào|nấu|nướng|chiên|rán|"
    r"co|an|uong|duoc|khong|nen|kieng|cua|cho|voi|ve|la|nhieu|dam|luong|dinh duong|ham luong"
    r")\b"
)


def _extract_food_fallback(user_query: str) -> str:
    # Giữ nguyên dấu tiếng Việt khi lọc từ dừng để KHÔNG làm mất 'bí' (bí đao) thành 'bị' hoặc 'anh' trong 'thạch anh'
    lowered = user_query.lower()
    cleaned = _NOISE_PHRASES_RE.sub(" ", lowered)
    cleaned = _ACCENTED_STOPWORDS_RE.sub(" ", cleaned)
    tokens = [w for w in re.findall(r"[0-9a-zà-ỹ]+", cleaned) if len(w) >= 2 and not w.isdigit()]
    return " ".join(tokens[:5]).strip()


def _fast_rule_classify(user_query: str) -> Optional[IntentClassification]:
    """Phân loại siêu tốc (< 1ms). Trả về None nếu câu hỏi mơ hồ cần nhờ LLM."""
    q = _norm(user_query)
    if not q:
        return IntentClassification(intent="GENERAL")

    # 1. Lập thực đơn
    if any(k in q for k in ("thuc don", "bua an", "hom nay an gi", "len menu", "lap menu")):
        period: Literal["DAY", "WEEK", "MONTH", "NONE"] = (
            "WEEK" if "tuan" in q else ("MONTH" if "thang" in q else "DAY")
        )
        return IntentClassification(intent="MEAL_PLANNING", period=period)

    # 2. Hỏi kiến thức chung / sơ chế / nguyên tắc / chào hỏi (không tra món lẻ)
    is_safety_phrase = any(
        k in q for k in ("an duoc khong", "uong duoc khong", "duoc khong", "co an duoc", "co uong duoc", "co sao khong", "nen kieng", "co nen an")
    )
    is_lookup_phrase = any(
        k in q for k in ("bao nhieu", "thanh phan dinh duong", "ham luong dinh duong", "calo cua", "kcal cua", "dam cua", "kali cua")
    )

    if not is_safety_phrase and not is_lookup_phrase:
        if any(
            k in q
            for k in (
                "cach ", "lam sao", "nguyen tac", "tai sao", "vi sao", "luu y", "huong dan",
                "so che", "trieu chung", "xin chao", "chao ban", "hello", "hi ", "cam on",
            )
        ):
            return IntentClassification(intent="GENERAL")

    # 3. Hỏi ăn món này có an toàn không
    if is_safety_phrase:
        food = _extract_food_fallback(user_query)
        if food:
            return IntentClassification(intent="SAFETY_CHECK", food_name=food)

    # 4. Tra cứu thành phần dinh dưỡng của 1 món
    if is_lookup_phrase or any(k in q for k in ("calo", "kcal", "kali", "dam", "natri", "phospho", "dinh duong")):
        food = _extract_food_fallback(user_query)
        if food and not any(k in q for k in ("cach ", "nguyen tac", "tai sao", "so che")):
            return IntentClassification(intent="NUTRITION_LOOKUP", food_name=food)

    return None


def _keyword_fallback(user_query: str) -> IntentClassification:
    fast = _fast_rule_classify(user_query)
    if fast is not None:
        return fast
    return IntentClassification(intent="GENERAL")


def classify_intent(user_query: str) -> IntentClassification:
    """Ưu tiên phân loại nhanh <1ms cho câu hỏi rõ ràng; chỉ gọi Gemini nếu câu hỏi mơ hồ."""
    fast = _fast_rule_classify(user_query)
    if fast is not None:
        return fast

    if not has_api_key():
        return _keyword_fallback(user_query)

    prompt = f"Phân loại ý định câu hỏi dinh dưỡng lâm sàng sau:\n\"{user_query}\""
    try:
        parsed, _ = generate_structured(prompt, IntentClassification, fast=True)
        return parsed
    except Exception:
        return _keyword_fallback(user_query)
