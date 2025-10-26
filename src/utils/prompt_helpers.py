"""
Helper Utilities - Các hàm hỗ trợ chung cho tất cả agents
"""

from typing import Dict, List, Any, Optional


def format_price(price: Optional[float]) -> str:
    """
    Format giá tiền theo định dạng Việt Nam
    
    Args:
        price: Giá tiền cần format
        
    Returns:
        Chuỗi giá đã format (VD: "890.000 ₫")
    """
    if price is None:
        price = 0
    return f"{price:,.0f} ₫".replace(",", ".")


class BotConfig:
    """Cấu hình chung cho bot"""
    def __init__(self):
        self.bot_name = "Phương"
        self.bot_role = "Chuyên viên chăm sóc khách hàng"
        self.greeting_style = "Em (nhân viên) - Chị/Anh (khách hàng)"
        self.tone = "Thân thiện, lịch sự, chuyên nghiệp"
        self.allowed_emojis = ["🌷", "💕", "✨", "💬", "💖", "🌸", "😍", "💌", "💎", "📝", "🚚"]


class StoreInfo:
    """Thông tin cửa hàng"""
    def __init__(self):
        self.name = "BeWo"
        self.description = "Shop thời trang Linen cao cấp, phong cách thanh lịch, sang trọng"
        self.policies = {
            "shipping": "Giao hàng toàn quốc 1-4 ngày, phí 30k (miễn phí từ 300k)",
            "return": "Đổi trả trong 7 ngày nếu còn nguyên tem, chưa qua sử dụng",
            "payment": "COD - Kiểm tra hàng trước khi thanh toán"
        }
        self.contact = {
            "hotline": "1900 xxxx",
            "email": "support@bewo.vn",
            "fanpage": "facebook.com/BeWoVietnam",
            "working_hours": "8:00 - 22:00 (Thứ 2 - Chủ nhật)"
        }


class ProductSummary:
    """Tổng quan sản phẩm"""
    def __init__(self):
        self.total_products = 125
        self.categories = ["Áo sơ mi", "Quần suông", "Áo vest", "Chân váy", "Váy liền thân", "Phụ kiện"]
        self.price_range = {"min": 299000, "max": 1890000}
        self.top_materials = ["Linen cao cấp", "Tweed", "Cotton lụa"]
        self.available_sizes = ["XS", "S", "M", "L", "XL"]


def build_customer_context(context: Dict[str, Any]) -> str:
    """
    Xây dựng context về khách hàng từ dữ liệu
    
    Args:
        context: Dictionary chứa thông tin khách hàng
        
    Returns:
        Chuỗi context đã format
    """
    full_context = ""
    
    # 1. CUSTOMER PROFILE
    if context.get('profile'):
        full_context += "\n👤 KHÁCH HÀNG:\n"
        p = context['profile']
        if p.get('preferred_name') or p.get('full_name'):
            full_context += f"Tên: {p.get('preferred_name') or p.get('full_name')}\n"
        if p.get('phone'):
            full_context += f"SĐT: {p['phone']}\n"
        if p.get('usual_size'):
            full_context += f"Size thường mặc: {p['usual_size']}\n"
        if p.get('style_preference'):
            full_context += f"Phong cách: {', '.join(p['style_preference'])}\n"
        if p.get('total_orders', 0) > 0:
            full_context += f"Đã mua: {p['total_orders']} đơn (khách quen)\n"
    else:
        full_context += "\n👤 KHÁCH HÀNG: Khách mới (chưa có profile)\n"
    
    return full_context


def build_address_context(context: Dict[str, Any]) -> str:
    """
    Xây dựng context về địa chỉ khách hàng
    
    Args:
        context: Dictionary chứa thông tin địa chỉ
        
    Returns:
        Chuỗi context địa chỉ đã format
    """
    full_context = ""
    
    if context.get('saved_address') and context['saved_address'].get('address_line'):
        addr = context['saved_address']
        full_context += "\n📍 ĐỊA CHỈ ĐÃ LƯU:\n"
        full_context += f"{addr['address_line']}"
        if addr.get('ward'):
            full_context += f", {addr['ward']}"
        if addr.get('district'):
            full_context += f", {addr['district']}"
        if addr.get('city'):
            full_context += f", {addr['city']}"
        full_context += f"\nSĐT: {addr.get('phone') or context.get('profile', {}).get('phone') or 'chưa có'}\n"
        full_context += "\n⚠️ KHI CHỐT ĐƠN: Dùng địa chỉ THẬT này để xác nhận!\n"
    else:
        full_context += "\n📍 ĐỊA CHỈ: Chưa có → Cần hỏi KHI KHÁCH MUỐN ĐẶT HÀNG\n"
    
    return full_context


def build_history_context(context: Dict[str, Any], limit: int = 5) -> str:
    """
    Xây dựng context lịch sử hội thoại
    
    Args:
        context: Dictionary chứa lịch sử
        limit: Số tin nhắn tối đa hiển thị
        
    Returns:
        Chuỗi context lịch sử đã format
    """
    full_context = ""
    
    if context.get('history'):
        full_context += f"\n📜 LỊCH SỬ HỘI THOẠI ({limit} TIN CUỐI):\n"
        for msg in context['history'][-limit:]:
            role = "👤 KHÁCH" if msg.get('sender_type') == 'customer' else "🤖 BOT"
            text = msg.get('content', {}).get('text', '')
            if text:
                full_context += f"{role}: {text[:150]}\n"
        full_context += "\n⚠️ ĐỌC KỸ LỊCH SỬ để hiểu ngữ cảnh và KHÔNG hỏi lại!\n"
    
    return full_context


def build_products_context(context: Dict[str, Any], limit: int = 10) -> str:
    """
    Xây dựng context danh sách sản phẩm
    
    Args:
        context: Dictionary chứa danh sách sản phẩm
        limit: Số sản phẩm tối đa hiển thị
        
    Returns:
        Chuỗi context sản phẩm đã format
    """
    full_context = ""
    
    if context.get('products'):
        full_context += f"\n🛍️ DANH SÁCH SẢN PHẨM ({limit} ĐẦU):\n"
        for idx, p in enumerate(context['products'][:limit], 1):
            full_context += f"{idx}. {p.get('name')}\n"
            full_context += f"   Giá: {format_price(p.get('price'))}"
            stock = p.get('stock')
            if stock is not None:
                if stock > 0:
                    full_context += f" | Còn: {stock} sp"
                else:
                    full_context += " | HẾT HÀNG"
            full_context += f"\n   ID: {p.get('id')}\n"
        full_context += "\n⚠️ CHỈ GỢI Ý sản phẩm PHÙ HỢP với nhu cầu khách!\n"
    
    return full_context


def build_cart_context(context: Dict[str, Any]) -> str:
    """
    Xây dựng context giỏ hàng
    
    Args:
        context: Dictionary chứa giỏ hàng
        
    Returns:
        Chuỗi context giỏ hàng đã format
    """
    full_context = ""
    
    if context.get('cart'):
        full_context += "\n🛒 GIỎ HÀNG HIỆN TẠI:\n"
        total = 0
        for idx, item in enumerate(context['cart'], 1):
            full_context += f"{idx}. {item.get('name')} - Size {item.get('size')} x{item.get('quantity')}\n"
            total += item.get('price', 0) * item.get('quantity', 1)
        full_context += f"\n💰 Tạm tính: {format_price(total)}\n"
    
    return full_context


def build_full_context(
    context: Dict[str, Any],
    include_customer: bool = True,
    include_address: bool = True,
    include_history: bool = True,
    include_products: bool = False,
    include_cart: bool = False
) -> str:
    """
    Xây dựng full context dựa trên các tùy chọn
    
    Args:
        context: Dictionary chứa tất cả thông tin
        include_customer: Có bao gồm thông tin khách hàng không
        include_address: Có bao gồm địa chỉ không
        include_history: Có bao gồm lịch sử không
        include_products: Có bao gồm sản phẩm không
        include_cart: Có bao gồm giỏ hàng không
        
    Returns:
        Chuỗi full context đã format
    """
    full_context = ""
    
    if include_customer:
        full_context += build_customer_context(context)
    
    if include_address:
        full_context += build_address_context(context)
    
    if include_history:
        full_context += build_history_context(context)
    
    if include_products:
        full_context += build_products_context(context)
    
    if include_cart:
        full_context += build_cart_context(context)
    
    return full_context