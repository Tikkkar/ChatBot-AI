# ============================================
# services/chatbot_order_service.py
# Tạo đơn hàng từ chatbot (không cần user_id)
# ============================================

import asyncio
import re
from typing import List, Dict, Optional, Any, TypedDict
from supabase import Client

# Giả định bạn có hàm create_supabase_client trong connect_supabase.py
from ..utils.connect_supabase import create_supabase_client

# ============================================
# ĐỊNH NGHĨA TYPE (TYPESCRIPT INTERFACES)
# ============================================

class ProductOrder(TypedDict, total=False):
    product_id: str
    name: str
    price: float
    size: str
    quantity: int
    image: str

class OrderData(TypedDict, total=False):
    conversationId: str
    profileId: str
    customerName: str
    customerPhone: str
    customerFbId: Optional[str]
    shippingAddress: str
    shippingWard: Optional[str]
    shippingDistrict: Optional[str]
    shippingCity: Optional[str]
    products: List[ProductOrder]
    notes: Optional[str]

class OrderSummary(TypedDict, total=False):
    subtotal: float
    shippingFee: float
    discountAmount: float
    total: float
    products: int

class CreateOrderResult(TypedDict, total=False):
    success: bool
    error: Optional[str]
    order: Optional[Dict[str, Any]] # Kiểu dữ liệu của đơn hàng trả về từ Supabase
    orderSummary: Optional[OrderSummary]


# ============================================
# HÀM CHÍNH
# ============================================

async def create_chatbot_order(data: OrderData) -> CreateOrderResult:
    supabase = create_supabase_client()

    print(f"🛒 Creating chatbot order for: {data.get('customerPhone')}")

    # ========================================
    # 0. VALIDATION
    # ========================================
    
    customer_name = data.get("customerName", "").strip()
    customer_phone = data.get("customerPhone", "").strip()
    shipping_address = data.get("shippingAddress", "").strip()
    products = data.get("products", [])
    shipping_city = data.get("shippingCity", "").strip()

    if not customer_name:
        print("❌ Missing customer name")
        return {
            "success": False,
            "error": "Thiếu tên khách hàng",
            "orderSummary": None,
        }

    if not customer_phone or not re.fullmatch(r"^[0+][\d]{9,11}$", customer_phone):
        print(f"❌ Invalid customer phone: {customer_phone}")
        return {
            "success": False,
            "error": "Số điện thoại không hợp lệ",
            "orderSummary": None,
        }

    if not shipping_address or len(shipping_address) < 5:
        print(f"❌ Missing or invalid shipping address: {shipping_address}")
        return {
            "success": False,
            "error": "Địa chỉ giao hàng không hợp lệ",
            "orderSummary": None,
        }

    if not products:
        print("❌ No products in order")
        return {
            "success": False,
            "error": "Không có sản phẩm trong đơn hàng",
            "orderSummary": None,
        }

    # Validate shippingCity (should be provided)
    if not shipping_city:
        print("⚠️ Missing shipping city, attempting to extract from address")
        # Try to extract city from address
        city_match = re.search(
            r",\s*(Hà Nội|TP\.?HCM|TP\s*Hồ Chí Minh|Đà Nẵng|Hải Phòng|Cần Thơ)$",
            shipping_address,
            re.IGNORECASE,
        )
        if city_match:
            shipping_city = city_match.group(1)
            data["shippingCity"] = shipping_city # Cập nhật lại data
        else:
            print("❌ Cannot determine shipping city")
            return {
                "success": False,
                "error": "Không xác định được thành phố giao hàng",
                "orderSummary": None,
            }
    
    print("✅ Validation passed")

    try:
        # ========================================
        # 1. CALCULATE TOTALS
        # ========================================
        subtotal = sum(p.get("price", 0) * p.get("quantity", 0) for p in products)
        shipping_fee = 0.0 if subtotal >= 300000 else 30000.0
        discount_amount = 0.0
        total_amount = subtotal + shipping_fee - discount_amount

        # ========================================
        # 2. PREPARE PRODUCT DETAILS
        # ========================================
        product_details = [
            {
                "product_id": p["product_id"],
                "name": p["name"],
                "price": p["price"],
                "size": p.get("size") or "One Size",
                "quantity": p["quantity"],
                "image": p.get("image"),
            }
            for p in products
        ]
        
        product_ids = [p["product_id"] for p in products]

        # ========================================
        # 3. CREATE CHATBOT ORDER
        # ========================================
        order_payload = {
            "conversation_id": data["conversationId"],
            "profile_id": data["profileId"],
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "customer_fb_id": data.get("customerFbId"),
            "shipping_address": shipping_address,
            "shipping_ward": data.get("shippingWard", "").strip() or None,
            "shipping_district": data.get("shippingDistrict", "").strip() or None,
            "shipping_city": shipping_city,
            "product_ids": product_ids,
            "product_details": product_details,
            "subtotal": subtotal,
            "shipping_fee": shipping_fee,
            "discount_amount": discount_amount,
            "total_amount": total_amount,
            "status": "pending",
            "notes": data.get("notes", "").strip() or None,
        }

        order_response = supabase.from_("chatbot_orders") \
            .insert(order_payload) \

        if order_response.data:
            print(f"❌ Error creating chatbot order: {order_response.data}")
            return {
                "success": False,
                "orderSummary": None,
            }

        order = order_response.data
        print(f"✅ Chatbot order created: {order['id']}")

        # ========================================
        # 4. UPDATE STOCK - NON-BLOCKING (LOG ERRORS)
        # ========================================
        try:
            for product in products:
                await update_product_stock(
                    supabase,
                    product["product_id"],
                    product.get("size", "One Size"), # Đảm bảo có size
                    product["quantity"],
                )
            print("✅ Stock updated for all products")
        except Exception as stock_error:
            print(f"⚠️ Stock update failed (non-blocking): {stock_error}")
            # Order is already created, just log the issue

        # ========================================
        # 5. SAVE AS MEMORY FACT - NON-BLOCKING
        # ========================================
        try:
            product_names = ", ".join([p.get("name", "N/A") for p in products])
            supabase.from_("customer_memory_facts").insert({
                "customer_profile_id": data["profileId"],
                "fact_type": "special_request",
                "fact_text": f"Đã đặt hàng: {product_names}",
                "importance_score": 8,
                "source_conversation_id": data["conversationId"],
            }).execute()
            print("✅ Memory fact saved")
        except Exception as memory_error:
            print(f"⚠️ Memory fact save failed (non-blocking): {memory_error}")

        # ========================================
        # 6. RETURN SUCCESS
        # ========================================
        order_summary_result: OrderSummary = {
            "subtotal": subtotal,
            "shippingFee": shipping_fee,
            "discountAmount": discount_amount,
            "total": total_amount,
            "products": len(products),
        }
        
        return {
            "success": True,
            "order": order,
            "orderSummary": order_summary_result,
        }

    except Exception as error:
        print(f"❌ Unexpected error in create_chatbot_order: {error}")
        return {
            "success": False,
            "error": str(error) or "Lỗi không xác định",
            "orderSummary": None,
        }

# ============================================
# HÀM HELPER
# ============================================

async def update_product_stock(
    supabase: Client,
    product_id: str,
    size: str,
    quantity: int,
) -> None:
    """
    Cập nhật tồn kho (product và product_sizes).
    Hàm này sẽ log lỗi nếu có, nhưng không ném ra (non-blocking).
    """
    try:
        # Update main product stock
        product_resp = supabase.from_("products") \
            .select("stock") \
            .eq("id", product_id) \
            .single() \
            .execute()

        if product_resp.error:
            print(f"⚠️ Product not found for stock update: {product_id}. Error: {product_resp.error}")
            return # Non-blocking

        if product_resp.data:
            current_stock = product_resp.data.get("stock", 0)
            new_stock = max(0, current_stock - quantity)
            
            update_resp = supabase.from_("products") \
                .update({"stock": new_stock}) \
                .eq("id", product_id) \
                .execute()
                
            if update_resp.error:
                print(f"❌ Failed to update product stock: {update_resp.error}")

        # Update size-specific stock
        if size and size != "One Size":
            size_resp = supabase.from_("product_sizes") \
                .select("stock") \
                .eq("product_id", product_id) \
                .eq("size", size) \
                .single() \
                .execute()

            if not size_resp.error and size_resp.data:
                current_size_stock = size_resp.data.get("stock", 0)
                new_size_stock = max(0, current_size_stock - quantity)
                
                supabase.from_("product_sizes") \
                    .update({"stock": new_size_stock}) \
                    .eq("product_id", product_id) \
                    .eq("size", size) \
                    .execute()
            elif size_resp.error:
                 print(f"⚠️ Product size not found for stock update: {product_id} (Size: {size})")


    except Exception as error:
        print(f"❌ Error in update_product_stock: {error}")
        # Don't throw - this is non-blocking
