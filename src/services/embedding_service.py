# ============================================
# Embedding Service - Fixed Version
# File: services/embedding_service.py
# ============================================

from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, TypedDict
from supabase import Client
from postgrest.exceptions import APIError

# Giả định bạn có hàm create_supabase_client trong connect_supabase.py
from ..utils.connect_supabase import create_supabase_client

# ============================================
# ĐỊNH NGHĨA TYPE (TYPESCRIPT INTERFACES)
# ============================================

class MessageEmbeddingMetadata(TypedDict, total=False):
    content_length: int
    created_at: str
    # ... any other metadata fields
    sender_type: Optional[str]

class SummaryEmbeddingMetadata(TypedDict, total=False):
    key_points_count: int
    created_at: str

class FactEmbeddingMetadata(TypedDict, total=False):
    source: str
    created_at: str

class BatchMessage(TypedDict, total=False):
    id: str
    content: str
    metadata: Optional[Any]

class BatchResult(TypedDict):
    success: int
    failed: int

# ============================================
# HÀM CHÍNH
# ============================================

"""
Create embedding for a chat message
Automatically called after saving customer/bot messages
"""
async def create_message_embedding(
    conversation_id: str,
    message_id: str,
    content: str,
    metadata: Dict[str, Any] = {},
) -> None:
    try:
        supabase = create_supabase_client()

        # Validate inputs
        if not all([conversation_id, message_id, content]):
            print("⚠️ Missing required fields for embedding")
            return

        # Limit content length (prevent huge embeddings)
        trimmed_content = content[:1000]

        # Prepare metadata
        embedding_metadata: MessageEmbeddingMetadata = {
            **metadata,
            "content_length": len(content),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        insert_resp = supabase.from_("conversation_embeddings") \
            .insert({
                "conversation_id": conversation_id,
                "message_id": message_id,
                "content": trimmed_content,
                "content_type": "message",
                "metadata": embedding_metadata,
            }) \
            .execute()

        print(f"✅ Created embedding for message {message_id[:8]}...")
    
    except APIError as api_error:
        print(f"❌ API Error creating embedding: {api_error}")
        # Don't throw - embedding creation shouldn't block main flow
    except Exception as error:
        print(f"❌ create_message_embedding failed: {error}")
        # Silent fail - don't break the chat flow

"""
Create embeddings for conversation summary
Called when conversation ends or periodically
"""
async def create_summary_embedding(
    conversation_id: str,
    summary_text: str,
    key_points: List[str] = [],
) -> None:
    try:
        supabase = create_supabase_client()
        now_iso = datetime.now(timezone.utc).isoformat()

        # Insert summary embedding
        summary_metadata: SummaryEmbeddingMetadata = {
            "key_points_count": len(key_points),
            "created_at": now_iso,
        }
        
        summary_resp = supabase.from_("conversation_embeddings") \
            .insert({
                "conversation_id": conversation_id,
                "message_id": None,
                "content": summary_text,
                "content_type": "summary",
                "metadata": summary_metadata,
            }) \
            .execute()

        # Insert embeddings for each key point
        if key_points:
            fact_embeddings = [{
                "conversation_id": conversation_id,
                "message_id": None,
                "content": point,
                "content_type": "fact",
                "metadata": {
                    "source": "summary",
                    "created_at": now_iso,
                },
            } for point in key_points]

            supabase.from_("conversation_embeddings") \
                .insert(fact_embeddings) \
                .execute()

        print(f"✅ Created summary embeddings ({len(key_points)} facts)")
    
    except APIError as api_error:
        print(f"❌ API Error creating summary embedding: {api_error}")
    except Exception as error:
        print(f"❌ create_summary_embedding failed: {error}")

"""
Search similar messages using embeddings
For semantic search in conversation history
"""
async def search_similar_messages(
    conversation_id: str,
    query: str,
    limit: int = 5,
) -> List[Any]:
    try:
        supabase = create_supabase_client()

        # For now, use simple text search
        # TODO: Implement vector similarity search when pgvector is enabled
        search_resp = supabase.from_("conversation_embeddings") \
            .select("*") \
            .eq("conversation_id", conversation_id) \
            .text_search("content", query, {
                "type": "websearch",
                "config": "english",  # Cân nhắc đổi sang 'simple' hoặc 'vietnamese' nếu có
            }) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()

        return search_resp.data or []
    
    except APIError as api_error:
        print(f"❌ API Error searching embeddings: {api_error}")
        return []
    except Exception as error:
        print(f"❌ search_similar_messages failed: {error}")
        return []

"""
Get recent context from embeddings
Used for building AI context
"""
async def get_recent_context(
    conversation_id: str,
    limit: int = 10,
) -> str:
    try:
        supabase = create_supabase_client()

        context_resp = supabase.from_("conversation_embeddings") \
            .select("content, content_type, created_at, metadata") \
            .eq("conversation_id", conversation_id) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()

        if not context_resp.data:
            return ""

        # Reverse to get chronological order
        messages = reversed(context_resp.data)

        context_parts = ["📋 RECENT CONTEXT FROM EMBEDDINGS:"]
        for msg in messages:
            content_type = msg.get("content_type")
            if content_type == "summary":
                icon = "📊"
            elif content_type == "fact":
                icon = "💡"
            else:
                icon = "💬"
            
            sender = msg.get("metadata", {}).get("sender_type", "")
            context_parts.append(f"{icon} [{sender}] {msg.get('content')}")

        return "\n".join(context_parts)
    
    except APIError as api_error:
        print(f"❌ API Error getting recent context: {api_error}")
        return ""
    except Exception as error:
        print(f"❌ get_recent_context failed: {error}")
        return ""

"""
Batch create embeddings for multiple messages
Used for migration or bulk operations
"""
async def batch_create_embeddings(
    conversation_id: str,
    messages: List[BatchMessage],
) -> BatchResult:
    success = 0
    failed = 0

    for msg in messages:
        try:
            await create_message_embedding(
                conversation_id,
                msg["id"],
                msg["content"],
                msg.get("metadata"),
            )
            success += 1
        except Exception:
            failed += 1

    print(f"✅ Batch embeddings: {success} success, {failed} failed")
    return {"success": success, "failed": failed}