# ============================================
# utils/formatters.py - Format utilities
# ============================================

import locale
from datetime import datetime

# Cần cài đặt locale 'vi_VN' trên hệ thống của bạn.
# Trên Ubuntu/Debian: sudo locale-gen vi_VN && sudo update-locale
# Trên Windows, tên locale có thể là 'vietnamese'
try:
    locale.setlocale(locale.LC_ALL, 'vi_VN.UTF-8')
except locale.Error:
    print("Locale 'vi_VN.UTF-8' không được hỗ trợ. Sử dụng locale mặc định.")
    # Bạn có thể đặt một locale thay thế ở đây, ví dụ: locale.setlocale(locale.LC_ALL, '')

def format_price(price: float) -> str:
    """Định dạng số thành chuỗi tiền tệ VND."""
    # Tham số grouping=True để thêm dấu phân cách hàng nghìn (vd: 1.000.000 ₫)
    return locale.currency(price, grouping=True)

def format_date(date_string: str) -> str:
    """Định dạng chuỗi ngày tháng (ISO format) thành 'DD/MM/YYYY'."""
    # Python < 3.11 không xử lý được chữ 'Z' ở cuối, nên ta thay thế nó
    if date_string.endswith('Z'):
        date_string = date_string[:-1] + '+00:00'
    date_obj = datetime.fromisoformat(date_string)
    return date_obj.strftime("%d/%m/%Y")

def format_time(date_string: str) -> str:
    """Định dạng chuỗi ngày tháng (ISO format) thành 'HH:MM'."""
    if date_string.endswith('Z'):
        date_string = date_string[:-1] + '+00:00'
    date_obj = datetime.fromisoformat(date_string)
    return date_obj.strftime("%H:%M")

def calculate_cost(tokens: int) -> float:
    """Tính toán chi phí dựa trên số lượng token."""
    # Dấu gạch dưới (_) trong số chỉ để dễ đọc, tương tự như trong TypeScript
    return tokens * 0.4 / 1_000_000 * 0.125 + tokens * 0.6 / 1_000_000 * 0.375

# --- Ví dụ sử dụng ---
if __name__ == "__main__":
    price_example = 1500000
    date_example = "2025-10-24T14:30:00Z"
    tokens_example = 2500000

    print(f"Giá đã định dạng: {format_price(price_example)}")
    print(f"Ngày đã định dạng: {format_date(date_example)}")
    print(f"Giờ đã định dạng: {format_time(date_example)}")
    print(f"Chi phí tính toán: {calculate_cost(tokens_example)}")
    print(f"Chi phí đã định dạng: {format_price(calculate_cost(tokens_example))}")