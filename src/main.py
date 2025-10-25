# src/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from fastapi.responses import JSONResponse

# ✅ Import với relative imports (dấu chấm)
from .config.env import settings
from .routes.chat import router as chat_router

# Create FastAPI app
app = FastAPI(
    title="BeWo Chatbot API",
    description="AI Chatbot for BeWo Fashion",
    version="1.0.0"
)
# Thêm middleware để force UTF-8
@app.middleware("http")
async def add_charset_header(request, call_next):
    response = await call_next(request)
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response

# Add CORS
origins = settings.CORS_ORIGINS.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat_router, tags=["Chat"])

# Health check
@app.get("/")
async def root():
    return {"status": "ok", "service": "BeWo Chatbot API"}

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}

# Startup event
@app.on_event("startup")
async def startup_event():
    print("=" * 50)
    print("🚀 BeWo Chatbot API Server")
    print(f"📡 Server running on: http://localhost:{settings.PORT}")
    print(f"🌍 Environment: {settings.NODE_ENV}")
    print(f"✅ Health check: http://localhost:{settings.PORT}/health")
    print("=" * 50)

# Run server (chỉ khi chạy trực tiếp file này)
if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",  # ✅ Đường dẫn đúng
        host="0.0.0.0",
        port=settings.PORT,
        reload=True if settings.NODE_ENV == "development" else False
    )