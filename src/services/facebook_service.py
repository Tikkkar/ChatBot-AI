# ============================================
# services/facebook_service.py - Facebook Messenger Integration (UPDATED)
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

async def send_facebook_message(
    recipient_id: str,
    text: str,
    access_token: str,
    products: List[Dict[str, Any]] = None,
):
    """
    Gửi tin nhắn (và card sản phẩm nếu có) tới Facebook Messenger.
    
    Args:
        recipient_id: Facebook user ID
        text: Tin nhắn text
        access_token: Facebook page access token
        products: Danh sách sản phẩm (optional)
    
    Product Format Support:
        - Agent format: {id, name, price, priceRaw, stock, url, image}
        - Database format: {id, name, price, stock, slug, images: [{image_url}]}
    """
    if products is None:
        products = []
    
    fb_api_url = f"https://graph.facebook.com/v18.0/me/messages?access_token={access_token}"
    
    print(f"[Facebook] Sending message to {recipient_id}")
    print(f"[Facebook] Text length: {len(text)} chars")
    print(f"[Facebook] Products: {len(products)} items")
    
    # Dùng chung một client cho các request
    async with httpx.AsyncClient() as client:
        
        # ========================================
        # 1. GỬI CARD SẢN PHẨM (nếu có)
        # ========================================
        if products and len(products) > 0:
            print(f"[Facebook] Creating product cards for {len(products)} products")
            
            elements = []
            for idx, p in enumerate(products[:10], 1):  # Limit 10 products
                try:
                    # Extract data với multiple format support
                    product_name = p.get("name", "Sản phẩm")
                    product_price = _extract_price(p)
                    stock_status = _get_stock_status(p)
                    image_url = _extract_product_image(p)
                    product_url = _extract_product_url(p)
                    
                    # Build card element
                    element = {
                        "title": product_name,
                        "subtitle": f"{_format_price(product_price)} - {stock_status}",
                        "image_url": image_url,
                        "buttons": [
                            {
                                "type": "web_url",
                                "title": "Xem chi tiết",
                                "url": product_url,
                            },
                        ],
                    }
                    
                    # Add thêm button "Thêm vào giỏ" nếu còn hàng
                    if p.get("stock", 0) > 0:
                        # Có thể thêm postback button để add to cart
                        # (cần implement webhook handler)
                        pass
                    
                    elements.append(element)
                    print(f"[Facebook] ✅ Card {idx}: {product_name}")
                    
                except Exception as e:
                    print(f"[Facebook] ⚠️ Error creating card for product {idx}: {e}")
                    # Skip product nếu có lỗi
                    continue
            
            # Chỉ gửi nếu có ít nhất 1 element
            if len(elements) > 0:
                product_payload = {
                    "recipient": {"id": recipient_id},
                    "message": {
                        "attachment": {
                            "type": "template",
                            "payload": {
                                "template_type": "generic",
                                "image_aspect_ratio": "square",
                                "elements": elements,
                            },
                        },
                    },
                }
                
                try:
                    print(f"[Facebook] Sending {len(elements)} product cards...")
                    response = await client.post(
                        fb_api_url,
                        json=product_payload,
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        print(f"[Facebook] ✅ Product cards sent successfully")
                    else:
                        print(f"[Facebook] ⚠️ Product cards response: {response.status_code}")
                        print(f"[Facebook] Response: {response.text[:200]}")
                    
                    # Đợi 500ms trước khi gửi tin nhắn text
                    await asyncio.sleep(0.5)
                    
                except httpx.RequestError as e:
                    print(f"[Facebook] ❌ Error sending product cards: {e}")
                    # Vẫn tiếp tục để gửi tin nhắn text dù có lỗi card
                except Exception as e:
                    print(f"[Facebook] ❌ Unexpected error sending cards: {e}")
            else:
                print(f"[Facebook] ⚠️ No valid product cards to send")

        # ========================================
        # 2. GỬI TIN NHẮN TEXT
        # ========================================
        # Split long messages (Facebook limit: 2000 chars)
        max_length = 2000
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
                "recipient": {"id": recipient_id},
                "message": {"text": chunk},
            }
            
            try:
                print(f"[Facebook] Sending text message chunk {idx}/{len(text_chunks)}...")
                response = await client.post(
                    fb_api_url,
                    json=text_payload,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    print(f"[Facebook] ✅ Text message chunk {idx} sent successfully")
                else:
                    print(f"[Facebook] ⚠️ Text response {idx}: {response.status_code}")
                    print(f"[Facebook] Response: {response.text[:200]}")
                
                # Delay giữa các chunks
                if idx < len(text_chunks):
                    await asyncio.sleep(0.3)
                    
            except httpx.RequestError as e:
                print(f"[Facebook] ❌ Error sending text chunk {idx}: {e}")
            except Exception as e:
                print(f"[Facebook] ❌ Unexpected error sending text {idx}: {e}")
        
        print(f"[Facebook] ✅ Message sending completed")


# ============================================
# TYPING INDICATOR
# ============================================

async def send_typing_indicator(
    recipient_id: str,
    access_token: str,
    action: str = "typing_on"
):
    """
    Gửi typing indicator (đang nhập...)
    
    Args:
        recipient_id: Facebook user ID
        access_token: Facebook page access token
        action: "typing_on" hoặc "typing_off"
    """
    fb_api_url = f"https://graph.facebook.com/v18.0/me/messages?access_token={access_token}"
    
    payload = {
        "recipient": {"id": recipient_id},
        "sender_action": action
    }
    
    try:
        async with httpx.AsyncClient() as client:
            await client.post(fb_api_url, json=payload, timeout=5.0)
            print(f"[Facebook] ✅ Typing indicator sent: {action}")
    except Exception as e:
        print(f"[Facebook] ⚠️ Error sending typing indicator: {e}")


# ============================================
# QUICK REPLIES
# ============================================

async def send_quick_replies(
    recipient_id: str,
    text: str,
    access_token: str,
    quick_replies: List[Dict[str, str]]
):
    """
    Gửi tin nhắn với quick reply buttons
    
    Args:
        recipient_id: Facebook user ID
        text: Tin nhắn
        access_token: Facebook page access token
        quick_replies: List of {title, payload}
    
    Example:
        quick_replies = [
            {"title": "Xem thêm", "payload": "VIEW_MORE"},
            {"title": "Đặt hàng", "payload": "ORDER_NOW"}
        ]
    """
    fb_api_url = f"https://graph.facebook.com/v18.0/me/messages?access_token={access_token}"
    
    # Build quick replies format
    fb_quick_replies = [
        {
            "content_type": "text",
            "title": qr["title"],
            "payload": qr.get("payload", qr["title"])
        }
        for qr in quick_replies[:13]  # Facebook limit: 13 quick replies
    ]
    
    payload = {
        "recipient": {"id": recipient_id},
        "message": {
            "text": text,
            "quick_replies": fb_quick_replies
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(fb_api_url, json=payload, timeout=10.0)
            
            if response.status_code == 200:
                print(f"[Facebook] ✅ Quick replies sent: {len(fb_quick_replies)} buttons")
            else:
                print(f"[Facebook] ⚠️ Quick replies response: {response.status_code}")
                
    except Exception as e:
        print(f"[Facebook] ❌ Error sending quick replies: {e}")


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