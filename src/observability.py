"""Observability tập trung (Logs - Traces - Metrics):
- Traces: root trace + span con (LLM / retriever / tool / node / guardrail) đẩy lên Langfuse.
- Metrics: latency, token, chi phí, error rate, guardrail trigger rate (lưu `nutri.agent_runs`).
- Logs: structured JSON log có `trace_id`, đã che PII (`src/logging_setup.py`).
"""
import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Iterator, List, Optional

from src.db import get_conn
from src.llm import DEFAULT_MODEL, start_usage_tracking, stop_usage_tracking
from src.logging_setup import get_logger, trace_id_var

log = get_logger("agent")
_SPAN_LIST_CTX: ContextVar[Optional[List[Dict[str, Any]]]] = ContextVar("span_list_ctx", default=None)


def has_langfuse_config() -> bool:
    """Kiểm tra đã cấu hình key Langfuse thật (không phải placeholder) chưa."""
    pk = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    sk = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    if not pk or not sk or pk.startswith("pk-lf-...") or sk.startswith("sk-lf-..."):
        return False
    host = os.getenv("LANGFUSE_HOST", "").strip()
    if host and not os.getenv("LANGFUSE_BASE_URL"):
        os.environ["LANGFUSE_BASE_URL"] = host
    return True


def start_run_log(patient_id: Optional[str], workflow: str) -> Dict[str, Any]:
    """Tạo bản ghi `RUNNING` trong `nutri.agent_runs`, bật bộ đếm token và gán trace_id cho log."""
    trace_id = uuid.uuid4().hex
    with get_conn() as conn:
        row = conn.execute(
            """
            INSERT INTO agent_runs (trace_id, patient_id, workflow, model_name, status)
            VALUES (%s, %s, %s, %s, 'RUNNING')
            RETURNING id;
            """,
            (trace_id, patient_id, workflow, DEFAULT_MODEL),
        ).fetchone()
    token = trace_id_var.set(trace_id)
    usage = start_usage_tracking()
    spans: List[Dict[str, Any]] = []
    _SPAN_LIST_CTX.set(spans)
    log.info("agent_run_started", extra={"run_id": row["id"], "workflow": workflow})
    return {
        "run_id": row["id"],
        "trace_id": trace_id,
        "t0": time.perf_counter(),
        "usage": usage,
        "spans": spans,
        "_ctx_token": token,
    }


def finish_run_log(
    meta: Dict[str, Any],
    status: str = "SUCCESS",
    error: str = "",
    model_name: Optional[str] = None,
) -> None:
    """Cập nhật latency, trạng thái, model, token & chi phí thực tế vào `nutri.agent_runs`."""
    latency_ms = int((time.perf_counter() - meta["t0"]) * 1000)
    usage = meta.get("usage") or {}
    in_tok = int(usage.get("input_tokens", 0))
    out_tok = int(usage.get("output_tokens", 0))
    cost = float(usage.get("cost_usd", 0.0))
    spans_json = json.dumps(meta.get("spans") or [], ensure_ascii=False)
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE agent_runs
            SET latency_ms = %s, status = %s, error = %s,
                model_name = COALESCE(%s, model_name),
                input_tokens = %s, output_tokens = %s, cost_usd = %s,
                span_timings = %s::jsonb
            WHERE id = %s;
            """,
            (latency_ms, status, error or None, model_name, in_tok, out_tok, cost, spans_json, meta["run_id"]),
        )
    log_fn = log.info if status == "SUCCESS" else log.error
    log_fn(
        "agent_run_finished",
        extra={
            "run_id": meta["run_id"],
            "status": status,
            "latency_ms": latency_ms,
            "model": model_name,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cost_usd": cost,
            "llm_calls": usage.get("llm_calls", 0),
            "error_message": error[:300] if error else None,
        },
    )
    stop_usage_tracking()
    _SPAN_LIST_CTX.set(None)
    try:
        trace_id_var.reset(meta["_ctx_token"])
    except Exception:
        trace_id_var.set(None)


def push_langfuse_score(trace_id: Optional[str], name: str, value: float, comment: str = "") -> bool:
    """Gắn điểm eval (0..1) ngược lại vào trace tương ứng trên Langfuse."""
    if not trace_id or not has_langfuse_config():
        return False
    try:
        from langfuse import get_client

        get_client().create_score(
            trace_id=trace_id,
            name=name,
            value=float(value),
            data_type="NUMERIC",
            comment=(comment or "")[:500],
        )
        return True
    except Exception:
        return False


def flush_langfuse() -> None:
    if not has_langfuse_config():
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:
        pass


def compute_agent_metrics(window_hours: int = 24 * 7) -> Dict[str, Any]:
    """Tổng hợp metrics từ `agent_runs` + `guardrail_events`: p50/p95, token, chi phí, error & trigger rate."""
    with get_conn() as conn:
        overall = conn.execute(
            """
            SELECT count(*) AS total_runs,
                   count(*) FILTER (WHERE status = 'ERROR') AS error_runs,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) AS p50_ms,
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_ms,
                   avg(latency_ms) AS avg_ms,
                   COALESCE(sum(input_tokens), 0) AS input_tokens,
                   COALESCE(sum(output_tokens), 0) AS output_tokens,
                   COALESCE(sum(cost_usd), 0) AS cost_usd,
                   count(*) FILTER (WHERE input_tokens IS NOT NULL AND input_tokens > 0) AS runs_with_tokens
            FROM agent_runs
            WHERE created_at >= now() - make_interval(hours => %s) AND status <> 'RUNNING';
            """,
            (window_hours,),
        ).fetchone()
        by_wf = conn.execute(
            """
            SELECT workflow,
                   count(*) AS runs,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) AS p50_ms,
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_ms,
                   count(*) FILTER (WHERE status = 'ERROR') AS errors,
                   COALESCE(sum(input_tokens + output_tokens), 0) AS tokens,
                   COALESCE(sum(cost_usd), 0) AS cost_usd
            FROM agent_runs
            WHERE created_at >= now() - make_interval(hours => %s) AND status <> 'RUNNING'
            GROUP BY workflow ORDER BY runs DESC;
            """,
            (window_hours,),
        ).fetchall()
        trig = conn.execute(
            """
            SELECT count(DISTINCT ge.run_id) AS triggered_runs
            FROM guardrail_events ge
            JOIN agent_runs ar ON ar.id = ge.run_id
            WHERE ar.created_at >= now() - make_interval(hours => %s)
              AND ge.action IN ('WARN', 'BLOCK', 'REWRITE');
            """,
            (window_hours,),
        ).fetchone()
        by_guard = conn.execute(
            """
            SELECT ge.guardrail_name, ge.action::text AS action, count(*) AS cnt
            FROM guardrail_events ge
            JOIN agent_runs ar ON ar.id = ge.run_id
            WHERE ar.created_at >= now() - make_interval(hours => %s)
            GROUP BY ge.guardrail_name, ge.action ORDER BY cnt DESC;
            """,
            (window_hours,),
        ).fetchall()

    total = int(overall["total_runs"] or 0)
    return {
        "window_hours": window_hours,
        "total_runs": total,
        "error_rate": round((overall["error_runs"] or 0) / total, 4) if total else 0.0,
        "latency_p50_ms": round(float(overall["p50_ms"]), 1) if overall["p50_ms"] is not None else None,
        "latency_p95_ms": round(float(overall["p95_ms"]), 1) if overall["p95_ms"] is not None else None,
        "latency_avg_ms": round(float(overall["avg_ms"]), 1) if overall["avg_ms"] is not None else None,
        "input_tokens": int(overall["input_tokens"] or 0),
        "output_tokens": int(overall["output_tokens"] or 0),
        "cost_usd": round(float(overall["cost_usd"] or 0), 6),
        "runs_with_tokens": int(overall["runs_with_tokens"] or 0),
        "guardrail_trigger_rate": round((trig["triggered_runs"] or 0) / total, 4) if total else 0.0,
        "guardrail_triggered_runs": int(trig["triggered_runs"] or 0),
        "by_workflow": [
            {
                "workflow": r["workflow"],
                "runs": int(r["runs"]),
                "p50_ms": round(float(r["p50_ms"]), 1) if r["p50_ms"] is not None else None,
                "p95_ms": round(float(r["p95_ms"]), 1) if r["p95_ms"] is not None else None,
                "error_rate": round(int(r["errors"]) / int(r["runs"]), 4) if r["runs"] else 0.0,
                "tokens": int(r["tokens"] or 0),
                "cost_usd": round(float(r["cost_usd"] or 0), 6),
            }
            for r in by_wf
        ],
        "by_guardrail": [dict(r) for r in by_guard],
    }


def log_guardrail_event(run_id: Optional[int], stage: str, name: str, action: str, detail: Dict[str, Any]) -> None:
    """Ghi sự kiện guardrail đầu vào (prompt injection / off-topic) vào `guardrail_events` + structured log."""
    if run_id:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO guardrail_events (run_id, stage, guardrail_name, rule_id, action, detail)
                VALUES (%s, %s, %s, NULL, %s::guardrail_action, %s::jsonb);
                """,
                (run_id, stage, name, action, json.dumps(detail, ensure_ascii=False)),
            )
    log.warning("guardrail_triggered", extra={"run_id": run_id, "guardrail": name, "action": action, "stage": stage})


def log_pii_redaction(run_id: Optional[int], field_name: str, raw_text: str, masked_text: str) -> bool:
    """Nếu phát hiện và che PII trong đầu vào, ghi sự kiện `REWRITE` vào `guardrail_events`."""
    if not raw_text or masked_text == raw_text:
        return False
    if run_id:
        detail = {"field": field_name, "action": "masked_pii", "masked_preview": masked_text[:200]}
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO guardrail_events (run_id, stage, guardrail_name, rule_id, action, detail)
                VALUES (%s, 'INPUT', 'pii_redaction', NULL, 'REWRITE'::guardrail_action, %s::jsonb);
                """,
                (run_id, json.dumps(detail, ensure_ascii=False)),
            )
    return True


@contextmanager
def trace_agent_run(
    name: str,
    trace_id: str,
    input_data: Any = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Iterator[Any]:
    """Mở root trace trên Langfuse nếu đã cấu hình key thật; ngược lại bỏ qua an toàn."""
    if not has_langfuse_config():
        yield None
        return

    client = None
    try:
        from langfuse import get_client

        client = get_client()
        with client.start_as_current_observation(
            trace_context={"trace_id": trace_id},
            name=name,
            as_type="agent",
            input=input_data,
            metadata=metadata,
        ) as span:
            yield span
    except Exception:
        yield None
    finally:
        if client is not None:
            try:
                # Đẩy trace Langfuse ngầm để không chặn phản hồi HTTP ~5-7s của người dùng
                threading.Thread(target=client.flush, daemon=True).start()
            except Exception:
                pass


@contextmanager
def trace_step(name: str, as_type: str = "span", input_data: Any = None) -> Iterator[Any]:
    """Mở span con (đo thời gian local vào `span_timings` + đẩy lên Langfuse nếu đang bật)."""
    t0 = time.perf_counter()
    try:
        if not has_langfuse_config():
            yield None
            return
        try:
            from langfuse import get_client

            client = get_client()
            with client.start_as_current_observation(
                name=name,
                as_type=as_type,  # type: ignore[arg-type]
                input=input_data,
            ) as span:
                yield span
        except Exception:
            yield None
    finally:
        spans = _SPAN_LIST_CTX.get()
        if spans is not None:
            ms = round((time.perf_counter() - t0) * 1000, 1)
            spans.append({"name": name, "type": as_type, "ms": ms})


def get_langgraph_callbacks() -> List[Any]:
    """Trả về CallbackHandler của Langfuse cho LangGraph nếu đã cấu hình key thật."""
    if not has_langfuse_config():
        return []
    try:
        from langfuse.langchain import CallbackHandler

        return [CallbackHandler()]
    except Exception:
        return []
