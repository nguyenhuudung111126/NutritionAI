"""Giao diện Streamlit cho NutriGuard AI – Trợ lý Dinh dưỡng Lâm sàng."""
import sys
from pathlib import Path

# Đảm bảo import được `src.*` khi chạy `streamlit run src/app.py`
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from evals.test_safety import run_evals
from src.agent.graph import run_agent
from src.db import get_conn
from src.observability import has_langfuse_config
from src.rag.ingest import (
    delete_knowledge_document,
    ingest_pdf_bytes,
    ingest_text,
    list_knowledge_documents,
    search_knowledge,
)
from src.tools.regime_tool import get_patient_context, match_and_compute_target
from src.vision.lab_extractor import extract_medical_record, save_extracted_checkup

st.set_page_config(page_title="NutriGuard AI", page_icon="🥗", layout="wide")
st.title("🥗 NutriGuard AI – Trợ lý Dinh dưỡng Lâm sàng")


def load_patients():
    with get_conn() as conn:
        return conn.execute("SELECT id::text AS id, nickname FROM patients ORDER BY created_at;").fetchall()


def create_patient_form(key_prefix: str = "new"):
    """Form tạo nhanh hồ sơ bệnh nhân mới lưu thẳng vào PostgreSQL."""
    with st.form(f"{key_prefix}_patient_form"):
        nickname = st.text_input("Tên gọi / Biệt danh", placeholder="VD: Bác Nam")
        c1, c2 = st.columns(2)
        gender = c1.selectbox("Giới tính", ["Nam", "Nữ"])
        birth_year = c2.number_input("Năm sinh", min_value=1920, max_value=2010, value=1968)
        c3, c4 = st.columns(2)
        height_cm = c3.number_input("Chiều cao (cm)", min_value=100.0, max_value=220.0, value=168.0)
        weight_kg = c4.number_input("Cân nặng (kg)", min_value=25.0, max_value=200.0, value=65.0)
        diseases = st.multiselect(
            "Bệnh lý đang mắc",
            ["Đái tháo đường (DTD)", "Bệnh thận mạn (CKD)", "Tăng huyết áp (HTN)"],
        )
        ckd_stage = st.selectbox("Giai đoạn suy thận (nếu có CKD)", ["Không", "1", "2", "3a", "3b", "4", "5"])
        allergies_txt = st.text_input("Dị ứng thực phẩm (cách nhau bởi dấu phẩy)", placeholder="VD: tôm, hải sản, lạc")
        submitted = st.form_submit_button("💾 Lưu hồ sơ vào CSDL", type="primary")

        if submitted and nickname.strip():
            allergies = [a.strip() for a in allergies_txt.split(",") if a.strip()]
            with get_conn() as conn:
                u = conn.execute(
                    "INSERT INTO app_users (email, display_name) VALUES ('default@nutriguard.ai', 'Default') "
                    "ON CONFLICT (email) DO UPDATE SET display_name = EXCLUDED.display_name RETURNING id;"
                ).fetchone()
                p = conn.execute(
                    """
                    INSERT INTO patients (user_id, nickname, gender, birth_year, height_cm, food_allergies)
                    VALUES (%s, %s, %s::gender_type, %s, %s, %s::text[])
                    RETURNING id::text AS id;
                    """,
                    (u["id"], nickname.strip(), gender, int(birth_year), float(height_cm), allergies),
                ).fetchone()
                pid = p["id"]
                conn.execute(
                    "INSERT INTO checkups (patient_id, checkup_date, weight_kg, source) VALUES (%s, CURRENT_DATE, %s, 'MANUAL');",
                    (pid, float(weight_kg)),
                )
                code_map = {"Đái tháo đường (DTD)": "DTD", "Bệnh thận mạn (CKD)": "CKD", "Tăng huyết áp (HTN)": "HTN"}
                for d_label in diseases:
                    d_code = code_map[d_label]
                    stage_id = None
                    if d_code == "CKD" and ckd_stage != "Không":
                        s_row = conn.execute(
                            "SELECT cs.id FROM condition_stages cs JOIN conditions c ON c.id = cs.condition_id "
                            "WHERE c.code = 'CKD' AND cs.stage_code = %s;",
                            (ckd_stage,),
                        ).fetchone()
                        stage_id = s_row["id"] if s_row else None
                    conn.execute(
                        "INSERT INTO patient_conditions (patient_id, condition_id, stage_id) "
                        "SELECT %s, id, %s FROM conditions WHERE code = %s;",
                        (pid, stage_id, d_code),
                    )
            match_and_compute_target(pid, save_to_db=True)
            st.success(f"Đã tạo hồ sơ '{nickname}'!")
            st.rerun()


try:
    patients = load_patients()
except Exception as e:
    st.error(f"Chưa kết nối được PostgreSQL. Hãy kiểm tra file `.env` (`DATABASE_URL`).\nChi tiết: {e}")
    st.stop()

if not patients:
    st.info("Chưa có hồ sơ bệnh nhân nào trong CSDL. Hãy tạo hồ sơ đầu tiên ngay dưới đây:")
    create_patient_form("init")
    st.stop()

# --- SIDEBAR: Chọn bệnh nhân & Upload phiếu khám ---
with st.sidebar:
    st.header("👤 Hồ sơ Bệnh nhân")
    patient_map = {p["nickname"]: p["id"] for p in patients}
    selected_name = st.selectbox("Chọn hồ sơ:", list(patient_map.keys()))
    patient_id = patient_map[selected_name]

    ctx = get_patient_context(patient_id)
    target = match_and_compute_target(patient_id, save_to_db=False)

    st.markdown(f"**Tuổi / Giới:** {ctx['age']} tuổi • {ctx['gender']}")
    st.markdown(f"**Cân nặng / BMI:** {ctx['weight_kg']} kg • BMI {ctx['bmi']}")
    st.markdown(f"**Bệnh lý:** {', '.join(ctx['conditions']) or 'Không có'}")
    st.markdown(f"**Dị ứng:** {', '.join(ctx['food_allergies']) or 'Không'}")
    st.info(
        f"**Phác đồ áp dụng:** `{target['regime_code']}` ({target['regime_name']})\n\n"
        f"- Calo mục tiêu: **{target['energy_kcal']} kcal**\n"
        f"- Đạm: **{target['protein_g']} g** | Natri ≤ **{target['sodium_max_mg']} mg** | Kali ≤ **{target['potassium_max_mg']} mg**"
    )

    st.divider()
    st.subheader("📎 Cập nhật phiếu khám mới")
    if "upload_msg" in st.session_state:
        st.success(st.session_state.pop("upload_msg"))
    uploaded = st.file_uploader("Tải ảnh/PDF kết quả xét nghiệm", type=["png", "jpg", "jpeg", "pdf"])
    custom_checkup_dt = st.date_input("Ngày khám (tùy chọn, để trống = lấy theo phiếu)", value=None)
    if uploaded and st.button("Phân tích & Cập nhật hồ sơ"):
        with st.spinner("AI Vision đang đọc phiếu xét nghiệm..."):
            try:
                rec = extract_medical_record(uploaded.read(), mime_type=uploaded.type)
                res = save_extracted_checkup(
                    patient_id,
                    rec,
                    file_path=uploaded.name,
                    mime_type=uploaded.type,
                    checkup_date_override=(custom_checkup_dt.isoformat() if custom_checkup_dt else None),
                )
                labs_txt = ", ".join(res["matched_labs"]) or "Đã lưu thông tin khám"
                st.session_state["upload_msg"] = (
                    f"Đã cập nhật đợt khám #{res['checkup_id']}! "
                    f"Chỉ số đọc được: {labs_txt}. "
                    f"Phác đồ hiện tại: {res['new_target']['regime_code']}"
                )
                st.rerun()
            except Exception as ex:
                st.error(f"Lỗi đọc phiếu khám: {ex}")

# --- TABS CHÍNH ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💬 Hỏi đáp & Thẩm định món",
    "📅 Lập thực đơn (1 / 3 / 7 ngày)",
    "📈 Lịch sử Tái khám",
    "🛡️ Observability & Guardrails",
    "📚 Kho tri thức RAG (PDF)",
])

with tab1:
    st.caption("Hỏi dinh dưỡng 1 món hoặc kiểm tra an toàn (VD: *'Tôi ăn rau ngót được không?'*, *'100g ức gà có bao nhiêu đạm?'*)")
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    if query := st.chat_input("Nhập câu hỏi dinh dưỡng của bạn..."):
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)
        with st.chat_message("assistant"):
            with st.spinner("Agent đang tra cứu CSDL & kiểm tra Guardrails..."):
                try:
                    out = run_agent(patient_id, query)
                    ans = out.get("final_response", "")
                except Exception as ex:
                    ans = f"Lỗi xử lý: {ex}"
                st.markdown(ans)
        st.session_state.messages.append({"role": "assistant", "content": ans})

with tab2:
    day_choice = st.radio(
        "Chọn số ngày lập thực đơn:",
        ["1 ngày", "3 ngày", "7 ngày"],
        horizontal=True,
    )
    custom_days = int(day_choice.split()[0])

    user_pref = st.text_area(
        "Yêu cầu / Prompt riêng của bạn (tùy chọn):",
        placeholder="VD: Ngân sách tiết kiệm khoảng 60.000đ/ngày, ưu tiên món luộc/hấp đơn giản từ trứng, đậu phụ, bí đao, không ăn cá...",
        height=75,
    )
    gen_btn = st.button("✨ Tạo thực đơn chuẩn y khoa", type="primary")

    if gen_btn:
        period_code = "DAY" if custom_days == 1 else "WEEK"
        with st.spinner("Đang lọc nguyên liệu an toàn, phối món Việt và kiểm tra Guardrail..."):
            try:
                agent_out = run_agent(
                    patient_id=patient_id,
                    user_query=user_pref,
                    forced_intent="MEAL_PLANNING",
                    period=period_code,
                    user_preferences=user_pref,
                    num_days=custom_days,
                )
                res = agent_out["draft_plan"]
                st.success(
                    f"Đã tạo thực đơn #{res['meal_plan_id']} ({res['total_days']} ngày) • "
                    f"Guardrail: {'ĐẠT CHUẨN ✅' if res['guardrail_passed'] else 'CẦN LƯU Ý ⚠️'}"
                )
                note_p = res["plan"].get("note_for_patient")
                if note_p:
                    st.info(f"💡 **Ghi chú cá nhân hóa:** {note_p}")
                food_map = res["food_map"]
                for day, rep in zip(res["plan"].get("days", []), res["day_reports"]):
                    t = rep["totals"]
                    with st.expander(
                        f"Ngày {day['day_index']} — Tổng: {t['energy_kcal']} kcal | Đạm {t['protein_g']}g | Kali {t['potassium_mg']}mg | Natri {t['sodium_mg']}mg",
                        expanded=True,
                    ):
                        for meal in day["meals"]:
                            st.markdown(f"**{meal['meal']}**")
                            for dish in meal["dishes"]:
                                ing_txt = ", ".join(f"{food_map.get(i['food_id'], i['food_id'])} ({i['grams']}g)" for i in dish["ingredients"])
                                st.markdown(f"- **{dish['name']}** (*{dish['cooking_method']}*): {ing_txt}")
            except Exception as ex:
                st.error(f"Không thể tạo thực đơn: {ex}")

with tab3:
    with get_conn() as conn:
        checkups = conn.execute(
            "SELECT id, checkup_date, weight_kg, systolic_bp, diastolic_bp, source FROM checkups WHERE patient_id = %s ORDER BY checkup_date DESC;",
            (patient_id,),
        ).fetchall()
        labs = conn.execute(
            """
            SELECT c.checkup_date, b.code, b.name, lr.value, b.unit, b.normal_min, b.normal_max
            FROM lab_results lr
            JOIN checkups c ON c.id = lr.checkup_id
            JOIN biomarkers b ON b.id = lr.biomarker_id
            WHERE c.patient_id = %s
            ORDER BY c.checkup_date DESC, b.code;
            """,
            (patient_id,),
        ).fetchall()
    st.subheader("Các đợt khám đã lưu")
    st.dataframe(checkups, use_container_width=True)
    st.subheader("Chi tiết chỉ số xét nghiệm theo thời gian")
    st.dataframe(labs, use_container_width=True)

with tab4:
    if has_langfuse_config():
        st.success("🟢 Langfuse Tracing đang BẬT (đẩy trace tự động lên Langfuse Cloud/Host).")
    else:
        st.info("🟡 Langfuse chưa cấu hình key thật trong `.env` (`LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`). Hệ thống đang ghi đầy đủ trace & latency cục bộ vào PostgreSQL.")
    with get_conn() as conn:
        runs = conn.execute(
            "SELECT id, trace_id, workflow, model_name, latency_ms, status, created_at FROM agent_runs ORDER BY id DESC LIMIT 20;"
        ).fetchall()
        events = conn.execute(
            "SELECT id, run_id, stage, guardrail_name, action, detail, created_at FROM guardrail_events ORDER BY id DESC LIMIT 20;"
        ).fetchall()
    st.subheader("Nhật ký Agent Runs (Observability)")
    st.dataframe(runs, use_container_width=True)
    st.subheader("Sự kiện Guardrails đã kích hoạt")
    st.dataframe(events, use_container_width=True)

    st.divider()
    st.subheader("🧪 Kiểm thử An toàn Y khoa (Evals)")
    ev_c1, ev_c2 = st.columns([1, 1])
    if ev_c1.button("⚡ Chạy Eval nhanh (Tier 1 – 0 token)"):
        with st.spinner("Đang chấm điểm phác đồ & Guardrails..."):
            ev_res = run_evals(include_e2e=False)
        st.success(f"Eval Run #{ev_res['eval_run_id']}: Đạt {ev_res['summary']['passed']}/{ev_res['summary']['total']} ({int(ev_res['summary']['pass_rate']*100)}%)")
        st.rerun()
    if ev_c2.button("🚀 Chạy Eval toàn diện (Agent + RAG + PII + Thực đơn)"):
        with st.spinner("Đang chạy toàn bộ 10 ca kiểm thử End-to-End..."):
            ev_res = run_evals(include_e2e=True)
        st.success(f"Eval Run #{ev_res['eval_run_id']}: Đạt {ev_res['summary']['passed']}/{ev_res['summary']['total']} ({int(ev_res['summary']['pass_rate']*100)}%)")
        st.rerun()

    with get_conn() as conn:
        eval_runs = conn.execute(
            "SELECT id, model_name, summary, started_at FROM eval_runs ORDER BY id DESC LIMIT 10;"
        ).fetchall()
        eval_details = conn.execute(
            """
            SELECT er.eval_run_id, ec.category, ec.input->>'case_key' AS case_key,
                   er.passed, er.metrics, er.output, er.trace_id
            FROM eval_results er
            JOIN eval_cases ec ON ec.id = er.case_id
            ORDER BY er.id DESC LIMIT 20;
            """
        ).fetchall()
    st.caption("Lịch sử các lần chấm điểm (eval_runs)")
    st.dataframe(eval_runs, use_container_width=True)
    st.caption("Chi tiết từng ca kiểm thử gần nhất (eval_results)")
    st.dataframe(eval_details, use_container_width=True)

with tab5:
    st.subheader("📥 Nạp tài liệu y khoa mới vào Kho tri thức RAG (PostgreSQL pgvector)")
    st.caption("Hỗ trợ file `.pdf` (kể cả PDF scan qua Gemini OCR), `.md`, `.txt`. Tài liệu sẽ được chuẩn hóa Unicode, cắt chunk theo đề mục kèm overlap và tạo vector 768 chiều.")

    rag_files = st.file_uploader(
        "Chọn 1 hoặc nhiều tài liệu hướng dẫn dinh dưỡng / phác đồ bệnh cùng lúc",
        type=["pdf", "md", "txt"],
        accept_multiple_files=True,
        key="rag_pdf_uploader",
    )
    c_r1, c_r2 = st.columns(2)
    rag_title = c_r1.text_input(
        "Tên tài liệu (bỏ trống để tự lấy tên từng file khi nạp nhiều file)",
        value=(Path(rag_files[0].name).stem if len(rag_files) == 1 else ""),
        placeholder="VD: Hướng dẫn dinh dưỡng bệnh thận - Bộ Y tế",
    )
    rag_source = c_r2.text_input("Nguồn tài liệu", value="Bộ Y tế / Phác đồ lâm sàng", placeholder="VD: Quyết định BYT / KDIGO 2024")
    c_r3, c_r4, c_r5, c_r6 = st.columns(4)
    rag_group = c_r3.selectbox(
        "Nhóm bệnh lý",
        ["Chung", "Đái tháo đường", "Thận-Tiết niệu", "Tim mạch", "Chuyển hóa", "Gan mật"],
    )
    rag_year = c_r4.number_input("Năm xuất bản", min_value=1990, max_value=2030, value=2024)
    rag_max_chars = c_r5.number_input("Kích thước chunk (ký tự)", min_value=300, max_value=2000, value=800, step=100)
    rag_overlap = c_r6.number_input("Overlap (ký tự)", min_value=0, max_value=400, value=120, step=20)

    if st.button(f"🚀 Trích xuất, Chunking & Nạp ({len(rag_files)} file) vào pgvector", type="primary", disabled=(not rag_files)):
        progress = st.progress(0)
        last_res = None
        for idx, rf in enumerate(rag_files):
            with st.spinner(f"Đang xử lý ({idx + 1}/{len(rag_files)}): {rf.name}..."):
                try:
                    raw_bytes = rf.read()
                    doc_title = rag_title.strip() if (len(rag_files) == 1 and rag_title.strip()) else Path(rf.name).stem
                    if rf.name.lower().endswith(".pdf"):
                        res = ingest_pdf_bytes(
                            pdf_bytes=raw_bytes,
                            filename=rf.name,
                            title=doc_title,
                            source=rag_source,
                            group_name=rag_group,
                            published_year=int(rag_year),
                            max_chars=int(rag_max_chars),
                            overlap=int(rag_overlap),
                        )
                        em = res.get("extract_meta", {})
                        st.success(
                            f"[{idx + 1}/{len(rag_files)}] Đã nạp **{res['title']}** (`ID=#{res['document_id']}`): "
                            f"**{res['chunk_count']} chunks** từ {em.get('pages', '?')} trang (`{em.get('extractor', 'pymupdf')}`)."
                        )
                    else:
                        text_data = raw_bytes.decode("utf-8")
                        res = ingest_text(
                            text=text_data,
                            title=doc_title,
                            source=rag_source,
                            group_name=rag_group,
                            published_year=int(rag_year),
                            max_chars=int(rag_max_chars),
                            overlap=int(rag_overlap),
                            source_filename=rf.name,
                        )
                        st.success(f"[{idx + 1}/{len(rag_files)}] Đã nạp **{res['title']}** (`ID=#{res['document_id']}`): **{res['chunk_count']} chunks**.")
                    last_res = res
                except Exception as ex:
                    st.error(f"Lỗi nạp file `{rf.name}`: {ex}")
            progress.progress((idx + 1) / len(rag_files))

        if last_res:
            with st.expander("🔍 Xem trước 3 chunk đầu tiên của tài liệu vừa nạp", expanded=True):
                for c_idx, ch in enumerate(last_res.get("sample_chunks", []), 1):
                    st.markdown(f"**Chunk #{c_idx} — Đề mục:** `{ch['section']}`")
                    st.text(ch["content"])

    st.divider()
    st.subheader("📖 Danh sách tài liệu đã nạp trong PostgreSQL")
    try:
        docs = list_knowledge_documents()
        st.dataframe(docs, use_container_width=True)
        if docs:
            del_col1, del_col2 = st.columns([3, 1])
            del_options = {f"#{d['id']} - {d['title']} ({d['chunk_count']} chunks)": d["id"] for d in docs}
            chosen_del = del_col1.selectbox("Chọn tài liệu cần xóa (nếu muốn nạp lại):", list(del_options.keys()))
            if del_col2.button("🗑️ Xóa tài liệu", use_container_width=True):
                delete_knowledge_document(del_options[chosen_del])
                st.success("Đã xóa tài liệu và toàn bộ vector chunks liên quan.")
                st.rerun()
    except Exception as ex:
        st.warning(f"Chưa đọc được danh sách tài liệu: {ex}")

    st.divider()
    st.subheader("🔎 Kiểm thử truy vấn Vector Search (RAG)")
    rag_test_query = st.text_input("Nhập câu hỏi thử độ khớp ngữ nghĩa trong pgvector:", placeholder="VD: Bệnh nhân suy thận có ăn được quả khế không? Hoặc bệnh Gout kiêng ăn gì?")
    if rag_test_query.strip():
        try:
            hits = search_knowledge(rag_test_query, top_k=3)
            for i, h in enumerate(hits, 1):
                st.markdown(f"**Top {i}** (Độ tương đồng: `{h['similarity']:.3f}` | Nhóm: `{h['group_name']}` | Nguồn: *{h['source']}* | Mục: `{h['section']}`)")
                st.info(h["content"])
        except Exception as ex:
            st.error(f"Lỗi truy vấn RAG: {ex}")
