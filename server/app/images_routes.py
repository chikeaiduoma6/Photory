import os
import uuid
from datetime import datetime, date
from fractions import Fraction
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


def _gps_to_decimal(gps_info) -> tuple[float | None, float | None]:
    def _conv(val):
        d, m, s = [Fraction(x[0], x[1]) for x in val]
        return float(d + m / 60 + s / 3600)

    try:
        lat = _conv(gps_info[2])
        if gps_info[1] in ["S", "s"]:
            lat = -lat
        lon = _conv(gps_info[4])
        if gps_info[3] in ["W", "w"]:
            lon = -lon
        return lat, lon
    except Exception:
        return None, None


def _extract_exif(pil_img: PILImage.Image) -> dict:
    exif: dict = {}
    try:
        raw = pil_img.getexif()
        data = dict(raw.items()) if raw else {}
        if not data and pil_img.info.get("exif"):
            try:
                exif_obj = PILImage.Exif()
                exif_obj.load(pil_img.info["exif"])
                data = dict(exif_obj.items())
            except Exception:
                pass
        tags = {ExifTags.TAGS.get(k, k): v for k, v in data.items()}
        exif["taken_at"] = tags.get("DateTimeOriginal") or tags.get("DateTime")
        exif["camera"] = tags.get("Model")
        exif["lens"] = tags.get("LensModel")
        exif["iso"] = str(tags.get("ISOSpeedRatings") or tags.get("PhotographicSensitivity") or "")
        exif["exposure"] = str(tags.get("ExposureTime") or "")
        exif["aperture"] = (
            f"f/{tags['FNumber'][0] / tags['FNumber'][1]}"
            if isinstance(tags.get("FNumber"), tuple)
            else str(tags.get("FNumber") or "")
        )
        exif["focal"] = str(tags.get("FocalLength") or "")
        exif["gps"] = tags.get("GPSInfo")
    except Exception:
        pass
    return exif


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


def _auto_tags(exif: dict, width: int, height: int) -> List[str]:
    tags: List[str] = []
    if exif.get("camera"):
        tags.append(exif["camera"])
    if exif.get("lens"):
        tags.append(exif["lens"])
    if exif.get("taken_at"):
        ts = exif["taken_at"].replace("-", ":").split()[0].split(":")
        if len(ts) >= 2:
            tags.append(ts[0])
            tags.append(f"{ts[0]}-{ts[1]}")
    if width and height:
        tags.append(f"{width}x{height}")
    if exif.get("iso"):
        try:
            iso_val = int(exif["iso"])
            if iso_val >= 1600:
                tags.append("高感光")
        except Exception:
            pass
    return [t for t in tags if t]


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
    verify_jwt_in_request(optional=False, locations=["headers", "query_string"])
    return int(get_jwt_identity())


def _normalize_rel_path(path: str | None) -> str | None:
    if not path:
        return None
    cleaned = os.path.normpath(path.replace("\\", "/")).lstrip("/\\")
    return cleaned


def _serialize_image(img: Image) -> dict:
    data = img.to_dict()
    data["raw_url"] = f"/api/v1/images/{img.id}/raw"
    data["thumb_url"] = f"/api/v1/images/{img.id}/thumb"
    data["in_recycle"] = img.deleted_at is not None
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


def _query_user_images(user_id: int, include_deleted=False):
    q = Image.query.filter_by(user_id=user_id)
    if not include_deleted:
        q = q.filter(Image.deleted_at.is_(None))
    return q


def _get_user_image(image_id: int, user_id: int, include_deleted: bool) -> Image:
    return (
        _query_user_images(user_id, include_deleted)
        .filter(Image.id == image_id)
        .first_or_404()
    )


def _remove_files(img: Image):
    try:
        rel = _normalize_rel_path(img.filename)
        if rel:
            disk_path = os.path.join(current_app.config["UPLOAD_DIR"], rel)
            if os.path.exists(disk_path):
                os.remove(disk_path)
    except Exception:
        pass
    try:
        rel = _normalize_rel_path(img.thumb_path)
        if rel:
            thumb_path = os.path.join(current_app.config["THUMB_DIR"], rel)
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
    except Exception:
        pass


@images_bp.post("/upload")
def upload():
    user_id = _current_user_id()
    files = request.files.getlist("file")
    if not files:
        return jsonify({"message": "请至少选择一个文件"}), 400
    if any(not f.filename or not _allowed(f.filename) for f in files):
        return jsonify({"message": "仅支持上传图片文件（jpg/jpeg/png/gif/webp/bmp/heic/heif）"}), 400

    folder = (request.form.get("folder") or "默认图库").strip() or "默认图库"
    visibility = request.form.get("visibility", "private")
    tag_names = [x.strip() for x in (request.form.get("tags") or "").split(",") if x.strip()]
    custom_name = (request.form.get("name") or "").strip()

    _ensure_user_dirs(user_id)

    saved: list[Image] = []
    try:
        for f in files:
            orig_ext = f.filename.rsplit(".", 1)[-1].lower()
            is_heic = orig_ext in {"heic", "heif"}
            ext = "jpg" if is_heic else orig_ext
            file_token = uuid.uuid4().hex
            rel_path = _normalize_rel_path(os.path.join(f"user_{user_id}", f"{file_token}.{ext}"))
            disk_path = os.path.join(current_app.config["UPLOAD_DIR"], rel_path)

            if is_heic:
                with PILImage.open(f.stream) as img:
                    width, height = img.size
                    exif = _extract_exif(img)
                    img.convert("RGB").save(disk_path, format="JPEG", quality=95)
            else:
                f.save(disk_path)
                with PILImage.open(disk_path) as img:
                    width, height = img.size
                    exif = _extract_exif(img)

            lat = lon = None
            if exif.get("gps"):
                lat, lon = _gps_to_decimal(exif["gps"])

            auto_tags = _auto_tags(exif, width, height)
            merged_tags = list(dict.fromkeys(tag_names + auto_tags))

            thumb_rel = _normalize_rel_path(os.path.join(f"user_{user_id}", f"{file_token}_thumb.jpg"))
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
                mime_type="image/jpeg" if is_heic else f.mimetype,
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
                latitude=lat,
                longitude=lon,
                thumb_path=thumb_rel,
                visibility="public" if visibility == "public" else "private",
                folder=folder,
            )
            image_row.tags = _get_or_create_tags(merged_tags)
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

    query = _query_user_images(user_id, include_deleted=False)
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


@images_bp.get("/stats")
def image_stats():
    user_id = _current_user_id()
    today = date.today()
    today_deleted = (
        _query_user_images(user_id, include_deleted=True)
        .filter(Image.deleted_at.isnot(None))
        .filter(db.func.date(Image.deleted_at) == today)
        .count()
    )
    total_active = _query_user_images(user_id, include_deleted=False).count()
    recycle_count = _query_user_images(user_id, include_deleted=True).filter(Image.deleted_at.isnot(None)).count()
    return jsonify({"today_deleted": today_deleted, "total_active": total_active, "recycle_count": recycle_count})


@images_bp.get("/recycle")
def list_recycle():
    user_id = _current_user_id()
    page = _positive_int(request.args.get("page"), 1)
    page_size = _positive_int(request.args.get("page_size"), 12, 50)
    query = _query_user_images(user_id, include_deleted=True).filter(Image.deleted_at.isnot(None))
    pagination = query.order_by(Image.deleted_at.desc()).paginate(page=page, per_page=page_size, error_out=False)
    return jsonify(
        {
            "items": [_serialize_image(img) for img in pagination.items],
            "total": pagination.total,
            "page": page,
            "page_size": page_size,
        }
    )


@images_bp.post("/trash-batch")
def trash_batch():
    user_id = _current_user_id()
    data = request.get_json() or {}
    ids = data.get("ids") or []
    if not ids:
        return jsonify({"message": "缺少图片 ID"}), 400
    imgs = _query_user_images(user_id, include_deleted=True).filter(Image.id.in_(ids)).all()
    for img in imgs:
        img.deleted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "ok", "count": len(imgs)})


@images_bp.post("/<int:image_id>/trash")
def trash_one(image_id: int):
    user_id = _current_user_id()
    img = _get_user_image(image_id, user_id, include_deleted=True)
    if img.deleted_at:
        return jsonify({"message": "已在回收站"}), 400
    img.deleted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "ok"})


@images_bp.post("/recycle/restore")
def recycle_restore():
    user_id = _current_user_id()
    data = request.get_json() or {}
    ids = data.get("ids") or []
    if not ids:
        return jsonify({"message": "缺少图片 ID"}), 400
    imgs = _query_user_images(user_id, include_deleted=True).filter(Image.id.in_(ids)).all()
    for img in imgs:
        img.deleted_at = None
    db.session.commit()
    return jsonify({"message": "ok", "restored": len(imgs)})


@images_bp.post("/recycle/purge")
def recycle_purge():
    user_id = _current_user_id()
    data = request.get_json() or {}
    ids = data.get("ids") or []
    if not ids:
        return jsonify({"message": "缺少图片 ID"}), 400
    imgs = _query_user_images(user_id, include_deleted=True).filter(Image.id.in_(ids)).all()
    for img in imgs:
        _remove_files(img)
        db.session.delete(img)
    db.session.commit()
    return jsonify({"message": "ok", "deleted": len(imgs)})


@images_bp.post("/recycle/clear")
def recycle_clear():
    user_id = _current_user_id()
    imgs = _query_user_images(user_id, include_deleted=True).filter(Image.deleted_at.isnot(None)).all()
    for img in imgs:
        _remove_files(img)
        db.session.delete(img)
    db.session.commit()
    return jsonify({"message": "ok", "deleted": len(imgs)})


@images_bp.get("/<int:image_id>")
def image_detail(image_id: int):
    user_id = _current_user_id()
    img = _get_user_image(image_id, user_id, include_deleted=True)
    return jsonify(_serialize_image(img))


@images_bp.get("/<int:image_id>/raw")
def serve_raw(image_id: int):
    user_id = _current_user_id()
    img = _get_user_image(image_id, user_id, include_deleted=True)
    rel = _normalize_rel_path(img.filename)
    disk_path = os.path.join(current_app.config["UPLOAD_DIR"], rel) if rel else None
    if not disk_path or not os.path.exists(disk_path):
        return jsonify({"message": "文件不存在"}), 404
    return send_file(disk_path, mimetype=img.mime_type)


@images_bp.get("/<int:image_id>/thumb")
def serve_thumb(image_id: int):
    user_id = _current_user_id()
    img = _get_user_image(image_id, user_id, include_deleted=True)

    thumb_rel = _normalize_rel_path(img.thumb_path)
    if thumb_rel:
        thumb_path = os.path.join(current_app.config["THUMB_DIR"], thumb_rel)
        if os.path.exists(thumb_path):
            return send_file(thumb_path, mimetype="image/jpeg")

    rel = _normalize_rel_path(img.filename)
    disk_path = os.path.join(current_app.config["UPLOAD_DIR"], rel) if rel else None
    if not disk_path or not os.path.exists(disk_path):
        return jsonify({"message": "文件不存在"}), 404
    return send_file(disk_path, mimetype=img.mime_type)


@images_bp.post("/<int:image_id>/tags")
def update_tags(image_id: int):
    user_id = _current_user_id()
    img = _get_user_image(image_id, user_id, include_deleted=False)

    data = request.get_json() or {}
    tags = [t.strip() for t in data.get("tags", []) if t and t.strip()]
    img.tags = _get_or_create_tags(tags)
    db.session.commit()
    return jsonify({"message": "ok", "tags": [t.name for t in img.tags]})
