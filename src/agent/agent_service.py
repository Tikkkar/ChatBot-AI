# ============================================
# agent/agent_service.py - Multi-Agent Architecture
# ============================================

import os
import json
from typing import List, Dict, Any, Optional
from pydantic import Field
from ..utils.prompts import get_system_prompt
from dotenv import load_dotenv
from pathlib import Path

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
# TOOLS - Cart Management
# ============================================

@function_tool
async def get_cart(
    conversationId: str = Field(..., description='ID của conversation')
) -> Dict[str, Any]:
    """Xem giỏ hàng hiện tại"""
    print(f"[Tool] get_cart: conversationId={conversationId}")
    
    if not supabase:
        return {"items": [], "total": 0}
    
    try:
        response = supabase.from_("cart_items") \
            .select("*, product:products(name, price)") \
            .eq("conversation_id", conversationId) \
            .execute()
        
        items = []
        total = 0
        
        for item in response.data or []:
            price = item.get("product", {}).get("price", 0)
            quantity = item.get("quantity", 1)
            subtotal = price * quantity
            total += subtotal
            
            items.append({
                "id": item["id"],
                "name": item.get("product", {}).get("name", "Unknown"),
                "price": _format_price(price),
                "quantity": quantity,
                "size": item.get("size"),
                "subtotal": _format_price(subtotal)
            })
        
        result = {
            "items": items,
            "total": _format_price(total),
            "totalRaw": total,
            "count": len(items)
        }
        
        print(f"[Tool] get_cart: {len(items)} items, total={_format_price(total)}")
        return result
        
    except Exception as e:
        print(f"[Tool] get_cart ERROR: {e}")
        return {"items": [], "total": 0}


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
    instructions= get_system_prompt,
    tools=[search_products, get_product_details],
    handoff_description='Chuyên gia tư vấn sản phẩm thời trang'
)


# ============================================
# AGENT 2: ORDER MANAGEMENT AGENT
# ============================================

orderAgent = Agent(
    name='Order Manager',
    model=gemini_model,
    model_settings=ModelSettings(include_usage=True),
    instructions="""
Bạn là chuyên viên xử lý đơn hàng của BeWo Fashion.

# NHIỆM VỤ CHÍNH:
1. Tra cứu trạng thái đơn hàng
2. Xem giỏ hàng
3. Hướng dẫn khách đặt hàng

# QUY TRÌNH TRA ĐƠN:
1. Hỏi mã đơn hàng nếu chưa có
2. Gọi tool: `get_order_status(orderId="12345")`
3. Thông báo trạng thái rõ ràng

# QUY TRÌNH XEM GIỎ HÀNG:
1. Gọi tool: `get_cart(conversationId="...")`
2. Hiển thị danh sách sản phẩm + tổng tiền
3. Hỏi khách có muốn chốt đơn không

# PHONG CÁCH:
- Chuyên nghiệp, rõ ràng
- Thông báo chính xác về trạng thái, thời gian
- Gọi khách là "chị"
""",
    tools=[get_order_status, get_cart],
    handoff_description='Chuyên viên quản lý đơn hàng'
)


# ============================================
# AGENT 3: SUPPORT AGENT
# ============================================

supportAgent = Agent(
    name='Customer Support',
    model=gemini_model,
    model_settings=ModelSettings(include_usage=True),
    instructions="""
Bạn là nhân viên hỗ trợ của BeWo Fashion.

# NHIỆM VỤ CHÍNH:
1. Trả lời câu hỏi về chính sách (shipping, return, payment)
2. Hỗ trợ thắc mắc chung
3. Chào hỏi khách hàng

# THÔNG TIN CHÍNH SÁCH:
🚚 **Giao hàng:** Toàn quốc 1-4 ngày, phí 30k (miễn phí từ 300k)
🔄 **Đổi trả:** 7 ngày nếu còn nguyên tem, chưa qua sử dụng
💳 **Thanh toán:** COD - Kiểm tra hàng trước khi thanh toán

# PHONG CÁCH:
- Thân thiện, lịch sự
- Giải thích rõ ràng, dễ hiểu
- Gọi khách là "chị"
- Emoji: 🌷 💕 ✨

# CHÀO HỎI:
"Dạ em chào chị ạ 🌷
Em là Phương của BeWo 💕
Chị cần em tư vấn gì ạ?"
""",
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
    instructions="""
Bạn là trợ lý chính của BeWo Fashion, phân tích yêu cầu và điều phối đến agent phù hợp.

# NHIỆM VỤ:
Phân tích ý định khách hàng và chuyển đến agent chuyên trách.

# QUY TẮC PHÂN LUỒNG:

## 1. TƯ VẤN SẢN PHẨM → Product Consultant
Trigger:
- "có [sản phẩm] nào không?"
- "cho xem [sản phẩm]"
- "tìm [sản phẩm]"
- "gợi ý [sản phẩm]"
- "giá bao nhiêu?"
- "[sản phẩm] có màu gì?"

## 2. ĐƠN HÀNG → Order Manager
Trigger:
- "đơn hàng [mã]"
- "kiểm tra đơn"
- "đặt hàng"
- "giỏ hàng"
- "chốt đơn"

## 3. HỖ TRỢ → Support Agent
Trigger:
- "chào"
- "ship bao lâu?"
- "đổi trả như thế nào?"
- "thanh toán thế nào?"
- Các câu hỏi chung về policy

# LƯU Ý:
- KHÔNG trả lời trực tiếp
- CHỈ phân tích và chuyển hướng
- Nếu không rõ → Chuyển Support Agent
""",
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
            print(f"[Agent] Total runs: {len(result.context_wrapper.runs)}")
            
            for idx, run in enumerate(result.context_wrapper.runs):
                for msg in run.messages:
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        print(f"[Agent] 🔧 Found {len(msg.tool_calls)} tool call(s) in run {idx}")
                        
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