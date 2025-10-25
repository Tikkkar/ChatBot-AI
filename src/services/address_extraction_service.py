# ============================================
# services/address_extraction_service.py - SIMPLIFIED (LLM ONLY)
# ============================================

from typing import Any
import asyncio

# Giả định file 'address_service.py' nằm cùng cấp
# và chứa hàm 'get_standardized_address'
from .address_service import get_standardized_address

# Lưu ý: createSupabaseClient và saveAddressStandardized đã được import
# trong file .ts gốc nhưng không được sử dụng,
# nên chúng được bỏ qua trong file Python này.

"""
Get saved address (STANDARDIZED)
Ưu tiên: addresses table → memory_facts (fallback)
"""
async def get_saved_address(conversation_id: str) -> Any:
    """
    Lấy địa chỉ đã lưu (ĐÃ CHUẨN HÓA).
    Hàm này đã cũ (deprecated) và chỉ chuyển tiếp cuộc gọi.
    """
    print(
        "⚠️ get_saved_address() is deprecated. Use get_standardized_address() from address_service.py",
    )
    # ✅ Delegate to the correct function
    return await get_standardized_address(conversation_id)

"""
⚠️ DEPRECATED - Không dùng function này nữa
Địa chỉ giờ được xử lý bởi LLM qua function calling
Giữ lại function này chỉ để backward compatibility
"""
async def extract_and_save_address(
    conversation_id: str,
    message_text: str,
) -> bool:
    """
    Hàm này đã cũ (deprecated) và không còn chức năng.
    """
    print(
        "⚠️ extract_and_save_address is deprecated. Use LLM function calling instead.",
    )
    return False

