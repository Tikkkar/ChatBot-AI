"""
Main Prompts Module - Import và sử dụng tất cả các agent prompts

Cách sử dụng:
    from prompts import get_triage_prompt, get_product_consultant_prompt
    
    # Lấy prompt cho agent cụ thể
    triage_prompt = get_triage_prompt()
    product_prompt = get_product_consultant_prompt()
    order_prompt = get_order_manager_prompt()
    support_prompt = get_support_agent_prompt()
    
    # Build full prompt với context
    full_prompt = build_agent_prompt_with_context(
        agent_type="product_consultant",
        user_message="Cho em xem áo vest",
        context={
            'profile': {...},
            'products': [...],
            'cart': [...]
        }
    )
"""

from typing import Dict, Any, Optional
from .Prompt.triage_agent_prompt import get_triage_agent_prompt
from .Prompt.product_consultant_prompt import get_product_consultant_prompt
from .Prompt.order_manager_prompt import get_order_manager_prompt
from .Prompt.support_agent_prompt import get_support_agent_prompt
from .prompt_helpers import (
    build_full_context,
    BotConfig,
    StoreInfo,
    ProductSummary,
    format_price
)


# Export các hàm chính
__all__ = [
    'get_triage_prompt',
    'get_product_consultant_prompt',
    'get_order_manager_prompt',
    'get_support_agent_prompt',
    'build_agent_prompt_with_context',
    'BotConfig',
    'StoreInfo',
    'ProductSummary',
    'format_price'
]


# Mapping agent types
AGENT_PROMPT_MAP = {
    "triage": get_triage_agent_prompt,
    "product_consultant": get_product_consultant_prompt,
    "order_manager": get_order_manager_prompt,
    "support": get_support_agent_prompt
}


def get_triage_prompt() -> str:
    """Lấy prompt cho Triage Agent"""
    return get_triage_agent_prompt()


def get_product_consultant_prompt() -> str:
    """Lấy prompt cho Product Consultant Agent"""
    return get_product_consultant_prompt()


def get_order_manager_prompt() -> str:
    """Lấy prompt cho Order Manager Agent"""
    return get_order_manager_prompt()


def get_support_agent_prompt() -> str:
    """Lấy prompt cho Support Agent"""
    return get_support_agent_prompt()


def build_agent_prompt_with_context(
    agent_type: str,
    user_message: str,
    context: Optional[Dict[str, Any]] = None,
    tool_instructions: Optional[str] = None
) -> str:
    """
    Build full prompt cho agent với context
    
    Args:
        agent_type: Loại agent (triage, product_consultant, order_manager, support)
        user_message: Tin nhắn của user
        context: Dictionary chứa thông tin context (profile, products, cart, history, etc.)
        tool_instructions: Hướng dẫn sử dụng tools (nếu có)
        
    Returns:
        Full prompt string đã kết hợp system prompt + context + user message
        
    Example:
        >>> context = {
        ...     'profile': {'name': 'Lan', 'phone': '0901234567'},
        ...     'products': [...],
        ...     'cart': [...]
        ... }
        >>> prompt = build_agent_prompt_with_context(
        ...     agent_type="product_consultant",
        ...     user_message="Cho em xem áo vest",
        ...     context=context
        ... )
    """
    if context is None:
        context = {}
    
    # Lấy system prompt dựa trên agent type
    prompt_func = AGENT_PROMPT_MAP.get(agent_type, get_triage_agent_prompt)
    system_prompt = prompt_func()
    
    # Build context dựa trên agent type
    if agent_type == "product_consultant":
        full_context = build_full_context(
            context,
            include_customer=True,
            include_address=True,
            include_history=True,
            include_products=True,
            include_cart=True
        )
    elif agent_type == "order_manager":
        full_context = build_full_context(
            context,
            include_customer=True,
            include_address=True,
            include_history=True,
            include_products=False,
            include_cart=True
        )
    elif agent_type == "support":
        full_context = build_full_context(
            context,
            include_customer=True,
            include_address=False,
            include_history=True,
            include_products=False,
            include_cart=False
        )
    else:  # triage
        full_context = build_full_context(
            context,
            include_customer=True,
            include_address=False,
            include_history=True,
            include_products=False,
            include_cart=False
        )
    
    # Combine everything
    final_prompt = f"""{system_prompt}

{full_context}

👤 TIN NHẮN CỦA KHÁCH: "{user_message}"

⚠️ QUAN TRỌNG:
- ĐỌC KỸ CONTEXT trước khi trả lời
- HIỂU Ý ĐỊNH khách
- TƯ VẤN phù hợp với vai trò agent
- SỬ DỤNG TOOLS khi cần thiết

{tool_instructions if tool_instructions else ''}

BẮT ĐẦU TRẢ LỜI!"""
    
    return final_prompt


def get_agent_type_from_message(message: str) -> str:
    """
    Tự động xác định agent type từ message (dành cho quick routing)
    
    Args:
        message: Tin nhắn của user
        
    Returns:
        Agent type (triage, product_consultant, order_manager, support)
        
    Note:
        Đây chỉ là hàm hỗ trợ đơn giản. Nên sử dụng Triage Agent để phân loại chính xác.
    """
    message_lower = message.lower()
    
    # Product keywords
    product_keywords = ['cho xem', 'có', 'tìm', 'gợi ý', 'giá', 'mẫu', 'tư vấn', 'áo', 'quần', 'váy', 'vest']
    if any(keyword in message_lower for keyword in product_keywords):
        return "product_consultant"
    
    # Order keywords
    order_keywords = ['đơn hàng', 'kiểm tra đơn', 'tra đơn', 'giỏ hàng', 'chốt đơn', 'đặt hàng', 'order']
    if any(keyword in message_lower for keyword in order_keywords):
        return "order_manager"
    
    # Support keywords
    support_keywords = ['chào', 'xin chào', 'ship', 'đổi trả', 'thanh toán', 'chính sách', 'liên hệ']
    if any(keyword in message_lower for keyword in support_keywords):
        return "support"
    
    # Default to triage
    return "triage"


# Example usage
if __name__ == "__main__":
    # Test getting prompts
    print("=== TRIAGE AGENT ===")
    print(get_triage_prompt()[:200])
    print("\n")
    
    print("=== PRODUCT CONSULTANT ===")
    print(get_product_consultant_prompt()[:200])
    print("\n")
    
    print("=== ORDER MANAGER ===")
    print(get_order_manager_prompt()[:200])
    print("\n")
    
    print("=== SUPPORT AGENT ===")
    print(get_support_agent_prompt()[:200])
    print("\n")
    
    # Test building full prompt with context
    test_context = {
        'profile': {
            'preferred_name': 'Lan',
            'phone': '0901234567',
            'total_orders': 3
        },
        'products': [
            {'id': 'P001', 'name': 'Áo Vest Linen', 'price': 890000, 'stock': 5}
        ],
        'cart': []
    }
    
    print("=== FULL PROMPT WITH CONTEXT ===")
    full_prompt = build_agent_prompt_with_context(
        agent_type="product_consultant",
        user_message="Cho em xem áo vest",
        context=test_context
    )
    print(full_prompt[:500])