# ============================================
# routes/chat.py
# (Tương đương với src/routes/chat.ts)
# ============================================

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from uuid import uuid4
from ..handlers.message_handler import handle_message
from ..models.types import ChatRequest
from fastapi.responses import JSONResponse
# --- Khởi tạo Router ---
router = APIRouter(
    prefix="/chat",
    tags=["Website Chat"]
)

# --- Định nghĩa Endpoint ---
@router.post("/")
async def handle_chat_message(
    chat_request: ChatRequest,
    x_session_id: Optional[str] = Header(default=None, description="Header session ID cho khách vãng lai")
) -> Dict[str, Any]:
    """
    Endpoint cho website chat.
    """
    try:
        # FastAPI tự động validate 'message'
        
        # 1. Xây dựng body cho handleMessage
        body: Dict[str, Any] = {
            "platform": "website",
            "message_text": chat_request.message,
        }

        # 2. Logic ưu tiên: conversationId > phone > session_id
        if chat_request.conversationId:
            body["conversation_id"] = chat_request.conversationId
        elif chat_request.phone:
            body["customer_phone"] = chat_request.phone
        else:
            body["session_id"] = x_session_id or str(uuid4())

        print(f"[Chat] Request body: {body}")

        # 3. Gọi handler chính
        result = await handle_message(body)
        return JSONResponse(
            content=result,
            media_type="application/json; charset=utf-8"
        )
        # 4. Trả về kết quả
        return result

    except Exception as error:
        print(f"[Chat] Error: {error}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False, 
                "error": str(error)
            }
        )