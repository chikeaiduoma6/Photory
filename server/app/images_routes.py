import os
import shutil
import uuid
from datetime import datetime, date
from fractions import Fraction
from typing import List

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from PIL import ExifTags, Image as PILImage, ImageEnhance
from sqlalchemy import func, or_

from .extensions import db
from .models import Image, ImageVersion, Tag, image_tags

images_bp = Blueprint("images", __name__, url_prefix="/api/v1/images")

DEFAULT_TAG_COLORS = ["#ff9db8", "#8ed0ff", "#ffd27f", "#9dd0a5", "#c3a0ff", "#f7a3ff"]


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


def _sanitize_color(raw: str | None) -> str | None:
    if not raw:
        return None
    val = raw.strip()
    if len(val) == 7 and val.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in val[1:]):
        return val.lower()
    return None


def _color_from_name(name: str) -> str:
    palette = current_app.config.get("TAG_COLORS") or DEFAULT_TAG_COLORS
    if not palette:
        return "#ff9db8"
    code = sum(ord(c) for c in name) if name else 0
    return palette[code % len(palette)]


def _get_or_create_tags(tag_names: List[str], user_id: int, color_map: dict[str, str] | None = None) -> List[Tag]:
    tags: List[Tag] = []
    color_map = color_map or {}
    for raw_name in tag_names:
        name = raw_name.strip()
        if not name:
            continue
        tag = Tag.query.filter_by(user_id=user_id, name=name).first()
        desired_color = _sanitize_color(color_map.get(name)) or color_map.get(name)
        if not tag:
            tag = Tag(name=name, user_id=user_id, color=desired_color or _color_from_name(name))
            db.session.add(tag)
        else:
            if desired_color:
                tag.color = desired_color
            elif not tag.color:
                tag.color = _color_from_name(name)
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


def _exif_tag_list(img: Image) -> list[str]:
    raw = [img.camera, img.lens, img.iso, img.aperture, img.exposure, img.focal]
    if img.width and img.height:
        raw.append(f"{img.width}x{img.height}")
    tags: list[str] = []
    for val in raw:
        if val:
            s = str(val).strip()
            if s:
                tags.append(s)
    seen = set()
    uniq = []
    for t in tags:
        if t not in seen:
            uniq.append(t)
            seen.add(t)
    return uniq


def _serialize_version(ver: ImageVersion) -> dict:
    return {
        "id": ver.id,
        "name": ver.name,
        "note": ver.note,
        "created_at": ver.created_at.isoformat(),
        "type": "edit",
        "filename": ver.filename,
        "thumb_path": ver.thumb_path,
    }


def _serialize_image(img: Image) -> dict:
    data = img.to_dict()
    data["raw_url"] = f"/api/v1/images/{img.id}/raw"
    data["thumb_url"] = f"/api/v1/images/{img.id}/thumb"
    data["in_recycle"] = img.deleted_at is not None
    data["tag_objects"] = [
        {"id": t.id, "name": t.name, "color": _sanitize_color(t.color) or _color_from_name(t.name)}
        for t in img.tags
    ]
    data["exif_tags"] = _exif_tag_list(img)
    versions = img.versions.order_by(ImageVersion.created_at.desc()).all()
    data["version_history"] = [_serialize_version(v) for v in versions]
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


def _center_box_by_ratio(ratio: float) -> dict:
    ratio = max(0.01, ratio)
    w = 0.9
    h = w / ratio
    if h > 0.9:
        h = 0.9
        w = h * ratio
    x = (1 - w) / 2
    y = (1 - h) / 2
    return {"x": x, "y": y, "w": w, "h": h}


def _apply_edits(pil: PILImage.Image, payload: dict) -> PILImage.Image:
    rotation = payload.get("rotation", 0) or 0
    zoom = payload.get("zoom", 1) or 1
    crop = payload.get("crop") or {}
    crop_box = payload.get("crop_box") or {}
    adjustments = payload.get("adjustments") or {}

    img = pil.convert("RGB")

    if rotation:
        img = img.rotate(-rotation, expand=True)

    if zoom and zoom != 1:
        w, h = img.size
        target_w = int(w / max(zoom, 0.001))
        target_h = int(h / max(zoom, 0.001))
        left = max(0, (w - target_w) // 2)
        top = max(0, (h - target_h) // 2)
        img = img.crop((left, top, left + target_w, top + target_h))

    preset = crop.get("preset") or crop.get("cropPreset") or "free"
    if preset == "free" and crop_box and crop_box.get("w") and crop_box.get("h"):
        w, h = img.size
        left = max(0, min(w, int(crop_box.get("x", 0) * w)))
        top = max(0, min(h, int(crop_box.get("y", 0) * h)))
        cw = max(1, int(crop_box.get("w", 1) * w))
        ch = max(1, int(crop_box.get("h", 1) * h))
        right = min(w, left + cw)
        bottom = min(h, top + ch)
        img = img.crop((left, top, right, bottom))
    else:
        aspect_w = crop.get("width") or crop.get("w")
        aspect_h = crop.get("height") or crop.get("h")
        ratio = None
        if preset and preset != "free" and preset != "auto":
            if preset == "custom" and aspect_w and aspect_h:
                ratio = float(aspect_w) / float(aspect_h)
            elif ":" in preset:
                try:
                    a, b = preset.split(":")
                    ratio = float(a) / float(b)
                except Exception:
                    ratio = None
            elif "/" in preset:
                try:
                    a, b = preset.split("/")
                    ratio = float(a) / float(b)
                except Exception:
                    ratio = None
        if ratio and ratio > 0:
            w, h = img.size
            target_w = w
            target_h = int(w / ratio)
            if target_h > h:
                target_h = h
                target_w = int(h * ratio)
            left = max(0, (w - target_w) // 2)
            top = max(0, (h - target_h) // 2)
            img = img.crop((left, top, left + target_w, top + target_h))

    bright = float(adjustments.get("brightness") or 0)
    exposure = float(adjustments.get("exposure") or 0)
    contrast = float(adjustments.get("contrast") or 0)
    saturation = float(adjustments.get("saturation") or 0)
    warm = float(adjustments.get("temperature") or 0)
    if bright or exposure:
        factor = 1 + (bright + exposure * 0.6) / 100
        img = ImageEnhance.Brightness(img).enhance(max(0, factor))
    if contrast:
        img = ImageEnhance.Contrast(img).enhance(max(0, 1 + contrast / 100))
    if saturation:
        img = ImageEnhance.Color(img).enhance(max(0, 1 + saturation / 100))
    if warm:
        r, g, b = img.split()
        r = r.point(lambda p: min(255, p * (1 + warm / 200)))
        b = b.point(lambda p: min(255, p * (1 - warm / 400)))
        img = PILImage.merge("RGB", (r, g, b))

    return img


def _save_version_entry(img: Image, note: str) -> None:
    try:
        rel = _normalize_rel_path(img.filename)
        if not rel:
            return
        src = os.path.join(current_app.config["UPLOAD_DIR"], rel)
        if not os.path.exists(src):
            return
        token = uuid.uuid4().hex
        ext = os.path.splitext(rel)[-1] or ".jpg"
        ver_rel = _normalize_rel_path(os.path.join(os.path.dirname(rel), f"ver_{token}{ext}"))
        ver_disk = os.path.join(current_app.config["UPLOAD_DIR"], ver_rel)
        shutil.copy2(src, ver_disk)
        thumb_rel = None
        if img.thumb_path:
            thumb_src = os.path.join(current_app.config["THUMB_DIR"], _normalize_rel_path(img.thumb_path))
            if os.path.exists(thumb_src):
                thumb_rel = _normalize_rel_path(os.path.join(os.path.dirname(img.thumb_path), f"ver_{token}_thumb.jpg"))
                shutil.copy2(thumb_src, os.path.join(current_app.config["THUMB_DIR"], thumb_rel))
        ver_row = ImageVersion(image_id=img.id, name=img.name, note=note, filename=ver_rel, thumb_path=thumb_rel)
        db.session.add(ver_row)
    except Exception:
        current_app.logger.exception("save version entry failed")


def _save_image_and_thumb(img: PILImage.Image, dest_rel: str, thumb_rel: str | None, mime: str) -> tuple[int, int, int, str | None]:
    disk_path = os.path.join(current_app.config["UPLOAD_DIR"], dest_rel)
    os.makedirs(os.path.dirname(disk_path), exist_ok=True)
    img.save(disk_path, format="JPEG", quality=92)
    width, height = img.size
    size = os.path.getsize(disk_path)
    thumb_path = None
    if thumb_rel:
        thumb_disk = os.path.join(current_app.config["THUMB_DIR"], thumb_rel)
        os.makedirs(os.path.dirname(thumb_disk), exist_ok=True)
        try:
            _save_thumb(disk_path, thumb_disk)
            thumb_path = thumb_rel
        except Exception:
            thumb_path = None
    return width, height, size, thumb_path


def _list_param(name: str) -> list[str]:
    vals: list[str] = []
    for v in request.args.getlist(name):
        vals.extend(str(v).split(","))
    raw = request.args.get(name)
    if raw:
        vals.extend(str(raw).split(","))
    return [s.strip() for s in vals if str(s).strip()]


def _parse_date_param(key: str, end_of_day: bool = False) -> datetime | None:
    raw = request.args.get(key)
    if not raw:
        return None
    try:
        dt = datetime.strptime(raw.strip(), "%Y-%m-%d")
        if end_of_day:
            return dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    except Exception:
        return None


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
            image_row.tags = _get_or_create_tags(tag_names, user_id=user_id)
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


@images_bp.get("/search")
def search_images():
    user_id = _current_user_id()
    page = _positive_int(request.args.get("page"), 1)
    page_size = _positive_int(request.args.get("page_size"), 12, 50)
    sort = request.args.get("sort", "captured_desc")

    keyword = (request.args.get("keyword") or "").strip()
    tag_names = _list_param("tags")
    format_list = [f.lstrip(".").lower() for f in _list_param("formats")]
    captured_start = _parse_date_param("captured_start")
    captured_end = _parse_date_param("captured_end", end_of_day=True)
    uploaded_start = _parse_date_param("uploaded_start")
    uploaded_end = _parse_date_param("uploaded_end", end_of_day=True)
    size_min_mb = request.args.get("size_min_mb")
    size_max_mb = request.args.get("size_max_mb")

    exif_map = {
        "camera": Image.camera,
        "lens": Image.lens,
        "iso": Image.iso,
        "aperture": Image.aperture,
        "focal_length": Image.focal,
        "shutter": Image.exposure,
    }

    query = _query_user_images(user_id, include_deleted=False)

    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(
            or_(
                Image.name.ilike(kw),
                Image.original_name.ilike(kw),
                Image.tags.any(Tag.name.ilike(kw)),
            )
        )

    for tag_name in tag_names:
        query = query.filter(Image.tags.any(Tag.name == tag_name))

    if format_list:
        conds = []
        for fmt in format_list:
            conds.append(func.lower(Image.filename).like(f"%.{fmt}"))
            conds.append(func.lower(Image.original_name).like(f"%.{fmt}"))
            conds.append(func.lower(Image.mime_type).like(f"%{fmt}%"))
        query = query.filter(or_(*conds))

    if captured_start:
        query = query.filter(Image.taken_at.isnot(None), Image.taken_at >= captured_start)
    if captured_end:
        query = query.filter(Image.taken_at.isnot(None), Image.taken_at <= captured_end)
    if uploaded_start:
        query = query.filter(Image.created_at >= uploaded_start)
    if uploaded_end:
        query = query.filter(Image.created_at <= uploaded_end)

    try:
        min_mb = int(size_min_mb) if size_min_mb is not None else 0
    except ValueError:
        min_mb = 0
    try:
        max_mb = int(size_max_mb) if size_max_mb is not None else 200
    except ValueError:
        max_mb = 200
    if min_mb > 0:
        query = query.filter(Image.size >= min_mb * 1024 * 1024)
    if max_mb < 9999:
        query = query.filter(Image.size <= max_mb * 1024 * 1024)

    for key, col in exif_map.items():
        val = (request.args.get(key) or "").strip()
        if val:
            query = query.filter(col.ilike(f"%{val}%"))

    tag_count_subq = (
        db.session.query(image_tags.c.image_id, func.count(image_tags.c.tag_id).label("tag_count"))
        .group_by(image_tags.c.image_id)
        .subquery()
    )
    res_expr = func.coalesce(Image.width, 0) * func.coalesce(Image.height, 0)
    sort_map = {
        "captured_desc": func.coalesce(Image.taken_at, Image.created_at).desc(),
        "captured_asc": func.coalesce(Image.taken_at, Image.created_at).asc(),
        "uploaded_desc": Image.created_at.desc(),
        "uploaded_asc": Image.created_at.asc(),
        "size_desc": Image.size.desc(),
        "size_asc": Image.size.asc(),
        "res_desc": res_expr.desc(),
        "res_asc": res_expr.asc(),
        "name_asc": Image.name.asc(),
    }

    if sort == "tag_desc":
        query = query.outerjoin(tag_count_subq, Image.id == tag_count_subq.c.image_id).order_by(
            tag_count_subq.c.tag_count.desc().nullslast(),
            Image.created_at.desc(),
        )
    else:
        order_clause = sort_map.get(sort, sort_map["captured_desc"])
        query = query.outerjoin(tag_count_subq, Image.id == tag_count_subq.c.image_id).order_by(order_clause)

    pagination = query.paginate(page=page, per_page=page_size, error_out=False)
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
    raw_tags = data.get("tags") or []
    color_map = data.get("colors") or {}
    names: list[str] = []
    colors: dict[str, str] = {}

    for item in raw_tags:
        if isinstance(item, dict):
            name = (item.get("name") or item.get("label") or "").strip()
            if not name:
                continue
            names.append(name)
            color_val = _sanitize_color(item.get("color"))
            if color_val:
                colors[name] = color_val
        else:
            name = str(item).strip()
            if name:
                names.append(name)

    for k, v in (color_map or {}).items():
        val = _sanitize_color(str(v))
        if val:
            colors[str(k)] = val

    img.tags = _get_or_create_tags(names, user_id=user_id, color_map=colors)
    db.session.commit()
    return jsonify(
        {
            "message": "ok",
            "tags": [t.name for t in img.tags],
            "tag_objects": [
                {"id": t.id, "name": t.name, "color": _sanitize_color(t.color) or _color_from_name(t.name)}
                for t in img.tags
            ],
        }
    )


@images_bp.post("/<int:image_id>/export")
def export_image(image_id: int):
    user_id = _current_user_id()
    img = _get_user_image(image_id, user_id, include_deleted=False)

    data = request.get_json() or {}
    mode = data.get("option") or data.get("mode") or data.get("export_option") or "override"
    name = (data.get("name") or img.name).strip() or img.name
    folder = (data.get("folder") or img.folder or "默认图库").strip() or "默认图库"
    tags_payload = data.get("tags") or []
    adjustments = data.get("adjustments") or {}
    crop = data.get("crop") or {}
    crop_box = data.get("crop_box") or {}
    rotation = data.get("rotation") or 0
    zoom = data.get("zoom") or 1

    color_map: dict[str, str] = {}
    tag_names: list[str] = []
    for item in tags_payload:
        if isinstance(item, dict):
            nm = (item.get("name") or item.get("label") or "").strip()
            if nm:
                tag_names.append(nm)
                val = _sanitize_color(item.get("color"))
                if val:
                    color_map[nm] = val
        else:
            nm = str(item).strip()
            if nm:
                tag_names.append(nm)

    rel = _normalize_rel_path(img.filename)
    if not rel:
        return jsonify({"message": "文件路径异常"}), 400
    src_path = os.path.join(current_app.config["UPLOAD_DIR"], rel)
    if not os.path.exists(src_path):
        return jsonify({"message": "源文件不存在"}), 404

    with PILImage.open(src_path) as pil_img:
        edited = _apply_edits(
            pil_img,
            {
                "rotation": rotation,
                "zoom": zoom,
                "crop": crop,
                "crop_box": crop_box if (crop.get("preset") or crop.get("cropPreset") or "free") == "free" else {},
                "adjustments": adjustments,
            },
        )

    if mode == "override":
        _save_version_entry(img, "覆盖前版本")

    file_token = uuid.uuid4().hex
    ext = os.path.splitext(rel)[-1] or ".jpg"
    if mode == "override":
        dest_rel = rel
        thumb_rel = img.thumb_path or _normalize_rel_path(os.path.join(f"user_{user_id}", f"{file_token}_thumb.jpg"))
    else:
        dest_rel = _normalize_rel_path(os.path.join(f"user_{user_id}", f"{file_token}{ext}"))
        thumb_rel = _normalize_rel_path(os.path.join(f"user_{user_id}", f"{file_token}_thumb.jpg"))

    width, height, size, thumb_path = _save_image_and_thumb(edited, dest_rel, thumb_rel, img.mime_type)

    if mode == "override":
        img.name = name
        img.folder = folder
        img.filename = dest_rel
        img.thumb_path = thumb_path
        img.size = size
        img.width = width
        img.height = height
        img.updated_at = datetime.utcnow()
        img.tags = _get_or_create_tags(tag_names or [t.name for t in img.tags], user_id=user_id, color_map=color_map)
        db.session.commit()
        return jsonify({"message": "ok", "item": _serialize_image(img)})

    new_img = Image(
        user_id=user_id,
        name=name,
        filename=dest_rel,
        original_name=name,
        mime_type=img.mime_type,
        size=size,
        width=width,
        height=height,
        taken_at=img.taken_at,
        camera=img.camera,
        lens=img.lens,
        iso=img.iso,
        exposure=img.exposure,
        aperture=img.aperture,
        focal=img.focal,
        latitude=img.latitude,
        longitude=img.longitude,
        thumb_path=thumb_path,
        visibility=img.visibility,
        folder=folder,
    )
    new_img.tags = _get_or_create_tags(tag_names or [t.name for t in img.tags], user_id=user_id, color_map=color_map)
    db.session.add(new_img)
    db.session.commit()
    return jsonify({"message": "ok", "item": _serialize_image(new_img)})
