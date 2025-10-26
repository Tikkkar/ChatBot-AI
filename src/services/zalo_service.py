# ============================================
# services/zalo_service.py - Zalo OA Integration
# ============================================

import httpx
import asyncio
from typing import List, Dict, Any, Optional

# ============================================
# HELPER FUNCTIONS
# ============================================

def _format_price(price: Optional[float]) -> str:
    """
    Định dạng số thành tiền tệ VNĐ.
    Ví dụ: 100000 -> "100.000 ₫"
    """
    if price is None:
        price = 0
    return f"{price:,.0f} ₫".replace(",", ".")


def _extract_product_image(product: Dict[str, Any]) -> str:
    """
    Trích xuất image URL từ product với nhiều format khác nhau
    
    Hỗ trợ:
    - product.image (string URL)
    - product.images (list of URLs)
    - product.images (list of dicts với image_url)
    """
    # Default placeholder
    default_image = "https://via.placeholder.com/300"
    
    # Format 1: Direct image field (string)
    if product.get("image"):
        return product["image"]
    
    # Format 2: images array
    images = product.get("images")
    if images and isinstance(images, list) and len(images) > 0:
        first_image = images[0]
        
        # Format 2a: Array of strings
        if isinstance(first_image, str):
            return first_image
        
        # Format 2b: Array of objects with image_url
        if isinstance(first_image, dict):
            img_url = first_image.get("image_url")
            if img_url:
                return img_url
    
    return default_image


def _extract_product_url(product: Dict[str, Any], base_url: str = "https://68f0a8368a61bd13b77fdc25--sweet-croissant-b165fe.netlify.app") -> str:
    """
    Trích xuất product URL
    
    Hỗ trợ:
    - product.url (full URL)
    - product.slug (relative slug)
    """
    # Format 1: Full URL already provided
    if product.get("url"):
        return product["url"]
    
    # Format 2: Build from slug
    slug = product.get("slug", "")
    if slug:
        return f"{base_url}/product/{slug}"
    
    # Fallback
    return base_url


def _get_stock_status(product: Dict[str, Any]) -> str:
    """
    Lấy trạng thái stock của sản phẩm
    """
    stock = product.get("stock", 0)
    
    if stock > 10:
        return f"Còn {stock} sản phẩm"
    elif stock > 0:
        return f"Còn {stock} sp (Sắp hết)"
    else:
        return "Hết hàng"


def _extract_price(product: Dict[str, Any]) -> float:
    """
    Trích xuất giá sản phẩm
    
    Hỗ trợ:
    - product.priceRaw (number)
    - product.price (string hoặc number)
    """
    # Format 1: priceRaw (preferred)
    if "priceRaw" in product:
        return product["priceRaw"]
    
    # Format 2: price field
    price = product.get("price", 0)
    
    # Nếu price là string (đã format), parse về number
    if isinstance(price, str):
        # Remove currency symbol và dots
        price_str = price.replace("₫", "").replace(".", "").replace(",", "").strip()
        try:
            return float(price_str)
        except:
            return 0
    
    return price


# ============================================
# MAIN FUNCTION
# ============================================

async def send_zalo_message(
    user_id: str,
    text: str,
    access_token: str,
    products: List[Dict[str, Any]] = None,
):
    """
    Gửi tin nhắn (và card sản phẩm nếu có) tới Zalo OA.
    
    Args:
        user_id: Zalo user ID
        text: Tin nhắn text
        access_token: Zalo OA access token
        products: Danh sách sản phẩm (optional)
    
    Product Format Support:
        - Agent format: {id, name, price, priceRaw, stock, url, image}
        - Database format: {id, name, price, stock, slug, images: [{image_url}]}
    """
    if products is None:
        products = []
    
    # Zalo OA API endpoint
    zalo_api_url = "https://openapi.zalo.me/v3.0/oa/message/cs"
    
    print(f"[Zalo] Sending message to {user_id}")
    print(f"[Zalo] Text length: {len(text)} chars")
    print(f"[Zalo] Products: {len(products)} items")
    
    # Headers cho Zalo API
    headers = {
        "access_token": access_token,
        "Content-Type": "application/json"
    }
    
    # Dùng chung một client cho các request
    async with httpx.AsyncClient() as client:
        
        # ========================================
        # 1. GỬI CARD SẢN PHẨM (nếu có)
        # ========================================
        if products and len(products) > 0:
            print(f"[Zalo] Creating product cards for {len(products)} products")
            
            # Zalo hỗ trợ list template với tối đa 10 items
            elements = []
            for idx, p in enumerate(products[:10], 1):
                try:
                    # Extract data với multiple format support
                    product_name = p.get("name", "Sản phẩm")
                    product_price = _extract_price(p)
                    stock_status = _get_stock_status(p)
                    image_url = _extract_product_image(p)
                    product_url = _extract_product_url(p)
                    
                    # Build element cho Zalo list template
                    element = {
                        "title": product_name,
                        "subtitle": f"{_format_price(product_price)}",
                        "image_url": image_url,
                        "default_action": {
                            "type": "oa.open.url",
                            "url": product_url
                        }
                    }
                    
                    elements.append(element)
                    print(f"[Zalo] ✅ Card {idx}: {product_name}")
                    
                except Exception as e:
                    print(f"[Zalo] ⚠️ Error creating card for product {idx}: {e}")
                    continue
            
            # Chỉ gửi nếu có ít nhất 1 element
            if len(elements) > 0:
                # Zalo sử dụng list template
                product_payload = {
                    "recipient": {
                        "user_id": user_id
                    },
                    "message": {
                        "attachment": {
                            "type": "template",
                            "payload": {
                                "template_type": "list",
                                "elements": elements
                            }
                        }
                    }
                }
                
                try:
                    print(f"[Zalo] Sending {len(elements)} product cards...")
                    response = await client.post(
                        zalo_api_url,
                        headers=headers,
                        json=product_payload,
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("error") == 0:
                            print(f"[Zalo] ✅ Product cards sent successfully")
                        else:
                            print(f"[Zalo] ⚠️ Product cards error: {result.get('message')}")
                    else:
                        print(f"[Zalo] ⚠️ Product cards response: {response.status_code}")
                        print(f"[Zalo] Response: {response.text[:200]}")
                    
                    # Đợi 500ms trước khi gửi tin nhắn text
                    await asyncio.sleep(0.5)
                    
                except httpx.RequestError as e:
                    print(f"[Zalo] ❌ Error sending product cards: {e}")
                except Exception as e:
                    print(f"[Zalo] ❌ Unexpected error sending cards: {e}")
            else:
                print(f"[Zalo] ⚠️ No valid product cards to send")

        # ========================================
        # 2. GỬI TIN NHẮN TEXT
        # ========================================
        # Zalo cho phép tin nhắn dài hơn (limit: 5000 chars)
        max_length = 5000
        text_chunks = []
        
        if len(text) <= max_length:
            text_chunks = [text]
        else:
            # Split by paragraphs first
            paragraphs = text.split("\n\n")
            current_chunk = ""
            
            for para in paragraphs:
                if len(current_chunk) + len(para) + 2 <= max_length:
                    current_chunk += para + "\n\n"
                else:
                    if current_chunk:
                        text_chunks.append(current_chunk.strip())
                    current_chunk = para + "\n\n"
            
            if current_chunk:
                text_chunks.append(current_chunk.strip())
        
        # Send each chunk
        for idx, chunk in enumerate(text_chunks, 1):
            text_payload = {
                "recipient": {
                    "user_id": user_id
                },
                "message": {
                    "text": chunk
                }
            }
            
            try:
                print(f"[Zalo] Sending text message chunk {idx}/{len(text_chunks)}...")
                response = await client.post(
                    zalo_api_url,
                    headers=headers,
                    json=text_payload,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("error") == 0:
                        print(f"[Zalo] ✅ Text message chunk {idx} sent successfully")
                    else:
                        print(f"[Zalo] ⚠️ Text error {idx}: {result.get('message')}")
                else:
                    print(f"[Zalo] ⚠️ Text response {idx}: {response.status_code}")
                    print(f"[Zalo] Response: {response.text[:200]}")
                
                # Delay giữa các chunks
                if idx < len(text_chunks):
                    await asyncio.sleep(0.3)
                    
            except httpx.RequestError as e:
                print(f"[Zalo] ❌ Error sending text chunk {idx}: {e}")
            except Exception as e:
                print(f"[Zalo] ❌ Unexpected error sending text {idx}: {e}")
        
        print(f"[Zalo] ✅ Message sending completed")


# ============================================
# TYPING INDICATOR
# ============================================

async def send_typing_indicator(
    user_id: str,
    access_token: str,
    action: str = "show_typing"
):
    """
    Gửi typing indicator (đang nhập...)
    
    Args:
        user_id: Zalo user ID
        access_token: Zalo OA access token
        action: "show_typing" hoặc "hide_typing"
    
    Note: Zalo OA API v3.0 chưa hỗ trợ typing indicator chính thức
    Function này để tương thích với Facebook service
    """
    print(f"[Zalo] ⚠️ Typing indicator not supported in Zalo OA API v3.0")
    # Có thể implement sau khi Zalo hỗ trợ


# ============================================
# QUICK REPLIES (Action Buttons)
# ============================================

async def send_quick_replies(
    user_id: str,
    text: str,
    access_token: str,
    quick_replies: List[Dict[str, str]]
):
    """
    Gửi tin nhắn với quick reply buttons (Zalo gọi là Action buttons)
    
    Args:
        user_id: Zalo user ID
        text: Tin nhắn
        access_token: Zalo OA access token
        quick_replies: List of {title, payload} hoặc {title, url}
    
    Example:
        quick_replies = [
            {"title": "Xem thêm", "url": "https://example.com/more"},
            {"title": "Đặt hàng", "payload": "ORDER_NOW"}
        ]
    """
    zalo_api_url = "https://openapi.zalo.me/v3.0/oa/message/cs"
    
    headers = {
        "access_token": access_token,
        "Content-Type": "application/json"
    }
    
    # Build buttons cho Zalo (tối đa 5 buttons)
    buttons = []
    for qr in quick_replies[:5]:  # Zalo limit: 5 buttons
        if qr.get("url"):
            # URL button
            buttons.append({
                "type": "oa.open.url",
                "title": qr["title"],
                "payload": {
                    "url": qr["url"]
                }
            })
        else:
            # Postback button (query show)
            buttons.append({
                "type": "oa.query.show",
                "title": qr["title"],
                "payload": qr.get("payload", qr["title"])
            })
    
    payload = {
        "recipient": {
            "user_id": user_id
        },
        "message": {
            "text": text,
            "attachment": {
                "type": "template",
                "payload": {
                    "buttons": buttons
                }
            }
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                zalo_api_url,
                headers=headers,
                json=payload,
                timeout=10.0
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("error") == 0:
                    print(f"[Zalo] ✅ Quick replies sent: {len(buttons)} buttons")
                else:
                    print(f"[Zalo] ⚠️ Quick replies error: {result.get('message')}")
            else:
                print(f"[Zalo] ⚠️ Quick replies response: {response.status_code}")
                
    except Exception as e:
        print(f"[Zalo] ❌ Error sending quick replies: {e}")


# ============================================
# IMAGE MESSAGE
# ============================================

async def send_image_message(
    user_id: str,
    image_url: str,
    access_token: str,
):
    """
    Gửi tin nhắn hình ảnh
    
    Args:
        user_id: Zalo user ID
        image_url: URL của hình ảnh
        access_token: Zalo OA access token
    """
    zalo_api_url = "https://openapi.zalo.me/v3.0/oa/message/cs"
    
    headers = {
        "access_token": access_token,
        "Content-Type": "application/json"
    }
    
    payload = {
        "recipient": {
            "user_id": user_id
        },
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "media",
                    "elements": [{
                        "media_type": "image",
                        "url": image_url
                    }]
                }
            }
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                zalo_api_url,
                headers=headers,
                json=payload,
                timeout=10.0
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("error") == 0:
                    print(f"[Zalo] ✅ Image sent successfully")
                else:
                    print(f"[Zalo] ⚠️ Image error: {result.get('message')}")
            else:
                print(f"[Zalo] ⚠️ Image response: {response.status_code}")
                
    except Exception as e:
        print(f"[Zalo] ❌ Error sending image: {e}")


# ============================================
# TRANSACTION MESSAGE (Request Info)
# ============================================

async def send_request_user_info(
    user_id: str,
    access_token: str,
    info_type: str = "name,phone"
):
    """
    Yêu cầu thông tin người dùng (tên, số điện thoại)
    
    Args:
        user_id: Zalo user ID
        access_token: Zalo OA access token
        info_type: "name", "phone", hoặc "name,phone"
    """
    zalo_api_url = "https://openapi.zalo.me/v3.0/oa/message/cs"
    
    headers = {
        "access_token": access_token,
        "Content-Type": "application/json"
    }
    
    payload = {
        "recipient": {
            "user_id": user_id
        },
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "request_user_info",
                    "elements": [{
                        "title": "Thông tin khách hàng",
                        "subtitle": "Vui lòng cung cấp thông tin",
                        "image_icon": "https://via.placeholder.com/100"
                    }]
                }
            }
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                zalo_api_url,
                headers=headers,
                json=payload,
                timeout=10.0
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("error") == 0:
                    print(f"[Zalo] ✅ User info request sent")
                else:
                    print(f"[Zalo] ⚠️ Request error: {result.get('message')}")
            else:
                print(f"[Zalo] ⚠️ Request response: {response.status_code}")
                
    except Exception as e:
        print(f"[Zalo] ❌ Error sending request: {e}")


# ============================================
# HELPER FUNCTIONS FOR TESTING
# ============================================

def _test_product_formats():
    """Test function để verify các format khác nhau"""
    
    # Format 1: Agent format
    agent_product = {
        "id": "123",
        "name": "Áo Vest Linen",
        "price": "890.000 ₫",
        "priceRaw": 890000,
        "stock": 5,
        "url": "https://example.com/products/ao-vest",
        "image": "https://example.com/image.jpg"
    }
    
    # Format 2: Database format
    db_product = {
        "id": "456",
        "name": "Quần Suông",
        "price": 690000,
        "stock": 0,
        "slug": "quan-suong",
        "images": [
            {"image_url": "https://example.com/image2.jpg", "is_primary": True}
        ]
    }
    
    # Test extraction
    print("\n=== Testing Product Format Extraction ===")
    
    for idx, prod in enumerate([agent_product, db_product], 1):
        print(f"\nProduct {idx}:")
        print(f"  Name: {prod.get('name')}")
        print(f"  Price: {_extract_price(prod)}")
        print(f"  Image: {_extract_product_image(prod)}")
        print(f"  URL: {_extract_product_url(prod)}")
        print(f"  Stock: {_get_stock_status(prod)}")


if __name__ == "__main__":
    # Run test
    _test_product_formats()