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


def draw_dashed_rect(draw, x1, y1, x2, y2):
    draw_dashed_line(draw, x1, y1, x2, y1)
    draw_dashed_line(draw, x2, y1, x2, y2)
    draw_dashed_line(draw, x2, y2, x1, y2)
    draw_dashed_line(draw, x1, y2, x1, y1)


def draw_legend(draw, W, H):
    """Draws a crisp bottom legend with actual geometric UML icons (no missing Unicode glyphs)."""
    s = SCALE
    cy = (H - 25) * s
    font_b = f_bold(11.5)
    font_r = f_reg(11.5)

    # Start X position centered across 980px width
    x = 76 * s
    draw.text((x, cy - 7 * s), "Chú thích:", fill="#1e293b", font=font_b)
    x += 74 * s

    # 1. Start node icon
    r = 6 * s
    draw.ellipse([x - r, cy - r, x + r, cy + r], fill="#0f172a", outline="#0f172a")
    draw.text((x + 11 * s, cy - 7 * s), "Start", fill="#334155", font=font_r)
    x += 58 * s

    # 2. Activity pill icon
    draw.rounded_rectangle([x, cy - 7 * s, x + 26 * s, cy + 7 * s], radius=7 * s, fill="#ffffff", outline="#222222", width=int(1.5 * s))
    draw.text((x + 32 * s, cy - 7 * s), "Activity (Hoạt động)", fill="#334155", font=font_r)
    x += 155 * s

    # 3. Diamond icon
    dr = 7 * s
    cx_d = x + 7 * s
    draw.polygon([(cx_d, cy - dr), (cx_d + dr, cy), (cx_d, cy + dr), (cx_d - dr, cy)], fill="#ffffff", outline="#222222", width=int(1.5 * s))
    draw.text((x + 20 * s, cy - 7 * s), "Branch / Merge (Rẽ nhánh)", fill="#334155", font=font_r)
    x += 182 * s

    # 4. Fork / Join bar icon
    draw.rectangle([x, cy - 2.5 * s, x + 22 * s, cy + 2.5 * s], fill="#0f172a")
    draw.text((x + 28 * s, cy - 7 * s), "Fork / Join (Song song)", fill="#334155", font=font_r)
    x += 168 * s

    # 5. Guard condition
    draw.text((x, cy - 7 * s), "[Điều kiện] Guard", fill="#334155", font=font_r)
    x += 112 * s

    # 6. End bullseye icon
    er = 7 * s
    ir = 4 * s
    cx_e = x + 7 * s
    draw.ellipse([cx_e - er, cy - er, cx_e + er, cy + er], fill="#ffffff", outline="#0f172a", width=int(1.5 * s))
    draw.ellipse([cx_e - ir, cy - ir, cx_e + ir, cy + ir], fill="#0f172a")
    draw.text((x + 19 * s, cy - 7 * s), "End", fill="#334155", font=font_r)


def draw_swimlane_frame(draw, W, H, lane_titles, title_banner):
    s = SCALE
    # Outer card shadow & frame (matching reference warm cream style)
    bx1, by1, bx2, by2 = 24 * s, 50 * s, (W - 24) * s, (H - 48) * s
    draw.rectangle([bx1 + 5 * s, by1 + 5 * s, bx2 + 5 * s, by2 + 5 * s], fill="#c8c8c8")
    draw.rectangle([bx1, by1, bx2, by2], fill="#fdf3b7", outline="#333333", width=2 * s)

    # Top title banner
    font_title = f_bold(16)
    tb = draw.textbbox((0, 0), title_banner, font=font_title)
    draw.text(((W * s - (tb[2] - tb[0])) / 2, 16 * s), title_banner, fill="#1e293b", font=font_title)

    # Inner dashed swimlane box
    ix1, iy1, ix2, iy2 = 42 * s, 66 * s, (W - 42) * s, (H - 64) * s
    draw_dashed_rect(draw, ix1, iy1, ix2, iy2)

    n = len(lane_titles)
    lane_w = (ix2 - ix1) / n
    centers = []
    font_lane = f_bold(14)
    for i, ltitle in enumerate(lane_titles):
        lx1 = ix1 + i * lane_w
        lx2 = lx1 + lane_w
        cx = (lx1 + lx2) / 2
        centers.append(cx / s)
        if i > 0:
            draw_dashed_line(draw, lx1, iy1, lx1, iy2)
        bb = draw.textbbox((0, 0), ltitle, font=font_lane)
        tw = bb[2] - bb[0]
        draw.text((cx - tw / 2, iy1 + 12 * s), ltitle, fill="#111111", font=font_lane)
    # Horizontal header separator
    draw_dashed_line(draw, ix1, iy1 + 40 * s, ix2, iy1 + 40 * s)

    # Crisp geometric bottom legend
    draw_legend(draw, W, H)
    return centers


def draw_start(draw, cx, cy, r=14):
    s = SCALE
    cx_s, cy_s, r_s = cx * s, cy * s, r * s
    draw.ellipse([cx_s - r_s + 2 * s, cy_s - r_s + 2 * s, cx_s + r_s + 2 * s, cy_s + r_s + 2 * s], fill="#b5ae87")
    draw.ellipse([cx_s - r_s, cy_s - r_s, cx_s + r_s, cy_s + r_s], fill="#0f172a", outline="#0f172a", width=2 * s)


def draw_end(draw, cx, cy, r=15):
    s = SCALE
    cx_s, cy_s, r_s = cx * s, cy * s, r * s
    ir_s = 9.5 * s
    draw.ellipse([cx_s - r_s + 2 * s, cy_s - r_s + 2 * s, cx_s + r_s + 2 * s, cy_s + r_s + 2 * s], fill="#b5ae87")
    draw.ellipse([cx_s - r_s, cy_s - r_s, cx_s + r_s, cy_s + r_s], fill="#ffffff", outline="#0f172a", width=2 * s)
    draw.ellipse([cx_s - ir_s, cy_s - ir_s, cx_s + ir_s, cy_s + ir_s], fill="#0f172a")


def draw_activity(draw, cx, cy, text, w=196, h=46):
    s = SCALE
    x1, y1 = (cx - w / 2) * s, (cy - h / 2) * s
    x2, y2 = (cx + w / 2) * s, (cy + h / 2) * s
    rad = (h / 2) * s
    draw.rounded_rectangle([x1 + 3 * s, y1 + 3 * s, x2 + 3 * s, y2 + 3 * s], radius=rad, fill="#c4bc91")
    draw.rounded_rectangle([x1, y1, x2, y2], radius=rad, fill="#ffffff", outline="#222222", width=2 * s)
    font = f_reg(12.5)
    lines = text.split("\n")
    lh = 15.5 * s
    th = len(lines) * lh
    sy = cy * s - th / 2
    for i, line in enumerate(lines):
        bb = draw.textbbox((0, 0), line, font=font)
        tw = bb[2] - bb[0]
        draw.text((cx * s - tw / 2, sy + i * lh), line, fill="#111111", font=font)


def draw_diamond(draw, cx, cy, r=18):
    s = SCALE
    cx_s, cy_s, r_s = cx * s, cy * s, r * s
    pts_shadow = [
        (cx_s + 2 * s, cy_s - r_s + 2 * s),
        (cx_s + r_s + 2 * s, cy_s + 2 * s),
        (cx_s + 2 * s, cy_s + r_s + 2 * s),
        (cx_s - r_s + 2 * s, cy_s + 2 * s),
    ]
    pts = [(cx_s, cy_s - r_s), (cx_s + r_s, cy_s), (cx_s, cy_s + r_s), (cx_s - r_s, cy_s)]
    draw.polygon(pts_shadow, fill="#c4bc91")
    draw.polygon(pts, fill="#ffffff", outline="#222222", width=2 * s)


def draw_bar(draw, cx, cy, w=110, h=7):
    s = SCALE
    x1, y1 = (cx - w / 2) * s, (cy - h / 2) * s
    x2, y2 = (cx + w / 2) * s, (cy + h / 2) * s
    draw.rectangle([x1 + 2 * s, y1 + 2 * s, x2 + 2 * s, y2 + 2 * s], fill="#b5ae87")
    draw.rectangle([x1, y1, x2, y2], fill="#0f172a", outline="#0f172a")


def draw_arrow_path(draw, pts, guard="", guard_pos=None):
    s = SCALE
    s_pts = [(x * s, y * s) for x, y in pts]
    for i in range(len(s_pts) - 1):
        draw.line([s_pts[i][0], s_pts[i][1], s_pts[i + 1][0], s_pts[i + 1][1]], fill="#1e293b", width=2 * s)
    x1, y1 = s_pts[-2]
    x2, y2 = s_pts[-1]
    ang = math.atan2(y2 - y1, x2 - x1)
    ah = 10 * s
    a1 = ang + math.pi - 0.45
    a2 = ang + math.pi + 0.45
    draw.line([x2, y2, x2 + ah * math.cos(a1), y2 + ah * math.sin(a1)], fill="#1e293b", width=2 * s)
    draw.line([x2, y2, x2 + ah * math.cos(a2), y2 + ah * math.sin(a2)], fill="#1e293b", width=2 * s)

    if guard:
        font = f_reg(11.5)
        if guard_pos is not None:
            gx, gy = guard_pos[0] * s, guard_pos[1] * s
        else:
            gx = (s_pts[0][0] + s_pts[1][0]) / 2
            gy = (s_pts[0][1] + s_pts[1][1]) / 2 - 11 * s
        bb = draw.textbbox((0, 0), guard, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        draw.rectangle([gx - tw / 2 - 2 * s, gy - th / 2 - 1 * s, gx + tw / 2 + 2 * s, gy + th / 2 + 1 * s], fill="#fdf3b7")
        draw.text((gx - tw / 2, gy - th / 2 - 1 * s), guard, fill="#111111", font=font)


def save_diagram(img, W, H, filename):
    out = img.resize((W, H), Image.Resampling.LANCZOS)
    p1 = DOCS_DIR / filename
    p2 = ART_DIR / filename
    out.save(p1, format="PNG")
    shutil.copyfile(p1, p2)
    print("Saved:", p1)


# ==============================================================================
# SƠ ĐỒ 1: LUỒNG HỎI ĐÁP TRỢ LÝ DINH DƯỠNG AI (LangGraph + RAG + Guardrails)
# ==============================================================================
def gen_act_1():
    W, H = 980, 960
    img = Image.new("RGB", (W * SCALE, H * SCALE), "#ffffff")
    draw = ImageDraw.Draw(img)
    c1, c2, c3 = draw_swimlane_frame(
        draw, W, H,
        ["Bệnh nhân (Patient)", "LangGraph Agent & Guardrails", "RAG pgvector & Gemini LLM"],
        "ACTIVITY DIAGRAM 1: LUỒNG HỎI ĐÁP TRỢ LÝ DINH DƯỠNG AI (UC08)",
    )

    draw_start(draw, c1, 140)
    draw_activity(draw, c1, 210, "Nhập câu hỏi tư vấn\ndinh dưỡng / món ăn")

    draw_activity(draw, c2, 210, "Che thông tin PII &\nKiểm tra Input Guardrail")
    draw_diamond(draw, c2, 290)

    draw_activity(draw, c2, 375, "Từ chối câu hỏi &\nGhi log sự kiện BLOCK")

    draw_bar(draw, c2, 455, w=130)
    draw_activity(draw, c2, 530, "Tải hồ sơ bệnh án &\nHybrid Fast Router (<1ms)")
    draw_activity(draw, c3, 530, "Truy xuất đoạn tài liệu\n(RAG pgvector + Cache)")
    draw_bar(draw, c2, 605, w=130)

    draw_diamond(draw, c2, 665)
    draw_activity(draw, c2, 745, "Đối chiếu ngưỡng Kali/Na/GI\n& Tìm món thay thế")

    draw_activity(draw, c3, 745, "Gemini LLM tổng hợp\ncâu trả lời & Ghi Trace")

    draw_diamond(draw, c1, 745)
    draw_activity(draw, c1, 815, "Xem câu trả lời tư vấn\n& Cảnh báo lâm sàng")
    draw_end(draw, c1, 870)

    draw_arrow_path(draw, [(c1, 154), (c1, 187)])
    draw_arrow_path(draw, [(c1 + 98, 210), (c2 - 98, 210)])
    draw_arrow_path(draw, [(c2, 233), (c2, 272)])

    draw_arrow_path(draw, [(c2, 308), (c2, 352)], guard="[Vi phạm / Lạc đề]", guard_pos=(c2 + 58, 326))
    draw_arrow_path(draw, [(c2 - 98, 375), (c1, 375), (c1, 727)])

    draw_arrow_path(draw, [(c2 + 18, 290), (c2 + 135, 290), (c2 + 135, 455), (c2 + 65, 455)], guard="[Hợp lệ]", guard_pos=(c2 + 80, 278))

    draw_arrow_path(draw, [(c2, 459), (c2, 507)])
    draw_arrow_path(draw, [(c2 + 45, 455), (c3, 455), (c3, 507)])

    draw_arrow_path(draw, [(c2, 553), (c2, 601)])
    draw_arrow_path(draw, [(c3, 553), (c3, 605), (c2 + 65, 605)])

    draw_arrow_path(draw, [(c2, 609), (c2, 647)])
    draw_arrow_path(draw, [(c2, 683), (c2, 722)], guard="[Hỏi món ăn]", guard_pos=(c2 - 48, 700))
    draw_arrow_path(draw, [(c2 + 18, 665), (c3, 665), (c3, 722)], guard="[Hỏi kiến thức chung]", guard_pos=(c2 + 115, 653))

    draw_arrow_path(draw, [(c2 + 98, 745), (c3 - 98, 745)])

    draw_arrow_path(draw, [(c3, 768), (c3, 790), (c1 + 60, 790), (c1 + 60, 745), (c1 + 18, 745)])
    draw_arrow_path(draw, [(c1, 763), (c1, 792)])
    draw_arrow_path(draw, [(c1, 838), (c1, 855)])

    save_diagram(img, W, H, "act_1_hoi_dap_ai.png")


# ==============================================================================
# SƠ ĐỒ 2: LUỒNG LẬP THỰC ĐƠN AI & TỰ ĐỘNG KIỂM DUYỆT (UC06)
# ==============================================================================
def gen_act_2():
    W, H = 980, 930
    img = Image.new("RGB", (W * SCALE, H * SCALE), "#ffffff")
    draw = ImageDraw.Draw(img)
    c1, c2, c3 = draw_swimlane_frame(
        draw, W, H,
        ["Bệnh nhân (Patient)", "Engine Thực đơn & Guardrail", "PostgreSQL & Gemini LLM"],
        "ACTIVITY DIAGRAM 2: LUỒNG LẬP THỰC ĐƠN AI & TỰ ĐỘNG KIỂM DUYỆT (UC06)",
    )

    draw_start(draw, c1, 140)
    draw_activity(draw, c1, 215, "Chọn số ngày (1-7 ngày),\nsố bữa & sở thích")

    draw_bar(draw, c2, 215, w=120)
    draw_activity(draw, c3, 185, "Lọc ngẫu nhiên 96 món\nan toàn & né món cũ")
    draw_activity(draw, c2, 295, "Tải phác đồ mục tiêu &\nhướng dẫn RAG y khoa")
    draw_bar(draw, c2, 375, w=120)

    draw_diamond(draw, c2, 430)
    draw_activity(draw, c3, 430, "Gemini Structured Output\nsinh thực đơn chi tiết")

    draw_activity(draw, c2, 525, "Tự động cân chỉnh gram &\nTính tổng dinh dưỡng ngày")
    draw_activity(draw, c2, 615, "Clinical Guardrail kiểm tra\ntrần Kali, Natri, Đạm, Calo")
    draw_diamond(draw, c2, 695)

    draw_activity(draw, c2, 775, "Tạo cảnh báo món vượt\nngưỡng để yêu cầu sửa")
    draw_activity(draw, c3, 695, "Lưu thực đơn vào CSDL\n& Ghi nhận Trace AI")

    draw_activity(draw, c1, 695, "Xem thực đơn 7 ngày &\nBiểu đồ ngân sách ngày")
    draw_end(draw, c1, 800)

    draw_arrow_path(draw, [(c1, 154), (c1, 192)])
    draw_arrow_path(draw, [(c1 + 98, 215), (c2 - 60, 215)])

    draw_arrow_path(draw, [(c2 + 30, 211), (c2 + 30, 185), (c3 - 98, 185)])
    draw_arrow_path(draw, [(c2, 219), (c2, 272)])

    draw_arrow_path(draw, [(c3, 208), (c3, 375), (c2 + 60, 375)])
    draw_arrow_path(draw, [(c2, 318), (c2, 371)])

    draw_arrow_path(draw, [(c2, 379), (c2, 412)])
    draw_arrow_path(draw, [(c2 + 18, 430), (c3 - 98, 430)])

    draw_arrow_path(draw, [(c3, 453), (c3, 525), (c2 + 98, 525)])
    draw_arrow_path(draw, [(c2, 548), (c2, 592)])
    draw_arrow_path(draw, [(c2, 638), (c2, 677)])

    draw_arrow_path(draw, [(c2, 713), (c2, 752)], guard="[Vượt ngưỡng (Lần 1)]", guard_pos=(c2 + 68, 732))
    draw_arrow_path(draw, [(c2 - 98, 775), (c2 - 135, 775), (c2 - 135, 430), (c2 - 18, 430)])

    draw_arrow_path(draw, [(c2 + 18, 695), (c3 - 98, 695)], guard="[Đạt chuẩn]", guard_pos=(c2 + 78, 682))
    draw_arrow_path(draw, [(c3, 718), (c3, 835), (c1 + 115, 835), (c1 + 115, 695), (c1 + 98, 695)])
    draw_arrow_path(draw, [(c1, 718), (c1, 785)])

    save_diagram(img, W, H, "act_2_lap_thuc_don.png")


# ==============================================================================
# SƠ ĐỒ 3: LUỒNG NẠP PHIẾU XÉT NGHIỆM ĐA ẢNH & KHỚP 24 PHÁC ĐỒ (UC02 & UC03)
# ==============================================================================
def gen_act_3():
    W, H = 980, 940
    img = Image.new("RGB", (W * SCALE, H * SCALE), "#ffffff")
    draw = ImageDraw.Draw(img)
    c1, c2, c3 = draw_swimlane_frame(
        draw, W, H,
        ["Bệnh nhân (Patient)", "Backend & Bộ Khớp Phác đồ", "Gemini Vision OCR & CSDL"],
        "ACTIVITY DIAGRAM 3: LUỒNG NẠP PHIẾU XÉT NGHIỆM ĐA ẢNH & KHỚP PHÁC ĐỒ (UC03)",
    )

    draw_start(draw, c1, 140)
    draw_activity(draw, c1, 215, "Chọn 1 hoặc nhiều ảnh/PDF\nphiếu xét nghiệm")

    draw_activity(draw, c2, 215, "Tính mã băm SHA-256 gộp\n& Kiểm tra trùng phiếu")
    draw_diamond(draw, c2, 300)

    draw_activity(draw, c2, 385, "Trả thông báo phiếu\nđã từng tải lên (409)")

    draw_activity(draw, c2, 485, "Nén chuẩn hóa các ảnh\n(max 1600px)")
    draw_activity(draw, c3, 485, "Gemini Vision đọc gộp\ntất cả trang trong 1 lượt")

    draw_activity(draw, c2, 585, "Chuẩn hóa ngày khám,\nChe PII & Ánh xạ chỉ số")
    draw_activity(draw, c3, 585, "Lưu / Gộp đợt khám &\nchỉ số vào PostgreSQL")

    draw_activity(draw, c2, 685, "Đối chiếu 24 phác đồ BYT\n(QĐ 2879/QĐ-BYT)")
    draw_activity(draw, c3, 685, "Cập nhật mục tiêu Calo,\nĐạm, Na, K, Phospho mới")

    draw_diamond(draw, c1, 685)
    draw_activity(draw, c1, 770, "Xem chỉ số mới & Phác đồ\nđiều trị đã cập nhật")
    draw_end(draw, c1, 835)

    draw_arrow_path(draw, [(c1, 154), (c1, 192)])
    draw_arrow_path(draw, [(c1 + 98, 215), (c2 - 98, 215)])
    draw_arrow_path(draw, [(c2, 238), (c2, 282)])

    draw_arrow_path(draw, [(c2, 318), (c2, 362)], guard="[Phiếu trùng]", guard_pos=(c2 + 48, 336))
    draw_arrow_path(draw, [(c2 - 98, 385), (c1, 385), (c1, 667)])

    # Route [Phiếu mới] cleanly into top center of "Nén chuẩn hóa các ảnh"
    draw_arrow_path(draw, [(c2 + 18, 300), (c2 + 130, 300), (c2 + 130, 438), (c2, 438), (c2, 462)], guard="[Phiếu mới]", guard_pos=(c2 + 78, 288))
    draw_arrow_path(draw, [(c2 + 98, 485), (c3 - 98, 485)])
    draw_arrow_path(draw, [(c3, 508), (c3, 536), (c2, 536), (c2, 562)])
    draw_arrow_path(draw, [(c2 + 98, 585), (c3 - 98, 585)])
    draw_arrow_path(draw, [(c3, 608), (c3, 636), (c2, 636), (c2, 662)])
    draw_arrow_path(draw, [(c2 + 98, 685), (c3 - 98, 685)])
    draw_arrow_path(draw, [(c3, 708), (c3, 735), (c1 + 60, 735), (c1 + 60, 685), (c1 + 18, 685)])
    draw_arrow_path(draw, [(c1, 703), (c1, 747)])
    draw_arrow_path(draw, [(c1, 793), (c1, 820)])

    save_diagram(img, W, H, "act_3_nap_phieu_ocr.png")


# ==============================================================================
# SƠ ĐỒ 4: LUỒNG QUẢN TRỊ RAG & ĐÁNH GIÁ HỆ THỐNG 30 GOLDEN EVALS (UC12 & UC15)
# ==============================================================================
def gen_act_4():
    W, H = 980, 960
    img = Image.new("RGB", (W * SCALE, H * SCALE), "#ffffff")
    draw = ImageDraw.Draw(img)
    c1, c2, c3 = draw_swimlane_frame(
        draw, W, H,
        ["Quản trị viên (Admin)", "Engine Quản trị & Evals", "Gemini Judge, pgvector & Langfuse"],
        "ACTIVITY DIAGRAM 4: LUỒNG NẠP TÀI LIỆU RAG & ĐÁNH GIÁ 30 GOLDEN CASES (UC12 & UC15)",
    )

    draw_start(draw, c1, 140)
    draw_activity(draw, c1, 210, "Truy cập Cổng Quản trị\n(Xác thực quyền Admin)")
    draw_diamond(draw, c1, 295)

    draw_activity(draw, c1, 385, "Tải lên file PDF / Markdown\nhướng dẫn y khoa Bộ Y tế")
    draw_activity(draw, c2, 385, "Trích xuất văn bản &\nCắt đoạn (Chunk + Overlap)")
    draw_activity(draw, c3, 385, "Nhúng vector 768 chiều &\nLưu vào bảng pgvector")

    draw_activity(draw, c1, 510, "Kích hoạt bộ kiểm thử\n30 Golden Cases (Nhanh / E2E)")
    draw_bar(draw, c2, 510, w=125)
    draw_activity(draw, c2, 585, "Chạy kiểm thử 8 ca RAG,\n10 ca Agent & 12 ca Guardrail")
    draw_activity(draw, c3, 585, "Chấm điểm LLM-as-Judge\ntheo Rubric (0.0 -> 1.0)")
    draw_bar(draw, c2, 660, w=125)

    draw_activity(draw, c2, 725, "Tính Pass Rate, False Positive\n& Kiểm tra cổng (Gate >= 90%)")
    draw_activity(draw, c3, 725, "Đồng bộ điểm lên Langfuse\n& Xuất báo cáo Markdown")

    draw_diamond(draw, c1, 725)
    draw_activity(draw, c1, 800, "Xem bảng điểm Evals &\nPhân rã thời gian Traces")
    draw_end(draw, c1, 862)

    draw_arrow_path(draw, [(c1, 154), (c1, 187)])
    draw_arrow_path(draw, [(c1, 233), (c1, 277)])

    draw_arrow_path(draw, [(c1, 313), (c1, 362)], guard="[Quản lý Tài liệu]", guard_pos=(c1 + 55, 334))
    draw_arrow_path(draw, [(c1 + 98, 385), (c2 - 98, 385)])
    draw_arrow_path(draw, [(c2 + 98, 385), (c3 - 98, 385)])
    draw_arrow_path(draw, [(c3, 408), (c3, 445), (c1 - 115, 445), (c1 - 115, 725), (c1 - 18, 725)])

    draw_arrow_path(draw, [(c1 + 18, 295), (c1 + 125, 295), (c1 + 125, 465), (c1, 465), (c1, 487)], guard="[Đánh giá Hệ thống]", guard_pos=(c1 + 78, 283))
    draw_arrow_path(draw, [(c1 + 98, 510), (c2 - 63, 510)])

    draw_arrow_path(draw, [(c2, 514), (c2, 562)])
    draw_arrow_path(draw, [(c2 + 45, 510), (c3, 510), (c3, 562)])
    draw_arrow_path(draw, [(c2, 608), (c2, 656)])
    draw_arrow_path(draw, [(c3, 608), (c3, 660), (c2 + 63, 660)])

    draw_arrow_path(draw, [(c2, 664), (c2, 702)])
    draw_arrow_path(draw, [(c2 + 98, 725), (c3 - 98, 725)])
    draw_arrow_path(draw, [(c3, 748), (c3, 775), (c1 + 60, 775), (c1 + 60, 725), (c1 + 18, 725)])
    draw_arrow_path(draw, [(c1, 743), (c1, 777)])
    draw_arrow_path(draw, [(c1, 823), (c1, 847)])

    save_diagram(img, W, H, "act_4_quan_tri_evals.png")


if __name__ == "__main__":
    gen_act_1()
    gen_act_2()
    gen_act_3()
    gen_act_4()
