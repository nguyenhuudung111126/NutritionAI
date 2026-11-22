"""Client tập trung dùng SDK `google-genai` (v1beta) kèm fallback đa model ổn định."""
import os
import re
import threading
import time
from contextvars import ContextVar
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_EMBED_WINDOW_START = 0.0
_EMBED_WINDOW_COUNT = 0
_EMBED_RPM_SAFE_LIMIT = 85  # Free tier limit = 100/phút; giữ mức an toàn 85/phút
_RETRY_DELAY_RE = re.compile(r"retry(?: in|Delay['\":\s]+)\s*(\d+(?:\.\d+)?)\s*s", re.IGNORECASE)

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
FALLBACK_MODELS = [
    DEFAULT_MODEL,
    "gemini-3.1-flash-lite-preview",
    "gemini-3-flash-preview",
    "gemini-3.8-flash",
]
EMBED_MODEL = "gemini-embedding-001"

# ---------------- TOKEN & COST METRICS ----------------
# Đơn giá ước tính (USD / 1 triệu token). Có thể ghi đè trong .env.
PRICE_INPUT_PER_1M = float(os.getenv("LLM_PRICE_INPUT_PER_1M", "0.10"))
PRICE_OUTPUT_PER_1M = float(os.getenv("LLM_PRICE_OUTPUT_PER_1M", "0.40"))

# Bộ tích lũy usage theo từng agent run (dict mutable -> chia sẻ được qua các thread LangGraph copy context).
_USAGE_CTX: ContextVar[Optional[Dict[str, Any]]] = ContextVar("llm_usage_ctx", default=None)


def start_usage_tracking() -> Dict[str, Any]:
    acc: Dict[str, Any] = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "llm_calls": 0}
    _USAGE_CTX.set(acc)
    return acc


def stop_usage_tracking() -> None:
    _USAGE_CTX.set(None)


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return round(input_tokens / 1e6 * PRICE_INPUT_PER_1M + output_tokens / 1e6 * PRICE_OUTPUT_PER_1M, 8)


def _record_usage(res: Any, model_name: str) -> None:
    """Đọc `usage_metadata` từ Gemini, cộng dồn vào run hiện tại và gắn lên Langfuse generation span."""
    um = getattr(res, "usage_metadata", None)
    if um is None:
        return
    in_tok = int(getattr(um, "prompt_token_count", 0) or 0)
    out_tok = int(getattr(um, "candidates_token_count", 0) or 0) + int(getattr(um, "thoughts_token_count", 0) or 0)
    cost = estimate_cost(in_tok, out_tok)

    acc = _USAGE_CTX.get()
    if acc is not None:
        acc["input_tokens"] += in_tok
        acc["output_tokens"] += out_tok
        acc["cost_usd"] = round(acc["cost_usd"] + cost, 8)
        acc["llm_calls"] += 1

    try:
        from src.observability import has_langfuse_config

        if has_langfuse_config():
            from langfuse import get_client

            get_client().update_current_generation(
                model=model_name,
                usage_details={"input": in_tok, "output": out_tok, "total": in_tok + out_tok},
                cost_details={"total": cost},
            )
    except Exception:
        pass


def has_api_key() -> bool:
    key = os.getenv("GEMINI_API_KEY", "")
    return bool(key) and not key.startswith("your_")


_CLIENT_CACHE: Dict[Tuple[str, int], genai.Client] = {}
_CLIENT_LOCK = threading.Lock()


def get_client(timeout_ms: int = 25_000) -> genai.Client:
    """Trả về singleton `genai.Client` theo `(api_key, timeout_ms)` để tái sử dụng kết nối keep-alive."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key or key.startswith("your_"):
        raise RuntimeError("Thiếu GEMINI_API_KEY hợp lệ trong file .env")
    cache_key = (key, int(timeout_ms))
    with _CLIENT_LOCK:
        client = _CLIENT_CACHE.get(cache_key)
        if client is None:
            client = genai.Client(
                api_key=key,
                http_options=types.HttpOptions(timeout=timeout_ms, api_version="v1beta"),
            )
            _CLIENT_CACHE[cache_key] = client
        return client


def _model_candidates() -> List[str]:
    seen = set()
    return [m for m in FALLBACK_MODELS if m and not (m in seen or seen.add(m))]


def _call_with_fallback(fn: Callable[[genai.Client, str], Any], timeout_ms: int = 25_000) -> tuple[Any, str]:
    client = get_client(timeout_ms=timeout_ms)
    errors: List[str] = []
    for model_name in _model_candidates():
        try:
            return fn(client, model_name), model_name
        except Exception as e:
            errors.append(f"{model_name}: {e}")
            continue
    raise RuntimeError("Không gọi được Gemini API: " + " | ".join(errors))


def _supports_zero_thinking(model_name: str) -> bool:
    """Chỉ tắt thinking_budget=0 với các model hỗ trợ và thực sự nhanh hơn khi tắt."""
    return "3-flash" in model_name or "3.8" in model_name or "2.5-flash" in model_name


def generate_text(contents: Any, fast: bool = False) -> tuple[str, str]:
    """Sinh văn bản kèm fallback qua các model khả dụng. Trả về (text, model_used)."""
    def _run(client: genai.Client, model_name: str):
        cfg: Optional[types.GenerateContentConfig] = (
            types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_budget=0))
            if fast and _supports_zero_thinking(model_name)
            else None
        )
        res = client.models.generate_content(model=model_name, contents=contents, config=cfg)
        _record_usage(res, model_name)
        return res.text or ""

    return _call_with_fallback(_run)


def generate_structured(contents: Any, schema: Type[T], fast: bool = False) -> tuple[T, str]:
    """Sinh JSON khớp Pydantic schema kèm fallback model. Trả về (parsed_obj, model_used)."""
    def _run(client: genai.Client, model_name: str):
        cfg_kwargs: dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_schema": schema,
        }
        if fast and _supports_zero_thinking(model_name):
            cfg_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        res = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(**cfg_kwargs),
        )
        _record_usage(res, model_name)
        return schema.model_validate_json(res.text)

    return _call_with_fallback(_run, timeout_ms=25_000)


_QUERY_EMBED_CFG = types.EmbedContentConfig(
    task_type="RETRIEVAL_QUERY",
    output_dimensionality=768,
)


def _normalize_query_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


@lru_cache(maxsize=512)
def _embed_query_cached(norm_text: str) -> Tuple[float, ...]:
    """Tạo & cache vector 768 chiều cho câu hỏi real-time (timeout 5s, tối đa 1 lần retry)."""
    client = get_client(timeout_ms=5_000)
    last_exc: Optional[Exception] = None
    for attempt in range(2):
        try:
            res = client.models.embed_content(
                model=EMBED_MODEL,
                contents=[norm_text],
                config=_QUERY_EMBED_CFG,
            )
            return tuple(res.embeddings[0].values)
        except Exception as exc:
            last_exc = exc
            if attempt == 0:
                time.sleep(0.25)
    raise last_exc  # type: ignore[misc]


def embed_text(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
    """Tạo vector 768 chiều bằng `gemini-embedding-001` (câu hỏi real-time được cache & timeout ngắn 5s)."""
    if task_type.upper() == "RETRIEVAL_QUERY":
        norm = _normalize_query_text(text)
        if not norm:
            return [0.0] * 768
        return list(_embed_query_cached(norm))
    return embed_texts([text], task_type=task_type)[0]


def warmup_gemini_client() -> bool:
    """Mở sẵn kết nối keep-alive tới Gemini Embedding & Text API khi server khởi động."""
    if not has_api_key():
        return False
    try:
        get_client(timeout_ms=25_000)
        _embed_query_cached("warmup")
        return True
    except Exception:
        return False


def _parse_retry_delay_sec(err_msg: str, default: float = 40.0) -> float:
    m = _RETRY_DELAY_RE.search(err_msg)
    if m:
        return min(max(float(m.group(1)) + 2.0, 5.0), 70.0)
    return default


def embed_texts(texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT", batch_size: int = 20) -> List[List[float]]:
    """Tạo vector 768 chiều theo batch, tự động điều tiết tốc độ & retry khi gặp 429 Free Tier."""
    global _EMBED_WINDOW_START, _EMBED_WINDOW_COUNT
    if not texts:
        return []
    client = get_client(timeout_ms=30_000)
    vectors: List[List[float]] = []
    cfg = types.EmbedContentConfig(
        task_type=task_type.upper(),
        output_dimensionality=768,
    )
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        now = time.monotonic()
        if _EMBED_WINDOW_START == 0.0 or (now - _EMBED_WINDOW_START) >= 62.0:
            _EMBED_WINDOW_START = now
            _EMBED_WINDOW_COUNT = 0
        elif _EMBED_WINDOW_COUNT + len(batch) > _EMBED_RPM_SAFE_LIMIT:
            sleep_sec = max(1.0, 62.0 - (now - _EMBED_WINDOW_START))
            print(f"[Embed] Chạm ngưỡng Free Tier (~85 chunks/phút), tạm nghỉ {sleep_sec:.0f}s rồi tiếp tục...")
            time.sleep(sleep_sec)
            _EMBED_WINDOW_START = time.monotonic()
            _EMBED_WINDOW_COUNT = 0

        for attempt in range(6):
            try:
                res = client.models.embed_content(
                    model=EMBED_MODEL,
                    contents=batch,
                    config=cfg,
                )
                vectors.extend(list(e.values) for e in res.embeddings)
                _EMBED_WINDOW_COUNT += len(batch)
                break
            except Exception as exc:
                msg = str(exc)
                if ("429" in msg or "RESOURCE_EXHAUSTED" in msg) and attempt < 5:
                    wait_sec = _parse_retry_delay_sec(msg, default=40.0)
                    print(f"[Embed] Quota 429, đợi {wait_sec:.0f}s rồi thử lại (lần {attempt + 1}/5)...")
                    time.sleep(wait_sec)
                    _EMBED_WINDOW_START = time.monotonic()
                    _EMBED_WINDOW_COUNT = 0
                    continue
                raise
    return vectors
