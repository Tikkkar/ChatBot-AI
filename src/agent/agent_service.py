# ============================================
# agent/agent_service.py - OpenAI Agents Version
# ============================================

import os
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from dotenv import load_dotenv
from pathlib import Path

# Load env
project_root = Path(__file__).resolve().parent.parent.parent
env_path = project_root / ".env"
if env_path.exists():
    print(f"[Agent] Đang tải biến môi trường từ: {env_path}")
    load_dotenv(dotenv_path=env_path)
else:
    print(f"[Agent] Cảnh báo: Không tìm thấy tệp .env tại {env_path}.")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://bewo.vn")

# Import OpenAI Agents
from agents import Agent, Runner, function_tool

# Import Supabase
from ..utils.connect_supabase import get_supabase_client

supabase = get_supabase_client()

# --- Helper Functions ---

def _format_price(price: Optional[float]) -> str:
    if price is None:
        price = 0
    return f"{price:,.0f} ₫".replace(",", ".")

# --- Pydantic Models ---

class Product(BaseModel):
    id: str
    name: str
    price: str
    priceRaw: float
    stock: int
    url: str
    description: Optional[str] = None
    image: Optional[str] = None

class OrderStatus(BaseModel):
    id: str
    status: str
    total: str
    createdAt: str

class ProductDetails(BaseModel):
    id: str
    name: str
    price: str
    priceRaw: float
    stock: int
    url: str
    description: Optional[str] = None
    images: Optional[List[str]] = None

# --- Tool Functions ---

@function_tool
async def search_products(
    query: str = Field(..., description='Từ khóa tìm kiếm (VD: "váy dạ hội", "áo sơ mi")'),
    limit: int = Field(default=5, description='Số lượng sản phẩm tối đa')
) -> List[Product]:
    """Tìm kiếm sản phẩm trong cửa hàng theo từ khóa"""
    print(f"[Tool] Searching products: \"{query}\"")
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
            
            products.append(Product(
                id=p["id"],
                name=p["name"],
                price=_format_price(p.get("price")),
                priceRaw=p.get("price", 0),
                stock=p.get("stock", 0),
                url=f"{WEBSITE_URL}/products/{p.get('slug', '')}",
                description=p.get("description", "")[:150] if p.get("description") else None,
                image=primary_image or first_image
            ))

        print(f"[Tool] Found {len(products)} products")
        return products
    except Exception as e:
        print(f"[Tool] Search error: {e}")
        return []

@function_tool
async def get_order_status(
    orderId: str = Field(..., description='Mã đơn hàng')
) -> Optional[OrderStatus]:
    """Tra cứu trạng thái đơn hàng theo mã đơn hàng"""
    print(f"[Tool] Getting order: {orderId}")
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
            print(f"[Tool] Order lookup error: No data returned")
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
        
        order_status = order.get("status", "unknown")

        return OrderStatus(
            id=str(order["id"]),
            status=status_map.get(order_status, order_status),
            total=_format_price(order.get("total_amount")),
            createdAt=order.get("created_at", "")
        )
    except Exception as e:
        print(f"[Tool] Order error: {e}")
        return None

@function_tool
async def get_product_details(
    productId: str = Field(..., description='ID của sản phẩm')
) -> Optional[ProductDetails]:
    """Lấy thông tin chi tiết của một sản phẩm cụ thể"""
    print(f"[Tool] Getting product details: {productId}")
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
            print(f"[Tool] Product lookup error: No data returned")
            return None

        product = response.data[0]
        images = product.get("images", [])
        
        # Sort images
        images.sort(key=lambda img: (
            not img.get("is_primary", False),
            img.get("display_order", 999)
        ))
        
        image_urls = [img["image_url"] for img in images]

        return ProductDetails(
            id=product["id"],
            name=product["name"],
            price=_format_price(product.get("price")),
            priceRaw=product.get("price", 0),
            stock=product.get("stock", 0),
            url=f"{WEBSITE_URL}/products/{product.get('slug', '')}",
            description=product.get("description"),
            images=image_urls
        )
    except Exception as e:
        print(f"[Tool] Product details error: {e}")
        return None

# --- Define Agents ---

# Set OpenAI API key for agents
os.environ["OPENAI_API_KEY"] = GEMINI_API_KEY
os.environ["OPENAI_BASE_URL"] = "https://generativelanguage.googleapis.com/v1beta/openai/"

GEMINI_MODEL = "gemini-2.0-flash-exp"

bewoAgent = Agent(
    name='BeWo Fashion Assistant',
    model=GEMINI_MODEL,
    instructions="""
Bạn là trợ lý ảo của BeWo Fashion - shop thời trang nữ cao cấp tại Việt Nam.

# NHÂN CÁCH & PHONG CÁCH:
- Thân thiện, nhiệt tình, chuyên nghiệp
- Gọi khách hàng là "chị" (formal) hoặc "bạn" (casual) tùy ngữ cảnh
- Dùng emoji nhẹ nhàng (😊 🌸 💕 ✨) nhưng không lạm dụng
- Trả lời ngắn gọn, rõ ràng, dễ hiểu

# NHIỆM VỤ CHÍNH:
1. Tư vấn sản phẩm phù hợp với nhu cầu khách hàng
2. Giới thiệu sản phẩm kèm link mua hàng
3. Tra cứu trạng thái đơn hàng
4. Hỗ trợ thắc mắc về sản phẩm, giá cả, vận chuyển

# QUY TRÌNH TƯ VẤN SẢN PHẨM:
1. Hỏi rõ nhu cầu: Dịp gì? Style nào? Ngân sách?
2. Dùng tool "search_products" để tìm sản phẩm phù hợp
3. Giới thiệu 2-3 sản phẩm TỐT NHẤT (không nên quá nhiều)
4. Mỗi sản phẩm bao gồm:
   - Tên sản phẩm
   - Giá bán
   - Mô tả ngắn gọn (tại sao phù hợp)
   - Link mua hàng: {url}

# KHI TRA ĐƠN HÀNG:
1. Hỏi mã đơn hàng nếu khách chưa cung cấp
2. Dùng tool "get_order_status"
3. Thông báo trạng thái chi tiết và thời gian dự kiến

# LƯU Ý:
- LUÔN đính kèm link sản phẩm khi giới thiệu
- KHÔNG bịa ra sản phẩm không có trong kết quả tool
- Nếu không tìm thấy sản phẩm phù hợp, gợi ý khách tìm trực tiếp trên website
- Nếu khách hỏi về chính sách, gợi ý liên hệ hotline hoặc xem website
""",
    tools=[search_products, get_order_status, get_product_details],
)

orderTrackingAgent = Agent(
    name='Order Tracking Agent',
    model=GEMINI_MODEL,
    instructions="""
Bạn là chuyên viên tra cứu đơn hàng của BeWo Fashion.

NHIỆM VỤ:
- Tra cứu trạng thái đơn hàng chính xác
- Giải thích rõ ràng từng trạng thái
- Thông báo thời gian dự kiến nếu có

QUY TRÌNH:
1. Hỏi mã đơn hàng nếu chưa có
2. Dùng tool get_order_status
3. Thông báo kết quả chi tiết
""",
    tools=[get_order_status],
    handoff_description='Chuyên xử lý tra cứu đơn hàng',
)

triageAgent = Agent(
    name='Triage Agent',
    model=GEMINI_MODEL,
    instructions="""
Bạn là bộ phận phân luồng yêu cầu của BeWo Fashion.

NHIỆM VỤ:
- Phân tích ý định của khách hàng
- Chuyển đến agent phù hợp

QUY TẮC:
- Nếu khách hỏi về TRA ĐƠN HÀNG, MÃ ĐƠN, TRẠNG THÁI ĐƠN → Chuyển Order Tracking Agent
- Mọi trường hợp khác → Chuyển BeWo Fashion Assistant

Không trả lời trực tiếp, chỉ phân tích và chuyển hướng.
""",
    handoffs=[orderTrackingAgent, bewoAgent],
)

# --- Main Function ---

async def run_bewo_agent(
    message: str,
    context: Optional[Any] = None
) -> str:
    """
    Chạy agent chính để xử lý tin nhắn của người dùng.
    """
    try:
        print(f"[Agent] Processing message: \"{message}\"")
        
        # Run agent
        result = await Runner.run(triageAgent, message)

        print("[Agent] Response generated successfully")
        return result.final_output
        
    except Exception as e:
        print(f"[Agent] Error: {e}")
        return "Xin lỗi chị, hệ thống đang bận. Vui lòng thử lại sau ít phút nhé! 🙏"