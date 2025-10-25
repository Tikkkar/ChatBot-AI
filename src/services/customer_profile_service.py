# ============================================
# services/customer_profile_service.py
# ============================================

from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, TypedDict
from supabase import Client

# Giả định bạn có hàm create_supabase_client trong connect_supabase.py
from ..utils.connect_supabase import create_supabase_client

# ============================================
# ĐỊNH NGHĨA TYPE (TYPESCRIPT INTERFACES)
# ============================================

class CustomerProfileData(TypedDict, total=False):
    full_name: Optional[str]
    preferred_name: Optional[str]
    phone: Optional[str]
    height: Optional[int]
    weight: Optional[int]
    usual_size: Optional[str]
    style_preference: Optional[List[str]]

class SaveProfileResult(TypedDict):
    success: bool
    message: str

# ============================================
# HÀM HELPER
# ============================================

def _build_fact_text(data: CustomerProfileData) -> str:
    """
    Build memory fact text from data
    """
    parts: List[str] = []

    preferred_name = data.get("preferred_name")
    full_name = data.get("full_name")
    phone = data.get("phone")
    height = data.get("height")
    weight = data.get("weight")
    usual_size = data.get("usual_size")
    style_preference = data.get("style_preference")

    if preferred_name or full_name:
        parts.append(f"Tên: {preferred_name or full_name}")
    if phone:
        parts.append(f"SĐT: {phone}")
    if height and weight:
        parts.append(f"Vóc dáng: {height}cm, {weight}kg")
    if usual_size:
        parts.append(f"Size thường mặc: {usual_size}")
    if style_preference and len(style_preference) > 0:
        parts.append(f"Phong cách: {', '.join(style_preference)}")

    return " | ".join(parts)

# ============================================
# HÀM CHÍNH
# ============================================

"""
Save or update customer profile information
"""
async def save_customer_profile(
    conversation_id: str,
    data: CustomerProfileData,
) -> SaveProfileResult:
    
    supabase = create_supabase_client()

    try:
        # Get profile
        profile_resp = supabase.from_("customer_profiles") \
            .select("id, full_name, phone") \
            .eq("conversation_id", conversation_id) \
            .single() \
            .execute()

        if profile_resp.error or not profile_resp.data:
            print(f"❌ Error fetching profile: {profile_resp.error}")
            return {
                "success": False,
                "message": "Không tìm thấy profile khách hàng",
            }
        
        profile = profile_resp.data

        # Build update object
        updates: Dict[str, Any] = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Lọc các giá trị None/empty trước khi thêm vào updates
        if data.get("full_name"):
            updates["full_name"] = data["full_name"]
        if data.get("preferred_name"):
            updates["preferred_name"] = data["preferred_name"]
        if data.get("phone"):
            updates["phone"] = data["phone"]
        if data.get("height"):
            updates["height"] = data["height"]
        if data.get("weight"):
            updates["weight"] = data["weight"]
        if data.get("usual_size"):
            updates["usual_size"] = data["usual_size"]
        if data.get("style_preference") and len(data["style_preference"]) > 0:
            updates["style_preference"] = data["style_preference"]

        # Update profile
        update_resp = supabase.from_("customer_profiles") \
            .update(updates) \
            .eq("id", profile["id"]) \
            .execute()

        if update_resp.error:
            raise update_resp.error

        # Save as memory fact
        fact_text = _build_fact_text(data)
        if fact_text:
            supabase.from_("customer_memory_facts") \
                .insert({
                    "customer_profile_id": profile["id"],
                    "fact_type": "personal_info",
                    "fact_text": fact_text,
                    "importance_score": 8,
                    "source_conversation_id": conversation_id,
                    "metadata": data,
                }) \
                .execute()

        print(f"✅ Customer profile saved: {updates}")

        return {
            "success": True,
            "message": "Đã lưu thông tin khách hàng",
        }
    
    except Exception as error:
        print(f"❌ Error saving customer profile: {error}")
        # Đảm bảo message là một chuỗi
        error_message = getattr(error, 'message', str(error))
        return {
            "success": False,
            "message": error_message or "Lỗi khi lưu thông tin",
        }
