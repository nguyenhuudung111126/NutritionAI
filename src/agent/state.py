"""Trạng thái (State) dùng chung cho LangGraph Workflow Agent thống nhất."""
from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    # Đầu vào & Định danh phiên chạy
    patient_id: str
    raw_query: str
    user_query: str
    user_preferences: str
    forced_intent: Optional[str]   # Nếu truyền từ Tab 2 ("MEAL_PLANNING") sẽ bỏ qua LLM router
    period: Optional[str]          # DAY | WEEK | MONTH
    start_date: Optional[str]      # Ngày bắt đầu thực đơn (YYYY-MM-DD)
    num_days: Optional[int]        # Số ngày tùy chỉnh (1..31)
    meals_per_day: Optional[int]   # Số bữa/ngày linh hoạt (3..6, None = theo phác đồ BYT)
    run_id: Optional[int]
    trace_id: Optional[str]

    # Ngữ cảnh cá nhân hóa (từ node `load_context`)
    patient_profile: Dict[str, Any]
    target_regime: Dict[str, Any]

    # Kết quả phân loại & Công cụ / RAG
    intent: str                    # NUTRITION_LOOKUP | SAFETY_CHECK | MEAL_PLANNING | GENERAL
    food_name: Optional[str]
    retrieved_foods: List[Dict[str, Any]]
    rag_context: List[str]
    safe_alternatives: List[Dict[str, Any]]

    # Kết quả Lập thực đơn & Guardrails
    draft_plan: Dict[str, Any]
    pii_redacted: bool
    input_blocked: bool
    input_block_reason: Optional[str]
    guardrail_passed: bool
    guardrail_warnings: List[str]

    # Đầu ra cuối
    model_used: Optional[str]
    final_response: str
