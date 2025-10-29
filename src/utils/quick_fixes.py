# ============================================
# utils/quick_fixes.py - Quick Improvements & Fixes
# Các improvements nhỏ để hoàn thiện 100%
# ============================================

from typing import List, Dict, Any, Optional
import re
from agent.agent_service import validate_address_function_call

# ============================================
# 1. RESPONSE TYPE CLASSIFICATION (FIX)
# ============================================

def classify_response_type(
    products: List[Dict],
    response_text: str,
    context_products: List[Dict] = None
) -> str:
    """
    Classify response type chính xác như TypeScript:
    - showcase: Giới thiệu sản phẩm MỚI (show cards)
    - mention: Nhắc đến sản phẩm ĐÃ CÓ trong context (không show cards)
    - none: Không liên quan sản phẩm
    
    Args:
        products: List sản phẩm mới được return từ tools
        response_text: Text response của AI
        context_products: List sản phẩm đã có trong context
    
    Returns:
        "showcase" | "mention" | "none"
    """
    
    # Rule 1: Có sản phẩm mới → showcase
    if products and len(products) > 0:
        return "showcase"
    
    # Rule 2: Không có sản phẩm mới, check xem có mention sản phẩm cũ không
    if not products or len(products) == 0:
        # Keywords indicate mentioning existing products
        mention_keywords = [
            "sản phẩm này", "mẫu này", "mẫu đó", "cái này", "cái đó",
            "giá", "màu", "size", "còn hàng", "hết hàng",
            "chất liệu", "ảnh thật", "ảnh mặc"
        ]
        
        text_lower = response_text.lower()
        
        # Check if mentioning products
        if any(keyword in text_lower for keyword in mention_keywords):
            return "mention"
    
    # Rule 3: Không liên quan sản phẩm
    return "none"


# ============================================
# 2. CONVERSATION ID INJECTION
# ============================================

def inject_conversation_id_to_tools(tools: List, conversation_id: str):
    """
    Inject conversationId vào tools để không cần pass mỗi lần gọi
    
    CÁCH DÙNG:
    ```python
    from functools import partial
    
    # Bind conversationId
    save_customer_info_bound = partial(
        save_customer_info, 
        conversationId=conversation_id
    )
    
    # Use in agent
    tools = [save_customer_info_bound, save_address_bound, ...]
    ```
    """
    from functools import partial
    
    bound_tools = []
    for tool in tools:
        # Bind conversationId to tool
        bound_tool = partial(tool, conversationId=conversation_id)
        bound_tools.append(bound_tool)
    
    return bound_tools


# ============================================
# 3. PRODUCT EXTRACTION HELPER
# ============================================

def extract_products_from_tool_results(
    run_messages: List,
    tool_calls: List
) -> List[Dict]:
    """
    Đơn giản hóa việc extract products từ tool responses
    
    Args:
        run_messages: List messages từ agent run
        tool_calls: List tool calls được executed
    
    Returns:
        List of products
    """
    import json
    
    products = []
    
    for tool_call in tool_calls:
        if tool_call.function.name != "search_products":
            continue
        
        # Find corresponding tool response
        tool_response = next(
            (msg for msg in run_messages 
             if hasattr(msg, 'tool_call_id') and msg.tool_call_id == tool_call.id),
            None
        )
        
        if not tool_response or not hasattr(tool_response, 'content'):
            continue
        
        try:
            response_products = json.loads(tool_response.content)
            if isinstance(response_products, list):
                products.extend(response_products)
        except Exception as e:
            print(f"❌ Failed to parse products from tool response: {e}")
    
    return products


# ============================================
# 4. ADDRESS EXTRACTION FROM TEXT
# ============================================

def extract_address_components(text: str) -> Optional[Dict[str, str]]:
    """
    Trích xuất components của địa chỉ từ text tự do
    
    VD: "123 Nguyễn Trãi, P.Thanh Xuân Trung, Q.Thanh Xuân, Hà Nội"
    → {
        "address_line": "123 Nguyễn Trãi",
        "ward": "Thanh Xuân Trung",
        "district": "Thanh Xuân",
        "city": "Hà Nội"
    }
    """
    
    # Patterns
    address_line_pattern = r'(\d+[A-Z]?\s+[^\,]+)'
    ward_pattern = r'(?:P\.|Phường|phường)\s*([^\,]+)'
    district_pattern = r'(?:Q\.|Quận|quận|Huyện|huyện)\s*([^\,]+)'
    city_pattern = r'(Hà Nội|TP\.HCM|Đà Nẵng|Cần Thơ|Hải Phòng|[A-ZĐÀÁẢÃẠ][a-zàáảãạăắằẳẵặâấầẩẫậđéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵ\s]+)'
    
    result = {}
    
    # Extract address line
    match = re.search(address_line_pattern, text)
    if match:
        result["address_line"] = match.group(1).strip()
    
    # Extract ward
    match = re.search(ward_pattern, text, re.IGNORECASE)
    if match:
        result["ward"] = match.group(1).strip()
    
    # Extract district
    match = re.search(district_pattern, text, re.IGNORECASE)
    if match:
        result["district"] = match.group(1).strip()
    
    # Extract city
    match = re.search(city_pattern, text, re.IGNORECASE)
    if match:
        result["city"] = match.group(1).strip()
    
    # Validate có đủ thông tin tối thiểu không
    if "address_line" in result and "city" in result:
        return result
    
    return None


# ============================================
# 5. PHONE NUMBER EXTRACTION & VALIDATION
# ============================================

def extract_phone_number(text: str) -> Optional[str]:
    """Trích xuất số điện thoại từ text"""
    # Patterns cho SĐT Việt Nam
    patterns = [
        r'\+84\s*\d{9,10}',  # +84 xxx xxx xxx
        r'84\d{9,10}',       # 84xxxxxxxxx
        r'0\d{9,10}',        # 0xxxxxxxxx
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            phone = match.group(0).replace(' ', '')
            # Normalize to 0xxxxxxxxx format
            if phone.startswith('+84'):
                phone = '0' + phone[3:]
            elif phone.startswith('84'):
                phone = '0' + phone[2:]
            return phone
    
    return None


def validate_phone_number(phone: str) -> bool:
    """Validate định dạng SĐT Việt Nam"""
    if not phone:
        return False
    
    # Remove spaces
    phone = phone.replace(' ', '')
    
    # Check format
    pattern = r'^[0+][\d]{9,11}$'
    if not re.match(pattern, phone):
        return False
    
    # Check Vietnamese phone prefixes
    valid_prefixes = ['03', '05', '07', '08', '09']
    if phone.startswith('0'):
        prefix = phone[:2]
        if prefix not in valid_prefixes:
            return False
    
    return True


# ============================================
# 6. SMART PRODUCT ID DETECTION
# ============================================

def detect_product_id_from_context(
    user_message: str,
    context_products: List[Dict],
    conversation_history: List[Dict] = None
) -> Optional[str]:
    """
    Phát hiện product_id mà khách muốn mua từ context
    
    Logic ưu tiên:
    1. Khách chỉ rõ "mẫu 1", "cái số 2" → Lấy theo index
    2. Chỉ có 1 sản phẩm trong context → Lấy sản phẩm đó
    3. Có nhiều sản phẩm → Lấy sản phẩm CUỐI CÙNG (gần nhất)
    
    Returns:
        product_id hoặc None nếu không xác định được
    """
    
    if not context_products or len(context_products) == 0:
        print("⚠️ No products in context")
        return None
    
    # Rule 1: Khách chỉ rõ index
    index_patterns = [
        r'mẫu\s*(\d+)',
        r'cái\s*(?:số\s*)?(\d+)',
        r'sản\s*phẩm\s*(?:số\s*)?(\d+)',
    ]
    
    for pattern in index_patterns:
        match = re.search(pattern, user_message.lower())
        if match:
            index = int(match.group(1)) - 1  # Convert to 0-based index
            if 0 <= index < len(context_products):
                product_id = context_products[index].get('id')
                print(f"✅ Detected product by index: {index + 1} → {product_id}")
                return product_id
    
    # Rule 2: Chỉ có 1 sản phẩm
    if len(context_products) == 1:
        product_id = context_products[0].get('id')
        print(f"✅ Only 1 product in context → {product_id}")
        return product_id
    
    # Rule 3: Lấy sản phẩm cuối cùng (gần nhất)
    product_id = context_products[-1].get('id')
    print(f"✅ Multiple products, taking last one → {product_id}")
    return product_id


# ============================================
# 7. STRUCTURED LOGGING HELPER
# ============================================

class ChatbotLogger:
    """Structured logging cho chatbot"""
    
    @staticmethod
    def log_message(
        level: str,
        event: str,
        conversation_id: str = None,
        **kwargs
    ):
        """
        Log structured event
        
        Usage:
        ChatbotLogger.log_message(
            "info",
            "agent_call",
            conversation_id="123",
            tokens=500,
            duration_ms=1234
        )
        """
        import json
        from datetime import datetime
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level.upper(),
            "event": event,
            "conversation_id": conversation_id,
            **kwargs
        }
        
        print(json.dumps(log_entry, ensure_ascii=False))
    
    @staticmethod
    def log_function_call(
        function_name: str,
        args: Dict,
        result: Dict = None,
        error: str = None
    ):
        """Log function call execution"""
        ChatbotLogger.log_message(
            "info",
            "function_call",
            function_name=function_name,
            args=args,
            success=result is not None,
            error=error
        )
    
    @staticmethod
    def log_agent_response(
        conversation_id: str,
        tokens: int,
        products_count: int,
        function_calls_count: int,
        duration_ms: float
    ):
        """Log agent response metrics"""
        ChatbotLogger.log_message(
            "info",
            "agent_response",
            conversation_id=conversation_id,
            tokens=tokens,
            products_count=products_count,
            function_calls_count=function_calls_count,
            duration_ms=duration_ms
        )


# ============================================
# 8. RETRY LOGIC FOR AI CALLS
# ============================================

async def retry_agent_call(
    agent_func,
    max_retries: int = 3,
    backoff_factor: float = 1.5,
    **kwargs
):
    """
    Retry logic cho agent calls với exponential backoff
    
    Usage:
    result = await retry_agent_call(
        run_bewo_agent,
        max_retries=3,
        message="Chào shop",
        context=context
    )
    """
    import asyncio
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            result = await agent_func(**kwargs)
            return result
        except Exception as e:
            last_error = e
            wait_time = backoff_factor ** attempt
            
            print(f"⚠️ Attempt {attempt + 1}/{max_retries} failed: {e}")
            
            if attempt < max_retries - 1:
                print(f"🔄 Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                print(f"❌ All {max_retries} attempts failed")
    
    raise last_error


# ============================================
# 9. CONTEXT SIZE OPTIMIZER
# ============================================

def optimize_context_size(
    context: Dict[str, Any],
    max_history_messages: int = 10,
    max_products: int = 10
) -> Dict[str, Any]:
    """
    Optimize context size để tránh token overflow
    
    Args:
        context: Original context
        max_history_messages: Max số messages trong history
        max_products: Max số products
    
    Returns:
        Optimized context
    """
    optimized = context.copy()
    
    # Limit history
    if "history" in optimized and len(optimized["history"]) > max_history_messages:
        optimized["history"] = optimized["history"][-max_history_messages:]
        print(f"✂️ Trimmed history to last {max_history_messages} messages")
    
    # Limit products
    if "products" in optimized and len(optimized["products"]) > max_products:
        optimized["products"] = optimized["products"][:max_products]
        print(f"✂️ Trimmed products to first {max_products} items")
    
    # Limit memory facts
    if "memory_facts" in optimized and len(optimized["memory_facts"]) > 5:
        optimized["memory_facts"] = optimized["memory_facts"][:5]
        print(f"✂️ Trimmed memory facts to 5 most recent")
    
    return optimized


# ============================================
# 10. QUICK TEST HELPERS
# ============================================

def test_address_validation():
    """Test address validation"""
    test_cases = [
        ("123 Nguyễn Trãi", "Hà Nội", True),
        ("áo vest cao cấp", "Hà Nội", False),
        ("123", "Hà Nội", False),
        ("", "Hà Nội", False),
    ]
    
    for address_line, city, expected in test_cases:
        args = {"address_line": address_line, "city": city}
        result = validate_address_function_call(args)
        status = "✅" if result == expected else "❌"
        print(f"{status} {address_line} → {result} (expected: {expected})")


def test_phone_validation():
    """Test phone validation"""
    test_cases = [
        ("0987654321", True),
        ("+84987654321", True),
        ("84987654321", True),
        ("123456", False),
        ("abc", False),
    ]
    
    for phone, expected in test_cases:
        result = validate_phone_number(phone)
        status = "✅" if result == expected else "❌"
        print(f"{status} {phone} → {result} (expected: {expected})")


# ============================================
# EXPORT
# ============================================

__all__ = [
    'classify_response_type',
    'inject_conversation_id_to_tools',
    'extract_products_from_tool_results',
    'extract_address_components',
    'extract_phone_number',
    'validate_phone_number',
    'detect_product_id_from_context',
    'ChatbotLogger',
    'retry_agent_call',
    'optimize_context_size',
    'test_address_validation',
    'test_phone_validation'
]


if __name__ == "__main__":
    print("🧪 Running quick tests...\n")
    
    print("📍 Testing address validation:")
    test_address_validation()
    
    print("\n📱 Testing phone validation:")
    test_phone_validation()
    
    print("\n✅ All tests completed!")