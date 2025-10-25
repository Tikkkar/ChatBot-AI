# ============================================
# services/memory_service.py - UPDATED VERSION
# CHỈ lưu insights vào memory_facts
# Structured data → tables riêng (customer_profiles, addresses)
# ============================================

import asyncio
import re
from typing import List, Dict, Optional, Any, TypedDict
from supabase import Client
from datetime import datetime, timezone, timedelta

# Giả định bạn có hàm create_supabase_client trong connect_supabase.py
from ..utils.connect_supabase import create_supabase_client

# ============================================
# ĐỊNH NGHĨA TYPE (TYPESCRIPT INTERFACES)
# ============================================

class AIResponseProduct(TypedDict):
    id: str

class AIResponse(TypedDict, total=False):
    text: str
    tokens: int
    type: str
    products: List[AIResponseProduct]

class MessageContent(TypedDict):
    text: str

class Message(TypedDict, total=False):
    content: MessageContent
    sender_type: str
    created_at: str

class PreferenceUpdates(TypedDict, total=False):
    color_preference: List[str]
    style_preference: List[str]
    material_preference: List[str]
    price_range: Dict[str, int]

class MemoryFact(TypedDict, total=False):
    customer_profile_id: str
    fact_type: str
    fact_text: str
    importance_score: int
    source_conversation_id: str
    expires_at: Optional[str]


# ============================================
# CORE FUNCTIONS
# ============================================

"""
Get or create customer profile
"""
async def get_or_create_profile(conversation_id: str) -> Optional[str]:
    supabase = create_supabase_client()

    try:
        response = supabase.rpc("get_or_create_customer_profile", {
            "p_conversation_id": conversation_id,
        }).execute()

        if not response.data:
            print(f"Error getting profile: {response.error}")
            return None

        # RPC có thể trả về một mảng hoặc một đối tượng đơn lẻ
        data = response.data
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        elif isinstance(data, (str, dict)): # Giả sử nó trả về ID (str) hoặc object
             # Nếu là dict, giả sử ID là 'id'
            if isinstance(data, dict):
                return data.get("id")
            return data # Giả sử trả về trực tiếp ID
        
        return None

    except Exception as e:
        print(f"Exception in get_or_create_profile: {e}")
        return None


"""
Extract and save memory from message
⚠️ CHỈ lưu insights, KHÔNG lưu structured data (name, phone, address)
"""
async def extract_and_save_memory(
    conversation_id: str,
    message_text: str,
    ai_response: AIResponse,
) -> None:
    supabase = create_supabase_client()

    # Get profile ID
    profile_id = await get_or_create_profile(conversation_id)
    if not profile_id:
        print("Failed to get profile ID, skipping memory save.")
        return

    # ⚠️ CHỈ extract preferences và interests
    # KHÔNG extract name, phone, address (đã có function calling xử lý)
    await asyncio.gather(
        extract_preferences(supabase, profile_id, message_text),
        extract_interests(supabase, profile_id, ai_response.get("products", [])),
    )

    # Update engagement
    try:
        supabase.rpc("update_customer_engagement", {
            "p_profile_id": profile_id,
        }).execute()
    except Exception as e:
        print(f"Error updating engagement: {e}")

"""
❌ REMOVED: extractPersonalInfo
Không còn extract name/phone/address ở đây nữa
Đã có AI function calling xử lý (save_customer_info, save_address)
"""

"""
Extract preferences (style, color, price)
CHỈ lưu vào customer_profiles.style_preference, color_preference (jsonb)
"""
async def extract_preferences(
    supabase: Client,
    profile_id: str,
    text: str,
) -> None:
    text_lower = text.lower()
    updates: PreferenceUpdates = {}

    try:
        # Get current profile
        profile_resp = supabase.from_("customer_profiles") \
            .select("style_preference, color_preference, material_preference") \
            .eq("id", profile_id) \
            .single() \
            .execute()

        if profile_resp.error or not profile_resp.data:
            print(f"Failed to get profile for preferences: {profile_resp.error}")
            return

        profile = profile_resp.data

        # Extract colors
        colors = [
            "đen", "trắng", "be", "xanh", "đỏ", "vàng", "hồng", "nâu", "xám", "navy", "kem", "pastel",
        ]
        mentioned_colors = [color for color in colors if color in text_lower]

        if mentioned_colors:
            existing_colors: List[str] = profile.get("color_preference") or []
            updates["color_preference"] = list(set(existing_colors + mentioned_colors))

        # Extract style
        styles = [
            "thanh lịch", "công sở", "casual", "thể thao", "sang trọng", "trẻ trung", "cổ điển", "hiện đại",
        ]
        mentioned_styles = [style for style in styles if style in text_lower]

        if mentioned_styles:
            existing_styles: List[str] = profile.get("style_preference") or []
            updates["style_preference"] = list(set(existing_styles + mentioned_styles))

        # Extract material preference
        materials = ["linen", "cotton", "silk", "kaki", "jean", "polyester"]
        mentioned_materials = [mat for mat in materials if mat in text_lower]

        if mentioned_materials:
            existing_materials: List[str] = profile.get("material_preference") or []
            updates["material_preference"] = list(set(existing_materials + mentioned_materials))

        # Extract price range
        price_matches = re.findall(r"(\d{1,3})[.,]?(\d{3})", text)
        if len(price_matches) >= 2:
            prices = [int("".join(p)) for p in price_matches]
            updates["price_range"] = {
                "min": min(prices),
                "max": max(prices),
            }

        # Update if found anything
        if updates:
            print(f"✅ Extracted preferences: {updates}")
            supabase.from_("customer_profiles") \
                .update(updates) \
                .eq("id", profile_id) \
                .execute()

    except Exception as e:
        print(f"Error extracting preferences: {e}")

"""
Save product interests
"""
async def extract_interests(
    supabase: Client,
    profile_id: str,
    products: List[AIResponseProduct],
) -> None:
    if not products:
        return

    print(f"💡 Saving {len(products)} product interests")
    
    now_iso = datetime.now(timezone.utc).isoformat()

    for product in products:
        try:
            product_id = product.get("id")
            if not product_id:
                continue

            # Check if interest exists
            existing_resp = supabase.from_("customer_interests") \
                .select("*") \
                .eq("customer_profile_id", profile_id) \
                .eq("product_id", product_id) \
                .eq("interest_type", "viewed") \
                .maybe_single() \
                .execute()
            
            existing = existing_resp.data

            if existing:
                # Increment view count
                supabase.from_("customer_interests") \
                    .update({
                        "view_count": existing.get("view_count", 0) + 1,
                        "last_viewed_at": now_iso,
                    }) \
                    .eq("id", existing["id"]) \
                    .execute()
            else:
                # Create new interest
                supabase.from_("customer_interests") \
                    .insert({
                        "customer_profile_id": profile_id,
                        "product_id": product_id,
                        "interest_type": "viewed",
                        "sentiment": "positive",
                        # last_viewed_at tự động default NOW()
                    }) \
                    .execute()
        except Exception as e:
            print(f"Error saving interest for product {product.get('id')}: {e}")


"""
Extract and save memory facts
⚠️ CHỈ LƯU INSIGHTS - KHÔNG lưu structured data
"""
async def extract_memory_facts(
    profile_id: str,
    message_text: str,
    conversation_id: str,
) -> None:
    supabase = create_supabase_client()
    text_lower = message_text.lower()
    facts: List[MemoryFact] = []

    try:
        # ========================================
        # 1. PREFERENCES (Sở thích)
        # ========================================
        
        # Negative preferences (không thích)
        negative_patterns = [
            re.compile(r"không\s+thích\s+([^.,!?\n]+)", re.IGNORECASE),
            re.compile(r"không\s+ưng\s+([^.,!?\n]+)", re.IGNORECASE),
            re.compile(r"ghét\s+([^.,!?\n]+)", re.IGNORECASE),
        ]

        for pattern in negative_patterns:
            for match in re.finditer(pattern, message_text):
                preference = match.group(1).strip()
                if "địa chỉ" not in preference and "sđt" not in preference and len(preference) < 50:
                    facts.append({
                        "customer_profile_id": profile_id,
                        "fact_type": "preference",
                        "fact_text": f"Không thích {preference}",
                        "importance_score": 8,
                        "source_conversation_id": conversation_id,
                    })

        # Positive preferences (thích)
        positive_patterns = [
            re.compile(r"thích\s+([^.,!?\n]+)", re.IGNORECASE),
            re.compile(r"ưng\s+([^.,!?\n]+)", re.IGNORECASE),
            re.compile(r"yêu thích\s+([^.,!?\n]+)", re.IGNORECASE),
        ]
        
        for pattern in positive_patterns:
            for match in re.finditer(pattern, message_text):
                preference = match.group(1).strip()
                if "địa chỉ" not in preference and "sđt" not in preference and len(preference) < 50:
                    facts.append({
                        "customer_profile_id": profile_id,
                        "fact_type": "preference",
                        "fact_text": f"Thích {preference}",
                        "importance_score": 8,
                        "source_conversation_id": conversation_id,
                    })

        # Fit preferences
        if "rộng" in text_lower or "thoải mái" in text_lower:
            facts.append({
                "customer_profile_id": profile_id, "fact_type": "preference",
                "fact_text": "Thích đồ rộng, thoải mái", "importance_score": 7,
                "source_conversation_id": conversation_id,
            })
        
        if "ôm" in text_lower and "không" in text_lower:
            facts.append({
                "customer_profile_id": profile_id, "fact_type": "preference",
                "fact_text": "Không thích đồ ôm", "importance_score": 7,
                "source_conversation_id": conversation_id,
            })

        # ========================================
        # 2. CONSTRAINTS (Hạn chế)
        # ========================================
        
        budget_patterns = [
            re.compile(r"(?:dưới|không quá|tối đa|budget|ngân sách)\s+(\d+[kK]?)", re.IGNORECASE),
            re.compile(r"khoảng\s+(\d+)\s*[-–]\s*(\d+)\s*[kK]?", re.IGNORECASE),
        ]

        for pattern in budget_patterns:
            for match in re.finditer(pattern, message_text):
                facts.append({
                    "customer_profile_id": profile_id, "fact_type": "constraint",
                    "fact_text": f"Budget: {match.group(0)}", "importance_score": 9,
                    "source_conversation_id": conversation_id,
                })

        # Time constraints
        if "gấp" in text_lower or "nhanh" in text_lower:
            expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
            facts.append({
                "customer_profile_id": profile_id, "fact_type": "constraint",
                "fact_text": "Cần gấp, thời gian hạn chế", "importance_score": 8,
                "source_conversation_id": conversation_id, "expires_at": expires,
            })

        # ========================================
        # 3. LIFE EVENTS (Sự kiện)
        # ========================================
        
        event_patterns = {
            "đi làm": 6, "dự tiệc": 8, "du lịch": 7, "đám cưới": 9,
            "phỏng vấn": 9, "sự kiện quan trọng": 9, "họp": 7, "gặp khách": 8,
        }
        
        expires_event = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        for keyword, importance in event_patterns.items():
            if keyword in text_lower:
                facts.append({
                    "customer_profile_id": profile_id, "fact_type": "life_event",
                    "fact_text": f"Sắp {keyword}", "importance_score": importance,
                    "source_conversation_id": conversation_id, "expires_at": expires_event,
                })

        # ========================================
        # 4. SPECIAL REQUESTS (Yêu cầu đặc biệt)
        # ========================================
        
        if "giao" in text_lower and ("sáng" in text_lower or "chiều" in text_lower):
            time_of_day = "buổi sáng" if "sáng" in text_lower else "buổi chiều"
            facts.append({
                "customer_profile_id": profile_id, "fact_type": "special_request",
                "fact_text": f"Yêu cầu giao hàng {time_of_day}", "importance_score": 8,
                "source_conversation_id": conversation_id,
            })

        if "đóng gói" in text_lower and "quà" in text_lower:
            facts.append({
                "customer_profile_id": profile_id, "fact_type": "special_request",
                "fact_text": "Yêu cầu đóng gói quà tặng", "importance_score": 7,
                "source_conversation_id": conversation_id,
            })

        # ========================================
        # 5. COMPLAINTS/COMPLIMENTS
        # ========================================
        
        complaint_keywords = ["chậm", "lâu", "tệ", "kém", "không tốt", "thất vọng"]
        has_complaint = any(k in text_lower for k in complaint_keywords)

        if has_complaint and ("lần trước" in text_lower or "trước đây" in text_lower):
            facts.append({
                "customer_profile_id": profile_id, "fact_type": "complaint",
                "fact_text": "Có phản hồi tiêu cực về trải nghiệm trước", "importance_score": 9,
                "source_conversation_id": conversation_id,
            })

        compliment_keywords = ["tuyệt", "tốt", "đẹp", "hài lòng", "thích", "ưng"]
        has_compliment = sum(1 for k in compliment_keywords if k in text_lower) >= 2

        if has_compliment:
            facts.append({
                "customer_profile_id": profile_id, "fact_type": "compliment",
                "fact_text": "Hài lòng với sản phẩm/dịch vụ", "importance_score": 7,
                "source_conversation_id": conversation_id,
            })

        # ========================================
        # SAVE ALL FACTS
        # ========================================
        
        if facts:
            print(f"✅ Saving {len(facts)} memory facts (insights only)")

            # Deactivate duplicate facts
            for fact in facts:
                supabase.from_("customer_memory_facts") \
                    .update({"is_active": False}) \
                    .eq("customer_profile_id", profile_id) \
                    .eq("fact_type", fact["fact_type"]) \
                    .eq("fact_text", fact["fact_text"]) \
                    .execute()
            
            # Insert new facts
            supabase.from_("customer_memory_facts").insert(facts).execute()

    except Exception as e:
        print(f"Error extracting memory facts: {e}")

"""
Create conversation summary
"""
async def create_conversation_summary(conversation_id: str) -> None:
    supabase = create_supabase_client()

    try:
        # Get all messages
        messages_resp = supabase.from_("chatbot_messages") \
            .select("content, sender_type, created_at") \
            .eq("conversation_id", conversation_id) \
            .order("created_at", ascending=True) \
            .execute()

        if messages_resp.error or not messages_resp.data or len(messages_resp.data) < 5:
            print("Not enough messages to summarize.")
            return

        messages: List[Message] = messages_resp.data

        customer_messages = [
            m["content"]["text"] for m in messages if m.get("sender_type") == "customer"
        ]
        
        if not customer_messages:
            return

        all_text = " ".join(customer_messages).lower()

        # Extract key points
        key_points: List[str] = []
        if "áo" in all_text: key_points.append("Quan tâm áo")
        if "quần" in all_text: key_points.append("Quan tâm quần")
        if "váy" in all_text: key_points.append("Quan tâm váy")
        if "vest" in all_text: key_points.append("Quan tâm vest")
        if "size" in all_text: key_points.append("Đã hỏi size")
        if "giá" in all_text: key_points.append("Hỏi giá")
        if "màu" in all_text: key_points.append("Hỏi về màu sắc")
        if "đặt" in all_text or "mua" in all_text: key_points.append("Có ý định mua")
        if "địa chỉ" in all_text: key_points.append("Đã cung cấp địa chỉ")

        # Determine intent
        intent = "browsing"
        if "đặt hàng" in all_text or "mua" in all_text or "chốt" in all_text:
            intent = "buying"
        elif "so sánh" in all_text or "chất liệu" in all_text:
            intent = "researching"
        elif "giao hàng" in all_text or "ship" in all_text:
            intent = "asking_support"

        # Calculate sentiment
        positive_words = ["tuyệt", "đẹp", "thích", "ok", "được", "hay", "ưng", "tốt"]
        negative_words = ["không", "chưa", "tệ", "xấu", "kém", "chậm"]

        positive_count = sum(1 for w in positive_words if w in all_text)
        negative_count = sum(1 for w in negative_words if w in all_text)

        sentiment = "neutral"
        sentiment_score = 0.0

        if positive_count > negative_count + 2:
            sentiment = "positive"
            sentiment_score = 0.7
        elif negative_count > positive_count + 2:
            sentiment = "negative"
            sentiment_score = -0.7

        # Determine outcome
        outcome = "pending"
        if "đặt hàng" in all_text or "chốt đơn" in all_text:
            outcome = "purchased"
        elif "cảm ơn" in all_text and sentiment == "positive":
            outcome = "resolved"
        elif len(key_points) > 3:
            outcome = "needs_followup"

        # Create summary text
        summary = f"Khách đã trao đổi {len(messages)} tin nhắn. {', '.join(key_points)}."

        # Save summary
        supabase.from_("conversation_summaries").insert({
            "conversation_id": conversation_id,
            "summary_text": summary,
            "key_points": key_points,
            "customer_intent": intent,
            "sentiment": sentiment,
            "sentiment_score": sentiment_score,
            "message_count": len(messages),
            "customer_messages": len(customer_messages),
            "bot_messages": len(messages) - len(customer_messages),
            "outcome": outcome,
        }).execute()

        print("✅ Conversation summary created")

    except Exception as e:
        print(f"Error creating summary: {e}")

"""
Load customer memory for context
"""
async def load_customer_memory(conversation_id: str) -> Optional[Dict[str, Any]]:
    supabase = create_supabase_client()

    try:
        # Get profile
        profile_resp = supabase.from_("customer_profiles") \
            .select("*") \
            .eq("conversation_id", conversation_id) \
            .maybe_single() \
            .execute()

        if profile_resp.error or not profile_resp.data:
            print("No profile found for memory load.")
            return None
        
        profile = profile_resp.data

        # Get interests
        interests_resp = supabase.from_("customer_interests") \
            .select("""
                product_id,
                interest_type,
                view_count,
                last_viewed_at,
                products (id, name, price, slug)
            """) \
            .eq("customer_profile_id", profile["id"]) \
            .order("last_viewed_at", ascending=False) \
            .limit(5) \
            .execute()

        # Get memory facts (CHỈ insights, không có structured data)
        facts_resp = supabase.from_("customer_memory_facts") \
            .select("fact_text, fact_type, importance_score") \
            .eq("customer_profile_id", profile["id"]) \
            .eq("is_active", True) \
            .order("importance_score", ascending=False) \
            .limit(10) \
            .execute()

        # Get summary
        summary_resp = supabase.from_("conversation_summaries") \
            .select("summary_text, key_points, customer_intent, sentiment") \
            .eq("conversation_id", conversation_id) \
            .order("summary_created_at", ascending=False) \
            .limit(1) \
            .maybe_single() \
            .execute()

        return {
            "profile": profile,
            "interests": interests_resp.data or [],
            "facts": facts_resp.data or [],
            "summary": summary_resp.data or None,
        }

    except Exception as e:
        print(f"Error loading customer memory: {e}")
        return None
