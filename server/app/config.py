import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://photouser:photopass@127.0.0.1:3307/photomanager",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False

    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")
    THUMB_DIR = os.getenv("THUMB_DIR", "/app/uploads/thumbs")
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20MB
    ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "heic", "heif"}

    QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
    QWEN_API_BASE = os.getenv(
        "QWEN_API_BASE",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",  
    )
    QWEN_VISION_MODEL = os.getenv("QWEN_VISION_MODEL", "qwen-vl-max")

    QWEN_CHAT_MODEL = os.getenv("QWEN_CHAT_MODEL", "qwen-turbo")

    AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "60"))
    AI_MAX_TAGS = int(os.getenv("AI_MAX_TAGS", "6"))

    # Recycle bin retention/purge
    RECYCLE_RETENTION_DAYS = int(os.getenv("RECYCLE_RETENTION_DAYS", "7"))
    RECYCLE_PURGE_INTERVAL_SECONDS = int(os.getenv("RECYCLE_PURGE_INTERVAL_SECONDS", "3600"))
