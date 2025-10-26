# services/address_service.py

import asyncio
import re
from typing import Any, Dict, Optional, TypedDict
from ..utils.connect_supabase import create_supabase_client

# Định nghĩa kiểu cho dữ liệu địa chỉ trả về
class StandardizedAddress(TypedDict, total=False):
    address_line: str
    ward: Optional[str]
    district: Optional[str]
    city: str
    phone: Optional[str]
    full_name: Optional[str]

# Định nghĩa kiểu cho dữ liệu đầu vào khi lưu
class AddressDataInput(TypedDict, total=False):
    full_name: Optional[str]
    phone: Optional[str]
    address_line: str
    ward: Optional[str]
    district: Optional[str]
    city: str

# Định nghĩa kiểu cho kết quả trả về khi lưu
class SaveAddressResult(TypedDict, total=False):
    success: bool
    message: str
    address_id: Optional[str]


"""
Get saved address - Works for both logged users and guests
Priority: customer_profiles (structured fields) → addresses table
"""
async def get_standardized_address(
    conversation_id: str,
    retries: int = 2,
) -> Optional[StandardizedAddress]:
    supabase = create_supabase_client()

    print(f"🔍 Getting address for conversation: {conversation_id}")

    for attempt in range(1, retries + 1):
        try:
            # ========================================
            # 1. Get profile first
            # ========================================
            profile_select_query = """
                id, 
                user_id, 
                phone, 
                full_name,
                preferred_name,
                shipping_address_line,
                shipping_ward,
                shipping_district,
                shipping_city
            """
            
            # Giả định v2: .maybe_single() không cần .execute() và trả về data
            profile = supabase.from_("customer_profiles") \
                .select(profile_select_query) \
                .eq("conversation_id", conversation_id) \
                .maybe_single()

            if not profile:
                print("⚠️ No profile found")
                # Không cần retry nếu không tìm thấy profile
                return None

            print(f"📋 Profile found: {{'id': {profile.get('id')}, 'has_shipping_address': {bool(profile.get('shipping_address_line'))}, 'has_city': {bool(profile.get('shipping_city'))}, 'attempt': {attempt}}}")

            # ========================================
            # 2. Try customer_profiles structured fields FIRST
            # ========================================
            if profile.get("shipping_address_line") and profile.get("shipping_city"):
                print("✅ Loaded address from customer_profiles (structured)")

                address: StandardizedAddress = {
                    "address_line": profile["shipping_address_line"],
                    "ward": profile.get("shipping_ward"),
                    "district": profile.get("shipping_district"),
                    "city": profile["shipping_city"],
                    "phone": profile.get("phone"),
                    "full_name": profile.get("preferred_name") or profile.get("full_name"),
                }
                
                print(f"📍 Address data: {address}")
                return address

            # ========================================
            # 3. Fallback: addresses table (for logged users)
            # ========================================
            if profile.get("user_id"):
                print(f"🔍 Checking addresses table for user_id: {profile['user_id']}")

                address = supabase.from_("addresses") \
                    .select("*") \
                    .eq("user_id", profile["user_id"]) \
                    .eq("is_default", True) \
                    .maybe_single()

                if address:
                    print("✅ Loaded address from addresses table (fallback)")

                    # Sync to customer_profiles for faster access next time
                    # .update() cần .execute()
                    supabase.from_("customer_profiles") \
                        .update({
                            "shipping_address_line": address.get("address_line"),
                            "shipping_ward": address.get("ward"),
                            "shipping_district": address.get("district"),
                            "shipping_city": address.get("city"),
                        }) \
                        .eq("id", profile["id"]) \
                        .execute()

                    result_address: StandardizedAddress = {
                        "address_line": address["address_line"],
                        "ward": address.get("ward"),
                        "district": address.get("district"),
                        "city": address["city"],
                        "phone": address.get("phone") or profile.get("phone"),
                        "full_name": address.get("full_name") or profile.get("preferred_name") or profile.get("full_name"),
                    }
                    return result_address

            # ✅ No address found (or no user_id for fallback), retry if allowed
            if attempt < retries:
                print(f"⏳ No address found, retry {attempt}/{retries} in 100ms...")
                await asyncio.sleep(0.1)
                continue

            print("⚠️ No saved address found after all retries")
            return None

        except Exception as error:
            print(f"❌ Error in get_standardized_address (attempt {attempt}): {error}")
            
            if attempt < retries:
                await asyncio.sleep(0.1)
                continue
            
            return None

    return None


"""
Save address - Works for both logged users AND guest/Facebook users
"""
async def save_address_standardized(
    conversation_id: str,
    address_data: AddressDataInput,
) -> SaveAddressResult:
    
    # ========================================
    # VALIDATION
    # ========================================
    address_line = address_data.get("address_line", "").strip()
    phone = address_data.get("phone")
    city = address_data.get("city")

    if not address_line or len(address_line) < 5:
        return {
            "success": False,
            "message": "Địa chỉ quá ngắn, vui lòng cung cấp đầy đủ số nhà và tên đường",
        }

    if re.fullmatch(r"[\d\s]+", address_line):
        return {
            "success": False,
            "message": "Địa chỉ không hợp lệ",
        }

    if not re.match(r"^\d+", address_line):
        product_keywords = ["cao cấp", "lớp", "set", "vest", "quần", "áo"]
        if any(k in address_line.lower() for k in product_keywords):
            return {
                "success": False,
                "message": "Địa chỉ không hợp lệ - vui lòng cung cấp số nhà và tên đường",
            }

    if phone and not re.fullmatch(r"^[0+][\d]{9,11}$", phone):
        return {
            "success": False,
            "message": "Số điện thoại không hợp lệ",
        }

    if not city:
        return {
            "success": False,
            "message": "Thiếu thông tin thành phố",
        }

    print(f"✅ Address validation passed: {address_data}")

    supabase = create_supabase_client()

    try:
        # ========================================
        # 1. GET PROFILE
        # ========================================
        profile = supabase.from_("customer_profiles") \
            .select("id, user_id, conversation_id, full_name, phone") \
            .eq("conversation_id", conversation_id) \
            .maybe_single()

        if not profile:
            print("❌ Profile error: Not found")
            return {
                "success": False,
                "message": "Không tìm thấy profile khách hàng",
            }

        address_id: Optional[str] = None
        full_name_or_default = address_data.get("full_name") or profile.get("full_name") or "Khách hàng"
        phone_or_default = address_data.get("phone") or profile.get("phone") or ""

        # ========================================
        # 2. LOGGED USER → Save to addresses table
        # ========================================
        if profile.get("user_id"):
            print("✅ Logged user, saving to addresses table")

            existing_address = supabase.from_("addresses") \
                .select("id") \
                .eq("user_id", profile["user_id"]) \
                .eq("is_default", True) \
                .maybe_single()

            address_payload = {
                "user_id": profile["user_id"],
                "full_name": full_name_or_default,
                "phone": phone_or_default,
                "address_line": address_line,
                "city": city,
                "district": address_data.get("district") or "",
                "ward": address_data.get("ward") or "",
                "is_default": True,
            }
##
            if existing_address:
                response = supabase.from_("addresses") \
                    .update(address_payload) \
                    .eq("id", existing_address["id"]) \
                    .execute()
                
                if response.data:
                    address_id = response.data.get("id")
                    print(f"✅ Updated address in addresses table: {address_id}")
            else:
                response = supabase.from_("addresses") \
                    .insert(address_payload) \
                
                if response.data:
                    address_id = response.data.get("id")
                    print(f"✅ Created address in addresses table: {address_id}")

        # ========================================
        # 3. ALWAYS save to customer_profiles (for both guest and logged users)
        # ========================================
        print("💾 Saving to customer_profiles structured fields")

        profile_update_payload = {
            "shipping_address_line": address_line,
            "shipping_ward": address_data.get("ward"),
            "shipping_district": address_data.get("district"),
            "shipping_city": city,
        }
        
        # ✅ Also update phone if provided
        if address_data.get("phone"):
            profile_update_payload["phone"] = address_data["phone"]
        
        # ✅ Also update name if provided
        if address_data.get("full_name"):
            profile_update_payload["full_name"] = address_data["full_name"]
        

        update_response = supabase.from_("customer_profiles") \
            .update(profile_update_payload) \
            .eq("id", profile["id"]) \
            .execute()

        if update_response.data:
            return {
                "success": False,
                "message": "Lỗi khi lưu địa chỉ",
            }

        print("✅ Saved address to customer_profiles (structured fields)")

        # ========================================
        # 4. VERIFY SAVE ✅
        # ========================================
        # .single() không cần .execute() và trả về data
        verify_profile = supabase.from_("customer_profiles") \
            .select("shipping_address_line, shipping_city, phone") \
            .eq("id", profile["id"]) \
            .single()

        print(f"🔍 Verify saved data: {verify_profile}")

        return {
            "success": True,
            "message": "Đã lưu địa chỉ thành công",
            "address_id": address_id,
        }

    except Exception as error:
        print(f"❌ Error saving address: {error}")
        return {
            "success": False,
            "message": str(error) or "Lỗi khi lưu địa chỉ",
        }
