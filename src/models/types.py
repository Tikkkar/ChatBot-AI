# src/models/types.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ChatRequest(BaseModel):
    message: str = Field(..., description="Nội dung tin nhắn")
    phone: Optional[str] = Field(default=None, description="SĐT khách hàng")
    conversationId: Optional[str] = Field(default=None, description="ID cuộc trò chuyện")

class ChatResponse(BaseModel):
    success: bool
    response: str
    products: List[Dict[str, Any]] = []
    recommendation_type: str = "conversational"
    message_type: str = "text"
    memory_stats: Optional[Dict[str, Any]] = None

class Product(BaseModel):
    id: str
    name: str
    price: float
    stock: int
    slug: str
    description: Optional[str] = None
    image_url: Optional[str] = None

class Order(BaseModel):
    id: str
    status: str
    total_amount: float
    created_at: str