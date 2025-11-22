from datetime import timedelta
import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)

    # 允许从 Header 与 query 读取 JWT（供 <img src> 使用）
    JWT_TOKEN_LOCATION = ["headers", "query_string"]
    JWT_QUERY_STRING_NAME = "jwt"

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://photouser:photopass@127.0.0.1:3307/photomanager",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False

    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")
    THUMB_DIR = os.getenv("THUMB_DIR", "/app/uploads/thumbs")
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
    ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp", "bmp"}
