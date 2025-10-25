# ============================================
# handlers/message_handler.py - COMPLETE VERSION with Multi-Agent
# ============================================

import asyncio
import re
from typing import Dict, Any, Optional, List
from supabase import Client

# Import Services
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


# ============================================
# HELPER FUNCTIONS
# ============================================

def calculate_cost(tokens: int) -> float:
    """Tính toán chi phí dựa trên token."""
    return (tokens / 1_000_000) * 0.5


def is_confirmation(message_text: str) -> bool:
    """Kiểm tra xem tin nhắn có phải là lời xác nhận không."""
    text = message_text.lower().strip()
    return any(kw == text for kw in ["đúng rồi", "ok", "confirm", "chốt", "vâng ạ", "đúng", "vâng", "được", "ừ", "có"])


def is_order_intent(message_text: str) -> bool:
    """Kiểm tra xem tin nhắn có ý định đặt hàng không."""
    text = message_text.lower()
    return any(kw in text for kw in ["đặt hàng", "mua hàng", "chốt đơn", "gửi về", "ship về"])


async def handle_order_creation(params: dict) -> dict:
    """Xử lý logic tạo đơn hàng."""
    print("--- Đang xử lý tạo đơn hàng ---")
    context = params.get("context", {})
    conversation_id = params.get("conversationId")
    
    # Import order service
    from ..services.chatbot_order_service import create_chatbot_order
    
    # Check giỏ hàng
    cart = await get_or_create_cart(conversation_id)
    if not cart or len(cart) == 0:
        return {
            "success": False,
            "needProducts": True,
            "message": "Dạ giỏ hàng của chị đang trống. Chị muốn em tư vấn thêm sản phẩm nào ạ?"
        }

    # Check địa chỉ
    saved_address = context.get("saved_address")
    if not saved_address or not saved_address.get("address_line"):
        return {
            "success": False,
            "needAddress": True,
            "message": "Dạ, chị cho em xin địa chỉ và số điện thoại để em chốt đơn nhé."
        }
    
    # Check profile
    profile = context.get("profile")
    if not profile:
        return {
            "success": False,
            "message": "Không tìm thấy thông tin khách hàng."
        }
    
    # Tạo đơn hàng thực tế
    order_data = {
        "conversationId": conversation_id,
        "profileId": profile.get("id"),
        "customerName": saved_address.get("full_name") or profile.get("full_name") or "Khách hàng",
        "customerPhone": saved_address.get("phone") or profile.get("phone"),
        "customerFbId": context.get("customer", {}).get("fb_id"),
        "shippingAddress": saved_address["address_line"],
        "shippingWard": saved_address.get("ward"),
        "shippingDistrict": saved_address.get("district"),
        "shippingCity": saved_address.get("city"),
        "products": cart,
        "notes": None
    }
    
    result = await create_chatbot_order(order_data)
    
    if result.get("success"):
        order = result.get("order", {})
        order_summary = result.get("orderSummary", {})
        
        # Clear cart sau khi đặt hàng thành công
        from ..services.cart_service import clear_cart
        await clear_cart(conversation_id)
        
        return {
            "success": True,
            "message": f"Dạ em đã chốt đơn thành công cho chị! 📝\nMã đơn hàng: #{order.get('id')}\nTổng tiền: {order_summary.get('total', 0):,.0f} ₫\n\nBộ phận kho sẽ liên hệ chị trong hôm nay để xác nhận và giao hàng ạ 🚚\nCảm ơn chị đã tin tưởng BeWo 💕",
            "orderId": str(order.get('id'))
        }
    else:
        return {
            "success": False,
            "message": result.get("error", "Có lỗi xảy ra khi tạo đơn hàng. Vui lòng thử lại.")
        }


async def _create_summary_and_embedding(conversation_id: str, supabase: Client):
    """Hàm helper để chạy summary và embedding trong nền."""
    try:
        await create_conversation_summary(conversation_id)
        
        summary_resp = supabase.from_("conversation_summaries") \
            .select("summary_text, key_points") \
            .eq("conversation_id", conversation_id) \
            .order("summary_created_at", desc=True) \
            .limit(1) \
            .execute()
        
        if summary_resp.data and len(summary_resp.data) > 0:
            summary = summary_resp.data[0]
            await create_summary_embedding(
                conversation_id,
                summary.get("summary_text", ""),
                summary.get("key_points", []),
            )
            print("✅ Summary embedding created")
    except Exception as e:
        print(f"❌ Summary/Embedding creation error: {e}")


# ============================================
# MAIN MESSAGE HANDLER
# ============================================

async def handle_message(body: Dict[str, Any]):
    """
    Xử lý tin nhắn từ người dùng với Multi-Agent System
    """
    platform = body.get("platform")
    customer_fb_id = body.get("customer_fb_id")
    customer_phone = body.get("customer_phone")
    user_id = body.get("user_id")
    session_id = body.get("session_id")
    message_text = body.get("message_text", "")
    page_id = body.get("page_id")
    access_token = body.get("access_token")

    # ✅ Normalize platform - map "web" to "website" for database
    if platform == "web":
        platform = "website"
    
    db_platform = platform

    print(f"Processing message: {{'platform': '{db_platform}', 'message': '{message_text[:50]}...'}}")

    supabase = get_supabase_client()
    if not supabase:
        raise ValueError("Không thể khởi tạo Supabase client.")

    # ========================================
    # 1. GET OR CREATE CONVERSATION
    # ========================================
    try:
        rpc_params = {
            "p_platform": platform,  # ✅ Đã được normalize ở trên
            "p_customer_fb_id": customer_fb_id,
            "p_customer_phone": customer_phone,
            "p_user_id": user_id,
            "p_session_id": session_id,
            "p_customer_name": "Guest",
            "p_customer_avatar": None,
        }
        print(f"[DEBUG] RPC params: platform={platform}")
        conv_resp = supabase.rpc("get_or_create_conversation", rpc_params).execute()
        
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
        "hasSavedAddress": bool(context.get("saved_address")),
        "historyCount": len(context.get("history", [])),
        "memoryCount": len(context.get("memory_facts", [])),
        "cartCount": len(context.get("cart", [])),
    })

    # ========================================
    # 4. GENERATE RESPONSE - MULTI-AGENT SYSTEM
    # ========================================
    llm_result = await run_bewo_agent(message_text, context)
    
    response_text = llm_result["text"]
    tokens_used = llm_result.get("tokens", 0)
    recommendation_type = llm_result.get("type", "conversational")
    product_cards = llm_result.get("products", [])
    function_calls = llm_result.get("functionCalls", [])
    
    # Tính lại tokens nếu cần
    if tokens_used == 0:
        tokens_used = (len(message_text) + len(response_text)) // 4
    
    print("Response generated:", {
        "type": recommendation_type,
        "products": len(product_cards),
        "tokens": tokens_used,
        "functionCalls": len(function_calls)
    })

    # ========================================
    # 4.1. EXECUTE FUNCTION CALLS
    # ========================================
    if function_calls:
        print(f"🔧 Executing {len(function_calls)} function call(s)")
        
        for fn_call in function_calls:
            try:
                function_result = {"success": False}
                fn_name = fn_call["name"]
                fn_args = fn_call["args"]
                
                print(f"🔧 Executing: {fn_name}({fn_args})")
                
                # ========================================
                # FUNCTION 1: Save Customer Info
                # ========================================
                if fn_name == "save_customer_info":
                    function_result = await save_customer_profile(conversation_id, fn_args)
                    print(f"✅ Customer profile saved: {function_result.get('message')}")
                    
                    if function_result.get("success"):
                        # Update response text if needed
                        response_text += f"\n\n✅ Đã lưu thông tin: {fn_args.get('full_name', '')}"
                
                # ========================================
                # FUNCTION 2: Save Address
                # ========================================
                elif fn_name == "save_address":
                    print(f"🏠 Saving address: {fn_args}")
                    
                    # Validate
                    if not fn_args.get("address_line") or not fn_args.get("city"):
                        print("❌ Missing required address fields")
                        continue
                    
                    # Check if address_line is phone number
                    if re.match(r'^[\d\s]+$', fn_args.get("address_line", "")):
                        print("❌ address_line is phone number, using fallback")
                        fix_result = await extract_and_save_address(conversation_id, message_text)
                        function_result = {
                            "success": fix_result,
                            "message": "Đã lưu địa chỉ" if fix_result else "Không thể lưu địa chỉ"
                        }
                    else:
                        result = await save_address_standardized(conversation_id, {
                            "full_name": fn_args.get("full_name"),
                            "phone": fn_args.get("phone"),
                            "address_line": fn_args["address_line"],
                            "ward": fn_args.get("ward"),
                            "district": fn_args.get("district"),
                            "city": fn_args["city"]
                        })
                        
                        function_result = result
                        print(f"✅ Address saved: {result.get('message')}")
                        
                        if result.get("success"):
                            response_text += f"\n\n✅ Đã lưu địa chỉ giao hàng"
                
                # ========================================
                # FUNCTION 3: Add to Cart
                # ========================================
                elif fn_name == "add_to_cart":
                    product_id = fn_args.get("product_id")
                    size = fn_args.get("size")
                    quantity = fn_args.get("quantity", 1)
                    
                    print(f"🛒 Adding to cart: product_id={product_id}, size={size}, quantity={quantity}")
                    
                    # Get product details
                    prod_resp = supabase.from_("products").select(
                        "id, name, price, images:product_images(image_url, is_primary)"
                    ).eq("id", product_id).limit(1).execute()
                    
                    if prod_resp.data and len(prod_resp.data) > 0:
                        product = prod_resp.data[0]
                        images = product.get("images", [])
                        primary_image = next((img["image_url"] for img in images if img.get("is_primary")), None)
                        first_image = images[0]["image_url"] if images else None
                        
                        cart_item = {
                            "product_id": product_id,
                            "name": product["name"],
                            "price": product.get("price", 0),
                            "size": size,
                            "quantity": quantity,
                            "image": primary_image or first_image
                        }
                        
                        updated_cart = await add_to_cart(conversation_id, cart_item)
                        
                        function_result = {
                            "success": True,
                            "message": f"Đã thêm {product['name']} vào giỏ hàng",
                            "cart_count": len(updated_cart)
                        }
                        
                        print(f"✅ Added to cart: {product['name']}")
                        response_text += f"\n\n🛒 Đã thêm vào giỏ: {product['name']} (Size {size}) x{quantity}"
                    else:
                        function_result = {
                            "success": False,
                            "message": "Không tìm thấy sản phẩm"
                        }
                        print(f"❌ Product not found: {product_id}")
                
                # ========================================
                # FUNCTION 4: Confirm Order
                # ========================================
                elif fn_name == "confirm_and_create_order":
                    if fn_args.get("confirmed"):
                        print("📦 Creating order...")
                        order_result = await handle_order_creation({
                            "conversationId": conversation_id,
                            "message_text": message_text,
                            "aiResponse": llm_result,
                            "context": context
                        })
                        
                        function_result = order_result
                        
                        if order_result.get("success"):
                            response_text = order_result["message"]
                            print(f"✅ Order created: {order_result.get('orderId')}")
                        else:
                            response_text = order_result["message"]
                            print(f"❌ Order failed: {order_result['message']}")
                
                else:
                    print(f"⚠️ Unknown function: {fn_name}")
                    
            except Exception as e:
                print(f"❌ Function execution error ({fn_name}): {e}")
                import traceback
                traceback.print_exc()

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
                "aiResponse": llm_result,
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
            "aiResponse": llm_result,
            "context": context
        })
        
        response_text = order_result["message"]

    # ========================================
    # 5. SAVE BOT RESPONSE
    # ========================================
    try:
        bot_msg_content = {
            "text": response_text,
            "products": product_cards,
            "recommendation_type": recommendation_type,
        }
        
        bot_msg_resp = supabase.from_("chatbot_messages") \
            .insert({
                "conversation_id": conversation_id,
                "sender_type": "bot",
                "message_type": "product_card" if product_cards else "text",
                "content": bot_msg_content,
                "tokens_used": tokens_used,
            }) \
            .execute()

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
    # 7-8. MEMORY PROCESSING
    # ========================================
    asyncio.create_task(
        extract_and_save_memory(conversation_id, message_text, llm_result)
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