import os
import uuid
from datetime import datetime
from typing import List

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from PIL import ExifTags, Image as PILImage

from .extensions import db
from .models import Image, Tag

images_bp = Blueprint("images", __name__, url_prefix="/api/v1/images")


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[-1].lower() in current_app.config["ALLOWED_IMAGE_EXTS"]


def _ensure_user_dirs(user_id: int) -> None:
    os.makedirs(os.path.join(current_app.config["UPLOAD_DIR"], f"user_{user_id}"), exist_ok=True)
    os.makedirs(os.path.join(current_app.config["THUMB_DIR"], f"user_{user_id}"), exist_ok=True)


def _extract_exif(pil_img: PILImage.Image) -> dict:
    data: dict = {}
    try:
        raw = pil_img._getexif() or {}
        tags = {ExifTags.TAGS.get(k, k): v for k, v in raw.items()}
        data["taken_at"] = tags.get("DateTimeOriginal") or tags.get("DateTime")
        data["camera"] = tags.get("Model")
        data["lens"] = tags.get("LensModel")
        data["iso"] = str(tags.get("ISOSpeedRatings") or tags.get("PhotographicSensitivity") or "")
        data["exposure"] = str(tags.get("ExposureTime") or "")
        data["aperture"] = (
            f"f/{tags['FNumber'][0] / tags['FNumber'][1]}"
            if isinstance(tags.get("FNumber"), tuple)
            else str(tags.get("FNumber") or "")
        )
        data["focal"] = str(tags.get("FocalLength") or "")
    except Exception:
        pass
    return data


def _parse_taken_at(raw: str | None):
    if not raw:
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _save_thumb(src_path: str, dest_path: str, size=(400, 400)) -> None:
    with PILImage.open(src_path) as img:
        img.thumbnail(size)
        img.save(dest_path, format="JPEG", quality=85)


def _get_or_create_tags(tag_names: List[str]) -> List[Tag]:
    tags: List[Tag] = []
    for name in tag_names:
        name = name.strip()
        if not name:
            continue
        tag = Tag.query.filter_by(name=name).first()
        if not tag:
            tag = Tag(name=name)
            db.session.add(tag)
        tags.append(tag)
    return tags


def _current_user_id() -> int:
    # 允许从 Header 或 query_string 读取 JWT，方便 <img src> 带 token
    verify_jwt_in_request(optional=False, locations=["headers", "query_string"])
    return int(get_jwt_identity())


def _serialize_image(img: Image) -> dict:
    data = img.to_dict()
    data["raw_url"] = f"/api/v1/images/{img.id}/raw"
    data["thumb_url"] = f"/api/v1/images/{img.id}/thumb"
    return data


def _positive_int(value, default: int, max_value: int | None = None) -> int:
    try:
        num = int(value)
    except (TypeError, ValueError):
        return default
    num = max(num, 1)
    if max_value:
        num = min(num, max_value)
    return num


@images_bp.post("/upload")
def upload():
    user_id = _current_user_id()
    files = request.files.getlist("file")
    if not files:
        return jsonify({"message": "请至少选择一个文件"}), 400
    if any(not f.filename or not _allowed(f.filename) for f in files):
        return jsonify({"message": "仅支持上传图片文件（jpg/png/gif/webp/bmp）"}), 400

    folder = (request.form.get("folder") or "默认图库").strip() or "默认图库"
    visibility = request.form.get("visibility", "private")
    tag_names = [x.strip() for x in (request.form.get("tags") or "").split(",") if x.strip()]
    custom_name = (request.form.get("name") or "").strip()

    _ensure_user_dirs(user_id)

    saved: list[Image] = []
    try:
        for f in files:
            ext = f.filename.rsplit(".", 1)[-1].lower()
            file_token = uuid.uuid4().hex
            rel_path = os.path.join(f"user_{user_id}", f"{file_token}.{ext}")
            disk_path = os.path.join(current_app.config["UPLOAD_DIR"], rel_path)
            f.save(disk_path)

            with PILImage.open(disk_path) as img:
                width, height = img.size
                exif = _extract_exif(img)

            thumb_rel = os.path.join(f"user_{user_id}", f"{file_token}_thumb.jpg")
            thumb_disk = os.path.join(current_app.config["THUMB_DIR"], thumb_rel)
            try:
                _save_thumb(disk_path, thumb_disk)
            except Exception:
                thumb_rel = None

            image_row = Image(
                user_id=user_id,
                name=custom_name or os.path.splitext(f.filename)[0],
                filename=rel_path,
                original_name=f.filename,
                mime_type=f.mimetype,
                size=os.path.getsize(disk_path),
                width=width,
                height=height,
                taken_at=_parse_taken_at(exif.get("taken_at")),
                camera=exif.get("camera"),
                lens=exif.get("lens"),
                iso=exif.get("iso"),
                exposure=exif.get("exposure"),
                aperture=exif.get("aperture"),
                focal=exif.get("focal"),
                thumb_path=thumb_rel,
                visibility="public" if visibility == "public" else "private",
                folder=folder,
            )
            image_row.tags = _get_or_create_tags(tag_names)
            db.session.add(image_row)
            saved.append(image_row)

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("image upload failed")
        return jsonify({"message": "上传失败，请稍后再试"}), 500

    return jsonify({"message": "上传成功", "items": [_serialize_image(i) for i in saved]}), 201


@images_bp.get("")
def list_images():
    user_id = _current_user_id()
    page = _positive_int(request.args.get("page"), 1)
    page_size = _positive_int(request.args.get("page_size"), 12, 50)
    sort = request.args.get("sort", "newest")

    query = Image.query.filter_by(user_id=user_id)
    folder = request.args.get("folder")
    if folder:
        query = query.filter(Image.folder == folder)

    order_by = Image.created_at.asc() if sort == "oldest" else Image.created_at.desc()
    pagination = query.order_by(order_by).paginate(page=page, per_page=page_size, error_out=False)

    return jsonify(
        {
            "items": [_serialize_image(img) for img in pagination.items],
            "total": pagination.total,
            "page": page,
            "page_size": page_size,
        }
    )


@images_bp.get("/<int:image_id>")
def image_detail(image_id: int):
    user_id = _current_user_id()
    img = Image.query.get_or_404(image_id)
    if img.user_id != user_id:
        return jsonify({"message": "无权限访问此图片"}), 403
    return jsonify(_serialize_image(img))


@images_bp.get("/<int:image_id>/raw")
def serve_raw(image_id: int):
    user_id = _current_user_id()
    img = Image.query.get_or_404(image_id)
    if img.user_id != user_id:
        return jsonify({"message": "无权限访问此图片"}), 403

    disk_path = os.path.join(current_app.config["UPLOAD_DIR"], img.filename)
    if not os.path.exists(disk_path):
        return jsonify({"message": "文件不存在"}), 404
    return send_file(disk_path, mimetype=img.mime_type)


@images_bp.get("/<int:image_id>/thumb")
def serve_thumb(image_id: int):
    user_id = _current_user_id()
    img = Image.query.get_or_404(image_id)
    if img.user_id != user_id:
        return jsonify({"message": "无权限访问此图片"}), 403

    if img.thumb_path:
        thumb_path = os.path.join(current_app.config["THUMB_DIR"], img.thumb_path)
        if os.path.exists(thumb_path):
            return send_file(thumb_path, mimetype="image/jpeg")

    disk_path = os.path.join(current_app.config["UPLOAD_DIR"], img.filename)
    if not os.path.exists(disk_path):
        return jsonify({"message": "文件不存在"}), 404
    return send_file(disk_path, mimetype=img.mime_type)
