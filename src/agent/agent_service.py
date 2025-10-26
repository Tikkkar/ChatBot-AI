# ============================================
# agent/agent_service_updated.py - Multi-Agent Architecture (UPDATED)
# ============================================

import os
import json
from typing import List, Dict, Any, Optional
from pydantic import Field
from dotenv import load_dotenv
from pathlib import Path

# Import prompts
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
        import re
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
    print(f"[Tool] save_address: {address_line}, {city}")
    
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
    product_id: str = Field(..., description='ID của sản phẩm'),
    size: str = Field(default="M", description='Size sản phẩm'),
    quantity: int = Field(default=1, description='Số lượng')
) -> Dict[str, Any]:
    """Thêm sản phẩm vào giỏ hàng"""
    print(f"[Tool] add_to_cart: product_id={product_id}, size={size}, quantity={quantity}")
    
    # TODO: Implement logic to add to cart in database
    # For now, return success message
    return {
        "success": True,
        "message": f"Đã thêm {quantity} sản phẩm vào giỏ hàng",
        "data": {
            "product_id": product_id,
            "size": size,
            "quantity": quantity
        }
    }


@function_tool
async def confirm_and_create_order(
    conversationId: str = Field(..., description='ID của conversation'),
    confirmed: bool = Field(True, description='Khách đã xác nhận đặt hàng')
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
# AGENT 1: PRODUCT CONSULTANT AGENT
# ============================================

productAgent = Agent(
    name='Product Consultant',
    model=gemini_model,
    model_settings=ModelSettings(include_usage=True),
    instructions=get_product_consultant_prompt(),
    tools=[search_products, get_product_details],
    handoff_description='Chuyên gia tư vấn sản phẩm thời trang của BeWo'
)


# ============================================
# AGENT 2: ORDER MANAGEMENT AGENT
# ============================================

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


# ============================================
# AGENT 3: SUPPORT AGENT
# ============================================

supportAgent = Agent(
    name='Customer Support',
    model=gemini_model,
    model_settings=ModelSettings(include_usage=True),
    instructions=get_support_agent_prompt(),
    tools=[],
    handoff_description='Nhân viên hỗ trợ khách hàng'
)


# ============================================
# AGENT 4: TRIAGE AGENT (Main Coordinator)
# ============================================

triageAgent = Agent(
    name='BeWo Assistant',
    model=gemini_model,
    model_settings=ModelSettings(include_usage=True),
    instructions=get_triage_agent_prompt(),
    handoffs=[productAgent, orderAgent, supportAgent]
)


# ============================================
# MAIN FUNCTION
# ============================================

async def run_bewo_agent(
    message: str,
    context: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Chạy multi-agent system để xử lý tin nhắn
    
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
        
        # Run agent with context
        result = await Runner.run(triageAgent, message)

        # Extract products & function calls
        products = []
        function_calls = []
        
        if hasattr(result, 'context_wrapper') and result.context_wrapper:
            print(f"[Agent] Run completed: {result.run.id if hasattr(result, 'run') else 'N/A'}")
            
            for idx, run in enumerate(result.context_wrapper.runs):
                for msg in run.messages:
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        print(f"[Agent] 🔧 Found {len(msg.tool_calls)} tool call(s) in run {idx}")
                        # Debug result structure
                        print(f"[DEBUG] Result type: {type(result)}")
                        print(f"[DEBUG] Result attributes: {dir(result)}")
                        if hasattr(result, 'context_wrapper'):
                            print(f"[DEBUG] Context wrapper type: {type(result.context_wrapper)}")
                            print(f"[DEBUG] Context wrapper attributes: {dir(result.context_wrapper)}")
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

        # Determine type
        rec_type = "product_recommendation" if products else "conversational"
        
        # Get tokens
        tokens = 0
        if hasattr(result, 'context_wrapper') and hasattr(result.context_wrapper, 'usage'):
            tokens = result.context_wrapper.usage.total_tokens

        print(f"[Agent] Response generated: {len(products)} products, {len(function_calls)} function calls, {tokens} tokens")
        
        return {
            "text": result.final_output,
            "products": products,
            "tokens": tokens,
            "type": rec_type,
            "functionCalls": function_calls
        }
        
    except Exception as e:
        print(f"[Agent] ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "text": "Xin lỗi chị, hệ thống đang bận. Vui lòng thử lại sau ít phút nhé! 🙏",
            "products": [],
            "tokens": 0,
            "type": "conversational",
            "functionCalls": []
        }


# ============================================
# EXAMPLE USAGE WITH CONTEXT
# ============================================

async def run_with_context_example():
    """Ví dụ sử dụng với context"""
    
    # Mock context data
    context = {
        "profile": {
            "preferred_name": "Lan",
            "phone": "0987654321",
            "usual_size": "M",
            "style_preference": ["thanh lịch", "sang trọng"],
            "total_orders": 3
        },
        "saved_address": {
            "address_line": "123 Nguyễn Trãi",
            "ward": "Phường Thanh Xuân Trung",
            "district": "Quận Thanh Xuân",
            "city": "Hà Nội",
            "phone": "0987654321"
        },
        "history": [
            {"sender_type": "customer", "content": {"text": "Chào shop"}},
            {"sender_type": "bot", "content": {"text": "Dạ chào chị Lan ạ 🌷"}},
            {"sender_type": "customer", "content": {"text": "Cho em xem áo vest"}}
        ],
        "products": [],
        "cart": []
    }
    
    # Test message
    message = "Cho em xem áo vest thanh lịch đi làm"
    
    # Run agent
    result = await run_bewo_agent(message, context)
    
    print("\n" + "="*60)
    print("RESULT:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("="*60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_with_context_example())