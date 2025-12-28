import os
import threading
import time
from flask import Flask, jsonify
from sqlalchemy import text, inspect
from .config import Config
from .extensions import bcrypt, db, jwt
from .auth_routes import auth_bp
from .images_routes import images_bp, _normalize_rel_path, purge_expired_recycle
from .tags_routes import tags_bp
from .albums_routes import albums_bp  # 导入相册路由蓝图
from .models import User, Image

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
    app.register_blueprint(tags_bp)
    app.register_blueprint(albums_bp)  # 注册相册路由蓝图

    with app.app_context():
        db.create_all()
        _ensure_columns()
        _ensure_dirs(app)
        _ensure_default_admin()
        _fix_existing_paths()
        
        try:
            purge_expired_recycle()
        except Exception:
            app.logger.exception("startup recycle purge failed")

    _start_recycle_purge_thread(app)

    return app


def _ensure_columns():
    """
    自动补充 images 表缺失的列（description, exif_json）。
    
    """
    try:
        insp = inspect(db.engine)
        cols = {c["name"] for c in insp.get_columns("images")}
        alters = []
        if "description" not in cols:
            alters.append("ALTER TABLE images ADD COLUMN description TEXT NULL")
        if "exif_json" not in cols:
            alters.append("ALTER TABLE images ADD COLUMN exif_json LONGTEXT NULL")
        for sql in alters:
            db.session.execute(text(sql))
        if alters:
            db.session.commit()
    except Exception:
        db.session.rollback()


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


def _start_recycle_purge_thread(app: Flask) -> None:
    
    if app.extensions.get("recycle_purge_started"):
        return
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    app.extensions["recycle_purge_started"] = True

    interval = int(app.config.get("RECYCLE_PURGE_INTERVAL_SECONDS", 3600))
    retention_days = int(app.config.get("RECYCLE_RETENTION_DAYS", 7))
    interval = max(60, interval)
    retention_days = max(1, retention_days)

    def _loop():
        while True:
            try:
                with app.app_context():
                    purge_expired_recycle(retention_days=retention_days)
            except Exception:
                app.logger.exception("recycle purge task failed")
            time.sleep(interval)

    threading.Thread(target=_loop, name="recycle-purge", daemon=True).start()
