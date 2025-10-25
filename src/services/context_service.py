# ============================================
# services/context_service.py - FIXED
# ============================================

import asyncio
from typing import List, Dict, Optional, Any
from supabase import Client

from .memory_service import load_customer_memory
from .address_service import get_standardized_address

def _get_image_sort_key(image: Dict[str, Any]) -> tuple:
    """Hàm helper để sắp xếp hình ảnh"""
    is_primary = image.get("is_primary", False)
    display_order = image.get("display_order", 999)
    return (not is_primary, display_order)

async def build_context(
    supabase: Client,
    conversation_id: str,
    message: str,
) -> Dict[str, Any]:
    
    context: Dict[str, Any] = {}

    try:
        # ========================================
        # 1. GET CONVERSATION INFO
        # ========================================
        # ✅ FIX: Bỏ .maybe_single(), dùng .limit(1)
        conv_resp = supabase \
            .from_("chatbot_conversations") \
            .select("*") \
            .eq("id", conversation_id) \
            .limit(1) \
            .execute()
        
        # ✅ FIX: Lấy phần tử đầu tiên
        conv = None
        if conv_resp.data and len(conv_resp.data) > 0:
            conv = conv_resp.data[0]

        if conv:
            context["customer"] = {
                "name": conv.get("customer_name") or "Guest",
                "phone": conv.get("customer_phone") or "",
            }

        # ========================================
        # 2. LOAD LONG-TERM MEMORY
        # ========================================
        memory = await load_customer_memory(conversation_id)

        if memory:
            context["profile"] = memory.get("profile")
            context["interests"] = memory.get("interests", [])
            context["memory_facts"] = memory.get("facts", [])
            
            previous_summary = memory.get("summary")
            if previous_summary:
                context["previous_summary"] = previous_summary.get("summary_text")
                context["key_points"] = previous_summary.get("key_points")
            else:
                context["previous_summary"] = None
                context["key_points"] = []

        # ========================================
        # 3. LOAD SAVED ADDRESS
        # ========================================
        saved_address = await get_standardized_address(conversation_id)

        if saved_address:
            context["saved_address"] = saved_address
            print(f"📍 Loaded address: {saved_address.get('address_line')}")
        else:
            context["saved_address"] = None
            print("⚠️ No saved address found")

        # ========================================
        # 4. GET RECENT MESSAGES (10 tin cuối)
        # ========================================
        messages_resp = supabase \
            .from_("chatbot_messages") \
            .select("sender_type, content, created_at") \
            .eq("conversation_id", conversation_id) \
            .order("created_at", desc=False) \
            .limit(10) \
            .execute()

        context["history"] = messages_resp.data or []

        # ========================================
        # 5. GET PRODUCTS
        # ========================================
        products_resp = supabase \
            .from_("products") \
            .select("""
                id, name, price, stock, slug, description,
                images:product_images(image_url, is_primary, display_order)
            """) \
            .eq("is_active", True) \
            .order("created_at", desc=True)\
            .limit(20) \
            .execute()

        products = products_resp.data or []
        
        # Sắp xếp hình ảnh
        for p in products:
            if p.get("images"):
                p["images"].sort(key=_get_image_sort_key)

        context["products"] = products

        # ========================================
        # 6. DEBUG LOG
        # ========================================
        address_line_log = "none"
        if context.get("saved_address") and context["saved_address"].get("address_line"):
             address_line_log = context["saved_address"]["address_line"]
       
        print("📊 Context Summary:", {
            "hasProfile": bool(context.get("profile")),
            "hasSavedAddress": bool(context.get("saved_address")),
            "addressLine": address_line_log,
            "historyCount": len(context.get("history", [])),
            "productCount": len(context.get("products", [])),
            "memoryFactsCount": len(context.get("memory_facts", [])),
        })

        return context

    except Exception as e:
        print(f"❌ Error building context: {e}")
        import traceback
        traceback.print_exc()
        return context