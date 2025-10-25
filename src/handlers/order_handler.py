# ============================================
# handlers/order_handler.py - Python Conversion
# ============================================

import re
import asyncio
from typing import Dict, Any, Optional, List
from supabase import Client

# --- 1. Import Services ---

try:
    # Thử import tương đối từ thư mục cha
    from ..services.chatbot_order_service import create_chatbot_order
    from ..services.address_service import get_standardized_address
    from ..services.cart_service import clear_cart, get_or_create_cart
    # Import connect_supabase từ thư mục gốc
    from ..utils.connect_supabase import create_async_supabase_client

except ImportError:
    # Fallback nếu cấu trúc file bị dẹt (flat)
    print("[OrderHandler] Cảnh báo: Không thể import ..services. Giả định cấu trúc flat.")
    from services.chatbot_order_service import create_chatbot_order
    from services.address_service import get_standardized_address
    from services.cart_service import clear_cart, get_or_create_cart
    from ..utils.connect_supabase import create_async_supabase_client

# --- 2. Stubs & Helpers ---

def _format_price(price: Optional[float]) -> str:
    """
    (Helper) Định dạng số thành tiền tệ VNĐ.
    """
    if price is None:
        price = 0
    return f"{price:,.0f} ₫".replace(",", ".")

async def sync_chatbot_order_to_main_orders(order_id: str) -> dict:
    """
    (Stub) Giả lập cho orderSyncService.ts.
    """
    print(f"[OrderHandler] (Stub) Đang đồng bộ order {order_id} sang hệ thống chính...")
    await asyncio.sleep(0.1) # Giả lập I/O
    return {
        "success": True,
        "orderNumber": f"SYNCD-{order_id[:8]}"
    }

# --- 3. Implementation ---

def is_add_to_cart_intent(message: str) -> bool:
    """
    Check if user wants to add to cart
    """
    add_keywords = [
        "thêm", "lấy thêm", "cho thêm", "nữa", "cùng mẫu", "mẫu này", "cái này",
        r"\d+\s*(?:bộ|cái|chiếc)" # "2 bộ", "3 cái"
    ]
    
    lower_message = message.lower()
    
    for keyword in add_keywords:
        if re.search(keyword, lower_message):
            return True
    return False

def is_order_intent(message: str) -> bool:
    """
    Check if user wants to order
    """
    order_keywords = [
        "đặt hàng", "mua", "order", "đặt mua", "đặt luôn", "lấy luôn",
        "chốt đơn", "em muốn mua", "cho em", "giao hàng",
    ]
    
    lower_message = message.lower()
    return any(keyword in lower_message for keyword in order_keywords)

def is_confirmation(message: str) -> bool:
    """
    Check if customer confirmed the address/order
    """
    trimmed = message.strip().lower()

    # Exact matches
    exact_matches = ["được", "ok", "ừ", "vâng", "có", "yes", "đúng rồi", "ok luôn", "chốt"]
    if trimmed in exact_matches:
        return True

    # Pattern matches (bắt đầu bằng)
    patterns = [
        r"^đúng",
        r"^chốt",
        r"^đồng ý",
    ]
    
    return any(re.match(pattern, trimmed, re.IGNORECASE) for pattern in patterns)

async def handle_order_creation(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle order creation
    """
    conversation_id = body.get("conversationId")
    message_text = body.get("message_text", "")
    # ai_response = body.get("aiResponse") # Không dùng trực tiếp

    supabase = create_async_supabase_client()
    if not supabase:
        return {"success": False, "message": "Lỗi kết nối."}

    print("🛒 Processing order creation...")
    print(f"📋 Conversation ID: {conversation_id}")

    try:
        # ========================================
        # 1. GET CUSTOMER PROFILE
        # ========================================
        profile_resp = supabase.from_("customer_profiles") \
            .select("id, full_name, preferred_name, phone, customer_fb_id") \
            .eq("conversation_id", conversation_id) \
            .single() \
            .execute()

        if profile_resp.error or not profile_resp.data:
            print(f"❌ Profile not found: {profile_resp.error}")
            return {
                "success": False,
                "message": "Dạ em chưa lưu được thông tin của chị. Chị vui lòng cho em tên và số điện thoại nhé 💕",
            }
        
        profile = profile_resp.data

        # Check if profile has required info
        if not profile.get("full_name") and not profile.get("preferred_name"):
            return {
                "success": False,
                "message": "Dạ chị cho em xin tên của chị ạ 😊",
            }
        
        if not profile.get("phone"):
            return {
                "success": False,
                "message": "Dạ chị cho em xin số điện thoại ạ 📞",
            }

        # ========================================
        # 2. GET SAVED ADDRESS
        # ========================================
        print("🔍 Step 1: Calling getStandardizedAddress...")
        saved_address = await get_standardized_address(conversation_id)
        print(f"🔍 Step 2: Address result: {saved_address}")

        if not saved_address or not saved_address.get("address_line"):
            print(f"❌ Address validation failed: {saved_address}")
            return {
                "success": False,
                "needAddress": True,
                "message": "Dạ chị cho em xin địa chỉ nhận hàng đầy đủ (số nhà, tên đường, quận/huyện, thành phố) để em tạo đơn ạ 💌",
            }

        if not saved_address.get("city"):
            return {
                "success": False,
                "needAddress": True,
                "message": "Dạ em cần biết thành phố giao hàng ạ. Chị cho em biết địa chỉ đầy đủ nhé 💌",
            }
        print("✅ Address validation passed")

        # ========================================
        # 3. GET PRODUCTS FROM CART
        # ========================================
        cart = await get_or_create_cart(conversation_id)

        if not cart:
            return {
                "success": False,
                "needProducts": True,
                "message": "Dạ giỏ hàng của chị đang trống. Chị muốn đặt sản phẩm nào ạ? Em gợi ý chị vài mẫu đẹp nhé 🌸",
            }
        
        print(f"🛒 Cart items: {len(cart)}")
        products = cart # Dùng trực tiếp giỏ hàng

        # ========================================
        # 4. CREATE ORDER
        # ========================================
        order_data = {
            "conversationId": conversation_id,
            "profileId": profile["id"],
            "customerName": profile.get("preferred_name") or profile.get("full_name") or "Khách hàng",
            "customerPhone": saved_address.get("phone") or profile.get("phone") or "",
            "customerFbId": profile.get("customer_fb_id"),
            "shippingAddress": saved_address["address_line"],
            "shippingWard": saved_address.get("ward") or "",
            "shippingDistrict": saved_address.get("district") or "",
            "shippingCity": saved_address["city"],
            "products": products,
            "notes": message_text,
        }

        print(f"📦 Order data prepared: {order_data['customerName']}, {order_data['shippingCity']}, {len(order_data['products'])} items")

        result = await create_chatbot_order(order_data)

        if not result.get("success"):
            print(f"❌ Order creation failed: {result.get('error')}")
            return {
                "success": False,
                "message": f"Dạ em xin lỗi chị, có lỗi khi tạo đơn: {result.get('error', 'Lỗi không xác định')}. Chị cho em thử lại nhé 🙏",
            }

        order = result.get("order")
        if not order:
             return {"success": False, "message": "Lỗi tạo đơn: Không nhận được order object."}

        print(f"✅ Order created successfully: {order.get('id')}")

        # ========================================
        # 4.5. CLEAR CART
        # ========================================
        await clear_cart(conversation_id)
        print("✅ Cart cleared after order creation")

        # ========================================
        # 4.6. SYNC TO MAIN ORDERS (NON-BLOCKING)
        # ========================================
        asyncio.create_task(
            sync_chatbot_order_to_main_orders(order.get('id'))
        )

        # ========================================
        # 5. FORMAT SUCCESS MESSAGE
        # ========================================
        summary = result.get("orderSummary")
        if not summary:
            print("❌ Order summary is null")
            return {
                "success": False,
                "message": "Dạ em xin lỗi chị, có lỗi khi tạo tóm tắt đơn hàng. Chị thử lại nhé 🙏",
            }

        product_list = "\n".join(
            [f"• {p.get('name')} - Size {p.get('size')} x{p.get('quantity')}" for p in products]
        )

        full_address = ", ".join(filter(None, [
            saved_address.get("address_line"),
            saved_address.get("ward"),
            saved_address.get("district"),
            saved_address.get("city"),
        ]))

        discount_line = ""
        if summary.get("discountAmount", 0) > 0:
            discount_line = f"• Giảm giá: -{_format_price(summary.get('discountAmount'))}\n"

        success_message = f"""
Dạ em đã ghi nhận đơn hàng của chị! 📝

📦 SẢN PHẨM:
{product_list}

💰 TỔNG TIỀN:
- Tiền hàng: {_format_price(summary.get('subtotal'))}
- Phí ship: {_format_price(summary.get('shippingFee'))}
{discount_line}• TỔNG: {_format_price(summary.get('total'))}

📍 GIAO ĐẾN:
{full_address}

📞 SĐT: {saved_address.get("phone") or profile.get("phone")}

🚚 Bộ phận kho sẽ liên hệ chị trong hôm nay để xác nhận và giao hàng ạ.

Chị cần em hỗ trợ thêm gì không ạ? 💕
        """.strip()

        return {
            "success": True,
            "orderId": order.get("id"),
            "message": success_message,
        }

    except Exception as error:
        print(f"❌ Order creation error: {error}")
        return {
            "success": False,
            "message": "Dạ em xin lỗi chị, có lỗi xảy ra. Chị thử lại sau nhé 🙏",
        }

async def get_products_from_conversation(
    supabase: Client,
    conversation_id: str,
) -> List[Dict[str, Any]]:
    """
    @deprecated - Use getOrCreateCart() instead
    """
    print("⚠️ getProductsFromConversation is deprecated. Use getOrCreateCart().")
    
    # Get recent messages with products
    msg_resp = supabase.from_("chatbot_messages") \
        .select("content") \
        .eq("conversation_id", conversation_id) \
        .eq("sender_type", "bot") \
        .order("created_at", desc=True) \
        .limit(5) \
        .execute()

    products: List[Dict[str, Any]] = []
    seen_product_ids = set()

    for msg in msg_resp.data or []:
        content = msg.get("content", {})
        if "products" in content and isinstance(content["products"], list):
            for product in content["products"]:
                if product.get("id") not in seen_product_ids:
                    
                    prod_resp = supabase.from_("products") \
                        .select("id, name, price, images:product_images(image_url, is_primary)") \
                        .eq("id", product["id"]) \
                        .single() \
                        .execute()

                    if prod_resp.data:
                        full_product = prod_resp.data
                        images = full_product.get("images", [])
                        primary_image = next((img["image_url"] for img in images if img.get("is_primary")), None)
                        first_image = images[0]["image_url"] if images else ""

                        products.append({
                            "product_id": full_product["id"],
                            "name": full_product["name"],
                            "price": full_product["price"],
                            "size": "M", # Default size
                            "quantity": 1,
                            "image": primary_image or first_image,
                        })
                        seen_product_ids.add(full_product["id"])
    return products
