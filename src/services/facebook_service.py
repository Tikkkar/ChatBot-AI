import requests
import time
from typing import Optional, List, Dict, Any


def format_price(price: float) -> str:
    """Format price in Vietnamese style"""
    return f"{int(price):,}".replace(",", ".")


def send_facebook_image(
    recipient_id: str,
    image_url: str,
    access_token: str,
    product: Optional[Dict[str, Any]] = None
) -> None:
    """
    Send image to Facebook Messenger.
    
    Args:
        recipient_id: Facebook user ID
        image_url: URL of the image to send
        access_token: Facebook page access token
        product: Optional product details dict with keys: id, name, price, slug
    """
    fb_api_url = f"https://graph.facebook.com/v21.0/me/messages?access_token={access_token}"
    
    try:
        # 1. Send image attachment
        image_payload = {
            "recipient": {"id": recipient_id},
            "message": {
                "attachment": {
                    "type": "image",
                    "payload": {
                        "url": image_url,
                        "is_reusable": True
                    }
                }
            }
        }
        
        requests.post(
            fb_api_url,
            headers={"Content-Type": "application/json"},
            json=image_payload
        )
        
        # 2. Send product details as quick replies (optional)
        if product:
            text_payload = {
                "recipient": {"id": recipient_id},
                "message": {
                    "text": f"{product['name']}\nGiá: {int(product['price']):,}đ".replace(",", "."),
                    "quick_replies": [
                        {
                            "content_type": "text",
                            "title": "🛒 Thêm vào giỏ",
                            "payload": f"ADD_TO_CART_{product['id']}"
                        },
                        {
                            "content_type": "text",
                            "title": "📱 Xem chi tiết",
                            "payload": f"VIEW_PRODUCT_{product['id']}"
                        }
                    ]
                }
            }
            
            requests.post(
                fb_api_url,
                headers={"Content-Type": "application/json"},
                json=text_payload
            )
        
        print("✅ Facebook image sent successfully")
        
    except Exception as error:
        print(f"❌ Facebook image send error: {error}")
        raise


def send_facebook_message(
    recipient_id: str,
    text: str,
    access_token: str,
    products: List[Dict[str, Any]] = None
) -> None:
    """
    Send text message or product cards to Facebook Messenger
    
    Args:
        recipient_id: Facebook user ID
        text: Text message to send
        access_token: Facebook page access token
        products: Optional list of product dicts
    """
    if products is None:
        products = []
        
    fb_api_url = f"https://graph.facebook.com/v18.0/me/messages?access_token={access_token}"
    
    # 1. Send Product Cards if showcase
    if products and len(products) > 0:
        elements = []
        
        for p in products:
            image_url = "https://via.placeholder.com/300"
            if p.get("images") and len(p["images"]) > 0:
                image_url = p["images"][0].get("image_url", image_url)
            
            stock_text = "Con hang" if p.get("stock", 0) > 0 else "Het hang"
            
            elements.append({
                "title": p["name"],
                "subtitle": f"{format_price(p['price'])} - {stock_text}",
                "image_url": image_url,
                "buttons": [
                    {
                        "type": "web_url",
                        "title": "Xem chi tiet",
                        "url": f"https://68f0a8368a61bd13b77fdc25--sweet-croissant-b165fe.netlify.app/product/{p['slug']}"
                    }
                ]
            })
        
        card_payload = {
            "recipient": {"id": recipient_id},
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "generic",
                        "image_aspect_ratio": "square",
                        "elements": elements
                    }
                }
            }
        }
        
        requests.post(
            fb_api_url,
            headers={"Content-Type": "application/json"},
            json=card_payload
        )
        
        # Wait 500ms before sending text
        time.sleep(0.5)
    
    # 2. Send text message
    text_payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    
    requests.post(
        fb_api_url,
        headers={"Content-Type": "application/json"},
        json=text_payload
    )
    
    print("Sent to Facebook Messenger")
