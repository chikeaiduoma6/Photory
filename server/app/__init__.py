from flask import Flask, jsonify
from sqlalchemy import text

from .config import Config
from .extensions import db
from .auth_routes import auth_bp


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    
    @app.get("/api/health")
    def health_check():
        try:
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False

        return jsonify({"status": "ok" if db_ok else "error", "db": db_ok}), (
            200 if db_ok else 500
        )

    # 注册认证相关接口
    app.register_blueprint(auth_bp)

    return app
