import math
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

DOCS_DIR = Path(r"D:\Nuttrition.AI bản 2\NutritionAI\docs")
ART_DIR = Path(r"C:\Users\Lenovo\.gemini\antigravity\brain\a89a584f-080c-437e-b276-ee709ec44d61")
DOCS_DIR.mkdir(parents=True, exist_ok=True)
ART_DIR.mkdir(parents=True, exist_ok=True)

SCALE = 2
FONT_REG = r"C:\Windows\Fonts\arial.ttf"
FONT_BOLD = r"C:\Windows\Fonts\arialbd.ttf"


def f_reg(size):
    return ImageFont.truetype(FONT_REG, int(size * SCALE))


def f_bold(size):
    return ImageFont.truetype(FONT_BOLD, int(size * SCALE))


def draw_dashed_line(draw, x1, y1, x2, y2, dash=7, gap=5, color="#222222", width=2):
    s = SCALE
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy)
    if dist < 1:
        return
    ux, uy = dx / dist, dy / dist
    d_s, g_s = dash * s, gap * s
    pos = 0.0
    while pos < dist:
        end = min(dist, pos + d_s)
        draw.line([x1 + ux * pos, y1 + uy * pos, x1 + ux * end, y1 + uy * end], fill=color, width=width * s)
        pos += d_s + g_s


def draw_arrow_path(draw, pts, guard="", guard_pos=None, color="#1e293b", bg_fill="#f8fafc", dashed=False):
    s = SCALE
    s_pts = [(x * s, y * s) for x, y in pts]
    for i in range(len(s_pts) - 1):
        if dashed:
            draw_dashed_line(draw, s_pts[i][0], s_pts[i][1], s_pts[i + 1][0], s_pts[i + 1][1], dash=6, gap=4, color=color, width=2)
        else:
            draw.line([s_pts[i][0], s_pts[i][1], s_pts[i + 1][0], s_pts[i + 1][1]], fill=color, width=2 * s)
    x1, y1 = s_pts[-2]
    x2, y2 = s_pts[-1]
    ang = math.atan2(y2 - y1, x2 - x1)
    ah = 9 * s
    a1 = ang + math.pi - 0.45
    a2 = ang + math.pi + 0.45
    draw.line([x2, y2, x2 + ah * math.cos(a1), y2 + ah * math.sin(a1)], fill=color, width=2 * s)
    draw.line([x2, y2, x2 + ah * math.cos(a2), y2 + ah * math.sin(a2)], fill=color, width=2 * s)

    if guard:
        font = f_bold(10.8)
        if guard_pos is not None:
            gx, gy = guard_pos[0] * s, guard_pos[1] * s
        else:
            gx = (s_pts[0][0] + s_pts[1][0]) / 2
            gy = (s_pts[0][1] + s_pts[1][1]) / 2 - 11 * s
        bb = draw.textbbox((0, 0), guard, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        draw.rectangle([gx - tw / 2 - 3 * s, gy - th / 2 - 1.5 * s, gx + tw / 2 + 3 * s, gy + th / 2 + 1.5 * s], fill=bg_fill)
        draw.text((gx - tw / 2, gy - th / 2 - 1 * s), guard, fill=color, font=font)


def save_diagram(img, W, H, filename):
    out = img.resize((W, H), Image.Resampling.LANCZOS)
    p1 = DOCS_DIR / filename
    p2 = ART_DIR / filename
    out.save(p1, format="PNG")
    shutil.copyfile(p1, p2)
    print("Saved:", p1)


def _render_workflow(filename, is_technical=False):
    W, H = 1160, 1000
    s = SCALE
    img = Image.new("RGB", (W * s, H * s), "#ffffff")
    draw = ImageDraw.Draw(img)

    # Outer frame
    bx1, by1, bx2, by2 = 20 * s, 48 * s, (W - 20) * s, (H - 44) * s
    draw.rectangle([bx1 + 5 * s, by1 + 5 * s, bx2 + 5 * s, by2 + 5 * s], fill="#d4d4d8")
    draw.rectangle([bx1, by1, bx2, by2], fill="#f8fafc", outline="#334155", width=2 * s)

    title = (
        "SƠ ĐỒ KIẾN TRÚC LANGGRAPH AGENT WORKFLOW (STATEGRAPH & CLINICAL GUARDRAILS)"
        if is_technical
        else "SƠ ĐỒ LUỒNG HOẠT ĐỘNG CỦA TRỢ LÝ AI (AI AGENT WORKFLOW)"
    )
    ft = f_bold(16)
    tb = draw.textbbox((0, 0), title, font=ft)
    draw.text(((W * s - (tb[2] - tb[0])) / 2, 15 * s), title, fill="#0f172a", font=ft)

    def draw_node_box(cx, cy, w, h, badge, title_txt, sub_txt, fill_bg="#ffffff", border_col="#1e293b", badge_bg="#0f172a", title_col="#0f172a"):
        x1, y1 = (cx - w / 2) * s, (cy - h / 2) * s
        x2, y2 = (cx + w / 2) * s, (cy + h / 2) * s
        rad = 12 * s
        draw.rounded_rectangle([x1 + 3 * s, y1 + 3 * s, x2 + 3 * s, y2 + 3 * s], radius=rad, fill="#cbd5e1")
        draw.rounded_rectangle([x1, y1, x2, y2], radius=rad, fill=fill_bg, outline=border_col, width=2 * s)

        fb = f_bold(10.5)
        bb = draw.textbbox((0, 0), badge, font=fb)
        bw = (bb[2] - bb[0]) + 18 * s
        bh = 18 * s
        bx_1 = cx * s - bw / 2
        by_1 = y1 - 9 * s
        draw.rounded_rectangle([bx_1, by_1, bx_1 + bw, by_1 + bh], radius=9 * s, fill=badge_bg)
        draw.text((cx * s - (bb[2] - bb[0]) / 2, by_1 + 2 * s), badge, fill="#ffffff", font=fb)

        ft_n = f_bold(12.8)
        t_lines = title_txt.split("\n")
        curr_y = y1 + (13 * s if sub_txt else 14 * s)
        for line in t_lines:
            lbb = draw.textbbox((0, 0), line, font=ft_n)
            draw.text((cx * s - (lbb[2] - lbb[0]) / 2, curr_y), line, fill=title_col, font=ft_n)
            curr_y += 15.8 * s

        if sub_txt:
            fs_n = f_reg(11.2)
            curr_y += 2 * s
            for line in sub_txt.split("\n"):
                lbb = draw.textbbox((0, 0), line, font=fs_n)
                draw.text((cx * s - (lbb[2] - lbb[0]) / 2, curr_y), line, fill="#475569", font=fs_n)
                curr_y += 14.2 * s

    def draw_diamond_node(cx, cy, r, label):
        cx_s, cy_s, r_s = cx * s, cy * s, r * s
        pts_sh = [
            (cx_s + 2 * s, cy_s - r_s + 2 * s),
            (cx_s + r_s * 1.95 + 2 * s, cy_s + 2 * s),
            (cx_s + 2 * s, cy_s + r_s + 2 * s),
            (cx_s - r_s * 1.95 + 2 * s, cy_s + 2 * s),
        ]
        pts = [(cx_s, cy_s - r_s), (cx_s + r_s * 1.95, cy_s), (cx_s, cy_s + r_s), (cx_s - r_s * 1.95, cy_s)]
        draw.polygon(pts_sh, fill="#cbd5e1")
        draw.polygon(pts, fill="#fef9c3", outline="#ca8a04", width=2 * s)
        fd = f_bold(11)
        lines = label.split("\n")
        lh = 13.5 * s
        sy = cy_s - (len(lines) * lh) / 2
        for i, line in enumerate(lines):
            bb = draw.textbbox((0, 0), line, font=fd)
            draw.text((cx_s - (bb[2] - bb[0]) / 2, sy + i * lh), line, fill="#713f12", font=fd)

    mid = W / 2  # 580

    if not is_technical:
        # Easy Vietnamese version
        draw_node_box(
            mid, 92, 360, 50,
            "ĐẦU VÀO (START)",
            "Yêu cầu từ Bệnh nhân",
            "Câu hỏi tư vấn / Tên món ăn / Yêu cầu lập thực đơn",
            fill_bg="#e0f2fe", border_col="#0284c7", badge_bg="#0369a1",
        )
        draw_node_box(
            mid, 180, 435, 62,
            "BƯỚC 1: TẢI NGỮ CẢNH Y KHOA",
            "Tải Hồ sơ Bệnh án & Khớp 24 Phác đồ",
            "Đọc bệnh lý, dị ứng, xét nghiệm mới nhất -> Tính trần Calo, Đạm, Na, K",
            fill_bg="#ffffff", border_col="#0f766e", badge_bg="#0f766e",
        )
        draw_node_box(
            mid, 276, 435, 62,
            "BƯỚC 2: CHỐT CHẶN AN TOÀN ĐẦU VÀO",
            "Ẩn Thông tin Cá nhân & Kiểm duyệt Câu hỏi",
            "Che SĐT/CCCD/Email & Kiểm tra câu hỏi độc hại / ngoài phạm vi y tế",
            fill_bg="#fff1f2", border_col="#be123c", badge_bg="#be123c",
        )
        draw_diamond_node(mid, 358, 25, "Câu hỏi\nhợp lệ?")
        draw_node_box(
            mid, 446, 420, 60,
            "BƯỚC 3: BỘ ĐỊNH TUYẾN Ý ĐỊNH",
            "Phân loại Mục đích Yêu cầu",
            "Tự động nhận diện yêu cầu thuộc 1 trong 4 nhánh nghiệp vụ (<1ms)",
            fill_bg="#eff6ff", border_col="#1d4ed8", badge_bg="#1d4ed8",
        )
        b_xs = [160, 415, 665, 975]
        b_y = 622
        draw_node_box(
            b_xs[0], b_y, 226, 120,
            "NHÁNH 1: TRA CỨU MÓN",
            "Tra cứu Thành phần\nDinh dưỡng",
            "- Tìm trong CSDL 690 món Việt\n- Đối chiếu quy tắc hạn chế\n- Tổng hợp 15 chỉ số vi chất\n& giải thích dễ hiểu",
            fill_bg="#ffffff", border_col="#0369a1", badge_bg="#0369a1",
        )
        draw_node_box(
            b_xs[1], b_y, 226, 120,
            "NHÁNH 2: THẨM ĐỊNH MÓN",
            "Kiểm tra Độ An toàn\n& Gợi ý Món Thay thế",
            "- So sánh ngưỡng Kali/Muối/GI\n- Phân loại: An toàn / Hạn chế / Cấm\n- Tìm món thay thế cùng nhóm\n- Kèm trích dẫn tài liệu Bộ Y tế",
            fill_bg="#ffffff", border_col="#0f766e", badge_bg="#0f766e",
        )
        draw_node_box(
            b_xs[2], b_y, 226, 120,
            "NHÁNH 3: LẬP THỰC ĐƠN",
            "Thiết kế Thực đơn AI\n& Tự động Cân chỉnh",
            "- Lọc ngẫu nhiên 96 món an toàn\n- AI sinh thực đơn theo ngày/bữa\n- Tự động cân chỉnh định lượng (g)\n- Kiểm tra tổng ngân sách ngày",
            fill_bg="#fefce8", border_col="#b45309", badge_bg="#b45309",
        )
        draw_node_box(
            b_xs[3], b_y, 226, 120,
            "NHÁNH 4: HỎI ĐÁP Y KHOA",
            "Tra cứu Kho Tri thức\n& Tư vấn Lâm sàng",
            "- Tìm đoạn tài liệu Bộ Y tế\n  tương đồng nhất (Kho tri thức)\n- Kết hợp hồ sơ bệnh nhân\n- AI tổng hợp lời khuyên chuẩn",
            fill_bg="#ffffff", border_col="#6d28d9", badge_bg="#6d28d9",
        )
        draw_node_box(
            b_xs[2], 744, 226, 48,
            "VÒNG LẶP TỰ SỬA LỖI",
            "Kiểm duyệt Trần Dinh dưỡng",
            "Nếu vượt ngưỡng -> Yêu cầu AI sửa lại",
            fill_bg="#fff7ed", border_col="#ea580c", badge_bg="#ea580c",
        )
        draw_node_box(
            mid, 845, 490, 62,
            "BƯỚC 5: CHỐT CHẶN ĐẦU RA & GIÁM SÁT",
            "Kiểm duyệt Phản hồi, Đính kèm Lưu ý Y khoa & Lưu Nhật ký",
            "Kiểm tra rò rỉ thông tin lần cuối + Ghi nhận thời gian xử lý từng bước",
            fill_bg="#f0fdf4", border_col="#15803d", badge_bg="#15803d",
        )
        draw_node_box(
            mid, 920, 360, 38,
            "ĐẦU RA (END)",
            "Trả Kết quả Tư vấn / Thực đơn cho Bệnh nhân",
            "",
            fill_bg="#0f172a", border_col="#0f172a", badge_bg="#334155", title_col="#ffffff",
        )
        branch_guards = ["[Hỏi thành phần]", "[Hỏi ăn được không]", "[Yêu cầu thực đơn]", "[Hỏi kiến thức bệnh]"]
        block_label = "[Vi phạm / Lạc đề -> Chặn sớm & Từ chối trả lời]"
        pass_label = "[Hợp lệ]"
        loop_label = "[Vượt ngưỡng -> Sửa]"
    else:
        # Full technical version (LangGraph StateGraph + RAG pgvector + Guardrails + Observability)
        draw_node_box(
            mid, 92, 420, 50,
            "START (AgentState)",
            "User Query / Meal Plan Request",
            "patient_id, user_query, forced_intent, num_days, meals_per_day",
            fill_bg="#e0f2fe", border_col="#0284c7", badge_bg="#0369a1",
        )
        draw_node_box(
            mid, 180, 470, 62,
            "NODE 1: node_load_context (Tool)",
            "Patient Context Loader & MoH Regime Matcher",
            "get_patient_context() + match_and_compute_target() (24 phác đồ QĐ 2879/BYT)",
            fill_bg="#ffffff", border_col="#0f766e", badge_bg="#0f766e",
        )
        draw_node_box(
            mid, 276, 470, 62,
            "NODE 2: node_input_guardrail (Guardrail)",
            "PII Redaction & Input Safety Filter",
            "mask_pii_text() (Regex PII) + check_input_safety() (Prompt Injection / Off-topic)",
            fill_bg="#fff1f2", border_col="#be123c", badge_bg="#be123c",
        )
        draw_diamond_node(mid, 358, 25, "input_blocked\n== False?")
        draw_node_box(
            mid, 446, 470, 60,
            "NODE 3: node_route (Hybrid Intent Router)",
            "Fast-Path Regex (<1ms) + Gemini Structured Output",
            "classify_intent() -> IntentClassification + search_food() (PostgreSQL pg_trgm)",
            fill_bg="#eff6ff", border_col="#1d4ed8", badge_bg="#1d4ed8",
        )
        b_xs = [160, 415, 665, 975]
        b_y = 622
        draw_node_box(
            b_xs[0], b_y, 232, 122,
            "NODE 4A: node_handle_lookup",
            "Nutrition Lookup\n& Rule Evaluation",
            "- search_food() (690 món Viện DD)\n- validate_food_for_patient()\n- Đối chiếu food_restriction_rules\n- Gemini 2.5 Flash tổng hợp",
            fill_bg="#ffffff", border_col="#0369a1", badge_bg="#0369a1",
        )
        draw_node_box(
            b_xs[1], b_y, 232, 122,
            "NODE 4B: node_handle_safety",
            "Clinical Safety Check\n& RAG Citation",
            "- validate_food() (PASS/WARN/BLOCK)\n- find_alternatives() (món thay thế)\n- search_knowledge() (pgvector 768d)\n- Gemini 2.5 Flash + Citation BYT",
            fill_bg="#ffffff", border_col="#0f766e", badge_bg="#0f766e",
        )
        draw_node_box(
            b_xs[2], b_y, 232, 122,
            "NODE 4C: node_handle_meal_plan",
            "Structured Meal Planner\n& Gram Auto-Scaler",
            "- Pool 96 món PASS (ORDER BY random)\n- Gemini Structured JSON (DayMealPlan)\n- _auto_balance_day_plan() (cân gram)\n- Tính tổng Kcal, Protein, Na, K, P",
            fill_bg="#fefce8", border_col="#b45309", badge_bg="#b45309",
        )
        draw_node_box(
            b_xs[3], b_y, 232, 122,
            "NODE 4D: node_handle_general",
            "Hybrid RAG Retrieval\n& Clinical Synthesis",
            "- Embed query (gemini-embedding-001)\n- LRU Cache + Cosine pgvector Top-K\n- Keyword Fallback khi timeout\n- Gemini 2.5 Flash cá nhân hóa",
            fill_bg="#ffffff", border_col="#6d28d9", badge_bg="#6d28d9",
        )
        draw_node_box(
            b_xs[2], 746, 232, 50,
            "SELF-CORRECTION LOOP",
            "Clinical Guardrail Validator",
            "validate_daily_meal_plan() (Retry <= 1)",
            fill_bg="#fff7ed", border_col="#ea580c", badge_bg="#ea580c",
        )
        draw_node_box(
            mid, 845, 520, 62,
            "NODE 5: node_output_guardrail & Observability",
            "Output PII Scrubbing, Medical Disclaimer & Span Tracing",
            "mask_pii_text() + finish_run_log(span_timings JSONB) + Langfuse OpenTelemetry",
            fill_bg="#f0fdf4", border_col="#15803d", badge_bg="#15803d",
        )
        draw_node_box(
            mid, 920, 390, 38,
            "END (Final AgentState)",
            "Return final_response, meal_plan, trace_id, usage",
            "",
            fill_bg="#0f172a", border_col="#0f172a", badge_bg="#334155", title_col="#ffffff",
        )
        branch_guards = ["[NUTRITION_LOOKUP]", "[SAFETY_CHECK]", "[MEAL_PLANNING]", "[GENERAL]"]
        block_label = "[input_blocked == True -> Early Exit (BLOCK)]"
        pass_label = "[route]"
        loop_label = "[Fail -> Regenerate]"

    # CONNECTIONS
    draw_arrow_path(draw, [(mid, 117), (mid, 140)])
    draw_arrow_path(draw, [(mid, 211), (mid, 236)])
    draw_arrow_path(draw, [(mid, 307), (mid, 333)])
    draw_arrow_path(draw, [(mid, 383), (mid, 407)], guard=pass_label, guard_pos=(mid + 36, 394))

    # Blocked shortcut from Diamond 1 -> Output Guardrail
    draw_arrow_path(
        draw,
        [(mid - 49, 358), (38, 358), (38, 845), (mid - (260 if is_technical else 245), 845)],
        guard=block_label,
        guard_pos=(260, 344),
        color="#be123c",
        dashed=True,
    )

    # Router -> 4 branches via horizontal distribution bus at y=498
    draw.line([(mid * s, 476 * s), (mid * s, 498 * s)], fill="#1e293b", width=2 * s)
    draw.line([(b_xs[0] * s, 498 * s), (b_xs[3] * s, 498 * s)], fill="#1e293b", width=2 * s)
    for bx, bg in zip(b_xs, branch_guards):
        draw_arrow_path(draw, [(bx, 498), (bx, 552)], guard=bg, guard_pos=(bx, 520))

    # Branch 3 -> Self-correction loop
    draw_arrow_path(draw, [(b_xs[2] - 35, 683), (b_xs[2] - 35, 711)], color="#ea580c")
    draw_arrow_path(
        draw,
        [(b_xs[2] + 116, 746), (b_xs[2] + 150, 746), (b_xs[2] + 150, 622), (b_xs[2] + 116, 622)],
        guard=loop_label,
        guard_pos=(b_xs[2] + 152, 697),
        color="#ea580c",
        dashed=True,
    )

    # Merge 4 branches into Output Guardrail via bus at y=786
    for i, bx in enumerate(b_xs):
        start_y = 771 if i == 2 else 683
        draw.line([(bx * s, start_y * s), (bx * s, 786 * s)], fill="#1e293b", width=2 * s)
    draw.line([(b_xs[0] * s, 786 * s), (b_xs[3] * s, 786 * s)], fill="#1e293b", width=2 * s)
    draw_arrow_path(draw, [(mid, 786), (mid, 805)])

    # Output Guardrail -> END
    draw_arrow_path(draw, [(mid, 876), (mid, 892)])

    # Footer legend
    f_leg = f_reg(11.5)
    leg = (
        "Chú thích:   [Node nét liền] LangGraph StateGraph Node   |   [Hình thoi vàng] Conditional Edge   |   [Mũi tên nét đứt] Early-Exit Block / Self-Correction Loop"
        if is_technical
        else "Chú thích:   [Hộp nét liền] Bước xử lý trong Agent   |   [Hình thoi vàng] Điểm kiểm tra điều kiện   |   [Mũi tên nét đứt] Luồng chặn sớm / Vòng lặp tự sửa lỗi"
    )
    lb = draw.textbbox((0, 0), leg, font=f_leg)
    draw.text(((W * s - (lb[2] - lb[0])) / 2, (H - 28) * s), leg, fill="#334155", font=f_leg)

    save_diagram(img, W, H, filename)


if __name__ == "__main__":
    _render_workflow("agent_workflow_diagram.png", is_technical=False)
    _render_workflow("agent_workflow_technical.png", is_technical=True)
