# ============================================
# src/config/env.py
# (Tương đương với src/config/env.ts)
# ============================================

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path
import os

# Đường dẫn đến file .env ở thư mục gốc
# (Giả định file này nằm trong src/config/)
env_path = Path(__file__).resolve().parent.parent.parent / ".env"

print(f"Đang tìm .env tại: {env_path}")

class Settings(BaseSettings):
    """
    Sử dụng Pydantic để tải và xác thực biến môi trường.
    Nếu thiếu biến bắt buộc (như SUPABASE_URL), Pydantic sẽ tự động báo lỗi.
    """
    
    # Tải biến từ file .env
    # extra='ignore' -> Bỏ qua các biến môi trường khác không được định nghĩa ở đây
    model_config = SettingsConfigDict(
        env_file=str(env_path), 
        env_file_encoding='utf-8', 
        extra='ignore'
    )

    # App
    PORT: int = Field(default=8000)
    NODE_ENV: str = Field(default="development")
    WEBSITE_URL: str = Field(default="https://bewo.vn")
    CORS_ORIGINS: str = Field(default="http://localhost:3000")
    
    # Supabase (Bắt buộc)
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    
    # Gemini (Bắt buộc)
    GEMINI_API_KEY: str
    
    # Facebook (Tùy chọn, với giá trị mặc định)
    WEBHOOK_VERIFY_TOKEN: str = Field(default="default_token")
    FACEBOOK_PAGE_ACCESS_TOKEN: str = Field(default="")

# Khởi tạo settings
# Biến này sẽ được import bởi các file khác (như main.py, supabase.py)
try:
    settings = Settings()
    
    # Tự động gán GEMINI_API_KEY vào biến môi trường
    # để thư viện 'agents' (litellm) có thể tự động đọc
    os.environ["GEMINI_API_KEY"] = settings.GEMINI_API_KEY
    
    print("✅ [Config] Tải .env và xác thực biến môi trường thành công.")
    print(f"✅ [Config] SUPABASE_URL: {settings.SUPABASE_URL[:30]}...")
    print("✅ [Config] GEMINI_API_KEY đã được thiết lập cho 'agents'.")

except Exception as e:
    print(f"❌ LỖI KHÔNG ĐỌC ĐƯỢC .env HOẶC THIẾU BIẾN MÔI TRƯỜNG")
    print(f"Lỗi: {e}")
    print("Vui lòng đảm bảo file .env tồn tại ở thư mục gốc và có đủ các biến bắt buộc.")
    # Ném lỗi ra ngoài để dừng server nếu config sai
    raise e
