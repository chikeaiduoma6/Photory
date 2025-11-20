import os

class Config:
    # Flask & JWT
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-me")

    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://photouser:photopass@127.0.0.1:3307/photomanager",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JSON_AS_ASCII = False
