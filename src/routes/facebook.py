from fastapi import APIRouter, Request, HTTPException
from ..config.env import settings
from ..handlers.message_handler import handle_message

router = APIRouter(prefix="/facebook", tags=["Facebook"])

@router.get("/webhook")
async def verify_webhook(
    request: Request,
):
    """Verify webhook with Facebook"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode == "subscribe" and token == settings.WEBHOOK_VERIFY_TOKEN:
        print("✅ Webhook verified")
        return int(challenge)
    else:
        raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/webhook")
async def receive_webhook(request: Request):
    """Receive messages from Facebook"""
    body = await request.json()
    
    if body.get("object") == "page":
        for entry in body.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                if messaging_event.get("message"):
                    sender_id = messaging_event["sender"]["id"]
                    message_text = messaging_event["message"].get("text", "")
                    
                    # Process message
                    await handle_message({
                        "platform": "facebook",
                        "customer_fb_id": sender_id,
                        "message_text": message_text,
                        "page_id": entry["id"],
                        "access_token": settings.FACEBOOK_PAGE_ACCESS_TOKEN
                    })
        
        return {"status": "ok"}
    
    raise HTTPException(status_code=404)