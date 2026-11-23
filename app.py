import streamlit as st
import pandas as pd
import re
from datetime import datetime

# Cấu hình giao diện ứng dụng AI Agent
st.set_page_config(page_title="AI Agent Điều Phối & Tra Cứu Logistics", page_icon="🚚", layout="wide")

# Dữ liệu đơn hàng mẫu của doanh nghiệp vận tải (Knowledge Base / Database)
SAMPLE_ORDERS = [
    {"ma_don": "LOG001", "khach_hang": "Nguyễn Văn An", "sdt": "0901234567", "tuyen": "TP.HCM -> Hà Nội",
     "khoi_luong_kg": 15.5, "loai_hang": "Linh kiện điện tử", "trang_thai": "Đang trung chuyển tại kho Đà Nẵng",
     "du_kien_giao": "25/11/2026", "su_co": "Không"},
    {"ma_don": "LOG002", "khach_hang": "Trần Thị Bình", "sdt": "0912345678", "tuyen": "TP.HCM -> Cần Thơ",
     "khoi_luong_kg": 42.0, "loai_hang": "Hàng tiêu dùng", "trang_thai": "Đang giao hàng (Shipper: Lê Minh - 0988111222)",
     "du_kien_giao": "23/11/2026", "su_co": "Không"},
    {"ma_don": "LOG003", "khach_hang": "Công ty TNHH Minh Phát", "sdt": "0933445566", "tuyen": "Bình Dương -> Hải Phòng",
     "khoi_luong_kg": 320.0, "loai_hang": "Thiết bị công nghiệp", "trang_thai": "Chậm trễ do thời tiết xấu tại miền Trung",
     "du_kien_giao": "26/11/2026 (Trễ 1 ngày)", "su_co": "Cần ưu tiên xử lý & thông báo khách"},
    {"ma_don": "LOG004", "khach_hang": "Phạm Hoàng Nam", "sdt": "0977889900", "tuyen": "Nội thành TP.HCM (Thủ Đức -> Quận 1)",
     "khoi_luong_kg": 3.2, "loai_hang": "Tài liệu & Mẫu vật", "trang_thai": "Giao thành công",
     "du_kien_giao": "23/11/2026", "su_co": "Không"}
]

# Bảng giá cước vận chuyển chuẩn (Pricing Rule Engine)
RATES = {
    "Nội thành": {"base": 25000, "per_kg": 4000, "time": "Trong ngày (4 - 6 giờ)"},
    "Liên tỉnh gần (Miền Nam / Miền Trung)": {"base": 45000, "per_kg": 8500, "time": "1 - 2 ngày"},
    "Liên tỉnh xa (Bắc - Nam)": {"base": 65000, "per_kg": 14000, "time": "3 - 4 ngày"}
}

# Khởi tạo bộ nhớ hội thoại (Agent Memory)
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Xin chào! Tôi là **LogiAgent** – Trợ lý AI tác tử hỗ trợ điều phối vận tải và chăm sóc khách hàng Logistics. Tôi có thể giúp bạn:\n"
                                          "- **Tra cứu trạng thái đơn hàng** (VD: *Kiểm tra đơn LOG001* hoặc *Đơn LOG003 bị gì vậy?*)\n"
                                          "- **Tính báo giá cước vận chuyển tự động** (VD: *Tính cước gửi 25kg hàng dễ vỡ đi Hà Nội*)\n"
                                          "- **Phân tích sự cố & tự động soạn email xin lỗi / điều phối** (VD: *Xử lý sự cố đơn LOG003*)\n"
                                          "- **Tổng hợp báo cáo vận hành** (VD: *Báo cáo tình hình hôm nay*)"}
    ]
if "orders_df" not in st.session_state:
    st.session_state.orders_df = pd.DataFrame(SAMPLE_ORDERS)

# ================= CÁC CÔNG CỤ (TOOLS) CỦA AI AGENT =================
def tool_lookup_order(order_id: str) -> str:
    df = st.session_state.orders_df
    match = df[df["ma_don"].str.upper() == order_id.upper()]
    if match.empty:
        return f"Không tìm thấy mã đơn **{order_id.upper()}** trong hệ thống. Vui lòng kiểm tra lại mã đơn (VD: LOG001, LOG002, LOG003, LOG004)."
    row = match.iloc[0]
    res = (
        f"### Kết quả tra cứu đơn hàng `{row['ma_don']}`\n"
        f"- **Khách hàng:** {row['khach_hang']} (SĐT: {row['sdt']})\n"
        f"- **Tuyến vận chuyển:** {row['tuyen']}\n"
        f"- **Loại hàng & Khối lượng:** {row['loai_hang']} ({row['khoi_luong_kg']} kg)\n"
        f"- **Trạng thái hiện tại:** {row['trang_thai']}\n"
        f"- **Dự kiến giao:** {row['du_kien_giao']}\n"
    )
    if row["su_co"] != "Không":
        res += f"- **Cảnh báo tác tử:** {row['su_co']} -> *Tôi có thể tự động soạn thông báo cho khách nếu bạn yêu cầu.*"
    return res

def tool_calculate_shipping(weight: float, zone: str, is_fragile: bool = False) -> str:
    rule = RATES[zone]
    surcharge = 30000 if is_fragile else 0
    total = rule["base"] + weight * rule["per_kg"] + surcharge
    return (
        f"### Bảng tính cước vận chuyển tự động\n"
        f"- **Khu vực tuyến:** {zone}\n"
        f"- **Khối lượng tính cước:** {weight:.1f} kg\n"
        f"- **Phí mở cửa:** {rule['base']:,.0f} VNĐ\n"
        f"- **Cước theo khối lượng:** {weight * rule['per_kg']:,.0f} VNĐ\n"
        f"- **Phụ phí hàng dễ vỡ/đặc biệt:** {surcharge:,.0f} VNĐ\n"
        f"- **Tổng cước dự kiến:** **{total:,.0f} VNĐ** (Thời gian toàn trình: {rule['time']})"
    )

def tool_handle_incident(order_id: str) -> str:
    df = st.session_state.orders_df
    match = df[df["ma_don"].str.upper() == order_id.upper()]
    if match.empty:
        return f"Không tìm thấy đơn `{order_id}` để lập phương án xử lý."
    row = match.iloc[0]
    email_draft = (
        f"Kính gửi Quý khách **{row['khach_hang']}**,\n\n"
        f"Hệ thống điều phối vận tải xin thông báo về lô hàng mã **{row['ma_don']}** ({row['loai_hang']} - tuyến {row['tuyen']}). "
        f"Hiện tại lô hàng đang gặp tình huống: *{row['trang_thai']}*.\n"
        f"Bộ phận điều phối đã kích hoạt phương án ưu tiên luồng vận chuyển ngay khi thông tuyến, thời gian giao dự kiến mới là **{row['du_kien_giao']}**.\n"
        f"Chúng tôi thành thật xin lỗi vì sự bất tiện này và miễn phí 100% phí lưu kho phát sinh. Mọi hỗ trợ trực tiếp xin liên hệ tổng đài 1900-xxxx.\n\n"
        f"Trân trọng,\n**Trợ lý Điều phối LogiAgent**"
    )
    return (
        f"### Kế hoạch hành động tự động (Agent Action Plan) cho `{row['ma_don']}`\n"
        f"1. **Bước 1 (Phát hiện):** Xác nhận đơn `{row['ma_don']}` bị chậm do yếu tố khách quan.\n"
        f"2. **Bước 2 (Điều phối):** Đã gắn cờ `ƯU TIÊN CAO` trên hệ thống kho trung chuyển.\n"
        f"3. **Bước 3 (Giao tiếp khách hàng):** Tự động tạo mẫu thông báo gửi khách:\n\n"
        f"---\n{email_draft}"
    )

# ================= BỘ NÃO LẬP KẾ HOẠCH (AGENT ROUTER / PLANNER) =================
def run_agent(user_prompt: str) -> str:
    text = user_prompt.lower()
    # Trích xuất mã đơn dạng LOGxxx bằng Regex
    m_code = re.search(r"log\d{3}", text)
    found_id = m_code.group(0).upper() if m_code else None

    # Intent 1: Xử lý sự cố / khiếu nại / soạn thông báo
    if any(k in text for k in ["xử lý", "sự cố", "xin lỗi", "chậm", "trễ", "khiếu nại"]):
        target = found_id if found_id else "LOG003"
        return tool_handle_incident(target)

    # Intent 2: Tra cứu đơn hàng
    if any(k in text for k in ["tra cứu", "kiểm tra", "đơn", "trạng thái", "ở đâu"]) or found_id:
        if found_id:
            return tool_lookup_order(found_id)
        return "Bạn vui lòng cung cấp **mã đơn hàng** (ví dụ: `LOG001`, `LOG002`, `LOG003`, `LOG004`) để tôi truy xuất dữ liệu nhé."

    # Intent 3: Tính cước vận chuyển
    if any(k in text for k in ["cước", "giá", "gửi", "kg", "báo giá", "vận chuyển"]):
        nums = re.findall(r"\d+(?:\.\d+)?", text)
        weight = float(nums[0]) if nums else 10.0
        if any(w in text for w in ["hà nội", "hải phòng", "bắc"]):
            zone = "Liên tỉnh xa (Bắc - Nam)"
        elif any(w in text for w in ["cần thơ", "đà nẵng", "miền trung", "miền tây", "bình dương"]):
            zone = "Liên tỉnh gần (Miền Nam / Miền Trung)"
        else:
            zone = "Nội thành"
        fragile = "dễ vỡ" in text or "điện tử" in text
        return tool_calculate_shipping(weight, zone, fragile)

    # Intent 4: Tổng hợp báo cáo nhanh toàn đội xe
    if any(k in text for k in ["báo cáo", "tổng hợp", "thống kê", "tình hình"]):
        df = st.session_state.orders_df
        delayed = len(df[df["su_co"] != "Không"])
        return (
            f"### Báo cáo nhanh tình hình vận hành ({datetime.now().strftime('%d/%m/%Y %H:%M')})\n"
            f"- **Tổng số đơn đang theo dõi:** {len(df)} đơn hàng\n"
            f"- **Tổng khối lượng hàng hóa:** {df['khoi_luong_kg'].sum():.1f} kg\n"
            f"- **Số đơn gặp sự cố / chậm trễ:** {delayed} đơn (Mã: `LOG003`)\n"
            f"- **Đề xuất của Agent:** Nên kích hoạt quy trình xử lý sự cố cho đơn `LOG003` ngay."
        )

    return (
        "Tôi chưa nhận diện rõ yêu cầu. Bạn có thể thử một trong các lệnh sau:\n"
        "- `Tra cứu đơn LOG002`\n"
        "- `Tính cước gửi 25kg hàng dễ vỡ đi Hà Nội`\n"
        "- `Xử lý sự cố đơn LOG003`\n"
        "- `Tổng hợp báo cáo vận hành hôm nay`"
    )

# ================= GIAO DIỆN HIỂN THỊ =================
st.title("LogiAgent – Hệ Thống AI Tác Tử Điều Phối & Chăm Sóc Khách Hàng Logistics")
st.caption("Mô hình minh họa Chương 4 (Mục 4.4 & 4.7): AI Agent tự động truy xuất dữ liệu, tính cước và xử lý sự cố vận tải")

col1, col2 = st.columns([1.3, 1])

with col1:
    st.subheader("Cửa sổ tương tác với AI Agent")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Nhập yêu cầu cho LogiAgent (VD: Kiểm tra đơn LOG003)..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        reply = run_agent(prompt)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)

with col2:
    st.subheader("Cơ sở dữ liệu đơn hàng thời gian thực")
    st.dataframe(st.session_state.orders_df, use_container_width=True, hide_index=True)

    st.subheader("Công cụ tính cước nhanh (Form trực quan)")
    with st.form("quick_calc"):
        w_input = st.number_input("Khối lượng hàng (kg)", min_value=0.5, max_value=5000.0, value=12.0, step=0.5)
        z_input = st.selectbox("Tuyến vận chuyển", list(RATES.keys()))
        f_input = st.checkbox("Hàng dễ vỡ / Linh kiện điện tử (+30.000đ)")
        submitted = st.form_submit_button("Yêu cầu Agent tính cước")
        if submitted:
            out = tool_calculate_shipping(w_input, z_input, f_input)
            st.info(out)