"""LangGraph Workflow Agent thống nhất điều phối toàn bộ luồng Hỏi đáp, Thẩm định an toàn & Lập thực đơn,
tích hợp PII Guardrail, Hồ sơ cá nhân hóa, RAG pgvector, Self-Correction Loop và Observability."""
from datetime import date
from typing import Any, Dict, Optional, Union

from langgraph.graph import END, START, StateGraph

from src.agent.planner import generate_meal_plan
from src.agent.router import classify_intent
from src.agent.state import AgentState
from src.guardrails.clinical_validator import validate_food_for_patient
from src.guardrails.input_guard import REFUSAL_MESSAGES, check_input_safety
from src.guardrails.pii_masker import mask_pii_text
from src.llm import generate_text, has_api_key
from src.observability import (
    finish_run_log,
    get_langgraph_callbacks,
    log_guardrail_event,
    log_pii_redaction,
    start_run_log,
    trace_agent_run,
    trace_step,
)
from src.rag.ingest import search_knowledge
from src.tools.food_tool import find_alternatives, search_food
from src.tools.regime_tool import get_patient_context, match_and_compute_target


def _node_input_guardrail(state: AgentState) -> AgentState:
    """Node 1: Chốt chặn đầu vào - Ẩn PII + Chặn Prompt Injection & Off-topic."""
    run_id = state.get("run_id")
    raw_q = state.get("raw_query") or state.get("user_query") or ""
    raw_pref = state.get("user_preferences") or ""

    with trace_step("node_input_guardrail", as_type="guardrail", input_data={"has_query": bool(raw_q), "has_pref": bool(raw_pref)}) as span:
        safe_q = mask_pii_text(raw_q)
        safe_pref = mask_pii_text(raw_pref)
        r1 = log_pii_redaction(run_id, "user_query", raw_q, safe_q)
        r2 = log_pii_redaction(run_id, "user_preferences", raw_pref, safe_pref)
        redacted = r1 or r2

        safety_chk = check_input_safety(f"{safe_q} {safe_pref}".strip())
        blocked = safety_chk["action"] == "BLOCK"
        block_cat = safety_chk["category"] if blocked else None
        if blocked and block_cat:
            log_guardrail_event(
                run_id,
                "INPUT",
                block_cat,
                "BLOCK",
                {"matched": safety_chk["matched"], "query_preview": (safe_q or safe_pref)[:160]},
            )
        if span is not None:
            span.update(output={"pii_redacted": redacted, "input_blocked": blocked, "category": block_cat})

    if blocked and block_cat:
        return {
            **state,
            "user_query": safe_q,
            "user_preferences": safe_pref,
            "pii_redacted": redacted,
            "input_blocked": True,
            "input_block_reason": block_cat,
            "intent": f"BLOCKED_{block_cat.upper()}",
            "guardrail_passed": False,
            "guardrail_warnings": [f"Chặn đầu vào ({block_cat})"],
            "model_used": "input-guardrail",
            "final_response": REFUSAL_MESSAGES.get(block_cat, "Yêu cầu bị từ chối bởi hệ thống an toàn."),
        }

    return {
        **state,
        "user_query": safe_q,
        "user_preferences": safe_pref,
        "pii_redacted": redacted,
        "input_blocked": False,
        "input_block_reason": None,
    }


def _node_load_context(state: AgentState) -> AgentState:
    """Node 2: Tải Hồ sơ cá nhân (tuổi, BMI, bệnh lý, xét nghiệm, dị ứng) & tính Phác đồ Bộ Y tế."""
    pid = state["patient_id"]
    with trace_step("node_load_context", as_type="tool", input_data={"patient_id": pid}) as span:
        ctx = get_patient_context(pid)
        target = match_and_compute_target(pid, save_to_db=False)
        if span is not None:
            span.update(output={"regime_code": target.get("regime_code"), "conditions": ctx.get("conditions")})
    return {**state, "patient_profile": ctx, "target_regime": target}


def _node_route(state: AgentState) -> AgentState:
    """Node 3: Phân loại Intent (hoặc nhận thẳng forced_intent từ Tab 2) và tra cứu món ăn ứng viên."""
    forced = state.get("forced_intent")
    if forced:
        return {
            **state,
            "intent": forced,
            "period": state.get("period") or "DAY",
            "retrieved_foods": [],
        }

    with trace_step("node_route", as_type="chain", input_data={"query": state["user_query"]}) as span:
        cls = classify_intent(state["user_query"])
        foods = (
            search_food(cls.food_name or state["user_query"], limit=3)
            if cls.intent in ("NUTRITION_LOOKUP", "SAFETY_CHECK")
            else []
        )
        period = cls.period if cls.period != "NONE" else (state.get("period") or "DAY")
        if span is not None:
            span.update(output={"intent": cls.intent, "food_name": cls.food_name, "food_hits": len(foods)})
    return {
        **state,
        "intent": cls.intent,
        "food_name": cls.food_name,
        "period": period,
        "retrieved_foods": foods,
    }


def _fmt(val: Any, unit: str) -> str:
    return f"{val} {unit}" if val is not None else "Chưa có số liệu"


def _format_patient_summary(ctx: Dict[str, Any], target: Dict[str, Any]) -> str:
    conds = ", ".join(ctx.get("conditions", [])) or "Không có"
    allergies = ", ".join(ctx.get("food_allergies", [])) or "Không"
    return (
        f"Tuổi {ctx.get('age')}, {ctx.get('gender')}, {ctx.get('weight_kg')}kg (BMI {ctx.get('bmi')}), "
        f"Bệnh lý: {conds} (CKD: {ctx.get('ckd_stage') or 'Không'}), Dị ứng: {allergies}. "
        f"Phác đồ: {target.get('regime_code')} ({target.get('regime_name')}) - "
        f"Calo {target.get('energy_kcal')} kcal, Đạm {target.get('protein_g')}g, "
        f"Kali <= {target.get('potassium_max_mg')}mg, Natri <= {target.get('sodium_max_mg')}mg."
    )


def _node_handle_lookup(state: AgentState) -> AgentState:
    """Nhánh 1 (NUTRITION_LOOKUP): Trả số liệu dinh dưỡng chuẩn từ bảng 690 thực phẩm."""
    foods = state.get("retrieved_foods") or []
    if not foods:
        return {
            **state,
            "guardrail_passed": True,
            "model_used": "sql-deterministic",
            "final_response": "Tôi chưa tìm thấy thực phẩm này trong bảng 690 món ăn Việt Nam.",
        }
    f = foods[0]
    msg = (
        f"**Thành phần dinh dưỡng của {f['name']}** (trên 100{f['unit']} ăn được):\n"
        f"- Năng lượng: **{_fmt(f['energy_kcal'], 'kcal')}**\n"
        f"- Protein (Đạm): **{_fmt(f['protein_g'], 'g')}** | Lipid (Béo): **{_fmt(f['lipid_g'], 'g')}** | Glucid (Đường bột): **{_fmt(f['glucid_g'], 'g')}**\n"
        f"- Chất xơ: **{_fmt(f['fiber_g'], 'g')}** | Natri: **{_fmt(f['sodium_mg'], 'mg')}** | Kali: **{_fmt(f['potassium_mg'], 'mg')}** | Phospho: **{_fmt(f['phosphorus_mg'], 'mg')}**\n"
        f"- Chỉ số đường huyết (GI): **{f['gi'] or 'Chưa xác định'}**"
    )
    return {**state, "guardrail_passed": True, "model_used": "sql-deterministic", "final_response": msg}


def _node_handle_safety(state: AgentState) -> AgentState:
    """Nhánh 2 (SAFETY_CHECK): Kết hợp Hồ sơ bệnh nhân + RAG pgvector + Guardrail + Gợi ý món thay thế."""
    pid = state["patient_id"]
    run_id = state.get("run_id")
    ctx = state["patient_profile"]
    target = state["target_regime"]
    foods = state.get("retrieved_foods") or []

    rag_snippets = []
    try:
        with trace_step("rag_search_knowledge", as_type="retriever", input_data={"query": state["user_query"]}) as r_span:
            rag_rows = search_knowledge(state["user_query"], top_k=2)
            rag_snippets = [r["content"] for r in rag_rows]
            if r_span is not None:
                r_span.update(output={"hits": len(rag_snippets)})
    except Exception:
        pass

    if not foods:
        return {
            **state,
            "rag_context": rag_snippets,
            "guardrail_passed": True,
            "final_response": "Tôi chưa tìm thấy tên thực phẩm trong CSDL. Bạn vui lòng nêu rõ tên món ăn nhé.",
        }

    food = foods[0]
    with trace_step("guardrail_food_safety", as_type="guardrail", input_data={"food": food["name"]}) as g_span:
        check = validate_food_for_patient(pid, food, run_id=run_id)
        if g_span is not None:
            g_span.update(output=check)

    alts = []
    if check["action"] in ("WARN", "BLOCK"):
        alts = find_alternatives(
            pid,
            max_potassium_mg=200 if target.get("potassium_max_mg") else None,
            require_low_gi=target.get("require_low_gi", False),
            limit=3,
        )

    def _deterministic_reply() -> Dict[str, Any]:
        verdict = "KHÔNG NÊN ĂN" if check["action"] == "BLOCK" else ("CẦN HẠN CHẾ" if check["action"] == "WARN" else "CÓ THỂ ĂN VỚI LƯỢNG PHÙ HỢP")
        alt_text = "\n- **Gợi ý thay thế an toàn:** " + ", ".join(a["name"] for a in alts) if alts else ""
        reasons = "\n- ".join(check["reasons"]) if check["reasons"] else "Các chỉ số trong ngưỡng an toàn."
        return {
            **state,
            "rag_context": rag_snippets,
            "safe_alternatives": alts,
            "guardrail_passed": check["action"] == "PASS",
            "guardrail_warnings": check["reasons"],
            "model_used": "guardrail-deterministic",
            "final_response": f"**Kết luận ({verdict})** cho món **{food['name']}** (phác đồ {target['regime_code']}):\n- {reasons}{alt_text}",
        }

    if not has_api_key():
        return _deterministic_reply()

    prompt = f"""
Bạn là chuyên gia dinh dưỡng lâm sàng. Hãy trả lời câu hỏi: "{state['user_query']}"
HỒ SƠ CÁ NHÂN & PHÁC ĐỒ: {_format_patient_summary(ctx, target)}
SỐ LIỆU MÓN '{food['name']}' (100g): Calo={food['energy_kcal']}, Đạm={food['protein_g']}g, Kali={food['potassium_mg']}mg, Natri={food['sodium_mg']}mg, Phospho={food['phosphorus_mg']}mg, GI={food['gi']}.
KẾT QUẢ GUARDRAIL: {check['action']} - Lý do: {check['reasons']}
GỢI Ý THAY THẾ AN TOÀN: {[a['name'] for a in alts]}
KIẾN THỨC Y KHOA (RAG): {rag_snippets}

Trình bày rõ ràng theo 3 mục: 1. Kết luận (Được ăn / Hạn chế / Không nên), 2. Giải thích dựa trên hồ sơ cá nhân & số liệu thật, 3. Gợi ý món thay thế & cách chế biến.
"""
    try:
        with trace_step("llm_safety_answer", as_type="generation") as gen_span:
            ans, model_used = generate_text(prompt, fast=True)
            if gen_span is not None:
                gen_span.update(output={"model": model_used})
    except Exception:
        return _deterministic_reply()
    return {
        **state,
        "rag_context": rag_snippets,
        "safe_alternatives": alts,
        "guardrail_passed": check["action"] == "PASS",
        "guardrail_warnings": check["reasons"],
        "model_used": model_used,
        "final_response": ans,
    }


def _node_handle_meal_plan(state: AgentState) -> AgentState:
    """Nhánh 3 (MEAL_PLANNING): Lập thực đơn từ Hồ sơ cá nhân + Phác đồ + RAG + Vòng lặp Guardrail tự sửa."""
    pid = state["patient_id"]
    ctx = state["patient_profile"]
    target = state["target_regime"]
    q = (state.get("user_query") or "").lower()
    period = state.get("period") or ("WEEK" if "tuần" in q else ("MONTH" if "tháng" in q else "DAY"))
    prefs = state.get("user_preferences") or state.get("user_query") or ""
    raw_sd = state.get("start_date")
    parsed_sd = date.fromisoformat(raw_sd) if isinstance(raw_sd, str) and raw_sd else None
    num_days = state.get("num_days")

    rag_snippets = []
    try:
        rag_query = f"Nguyên tắc thực đơn và chế biến cho {target.get('regime_name')} {' '.join(ctx.get('conditions', []))}"
        with trace_step("rag_meal_guidelines", as_type="retriever", input_data={"query": rag_query}) as r_span:
            rag_snippets = [r["content"] for r in search_knowledge(rag_query, top_k=2)]
            if r_span is not None:
                r_span.update(output={"hits": len(rag_snippets)})
    except Exception:
        pass

    result = generate_meal_plan(
        patient_id=pid,
        target=target,
        period=period,
        user_preferences=prefs,
        run_id=state.get("run_id"),
        patient_profile=ctx,
        rag_guidelines=rag_snippets,
        start_date=parsed_sd,
        num_days=num_days,
        meals_per_day=state.get("meals_per_day"),
    )
    note = result.get("plan", {}).get("note_for_patient", "")
    note_txt = f"\n\n💡 *Ghi chú:* {note}" if note else ""
    return {
        **state,
        "rag_context": rag_snippets,
        "draft_plan": result,
        "guardrail_passed": result["guardrail_passed"],
        "model_used": result.get("model_used"),
        "final_response": f"Đã lập xong thực đơn **{result['total_days']} ngày** ({result['start_date']} → {result['end_date']}) theo phác đồ **{target['regime_code']}** (Guardrail đạt chuẩn: {result['guardrail_passed']}).{note_txt}",
    }


def _node_handle_general(state: AgentState) -> AgentState:
    """Nhánh 4 (GENERAL): Tư vấn dinh dưỡng y khoa dựa trên Hồ sơ bệnh nhân + Phác đồ + RAG pgvector."""
    ctx = state["patient_profile"]
    target = state["target_regime"]
    rag_snippets = []
    try:
        with trace_step("rag_search_knowledge", as_type="retriever", input_data={"query": state["user_query"]}) as r_span:
            rag_snippets = [r["content"] for r in search_knowledge(state["user_query"], top_k=3)]
            if r_span is not None:
                r_span.update(output={"hits": len(rag_snippets)})
    except Exception:
        pass
    if not has_api_key():
        return {
            **state,
            "guardrail_passed": True,
            "final_response": "Hãy bổ sung GEMINI_API_KEY trong `.env` để tôi tư vấn chi tiết hơn.",
        }
    with trace_step("llm_general_answer", as_type="generation") as gen_span:
        ans, model_used = generate_text(
            f"Bạn là chuyên gia dinh dưỡng lâm sàng.\n"
            f"HỒ SƠ BỆNH NHÂN & PHÁC ĐỒ: {_format_patient_summary(ctx, target)}\n"
            f"TÀI LIỆU Y KHOA (RAG): {rag_snippets}\n"
            f"Câu hỏi: {state['user_query']}",
            fast=True,
        )
        if gen_span is not None:
            gen_span.update(output={"model": model_used})
    return {
        **state,
        "rag_context": rag_snippets,
        "guardrail_passed": True,
        "model_used": model_used,
        "final_response": ans,
    }


def _node_output_guardrail(state: AgentState) -> AgentState:
    """Node cuối: Kiểm tra và ẩn PII lần cuối trên câu trả lời đầu ra trước khi trả về UI."""
    resp = mask_pii_text(state.get("final_response") or "")
    return {
        **state,
        "final_response": resp,
        "guardrail_passed": state.get("guardrail_passed", True),
    }


def _after_input_guardrail(state: AgentState) -> str:
    return "blocked" if state.get("input_blocked") else "route"


def _pick_branch(state: AgentState) -> str:
    return state.get("intent", "GENERAL")


def build_graph():
    """Xây dựng đồ thị LangGraph thống nhất cho toàn bộ hệ thống."""
    g = StateGraph(AgentState)
    g.add_node("input_guardrail", _node_input_guardrail)
    g.add_node("load_context", _node_load_context)
    g.add_node("route", _node_route)
    g.add_node("lookup", _node_handle_lookup)
    g.add_node("safety", _node_handle_safety)
    g.add_node("meal_plan", _node_handle_meal_plan)
    g.add_node("general", _node_handle_general)
    g.add_node("output_guardrail", _node_output_guardrail)

    g.add_edge(START, "load_context")
    g.add_edge("load_context", "input_guardrail")
    g.add_conditional_edges(
        "input_guardrail",
        _after_input_guardrail,
        {
            "blocked": "output_guardrail",
            "route": "route",
        },
    )
    g.add_conditional_edges(
        "route",
        _pick_branch,
        {
            "NUTRITION_LOOKUP": "lookup",
            "SAFETY_CHECK": "safety",
            "MEAL_PLANNING": "meal_plan",
            "GENERAL": "general",
        },
    )
    for node in ("lookup", "safety", "meal_plan", "general"):
        g.add_edge(node, "output_guardrail")
    g.add_edge("output_guardrail", END)
    return g.compile()


def run_agent(
    patient_id: str,
    user_query: str = "",
    forced_intent: Optional[str] = None,
    period: Optional[str] = None,
    user_preferences: str = "",
    start_date: Optional[Union[date, str]] = None,
    num_days: Optional[int] = None,
    meals_per_day: Optional[int] = None,
) -> Dict[str, Any]:
    """Điểm gọi thống nhất cho cả Tab 1 (Hỏi đáp) và Tab 2 (Lập thực đơn),
    chạy trọn vẹn qua LangGraph + ghi log `agent_runs` + đẩy trace Langfuse."""
    workflow_name = "meal_plan" if forced_intent == "MEAL_PLANNING" else "agent_chat"
    meta = start_run_log(patient_id, workflow_name)
    safe_preview = mask_pii_text(user_query or user_preferences)
    sd_str = start_date.isoformat() if isinstance(start_date, date) else start_date

    try:
        app = build_graph()
        callbacks = get_langgraph_callbacks()
        invoke_cfg = {"callbacks": callbacks} if callbacks else None
        with trace_agent_run(
            name=f"nutriguard_{workflow_name}",
            trace_id=meta["trace_id"],
            input_data={
                "patient_id": patient_id,
                "query": safe_preview,
                "forced_intent": forced_intent,
                "period": period,
                "start_date": sd_str,
                "num_days": num_days,
            },
        ) as root_span:
            out = app.invoke(
                {
                    "patient_id": patient_id,
                    "raw_query": user_query,
                    "user_query": user_query,
                    "user_preferences": user_preferences,
                    "forced_intent": forced_intent,
                    "period": period,
                    "start_date": sd_str,
                    "num_days": num_days,
                    "meals_per_day": meals_per_day,
                    "run_id": meta["run_id"],
                    "trace_id": meta["trace_id"],
                },
                config=invoke_cfg,
            )
            if root_span is not None:
                root_span.update(
                    output={
                        "intent": out.get("intent"),
                        "regime_code": (out.get("target_regime") or {}).get("regime_code"),
                        "guardrail_passed": out.get("guardrail_passed"),
                        "model": out.get("model_used"),
                        "response_preview": (out.get("final_response") or "")[:300],
                    }
                )
        finish_run_log(meta, "SUCCESS", model_name=out.get("model_used"))
        out["trace_id"] = meta["trace_id"]
        out["run_id"] = meta["run_id"]
        out["usage"] = dict(meta.get("usage") or {})
        return out
    except Exception as e:
        finish_run_log(meta, "ERROR", str(e))
        raise
