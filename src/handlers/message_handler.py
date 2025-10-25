# ============================================
# handlers/message_handler.py - Python Conversion
# ============================================

import asyncio
import re
from typing import Dict, Any, Optional, List
from supabase import Client

# --- 1. Import Services với relative imports ---
from ..services.context_service import build_context
from ..agent.agent_service import run_bewo_agent 
from ..services.facebook_service import send_facebook_message
from ..services.address_extraction_service import extract_and_save_address
from ..services.customer_profile_service import save_customer_profile
from ..services.address_service import save_address_standardized
from ..services.cart_service import (
    add_to_cart,
    get_cart_summary,
    get_or_create_cart,
)
from ..services.embedding_service import (
    create_message_embedding,
    create_summary_embedding,
)
from ..services.memory_service import (
    create_conversation_summary,
    extract_and_save_memory,
    extract_memory_facts,
)
from ..utils.connect_supabase import get_supabase_client

print("✅ [MessageHandler] All imports successful")

# --- 2. STUBS cho các file chưa được cung cấp ---

def calculate_cost(tokens: int) -> float:
    """(Stub) Tính toán chi phí dựa trên token."""
    return (tokens / 1_000_000) * 0.5 

def is_confirmation(message_text: str) -> bool:
    """(Stub) Kiểm tra xem tin nhắn có phải là lời xác nhận không."""
    text = message_text.lower().strip()
    return any(kw == text for kw in ["đúng rồi", "ok", "confirm", "chốt", "vâng ạ", "đúng", "vâng"])

def is_order_intent(message_text: str) -> bool:
    """(Stub) Kiểm tra xem tin nhắn có ý định đặt hàng không."""
    text = message_text.lower()
    return any(kw in text for kw in ["đặt hàng", "mua hàng", "chốt đơn"])

async def handle_order_creation(params: dict) -> dict:
    """(Stub) Xử lý logic tạo đơn hàng từ orderHandler.ts."""
    print("--- (Stub) Đang xử lý tạo đơn hàng ---")
    context = params.get("context", {})
    
    # Logic giả lập:
    cart = await get_or_create_cart(params.get("conversationId"))
    if not cart:
         return {
            "success": False,
            "needProducts": True,
            "message": "Dạ giỏ hàng của chị đang trống. Chị muốn em tư vấn thêm sản phẩm nào ạ?"
        }

    if not context.get("saved_address"):
        return {
            "success": False,
            "needAddress": True,
            "message": "Dạ, chị cho em xin địa chỉ và số điện thoại để em chốt đơn nhé."
        }
    
    return {
        "success": True,
        "message": "Dạ em đã chốt đơn thành công cho chị. Mã đơn là #12345. Cảm ơn chị đã mua hàng ạ!",
        "orderId": "12345"
    }

# --- 3. Hàm Helper ---

async def _create_summary_and_embedding(conversation_id: str, supabase: Client):
    """Hàm helper để chạy summary và embedding trong nền."""
    try:
        await create_conversation_summary(conversation_id)
        
        # ✅ FIX: Bỏ .single(), dùng limit(1) và lấy phần tử đầu
        summary_resp = supabase.from_("conversation_summaries") \
            .select("summary_text, key_points") \
            .eq("conversation_id", conversation_id) \
            .order("summary_created_at", desc=True) \
            .limit(1) \
            .execute()
        
        # ✅ FIX: Kiểm tra data và lấy phần tử đầu tiên
        if summary_resp.data and len(summary_resp.data) > 0:
            summary = summary_resp.data[0]  # Lấy phần tử đầu tiên
            await create_summary_embedding(
                conversation_id,
                summary.get("summary_text", ""),
                summary.get("key_points", []),
            )
            print("✅ Summary embedding created")
    except Exception as e:
        print(f"❌ Summary/Embedding creation error: {e}")

# --- 4. HÀM XỬ LÝ CHÍNH ---

async def handle_message(body: Dict[str, Any]):
    platform = body.get("platform")
    customer_fb_id = body.get("customer_fb_id")
    customer_phone = body.get("customer_phone")
    user_id = body.get("user_id")
    session_id = body.get("session_id")
    message_text = body.get("message_text", "")
    page_id = body.get("page_id")
    access_token = body.get("access_token")

    db_platform = "website" if platform == "web" else platform

    print(f"Processing message: {{'platform': '{db_platform}', 'message': '{message_text[:50]}...'}}")

    # ✅ FIX: Dùng get_supabase_client thay vì create_supabase_client
    supabase = get_supabase_client()
    if not supabase:
        raise ValueError("Không thể khởi tạo Supabase client.")

    # ========================================
    # 1. GET OR CREATE CONVERSATION
    # ========================================
    try:
        rpc_params = {
            "p_platform": platform,
            "p_customer_fb_id": customer_fb_id,
            "p_customer_phone": customer_phone,
            "p_user_id": user_id,
            "p_session_id": session_id,
            "p_customer_name": "Guest",
            "p_customer_avatar": None,
        }
        print("[DEBUG] Step 1: Getting conversation...")
        conv_resp = supabase.rpc("get_or_create_conversation", rpc_params).execute()
        print("[DEBUG] Step 1: DONE")
        print("[DEBUG] Step 2: Saving message...")
        if not conv_resp.data:
            raise Exception("Could not create/get conversation")
        conversation_id = conv_resp.data
        print(f"✅ Conversation ID: {conversation_id}")
        
    except Exception as e:
        print(f"❌ Conversation error: {e}")
        raise

    # ========================================
    # 2. SAVE CUSTOMER MESSAGE
    # ========================================
    try:
        msg_resp = supabase.from_("chatbot_messages") \
            .insert({
                "conversation_id": conversation_id,
                "sender_type": "customer",
                "message_type": "text",
                "content": {"text": message_text},
            }) \
            .execute()
        
        # ✅ FIX: Lấy phần tử đầu tiên
        if not msg_resp.data or len(msg_resp.data) == 0:
            raise Exception("Could not save customer message")
        customer_message = msg_resp.data[0]
        
    except Exception as e:
        print(f"❌ Error saving customer message: {e}")
        raise

    # 🔥 2.1. CREATE EMBEDDING (Chạy nền)
    embedding_metadata = {
        "sender_type": "customer",
        "platform": db_platform,
        "customer_fb_id": customer_fb_id,
        "user_id": user_id,
        "session_id": session_id,
    }
    asyncio.create_task(
        create_message_embedding(
            conversation_id,
            customer_message["id"],
            message_text,
            embedding_metadata,
        )
    )

    # ========================================
    # 3. BUILD CONTEXT
    # ========================================
    context = await build_context(supabase, conversation_id, message_text)

    print("Context built:", {
        "hasProfile": bool(context.get("profile")),
        "historyCount": len(context.get("history", [])),
        "memoryCount": len(context.get("memory_facts", [])),
    })

    # ========================================
    # 4. GENERATE RESPONSE - GỌI AGENT SERVICE
    # ========================================
    ai_response_text = await run_bewo_agent(message_text, context)
    
    response_text = ai_response_text
    tokens_used = (len(message_text) + len(ai_response_text)) // 4
    recommendation_type = "conversational"
    product_cards = []
    
    print("Response generated:", {
        "type": recommendation_type,
        "products": len(product_cards),
        "tokens": tokens_used,
    })

    # ========================================
    # 4.5. CHECK ORDER CONFIRMATION
    # ========================================
    if is_confirmation(message_text):
        history = context.get("history", [])
        recent_bot_messages = [m for m in history if m.get("sender_type") == "bot"][-2:]
        
        just_asked_for_confirmation = False
        for msg in recent_bot_messages:
            text = msg.get("content", {}).get("text", "")
            if "giao về" in text and "phải không" in text:
                just_asked_for_confirmation = True
                break
        
        if just_asked_for_confirmation:
            print("✅ Customer confirmed address - Creating order")
            order_result = await handle_order_creation({
                "conversationId": conversation_id,
                "message_text": message_text,
                "aiResponse": {"text": ai_response_text},
                "context": context
            })
            response_text = order_result["message"]

    # ========================================
    # 4.6. CHECK IF ORDER INTENT
    # ========================================
    elif is_order_intent(message_text):
        print("🛒 Order intent detected")
        order_result = await handle_order_creation({
            "conversationId": conversation_id,
            "message_text": message_text,
            "aiResponse": {"text": ai_response_text},
            "context": context
        })
        
        response_text = order_result["message"]
        if order_result.get("success"):
            # ✅ FIX: Bỏ await
            supabase.from_("chatbot_messages").insert({
                "conversation_id": conversation_id,
                "sender_type": "bot",
                "message_type": "text",
                "content": {"text": response_text},
            }).execute()

    # ========================================
    # 5. SAVE BOT RESPONSE
    # ========================================
    try:
        bot_msg_content = {
            "text": response_text,
            "products": product_cards,
            "recommendation_type": recommendation_type,
        }
        
        # ✅ FIX: Bỏ .single(), lấy data[0]
        bot_msg_resp = supabase.from_("chatbot_messages") \
            .insert({
                "conversation_id": conversation_id,
                "sender_type": "bot",
                "message_type": "product_card" if product_cards else "text",
                "content": bot_msg_content,
                "tokens_used": tokens_used,
            }) \
            .execute()

        # ✅ FIX: Lấy phần tử đầu tiên
        if not bot_msg_resp.data or len(bot_msg_resp.data) == 0:
            raise Exception("Could not save bot message")
        bot_message = bot_msg_resp.data[0]
        
    except Exception as e:
        print(f"❌ Error saving bot message: {e}")
        raise

    # 🔥 5.1. CREATE BOT EMBEDDING
    bot_embedding_metadata = {
        "sender_type": "bot",
        "platform": db_platform,
        "has_products": bool(product_cards),
        "product_count": len(product_cards),
        "recommendation_type": recommendation_type,
        "product_ids": [p.get("id") for p in product_cards],
    }
    asyncio.create_task(
        create_message_embedding(
            conversation_id,
            bot_message["id"],
            response_text,
            bot_embedding_metadata,
        )
    )

    # ========================================
    # 6. LOG USAGE
    # ========================================
    if tokens_used > 0:
        # ✅ FIX: Bỏ await
        supabase.from_("chatbot_usage_logs").insert({
            "conversation_id": conversation_id,
            "input_tokens": tokens_used // 2,
            "output_tokens": tokens_used // 2,
            "cost": calculate_cost(tokens_used),
            "model": "gemini-2.0-flash-exp",
        }).execute()

    # ========================================
    # 6.5. EXTRACT ADDRESS
    # ========================================
    has_address_keywords = re.search(
        r"(?:địa chỉ|giao|ship|nhận hàng|đường|phường|quận|huyện|\d+\s+[A-Z])",
        message_text,
        re.IGNORECASE
    )
    if has_address_keywords:
        print("🏠 Detected potential address, extracting...")
        asyncio.create_task(
            extract_and_save_address(conversation_id, message_text)
        )

    # ========================================
    # MEMORY PROCESSING
    # ========================================
    ai_response_obj = {
        "text": ai_response_text,
        "tokens": tokens_used,
        "type": recommendation_type,
        "products": product_cards,
    }
    asyncio.create_task(
        extract_and_save_memory(conversation_id, message_text, ai_response_obj)
    )

    profile_id = context.get("profile", {}).get("id")
    if profile_id:
        asyncio.create_task(
            extract_memory_facts(profile_id, message_text, conversation_id)
        )

    # ========================================
    # 9. CREATE CONVERSATION SUMMARY
    # ========================================
    message_count = len(context.get("history", []))
    if message_count > 0 and message_count % 20 == 0:
        print(f"📊 Creating summary at {message_count} messages")
        asyncio.create_task(
            _create_summary_and_embedding(conversation_id, supabase)
        )

    # ========================================
    # 10. SEND TO FACEBOOK
    # ========================================
    if platform == "facebook" and access_token and customer_fb_id:
        await send_facebook_message(
            customer_fb_id,
            response_text,
            access_token,
            product_cards,
        )

    # ========================================
    # 11. RETURN RESPONSE
    # ========================================
    return {
        "success": True,
        "response": response_text,
        "products": product_cards,
        "recommendation_type": recommendation_type,
        "message_type": "product_card" if product_cards else "text",
        "memory_stats": {
            "conversation_messages": message_count,
            "memory_retrieved": len(context.get("memory_facts", [])),
            "has_summary": bool(context.get("previous_summary")),
            "embeddings_created": True,
        },
    }