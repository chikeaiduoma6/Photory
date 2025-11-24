import os
from flask import Flask, jsonify
from sqlalchemy import text
from .config import Config
from .extensions import bcrypt, db, jwt
from .auth_routes import auth_bp
from .images_routes import images_bp, _normalize_rel_path
from .models import User, Image

# 允许 PIL 读取 HEIC/HEIF
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass

def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)

    @app.get("/api/health")
    def health_check():
        try:
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False
        return jsonify({"status": "ok" if db_ok else "error", "db": db_ok}), (200 if db_ok else 500)

    app.register_blueprint(auth_bp)
    app.register_blueprint(images_bp)

    with app.app_context():
        db.create_all()
        _ensure_dirs(app)
        _ensure_default_admin()
        _fix_existing_paths()

    return app


def _ensure_dirs(app: Flask):
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    os.makedirs(app.config["THUMB_DIR"], exist_ok=True)


def _ensure_default_admin():
    admin = User.query.filter_by(username="hyk").first()
    if not admin:
        admin = User(username="hyk", email="3230103921@zju.edu.cn", is_admin=True)
        admin.set_password("bs2025123")
        db.session.add(admin)
        db.session.commit()


def _fix_existing_paths():
    """启动时把数据库里残留的反斜杠路径改成标准斜杠。"""
    updated = 0
    for img in Image.query.all():
        new_filename = _normalize_rel_path(img.filename)
        new_thumb = _normalize_rel_path(img.thumb_path)
        if new_filename != img.filename or new_thumb != img.thumb_path:
            img.filename = new_filename
            img.thumb_path = new_thumb
            updated += 1
    if updated:
        db.session.commit()
