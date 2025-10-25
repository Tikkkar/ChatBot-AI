# ============================================
# services/context_service.py - FIXED TO USE get_standardized_address
# ============================================

from typing import Dict, Any, Optional, List
from ..utils.connect_supabase import get_supabase_client

# Import services (sẽ cần implement)
from .memory_service import load_customer_memory
from .address_service import get_standardized_address


# ========================================
# STUB FUNCTIONS (Bạn thay bằng code thật)
# ========================================

async def load_customer_memory(conversation_id: str) -> Optional[Dict]:
    """
    (Stub) Load long-term memory của khách hàng
    Returns: {
        "profile": {...},
        "interests": [...],
        "facts": [...],
        "summary": {...}
    }
    """
    # TODO: Implement từ memoryService.ts
    return None


async def get_standardized_address(conversation_id: str) -> Optional[Dict]:
    """
    (Stub) Lấy địa chỉ đã chuẩn hóa từ customer_profiles
    Returns: {
        "address_line": str,
        "ward": str,
        "district": str,
        "city": str,
        "phone": str,
        "full_name": str
    }
    """
    # TODO: Implement từ addressService.ts
    return None


# ========================================
# MAIN FUNCTION
# ========================================

async def build_context(
    supabase: Any,
    conversation_id: str,
    message: str
) -> Dict[str, Any]:
    """
    Build context đầy đủ cho agent
    
    Returns:
    {
        "customer": {...},
        "profile": {...},
        "saved_address": {...},
        "history": [...],
        "products": [...],
        "memory_facts": [...],
        "previous_summary": str
    }
    """
    context: Dict[str, Any] = {}

    # ========================================
    # 1. GET CONVERSATION INFO
    # ========================================
    conv_resp = supabase.from_("chatbot_conversations") \
        .select("*") \
        .eq("id", conversation_id) \
        .limit(1) \
        .execute()

    if conv_resp.data and len(conv_resp.data) > 0:
        conv = conv_resp.data[0]
        context["customer"] = {
            "name": conv.get("customer_name") or "Guest",
            "phone": conv.get("customer_phone") or ""
        }
    else:
        context["customer"] = {"name": "Guest", "phone": ""}

    # ========================================
    # 2. LOAD LONG-TERM MEMORY
    # ========================================
    memory = await load_customer_memory(conversation_id)

    if memory:
        context["profile"] = memory.get("profile",{})
        context["interests"] = memory.get("interests", [])
        context["memory_facts"] = memory.get("facts", [])
        
        summary = memory.get("summary")
        if summary:
            context["previous_summary"] = summary.get("summary_text")
            context["key_points"] = summary.get("key_points", [])
    else:
        context["profile"] = {}
        context["interests"] = []
        context["memory_facts"] = []
        context["previous_summary"] = {}
        context["key_points"] = []

    # ========================================
    # 3. LOAD SAVED ADDRESS - ✅ FIXED
    # ========================================
    saved_address = await get_standardized_address(conversation_id)

    if saved_address:
        context["saved_address"] = saved_address
        print(f"📍 Loaded address from customer_profiles (structured): {saved_address.get('address_line')}")
    else:
        context["saved_address"] = {}
        print("⚠️ No saved address found")

    # ========================================
    # 4. GET RECENT MESSAGES (10 tin cuối)
    # ========================================
    msg_resp = supabase.from_("chatbot_messages") \
        .select("sender_type, content, created_at") \
        .eq("conversation_id", conversation_id) \
        .order("created_at", desc=False) \
        .limit(10) \
        .execute()

    context["history"] = msg_resp.data or []

    # ========================================
    # 5. GET PRODUCTS
    # ========================================
    prod_resp = supabase.from_("products") \
        .select("""
            id, name, price, stock, slug, description,
            images:product_images(image_url, is_primary, display_order)
        """) \
        .eq("is_active", True) \
        .order("created_at", desc=True) \
        .limit(20) \
        .execute()

    products = prod_resp.data or []

    # Sort images: primary first, then by display_order
    for p in products:
        if p.get("images"):
            p["images"].sort(key=lambda img: (
                not img.get("is_primary", False),
                img.get("display_order", 999)
            ))

    context["products"] = products

    # # ========================================
    # # 6. GET CART (if exists)
    # # ========================================
    # cart_resp = supabase.from_("cart_items") \
    #     .select("""
    #         id, product_id, quantity, size,
    #         product:products(name, price)
    #     """) \
    #     .eq("conversation_id", conversation_id) \
    #     .execute()

    # if cart_resp.data:
    #     context["cart"] = [
    #         {
    #             "id": item["id"],
    #             "product_id": item["product_id"],
    #             "name": item.get("product", {}).get("name", "Unknown"),
    #             "price": item.get("product", {}).get("price", 0),
    #             "quantity": item["quantity"],
    #             "size": item.get("size")
    #         }
    #         for item in cart_resp.data
    #     ]
    # else:
    #     context["cart"] = []

    # ========================================
    # 7. DEBUG LOG
    # ========================================
    print("📊 Context Summary:", {
        "hasProfile": bool(context.get("profile")),
        "hasSavedAddress": bool(context.get("saved_address")),
        "addressLine": context.get("saved_address", {}).get("address_line", "none"),
        "historyCount": len(context.get("history", [])),
        "productCount": len(context.get("products", [])),
        "cartCount": len(context.get("cart", [])),
        "memoryFactsCount": len(context.get("memory_facts", []))
    })

    return context