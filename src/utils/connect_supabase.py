# src/utils/connect_supabase.py

from supabase import create_client, Client
from ..config.env import settings

def create_supabase_client() -> Client:
    """
    Tạo Supabase client.
    Supabase Python SDK tự động handle async trong FastAPI context.
    """
    print(f"Đang kết nối đến Supabase tại: {settings.SUPABASE_URL[:50]}...")
    client = create_client(
        settings.SUPABASE_URL, 
        settings.SUPABASE_SERVICE_KEY
    )
    print("Khởi tạo Supabase client thành công.")
    return client

# Singleton instance
_supabase_client = None

def get_supabase_client() -> Client:
    """Get or create singleton Supabase client"""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_supabase_client()
    return _supabase_client