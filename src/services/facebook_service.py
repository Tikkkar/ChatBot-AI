# ============================================
# services/facebook_service.py - Facebook Messenger integration
# ============================================

import httpx
import asyncio
from typing import List, Dict, Any, Optional

# ============================================
# HELPER FUNCTION (Tương đương formatPrice từ utils)
# ============================================
#...
def _format_price(price: Optional[float]) -> str:
    """
    Định dạng số thành tiền tệ VNĐ.
    Ví dụ: 100000 -> "100.000 ₫"
    """
    if price is None:
        price = 0
    # Sử dụng f-string formatting với dấu phẩy làm phân cách hàng nghìn
    # và thêm ký hiệu "₫"
    # .replace(",", ".") để đổi 100,000 -> 100.000
    return f"{price:,.0f} ₫".replace(",", ".")

# ============================================
# HÀM CHÍNH
# ============================================

async def send_facebook_message(
    recipient_id: str,
    text: str,
    access_token: str,
    products: List[Dict[str, Any]] = [],
):
    """
    Gửi tin nhắn (và card sản phẩm nếu có) tới Facebook Messenger.
    """
    fb_api_url = f"https://graph.facebook.com/v18.0/me/messages?access_token={access_token}"
    
    # Dùng chung một client cho các request
    async with httpx.AsyncClient() as client:
        
        # 1. Gửi card sản phẩm (nếu có)
        if products:
            elements = []
            for p in products:
                stock_status = "Con hang" if p.get("stock", 0) > 0 else "Het hang"
                
                # Xử lý optional chaining cho image_url một cách an toàn
                image_url = "https://via.placeholder.com/300"
                images = p.get("images")
                if images and isinstance(images, list) and len(images) > 0:
                    # Đảm bảo images[0] là dict trước khi .get()
                    if isinstance(images[0], dict):
                         image_url = images[0].get("image_url") or image_url

                elements.append({
                    "title": p.get("name", "Sản phẩm"),
                    "subtitle": f"{_format_price(p.get('price', 0))} - {stock_status}",
                    "image_url": image_url,
                    "buttons": [
                        {
                            "type": "web_url",
                            "title": "Xem chi tiet",
                            # Đảm bảo slug có giá trị, nếu không thì dùng rỗng
                            "url": f"https://68f0a8368a61bd13b77fdc25--sweet-croissant-b165fe.netlify.app/product/{p.get('slug', '')}",
                        },
                    ],
                })

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
                # Gửi card sản phẩm
                await client.post(fb_api_url, json=product_payload, timeout=10.0)
                # Đợi 500ms trước khi gửi tin nhắn text
                await asyncio.sleep(0.5)
            except httpx.RequestError as e:
                print(f"❌ Error sending FB product cards: {e}")
                # Vẫn tiếp tục để gửi tin nhắn text dù có lỗi card

        # 2. Gửi tin nhắn text
        text_payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": text},
        }
        
        try:
            await client.post(fb_api_url, json=text_payload, timeout=10.0)
            print("✅ Sent text message to Facebook Messenger")
        except httpx.RequestError as e:
            print(f"❌ Error sending FB text message: {e}")
