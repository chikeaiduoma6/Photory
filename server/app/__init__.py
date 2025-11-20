from flask import Flask, jsonify
from sqlalchemy import text

from .config import Config
from .extensions import db

def create_app(config_class: type[Config] = Config) -> Flask:
    # 创建并配置 Flask 实例
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 初始化扩展
    db.init_app(app)

    # 检查服务是否正常 & 数据库是否可连
    @app.get("/api/health")
    def health_check():
        try:
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False

        return (
            jsonify({
                "status": "ok" if db_ok else "error",
                "db": db_ok,
            }),
            200 if db_ok else 500,
        )

    return app