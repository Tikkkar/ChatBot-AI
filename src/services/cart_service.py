# ============================================
# services/cart_service.py - FIXED
# ============================================

import asyncio
from typing import List, Dict, Optional, Any, TypedDict

from ..utils.connect_supabase import get_supabase_client

# Định nghĩa kiểu dữ liệu cho một sản phẩm trong giỏ hàng
class CartItem(TypedDict, total=False):
    product_id: str
    name: str
    price: float
    size: str
    quantity: int
    image: str

class ServiceResult(TypedDict, total=False):
    success: bool
    message: str
    cart: Optional[List[CartItem]]

def format_price(price: float) -> str:
    try:
        formatted_price = f"{price:,.0f}".replace(",", ".")
        return f"{formatted_price} ₫"
    except Exception:
        return f"{price} VND"

async def get_or_create_cart(conversation_id: str) -> List[CartItem]:
    supabase = get_supabase_client()

    try:
        # ✅ FIX: Bỏ .single(), dùng .limit(1)
        response = supabase.from_("chatbot_conversations") \
            .select("context") \
            .eq("id", conversation_id) \
            .limit(1) \
            .execute()

        # ✅ FIX: Lấy phần tử đầu tiên
        if response.data and len(response.data) > 0:
            conversation = response.data[0]
            if not isinstance(conversation.get("context"), dict):
                return []
            
            cart = conversation["context"].get("cart", [])
            return cart if isinstance(cart, list) else []
        
        return []

    except Exception as error:
        print(f"Error fetching conversation for cart: {error}")
        return []

async def save_cart(conversation_id: str, cart: List[CartItem]) -> None:
    supabase = get_supabase_client()
    try:
        # ✅ FIX: .rpc() không cần .select()
        supabase.rpc("merge_context", {
            "p_conversation_id": conversation_id,
            "p_new_context": {"cart": cart},
        }).execute()
    except Exception as error:
        print(f"Error saving cart via RPC: {error}")

async def add_to_cart(conversation_id: str, item: CartItem) -> List[CartItem]:
    cart = await get_or_create_cart(conversation_id)

    existing_index = -1
    for i, cart_item in enumerate(cart):
        if cart_item.get("product_id") == item.get("product_id") and cart_item.get("size") == item.get("size"):
            existing_index = i
            break

    if existing_index >= 0:
        cart[existing_index]["quantity"] = cart[existing_index].get("quantity", 0) + item.get("quantity", 1)
    else:
        cart.append(item)

    await save_cart(conversation_id, cart)

    print(f"✅ Added to cart: {item.get('name')} x{item.get('quantity')}")
    return cart

async def remove_from_cart(conversation_id: str, product_id: str) -> ServiceResult:
    cart = await get_or_create_cart(conversation_id)
    initial_length = len(cart)

    new_cart = [item for item in cart if item.get("product_id") != product_id]

    if len(new_cart) < initial_length:
        await save_cart(conversation_id, new_cart)
        print(f"🗑️ Removed product {product_id} from cart.")
        return {
            "success": True,
            "message": "Đã xóa sản phẩm khỏi giỏ hàng.",
            "cart": new_cart,
        }
    else:
        print(f"⚠️ Product {product_id} not found in cart to remove.")
        return {
            "success": False,
            "message": "Không tìm thấy sản phẩm này trong giỏ hàng.",
        }

class UpdateCartArgs(TypedDict, total=False):
    product_id: str
    quantity: int
    size: Optional[str]

async def update_cart_item(conversation_id: str, args: UpdateCartArgs) -> ServiceResult:
    if args.get("quantity", 1) <= 0:
        return await remove_from_cart(conversation_id, args["product_id"])

    cart = await get_or_create_cart(conversation_id)
    item_index = -1
    product_id_to_update = args["product_id"]
    size_to_update = args.get("size")

    if size_to_update:
        try:
            item_index = next(
                i for i, item in enumerate(cart)
                if item.get("product_id") == product_id_to_update and item.get("size") == size_to_update
            )
        except StopIteration:
            item_index = -1
    else:
        matching_items_indices = [
            i for i, item in enumerate(cart)
            if item.get("product_id") == product_id_to_update
        ]
        
        if len(matching_items_indices) == 1:
            item_index = matching_items_indices[0]
        elif len(matching_items_indices) > 1:
            return {
                "success": False,
                "message": "Sản phẩm này có nhiều size trong giỏ, chị vui lòng chỉ rõ size muốn cập nhật ạ.",
            }

    if item_index >= 0:
        cart[item_index]["quantity"] = args["quantity"]
        if size_to_update:
            cart[item_index]["size"] = size_to_update
        
        await save_cart(conversation_id, cart)
        print(f"🔄 Updated cart item {product_id_to_update} to quantity {args['quantity']}.")
        return {
            "success": True,
            "message": "Đã cập nhật giỏ hàng thành công.",
            "cart": cart,
        }
    else:
        print(f"⚠️ Item {product_id_to_update} not found to update.")
        return {
            "success": False,
            "message": "Không tìm thấy sản phẩm này trong giỏ để cập nhật.",
        }

async def clear_cart(conversation_id: str) -> None:
    cart = await get_or_create_cart(conversation_id)
    if cart:
        await save_cart(conversation_id, [])
    print("✅ Cart cleared")

async def get_cart_summary(conversation_id: str) -> str:
    cart = await get_or_create_cart(conversation_id)

    if not cart:
        return "Dạ giỏ hàng của chị hiện đang trống ạ."

    total_quantity = sum(item.get("quantity", 0) for item in cart)
    subtotal = sum(item.get("price", 0) * item.get("quantity", 0) for item in cart)

    items_list = "\n".join([
        f"• {item.get('name')} (Size {item.get('size')}) x{item.get('quantity', 0)} - {format_price(item.get('price', 0) * item.get('quantity', 0))}"
        for item in cart
    ])

    return f"Dạ, em kiểm tra giỏ hàng của chị đang có {total_quantity} sản phẩm:\n{items_list}\n\n💰 Tạm tính: {format_price(subtotal)}"