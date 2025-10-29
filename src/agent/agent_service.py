# ============================================
# agent/agent_service_improved.py - IMPROVED Multi-Agent Architecture
# Bổ sung các tính năng còn thiếu từ bản TypeScript
# ============================================

import os
import json
import re
from typing import List, Dict, Any, Optional
from pydantic import Field
from dotenv import load_dotenv
from pathlib import Path

# Import prompts - SỬ DỤNG PROMPTS MỚI
from ..utils.prompts import (
    get_product_consultant_prompt,
    get_order_manager_prompt,
    get_support_agent_prompt,
    get_triage_agent_prompt,
    build_full_prompt_with_context
)

# Load env
project_root = Path(__file__).resolve().parent.parent.parent
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://bewo.vn")

# Import OpenAI Agents
from agents import Agent, Runner, function_tool, ModelSettings
from agents.extensions.models.litellm_model import LitellmModel

# Import Supabase
from ..utils.connect_supabase import get_supabase_client

supabase = get_supabase_client()


# ============================================
# VALIDATION FUNCTIONS (THIẾU Ở BẢN CŨ)
# ============================================

def validate_address_function_call(args: dict) -> bool:
    """
    Validate address arguments trước khi execute
    Tương đương validateAddressFunctionCall() trong TypeScript
    """
    # 1. Check address_line exists
    if not args.get("address_line"):
        print("⚠️ save_address: Missing address_line")
        return False
    
    address_line = args["address_line"]
    
    # 2. Check if address_line có số nhà và tên đường
    if not re.match(r'^\d+[A-Z]?\s+.+', address_line):
        print(f"⚠️ save_address: Invalid address_line format: {address_line}")
        return False
    
    # 3. Check if address_line is only numbers
    if re.match(r'^[\d\s]+$', address_line):
        print(f"⚠️ save_address: address_line is only numbers: {address_line}")
        return False
    
    # 4. Validate city
    if not args.get("city"):
        print("⚠️ save_address: Missing city")
        return False
    
    # 5. Check if address_line looks like product description
    product_keywords = ["cao cấp", "lớp", "set", "vest", "quần", "áo"]
    if any(keyword in address_line.lower() for keyword in product_keywords):
        print(f"⚠️ save_address: address_line looks like product description: {address_line}")
        return False
    
    print("✅ save_address validation passed")
    return True


def validate_customer_info_function_call(args: dict) -> bool:
    """Validate customer info trước khi execute"""
    # Check if có ít nhất 1 thông tin hữu ích
    if not args.get("full_name") and not args.get("preferred_name") and not args.get("phone"):
        print("⚠️ save_customer_info: No useful data provided")
        return False
    
    # Validate phone format nếu có
    if args.get("phone"):
        phone = args["phone"]
        if not re.match(r'^[0+][\d]{9,11}$', phone):
            print(f"⚠️ save_customer_info: Invalid phone format: {phone}")
            return False
    
    print("✅ save_customer_info validation passed")
    return True


# ============================================
# HELPER FUNCTIONS
# ============================================

def _format_price(price: Optional[float]) -> str:
    if price is None:
        price = 0
    return f"{price:,.0f} ₫".replace(",", ".")


# ============================================
# TOOLS - Product Management
# ============================================

@function_tool
async def search_products(
    query: str = Field(..., description='Từ khóa tìm kiếm (VD: "váy dạ hội", "áo sơ mi")'),
    limit: int = Field(default=5, description='Số lượng sản phẩm tối đa')
) -> List[Dict]:
    """Tìm kiếm sản phẩm trong cửa hàng theo từ khóa"""
    print(f"[Tool] search_products: query='{query}', limit={limit}")
    
    if not supabase:
        return []
    
    try:
        response = supabase.from_("products") \
            .select("id, name, price, stock, slug, description, images:product_images(image_url, is_primary)") \
            .eq("is_active", True) \
            .text_search("name", query) \
            .limit(limit) \
            .execute()

        products = []
        for p in response.data or []:
            images = p.get("images", [])
            primary_image = next((img["image_url"] for img in images if img.get("is_primary")), None)
            first_image = images[0]["image_url"] if images else None
            
            products.append({
                "id": p["id"],
                "name": p["name"],
                "price": _format_price(p.get("price")),
                "priceRaw": p.get("price", 0),
                "stock": p.get("stock", 0),
                "url": f"{WEBSITE_URL}/products/{p.get('slug', '')}",
                "description": (p.get("description", "") or "")[:150],
                "image": primary_image or first_image
            })

        print(f"[Tool] search_products: Found {len(products)} products")
        return products
        
    except Exception as e:
        print(f"[Tool] search_products ERROR: {e}")
        return []


@function_tool
async def get_product_details(
    productId: str = Field(..., description='ID của sản phẩm')
) -> Optional[Dict]:
    """Lấy thông tin chi tiết của một sản phẩm cụ thể"""
    print(f"[Tool] get_product_details: productId={productId}")
    
    if not supabase:
        return None
        
    try:
        response = supabase.from_("products") \
            .select("id, name, price, stock, slug, description, images:product_images(image_url, is_primary, display_order)") \
            .eq("id", productId) \
            .eq("is_active", True) \
            .limit(1) \
            .execute()

        if not response.data or len(response.data) == 0:
            return None

        product = response.data[0]
        images = product.get("images", [])
        
        images.sort(key=lambda img: (
            not img.get("is_primary", False),
            img.get("display_order", 999)
        ))
        
        image_urls = [img["image_url"] for img in images]

        result = {
            "id": product["id"],
            "name": product["name"],
            "price": _format_price(product.get("price")),
            "priceRaw": product.get("price", 0),
            "stock": product.get("stock", 0),
            "url": f"{WEBSITE_URL}/products/{product.get('slug', '')}",
            "description": product.get("description"),
            "images": image_urls
        }
        
        print(f"[Tool] get_product_details: Found {product['name']}")
        return result
        
    except Exception as e:
        print(f"[Tool] get_product_details ERROR: {e}")
        return None


# ============================================
# TOOLS - Order Management
# ============================================

@function_tool
async def get_order_status(
    orderId: str = Field(..., description='Mã đơn hàng')
) -> Optional[Dict]:
    """Tra cứu trạng thái đơn hàng theo mã đơn hàng"""
    print(f"[Tool] get_order_status: orderId={orderId}")
    
    if not supabase:
        return None

    try:
        cleaned_order_id = re.sub(r'\D', '', orderId)
        
        response = supabase.from_("orders") \
            .select("*") \
            .eq("id", int(cleaned_order_id) if cleaned_order_id.isdigit() else orderId) \
            .limit(1) \
            .execute()

        if not response.data or len(response.data) == 0:
            return None

        order = response.data[0]
        status_map = {
            "pending": "Đang chờ xác nhận",
            "confirmed": "Đã xác nhận",
            "processing": "Đang xử lý",
            "shipping": "Đang giao hàng",
            "delivered": "Đã giao hàng",
            "cancelled": "Đã hủy",
        }
        
        result = {
            "id": str(order["id"]),
            "status": status_map.get(order.get("status", "unknown"), order.get("status")),
            "total": _format_price(order.get("total_amount")),
            "createdAt": order.get("created_at", "")
        }
        
        print(f"[Tool] get_order_status: Status={result['status']}")
        return result
        
    except Exception as e:
        print(f"[Tool] get_order_status ERROR: {e}")
        return None


# ============================================
# TOOLS - Cart & Customer Management
# ============================================

@function_tool
async def save_customer_info(
    conversationId: str = Field(..., description='ID của conversation'),
    full_name: Optional[str] = Field(None, description='Tên đầy đủ'),
    preferred_name: Optional[str] = Field(None, description='Tên gọi thân mật'),
    phone: Optional[str] = Field(None, description='Số điện thoại'),
    style_preference: Optional[List[str]] = Field(None, description='Phong cách yêu thích'),
    usual_size: Optional[str] = Field(None, description='Size thường mặc')
) -> Dict[str, Any]:
    """Lưu thông tin cơ bản của khách hàng"""
    print(f"[Tool] save_customer_info: conversationId={conversationId}")
    
    # TODO: Implement logic to save customer info to database
    # For now, return success message
    return {
        "success": True,
        "message": "Đã lưu thông tin khách hàng",
        "data": {
            "full_name": full_name,
            "preferred_name": preferred_name,
            "phone": phone,
            "style_preference": style_preference,
            "usual_size": usual_size
        }
    }


@function_tool
async def save_address(
    conversationId: str = Field(..., description='ID của conversation'),
    address_line: str = Field(..., description='Số nhà + Tên đường'),
    city: str = Field(..., description='Thành phố'),
    district: Optional[str] = Field(None, description='Quận/Huyện'),
    ward: Optional[str] = Field(None, description='Phường/Xã'),
    phone: Optional[str] = Field(None, description='SĐT người nhận'),
    full_name: Optional[str] = Field(None, description='Tên người nhận')
) -> Dict[str, Any]:
    """Lưu địa chỉ giao hàng"""
    print(f"[Tool] save_address: conversationId={conversationId}")
    
    # TODO: Implement logic to save address to database
    # For now, return success message
    return {
        "success": True,
        "message": "Đã lưu địa chỉ giao hàng",
        "data": {
            "address_line": address_line,
            "ward": ward,
            "district": district,
            "city": city,
            "phone": phone,
            "full_name": full_name
        }
    }


@function_tool
async def add_to_cart(
    conversationId: str = Field(..., description='ID của conversation'),
    product_id: str = Field(..., description='UUID của sản phẩm'),
    size: str = Field(default="M", description='Size sản phẩm'),
    quantity: int = Field(default=1, description='Số lượng')
) -> Dict[str, Any]:
    """Thêm sản phẩm vào giỏ hàng"""
    print(f"[Tool] add_to_cart: product_id={product_id}, size={size}, quantity={quantity}")
    
    # TODO: Implement logic to add product to cart
    # For now, return success message
    return {
        "success": True,
        "message": f"Đã thêm sản phẩm vào giỏ hàng",
        "data": {
            "product_id": product_id,
            "size": size,
            "quantity": quantity
        }
    }


@function_tool
async def confirm_and_create_order(
    conversationId: str = Field(..., description='ID của conversation'),
    confirmed: bool = Field(..., description='Xác nhận đặt hàng')
) -> Dict[str, Any]:
    """Xác nhận và tạo đơn hàng"""
    print(f"[Tool] confirm_and_create_order: confirmed={confirmed}")
    
    if not confirmed:
        return {
            "success": False,
            "message": "Khách chưa xác nhận đặt hàng"
        }
    
    # TODO: Implement logic to create order in database
    # For now, return success message
    return {
        "success": True,
        "message": "Đã tạo đơn hàng thành công",
        "order_id": "ORD-" + conversationId[:8].upper()
    }


# ============================================
# DEFINE MODEL
# ============================================

gemini_model = LitellmModel(
    model="gemini/gemini-2.0-flash-exp",
    api_key=GEMINI_API_KEY
)


# ============================================
# DEFINE AGENTS
# ============================================

productAgent = Agent(
    name='Product Consultant',
    model=gemini_model,
    model_settings=ModelSettings(include_usage=True),
    instructions=get_product_consultant_prompt(),
    tools=[search_products, get_product_details],
    handoff_description='Chuyên gia tư vấn sản phẩm thời trang của BeWo'
)

orderAgent = Agent(
    name='Order Manager',
    model=gemini_model,
    model_settings=ModelSettings(include_usage=True),
    instructions=get_order_manager_prompt(),
    tools=[
        get_order_status,
        save_customer_info,
        save_address,
        add_to_cart,
        confirm_and_create_order
    ],
    handoff_description='Chuyên viên quản lý đơn hàng'
)

supportAgent = Agent(
    name='Customer Support',
    model=gemini_model,
    model_settings=ModelSettings(include_usage=True),
    instructions=get_support_agent_prompt(),
    tools=[],
    handoff_description='Nhân viên hỗ trợ khách hàng'
)

triageAgent = Agent(
    name='BeWo Assistant',
    model=gemini_model,
    model_settings=ModelSettings(include_usage=True),
    instructions=get_triage_agent_prompt(),
    handoffs=[productAgent, orderAgent, supportAgent]
)


# ============================================
# FUNCTION CALL VALIDATION & FILTERING
# ============================================

def filter_and_validate_function_calls(function_calls: List[Dict]) -> List[Dict]:
    """
    Filter và validate function calls trước khi execute
    Tương đương logic trong geminiService.ts
    """
    validated_calls = []
    
    for fc in function_calls:
        fn_name = fc.get("name")
        fn_args = fc.get("args", {})
        
        # Validate save_address
        if fn_name == "save_address":
            if not validate_address_function_call(fn_args):
                print(f"⚠️ Filtered invalid save_address call")
                continue
        
        # Validate save_customer_info
        elif fn_name == "save_customer_info":
            if not validate_customer_info_function_call(fn_args):
                print(f"⚠️ Filtered invalid save_customer_info call")
                continue
        
        # Validate add_to_cart
        elif fn_name == "add_to_cart":
            if not fn_args.get("product_id"):
                print(f"⚠️ Filtered invalid add_to_cart call: missing product_id")
                continue
        
        # Function call hợp lệ
        validated_calls.append(fc)
    
    if len(validated_calls) < len(function_calls):
        print(f"⚠️ Filtered out {len(function_calls) - len(validated_calls)} invalid function calls")
    
    return validated_calls


# ============================================
# CONTINUATION CALL (THIẾU Ở BẢN CŨ)
# ============================================

async def call_agent_with_function_result(
    context: Dict[str, Any],
    user_message: str,
    function_name: str,
    function_result: Dict[str, Any]
) -> Dict[str, str]:
    """
    Gọi agent SAU KHI function được execute để generate natural response
    Tương đương callGeminiWithFunctionResult() trong TypeScript
    """
    try:
        print(f"[Agent] Continuation call after function: {function_name}")
        
        # Build continuation prompt
        continuation_message = f"""
🔧 FUNCTION ĐÃ THỰC THI: {function_name}
📊 KẾT QUẢ: {json.dumps(function_result, ensure_ascii=False, indent=2)}

⚠️ KẾT QUẢ THỰC THI FUNCTION:
{'✅ Thành công!' if function_result.get('success') else '❌ Thất bại!'}
{function_result.get('message', '')}

NHIỆM VỤ:
1. Nếu thành công → Thông báo cho khách một cách tự nhiên, thân thiện
2. Nếu thất bại → Xin lỗi và hướng dẫn khách cung cấp đúng thông tin

VÍ DỤ RESPONSE THÀNH CÔNG (save_address):
"Dạ em đã ghi nhận địa chỉ của chị rồi ạ! ✨
Địa chỉ giao hàng: {function_result.get('data', {}).get('address_line', '[ĐỊA CHỈ]')}
Chị cần em hỗ trợ gì thêm không ạ? 💕"

VÍ DỤ RESPONSE THẤT BẠI:
"Dạ xin lỗi chị, địa chỉ chưa đầy đủ ạ 😊
Chị vui lòng cung cấp đầy đủ: số nhà + tên đường + thành phố nhé!"

Tin nhắn gốc của khách: "{user_message}"

Hãy tạo response TỰ NHIÊN dựa trên kết quả function!
"""
        
        # Run agent với continuation message
        result = await Runner.run(triageAgent, continuation_message)
        
        return {
            "text": result.final_output or "Đã xử lý xong ạ! 💕"
        }
        
    except Exception as e:
        print(f"[Agent] Continuation call ERROR: {e}")
        
        # Fallback response based on function result
        if function_result.get("success"):
            if function_result.get("message"):
                return {"text": function_result["message"]}
            return {"text": "Đã lưu thông tin thành công ạ! ✨"}
        else:
            if function_result.get("message"):
                return {"text": function_result["message"]}
            return {"text": "Có lỗi xảy ra, chị vui lòng thử lại nhé 😊"}


# ============================================
# MAIN FUNCTION (IMPROVED)
# ============================================

async def run_bewo_agent(
    message: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Chạy multi-agent system để xử lý tin nhắn
    IMPROVED với validation, continuation call, và error handling
    
    Args:
        message: Tin nhắn của user
        context: Context bao gồm history, products, cart, profile, etc.
    
    Returns:
        {
            "text": str,
            "products": List[Dict],
            "tokens": int,
            "type": str,
            "functionCalls": List[Dict]
        }
    """
    try:
        print(f"[Agent] Processing message: \"{message}\"")
        
        # Build full prompt with context (IMPROVEMENT: inject context vào agent)
        if context:
            full_message = await build_full_prompt_with_context(context, message)
        else:
            full_message = message
        
        # Run agent
        result = await Runner.run(triageAgent, full_message)

        # Extract products & function calls
        products = []
        function_calls = []
        
        if hasattr(result, 'context_wrapper') and result.context_wrapper:
            print(f"[Agent] Run completed: {result.run.id if hasattr(result, 'run') else 'N/A'}")
            
            if hasattr(result, 'run') and result.run:
                run = result.run
                for msg in run.messages:
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        print(f"[Agent] 🔧 Found {len(msg.tool_calls)} tool call(s)")
                        
                        for tool_call in msg.tool_calls:
                            tool_name = tool_call.function.name
                            tool_args = json.loads(tool_call.function.arguments)
                            
                            print(f"[Agent] 🔧 Tool: {tool_name}({tool_args})")
                            
                            function_calls.append({
                                "name": tool_name,
                                "args": tool_args
                            })
                            
                            # Extract products from search_products
                            if tool_name == "search_products":
                                tool_response = next(
                                    (m for m in run.messages 
                                     if hasattr(m, 'tool_call_id') and m.tool_call_id == tool_call.id),
                                    None
                                )
                                if tool_response and hasattr(tool_response, 'content'):
                                    try:
                                        products = json.loads(tool_response.content)
                                        print(f"[Agent] ✅ Extracted {len(products)} products")
                                    except Exception as e:
                                        print(f"[Agent] ❌ Failed to parse products: {e}")

        # IMPROVEMENT: Validate và filter function calls
        validated_function_calls = filter_and_validate_function_calls(function_calls)
        
        # # Determine type (IMPROVEMENT: better type classification)
        # rec_type = "showcase" if products else "conversational"
        # AFTER
        def classify_response_type(products: List, function_calls: List, response_text: str) -> str:
            """Classify response type giống TypeScript"""
            # Có products mới → showcase
            if products and len(products) > 0:
                return "showcase"
            
            # Mention sản phẩm đã có trong context (không show card mới)
            # Check keywords: "sản phẩm này", "mẫu đó", "giá", "màu"
            mention_keywords = ["sản phẩm", "mẫu", "giá", "màu", "size", "còn hàng"]
            if any(kw in response_text.lower() for kw in mention_keywords):
                return "mention"
            
            return "none"
        rec_type = classify_response_type(products, validated_function_calls, result.final_output)
        # Get tokens
        tokens = 0
        if hasattr(result, 'context_wrapper') and hasattr(result.context_wrapper, 'usage'):
            tokens = result.context_wrapper.usage.total_tokens

        print(f"[Agent] Response: {len(products)} products, {len(validated_function_calls)} function calls, {tokens} tokens")
        
        return {
            "text": result.final_output,
            "products": products,
            "tokens": tokens,
            "type": rec_type,
            "functionCalls": validated_function_calls
        }
        
    except Exception as e:
        print(f"[Agent] ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        # IMPROVEMENT: Better fallback response
        return {
            "text": "Xin lỗi chị, hệ thống đang bận. Vui lòng thử lại sau ít phút nhé! 🙏",
            "products": [],
            "tokens": 0,
            "type": "conversational",
            "functionCalls": []
        }


# ============================================
# EXPORT
# ============================================

__all__ = [
    'run_bewo_agent',
    'call_agent_with_function_result',
    'validate_address_function_call',
    'validate_customer_info_function_call',
    'filter_and_validate_function_calls'
]