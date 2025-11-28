import io
import os
import re
import shutil
import uuid
import json
from datetime import datetime, date, time
from fractions import Fraction
from typing import List

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from pillow_heif import read_heif, register_heif_opener
from PIL import ExifTags, Image as PILImage, ImageEnhance, ImageOps
from sqlalchemy import func, or_

from .extensions import db
from .models import Image, ImageVersion, Tag, image_tags

images_bp = Blueprint("images", __name__, url_prefix="/api/v1/images")

DEFAULT_TAG_COLORS = ["#ff9db8", "#8ed0ff", "#ffd27f", "#9dd0a5", "#c3a0ff", "#f7a3ff"]

register_heif_opener()


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[-1].lower() in current_app.config["ALLOWED_IMAGE_EXTS"]


def _ensure_user_dirs(user_id: int) -> None:
    os.makedirs(os.path.join(current_app.config["UPLOAD_DIR"], f"user_{user_id}"), exist_ok=True)
    os.makedirs(os.path.join(current_app.config["THUMB_DIR"], f"user_{user_id}"), exist_ok=True)


def _tag_name(tag_id) -> str:
    if isinstance(tag_id, int):
        return ExifTags.TAGS.get(tag_id, f"Tag_{tag_id}")
    return str(tag_id)


def _format_exif_value(val):
    try:
        if isinstance(val, bytes):
            return val.decode(errors="ignore")
        if isinstance(val, tuple):
            if len(val) == 2 and all(isinstance(x, (int, float)) for x in val):
                a, b = val
                return f"{a}/{b}" if b else str(a)
            return " ".join(str(x) for x in val)
        return str(val)
    except Exception:
        return str(val)


def _to_fraction(val) -> Fraction | None:
    try:
        if isinstance(val, Fraction):
            return val
        if hasattr(val, "numerator") and hasattr(val, "denominator"):
            return Fraction(val.numerator, val.denominator)
        if isinstance(val, (tuple, list)) and len(val) == 2 and val[1]:
            return Fraction(val[0], val[1])
        if isinstance(val, (int, float)):
            return Fraction(val).limit_denominator()
        if isinstance(val, str):
            txt = val.strip()
            if "/" in txt:
                a, b = txt.split("/", 1)
                return Fraction(float(a), float(b))
            return Fraction(txt).limit_denominator()
    except Exception:
        return None
    return None


def _format_fraction(val) -> Fraction | None:
    frac = _to_fraction(val)
    if frac is None:
        return None
    return frac


def _friendly_exposure(val) -> str:
    frac = _format_fraction(val)
    if not frac:
        return _format_exif_value(val) if val is not None else ""
    if frac.numerator == 0:
        return ""
    if frac.numerator == 1:
        return f"1/{frac.denominator}s"
    return f"{float(frac):.4f}s"


def _friendly_aperture(val) -> str:
    num = None
    frac = _format_fraction(val)
    if frac is not None:
        try:
            num = float(frac)
        except Exception:
            num = None
    if num is None:
        try:
            num = float(val)
        except Exception:
            num = None
    if num:
        return f"f/{num:.1f}".rstrip("0").rstrip(".")
    return _format_exif_value(val) if val is not None else ""


def _friendly_focal(val) -> str:
    num = None
    frac = _format_fraction(val)
    if frac is not None:
        try:
            num = float(frac)
        except Exception:
            num = None
    if num is None:
        try:
            num = float(val)
        except Exception:
            num = None
    if num:
        return f"{num:.1f} mm".rstrip("0").rstrip(".")
    return _format_exif_value(val) if val is not None else ""


def _format_lens_spec(val) -> str:
    if isinstance(val, (list, tuple)):
        nums = []
        for item in val:
            frac = _format_fraction(item)
            if frac is not None:
                nums.append(float(frac))
            else:
                try:
                    nums.append(float(item))
                except Exception:
                    continue
        nums = [n for n in nums if n > 0]
        if not nums:
            return ""
        if len(nums) == 1:
            s = f"{nums[0]:.1f}".rstrip("0").rstrip(".")
            return f"{s} mm"
        low, high = min(nums), max(nums)
        if abs(low - high) < 0.01:
            s = f"{low:.1f}".rstrip("0").rstrip(".")
            return f"{s} mm"
        s_low = f"{low:.1f}".rstrip("0").rstrip(".")
        s_high = f"{high:.1f}".rstrip("0").rstrip(".")
        return f"{s_low}-{s_high} mm"
    return _format_exif_value(val) if val is not None else ""


def _dms_to_deg(val) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float, Fraction)):
        try:
            return float(val)
        except Exception:
            return None
    if hasattr(val, "numerator") and hasattr(val, "denominator"):
        try:
            return float(Fraction(val.numerator, val.denominator))
        except Exception:
            return None
    if isinstance(val, (list, tuple)):
        parts = list(val)
        if len(parts) == 3:
            fracs = [_format_fraction(p) for p in parts]
            if any(f is None for f in fracs):
                return None
            deg = fracs[0] + fracs[1] / 60 + fracs[2] / 3600
            try:
                return float(deg)
            except Exception:
                return None
        if len(parts) == 2:
            fracs = [_format_fraction(p) for p in parts]
            if any(f is None for f in fracs):
                return None
            try:
                return float(fracs[0] + fracs[1] / 60)
            except Exception:
                return None
    try:
        return float(val)
    except Exception:
        return None


def _normalize_gps_dict(gps_info) -> dict:
    if not isinstance(gps_info, dict):
        return {}
    norm = {}
    for k, v in gps_info.items():
        name = ExifTags.GPSTAGS.get(k, k) if isinstance(k, int) else str(k)
        norm[name] = v
    return norm


def _gps_to_decimal(gps_info) -> tuple[float | None, float | None]:
    try:
        norm = _normalize_gps_dict(gps_info)
        lat_raw = norm.get("GPSLatitude") or norm.get("Latitude")
        lon_raw = norm.get("GPSLongitude") or norm.get("Longitude")
        lat_ref = norm.get("GPSLatitudeRef") or norm.get("LatitudeRef")
        lon_ref = norm.get("GPSLongitudeRef") or norm.get("LongitudeRef")
        if lat_raw is None or lon_raw is None:
            return None, None
        lat = _dms_to_deg(lat_raw)
        lon = _dms_to_deg(lon_raw)
        if lat is None or lon is None:
            return None, None
        if str(lat_ref or "").upper().startswith("S"):
            lat = -abs(lat)
        if str(lon_ref or "").upper().startswith("W"):
            lon = -abs(lon)
        return lat, lon
    except Exception:
        return None, None


def _format_location(lat: float | None, lon: float | None) -> str:
    if lat is None or lon is None:
        return ""
    try:
        return f"{lat:.6f}, {lon:.6f}"
    except Exception:
        return ""


def _parse_iso6709(text: str) -> tuple[float | None, float | None]:
    try:
        tokens = re.findall(r"[+-]\d+(?:\.\d+)?", text)
        if len(tokens) >= 2:
            return float(tokens[0]), float(tokens[1])
    except Exception:
        return None, None
    return None, None


def _parse_xmp_location(xmp_bytes: bytes | str | None) -> tuple[float | None, float | None]:
    if not xmp_bytes:
        return None, None
    try:
        txt = xmp_bytes.decode("utf-8", errors="ignore") if isinstance(xmp_bytes, (bytes, bytearray)) else str(xmp_bytes)
    except Exception:
        txt = str(xmp_bytes)
    lat = lon = None
    try:
        lat_match = re.search(r"GPSLatitude[^0-9+.-]*([+-]?\d+(?:\.\d+)?)", txt)
        lon_match = re.search(r"GPSLongitude[^0-9+.-]*([+-]?\d+(?:\.\d+)?)", txt)
        if lat_match and lon_match:
            lat = float(lat_match.group(1))
            lon = float(lon_match.group(1))
    except Exception:
        pass
    if (lat is None or lon is None) and "ISO6709" in txt:
        iso_match = re.search(r"ISO6709[^<>\n]*([+-]\d+(?:\.\d+)?[+-]\d+(?:\.\d+)?(?:[+-]\d+(?:\.\d+)?/?)?)", txt)
        if iso_match:
            lat_iso, lon_iso = _parse_iso6709(iso_match.group(1))
            lat = lat if lat is not None else lat_iso
            lon = lon if lon is not None else lon_iso
    return lat, lon


def _parse_taken_at(raw: str | None):
    if not raw:
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _format_taken_at_str(raw: str | None) -> str:
    dt = _parse_taken_at(raw)
    if dt:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return raw or ""


def _collect_exif_sources(pil_img: PILImage.Image, exif_bytes: bytes | None) -> tuple[dict, dict]:
    merged: dict = {}
    raw_map: dict = {}
    sources: list[dict] = []

    try:
        raw = pil_img.getexif()
        if raw:
            sources.append(dict(raw.items()))
            if hasattr(raw, "get_ifd"):
                for ifd_name in ("Exif", "GPS", "Interop"):
                    try:
                        ifd_id = getattr(ExifTags.IFD, ifd_name, None)
                        if ifd_id is not None:
                            sources.append(dict(raw.get_ifd(ifd_id).items()))
                    except Exception:
                        continue
    except Exception:
        pass

    if exif_bytes:
        try:
            exif_obj = PILImage.Exif()
            exif_obj.load(exif_bytes)
            sources.append(dict(exif_obj.items()))
        except Exception:
            pass

    for src in sources:
        for k, v in (src.items() if src else []):
            name = _tag_name(k)
            if name not in merged:
                merged[name] = v
            raw_map[name] = _format_exif_value(v)
            raw_map[str(k)] = _format_exif_value(v)

    gps_block = merged.get("GPSInfo") or merged.get("GPS")
    if isinstance(gps_block, dict):
        for gk, gv in gps_block.items():
            gname = ExifTags.GPSTAGS.get(gk, f"{gk}")
            raw_map[f"GPS_{gname}"] = _format_exif_value(gv)

    return merged, raw_map


def _load_heif_with_exif(raw_bytes: bytes) -> tuple[PILImage.Image | None, bytes | None, bytes | None]:
    """读取 HEIF，返回 PIL Image、EXIF 二进制、XMP 二进制"""
    try:
        heif = read_heif(raw_bytes)
    except Exception:
        return None, None, None
    exif_bytes = None
    xmp_bytes = None
    for meta in heif.metadata or []:
        if meta.get("type") == "Exif":
            exif_bytes = meta.get("data")
        elif meta.get("type") == "XMP":
            xmp_bytes = meta.get("data")
    try:
        img = PILImage.frombytes(heif.mode or "RGB", heif.size, heif.data, "raw")
    except Exception:
        img = None
    return img, exif_bytes, xmp_bytes


def _extract_exif(pil_img: PILImage.Image, exif_bytes: bytes | None = None, xmp_bytes: bytes | None = None) -> dict:
    exif: dict = {}
    width, height = pil_img.size
    raw_map: dict = {}
    lat = lon = None
    try:
        tags, raw_map = _collect_exif_sources(pil_img, exif_bytes)

        exif["taken_at"] = tags.get("DateTimeOriginal") or tags.get("DateTimeDigitized") or tags.get("DateTime")
        exif["camera"] = tags.get("Model") or tags.get("Make")
        lens_spec = tags.get("LensSpecification")
        exif["lens"] = tags.get("LensModel") or tags.get("LensMake") or _format_lens_spec(lens_spec)
        iso_val = (
            tags.get("ISOSpeedRatings")
            or tags.get("PhotographicSensitivity")
            or tags.get("ISO")
            or tags.get("StandardOutputSensitivity")
        )
        exif["iso"] = _format_exif_value(iso_val) if iso_val is not None else ""
        exposure_val = tags.get("ExposureTime") or tags.get("ShutterSpeedValue") or tags.get("ExposureBiasValue")
        exif["exposure"] = _friendly_exposure(exposure_val)
        aperture_val = tags.get("FNumber") or tags.get("ApertureValue")
        exif["aperture"] = _friendly_aperture(aperture_val)

        focal_val = tags.get("FocalLength") or tags.get("FocalLengthIn35mmFilm")
        if not focal_val and isinstance(lens_spec, (list, tuple)) and lens_spec:
            focal_val = lens_spec[0]
        exif["focal"] = _friendly_focal(focal_val)

        gps_info = tags.get("GPSInfo") or tags.get("GPS")
        exif["gps"] = gps_info
        if gps_info:
            lat, lon = _gps_to_decimal(gps_info)

        if (lat is None or lon is None) and xmp_bytes:
            lat_xmp, lon_xmp = _parse_xmp_location(xmp_bytes)
            if lat_xmp is not None and lon_xmp is not None:
                lat, lon = lat_xmp, lon_xmp
                raw_map["XMP_Latitude"] = f"{lat:.6f}"
                raw_map["XMP_Longitude"] = f"{lon:.6f}"

        exif["latitude"] = lat
        exif["longitude"] = lon

        exif["resolution"] = f"{width}x{height}" if width and height else ""
        exif["software"] = tags.get("Software") or ""
        exif["make"] = tags.get("Make") or ""
        exif["model"] = tags.get("Model") or ""
        exif["orientation"] = tags.get("Orientation") or ""
        exif["datetime_digitized"] = tags.get("DateTimeDigitized") or tags.get("DateTime") or ""

        if lat is not None and lon is not None:
            raw_map["Latitude"] = f"{lat:.6f}"
            raw_map["Longitude"] = f"{lon:.6f}"
            raw_map["Location"] = _format_location(lat, lon)

        if isinstance(gps_info, dict):
            for k, v in gps_info.items():
                raw_map[f"GPS_{k}"] = _format_exif_value(v)

        raw_map.update(
            {
                "Resolution": exif["resolution"],
                "TakenAt": exif["taken_at"] or "",
                "Camera": exif["camera"] or "",
                "Lens": exif["lens"] or _format_lens_spec(lens_spec),
                "ISO": exif["iso"] or _format_exif_value(iso_val),
                "ExposureTime": exif["exposure"] or _format_exif_value(exposure_val),
                "Aperture": exif["aperture"] or _format_exif_value(aperture_val),
                "FocalLength": exif["focal"] or _format_exif_value(focal_val),
                "Software": exif["software"] or "",
                "Make": exif["make"] or "",
                "Model": exif["model"] or "",
            }
        )
    except Exception:
        current_app.logger.exception("extract exif failed")

    exif["raw"] = raw_map
    return exif


def _save_thumb(src_path: str, dest_path: str, size=(400, 400)) -> None:
    with PILImage.open(src_path) as img:
        img = ImageOps.exif_transpose(img)
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


def _image_file_exists(img: Image) -> bool:
    rel = _normalize_rel_path(img.filename)
    if not rel:
        return False
    disk_path = os.path.join(current_app.config["UPLOAD_DIR"], rel)
    return os.path.exists(disk_path)


def _filter_existing(images: list[Image]) -> list[Image]:
    """过滤磁盘缺失的图片；若缺失且未标记删除，则软删除以避免重复 404。"""
    kept: list[Image] = []
    missing = 0
    dirty = False
    for img in images:
        if _image_file_exists(img):
            kept.append(img)
            continue
        missing += 1
        if img.deleted_at is None:
            img.deleted_at = datetime.utcnow()
            dirty = True
    if dirty:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
    if missing and kept:
        current_app.logger.info("filtered missing files: %s (kept %s)", missing, len(kept))
    return kept


def _build_display_exif(img: Image, exif_raw: dict) -> list[dict]:
    def pick(*keys):
        for k in keys:
            val = exif_raw.get(k)
            if val:
                return val
        return ""

    taken = img.taken_at.strftime("%Y-%m-%d %H:%M:%S") if img.taken_at else _format_taken_at_str(
        pick("TakenAt", "DateTimeOriginal", "DateTime")
    )
    resolution = f"{img.width} x {img.height}" if img.width and img.height else pick("Resolution", "ImageWidth")
    location_str = _format_location(img.latitude, img.longitude) or pick("Location")

    items = [
        {"key": "camera", "label": "相机", "value": img.camera or pick("Camera", "Model", "Make")},
        {"key": "lens", "label": "镜头", "value": img.lens or pick("Lens", "LensModel", "LensSpecification")},
        {"key": "aperture", "label": "光圈", "value": img.aperture or pick("Aperture", "FNumber", "ApertureValue")},
        {"key": "exposure", "label": "快门", "value": img.exposure or pick("ExposureTime", "ShutterSpeedValue")},
        {"key": "iso", "label": "ISO", "value": img.iso or pick("ISO", "PhotographicSensitivity", "ISOSpeedRatings")},
        {"key": "focal", "label": "焦距", "value": img.focal or pick("FocalLength", "FocalLengthIn35mmFilm")},
        {"key": "resolution", "label": "分辨率", "value": resolution},
        {"key": "taken_at", "label": "拍摄时间", "value": taken},
        {"key": "location", "label": "拍摄地点", "value": location_str},
        {"key": "software", "label": "软件", "value": pick("Software")},
    ]
    for item in items:
        item["value"] = item["value"] or "--"
    return items


def _exif_tag_list(img: Image) -> list[str]:
    tags: list[str] = []
    base = [
        img.camera,
        img.lens,
        img.iso,
        img.aperture,
        img.exposure,
        img.focal,
    ]
    if img.width and img.height:
        base.append(f"{img.width}x{img.height}")
    if img.taken_at:
        base.append(img.taken_at.strftime("%Y-%m-%d %H:%M:%S"))
    if img.latitude is not None and img.longitude is not None:
        base.append(_format_location(img.latitude, img.longitude))

    seen = set()
    for val in base:
        if not val:
            continue
        s = str(val).strip()
        if s and s not in seen:
            tags.append(s)
            seen.add(s)
    return tags


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
    if img.exif_json:
        try:
            data["exif_raw"] = json.loads(img.exif_json)
        except Exception:
            data["exif_raw"] = {}
    else:
        data["exif_raw"] = {}
    data["exif_display"] = _build_display_exif(img, data["exif_raw"])
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
    img = ImageOps.exif_transpose(img)
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
    description = (request.form.get("description") or "").strip()

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

            exif = {}
            width = height = 0
            xmp_bytes = None

            if is_heic:
                raw_bytes = f.stream.read()
                exif_bytes = None
                pil_img = None
                try:
                    heif_img, heif_exif, heif_xmp = _load_heif_with_exif(raw_bytes)
                    exif_bytes = heif_exif or exif_bytes
                    xmp_bytes = heif_xmp or xmp_bytes
                    pil_img = heif_img
                except Exception:
                    pil_img = None
                try:
                    with PILImage.open(io.BytesIO(raw_bytes)) as probe:
                        pil_img = pil_img or probe.copy()
                        exif_bytes = exif_bytes or probe.info.get("exif")
                    xmp_bytes = xmp_bytes or None
                except Exception:
                    pil_img = pil_img or None
                if pil_img is None:
                    pil_img = PILImage.open(io.BytesIO(raw_bytes))
                pil_img = ImageOps.exif_transpose(pil_img)
                width, height = pil_img.size
                exif = _extract_exif(pil_img, exif_bytes, xmp_bytes)
                save_kwargs = {"format": "JPEG", "quality": 95}
                if exif_bytes:
                    save_kwargs["exif"] = exif_bytes
                pil_img.convert("RGB").save(disk_path, **save_kwargs)
            else:
                f.save(disk_path)
                with PILImage.open(disk_path) as img:
                    img = ImageOps.exif_transpose(img)
                    width, height = img.size
                    exif = _extract_exif(img)
                    fmt = img.format or "JPEG"
                    save_kwargs = {"format": fmt}
                    if img.info.get("exif"):
                        save_kwargs["exif"] = img.info["exif"]
                    img.save(disk_path, **save_kwargs)

            lat = exif.get("latitude")
            lon = exif.get("longitude")
            if (lat is None or lon is None) and exif.get("gps"):
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
                description=description or None,
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
                exif_json=json.dumps(exif.get("raw") or {}),
                thumb_path=thumb_rel,
                visibility="public" if visibility == "public" else "private",
                is_featured=False,
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
    featured_flag = request.args.get("featured")

    query = _query_user_images(user_id, include_deleted=False)
    folder = request.args.get("folder")
    if folder:
        query = query.filter(Image.folder == folder)
    if featured_flag is not None:
        want_featured = str(featured_flag).lower() in ("1", "true", "yes", "on")
        query = query.filter(Image.is_featured.is_(want_featured))

    order_by = Image.created_at.asc() if sort == "oldest" else Image.created_at.desc()
    pagination = query.order_by(order_by).paginate(page=page, per_page=page_size, error_out=False)
    items = _filter_existing(list(pagination.items))
    missing_count = len(pagination.items) - len(items)
    total_adjusted = max(0, (pagination.total or 0) - missing_count)

    return jsonify(
        {
            "items": [_serialize_image(img) for img in items],
            "total": total_adjusted,
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
    featured_flag = request.args.get("featured")

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

    if featured_flag is not None:
        want_featured = str(featured_flag).lower() in ("1", "true", "yes", "on")
        query = query.filter(Image.is_featured.is_(want_featured))

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
    items = _filter_existing(list(pagination.items))
    missing_count = len(pagination.items) - len(items)
    total_adjusted = max(0, (pagination.total or 0) - missing_count)

    return jsonify(
        {
            "items": [_serialize_image(img) for img in items],
            "total": total_adjusted,
            "page": page,
            "page_size": page_size,
        }
    )


@images_bp.get("/stats")
def image_stats():
    user_id = _current_user_id()
    today = date.today()
    today_start = datetime.combine(today, time.min)
    today_end = datetime.combine(today, time.max)

    today_deleted = (
        _query_user_images(user_id, include_deleted=True)
        .filter(Image.deleted_at.isnot(None))
        .filter(db.func.date(Image.deleted_at) == today)
        .count()
    )
    today_uploaded = (
        _query_user_images(user_id, include_deleted=True)
        .filter(Image.created_at >= today_start, Image.created_at <= today_end)
        .count()
    )
    total_active = _query_user_images(user_id, include_deleted=False).count()
    recycle_count = _query_user_images(user_id, include_deleted=True).filter(Image.deleted_at.isnot(None)).count()
    return jsonify(
        {
            "today_deleted": today_deleted,
            "today_uploaded": today_uploaded,
            "total_active": total_active,
            "recycle_count": recycle_count,
        }
    )


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


@images_bp.post("/<int:image_id>/tags")
def update_tags(image_id: int):
    user_id = _current_user_id()
    img = _get_user_image(image_id, user_id, include_deleted=False)

    data = request.get_json() or {}
    raw_tags = data.get("tags")
    if raw_tags is None:
        return jsonify({"message": "请提供 tags 数组"}), 400
    if not isinstance(raw_tags, list):
        return jsonify({"message": "tags 字段必须是数组"}), 400

    names: list[str] = []
    color_map: dict[str, str] = {}
    for item in raw_tags:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            if item.get("color"):
                color_map[name] = item.get("color")
        else:
            continue
        if name:
            names.append(name)

    uniq_names: list[str] = []
    seen = set()
    for n in names:
        if n not in seen:
            uniq_names.append(n)
            seen.add(n)

    try:
        img.tags = _get_or_create_tags(uniq_names, user_id=user_id, color_map=color_map)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("update tags failed")
        return jsonify({"message": "更新标签失败"}), 500

    tag_objs = [
        {"id": t.id, "name": t.name, "color": _sanitize_color(t.color) or _color_from_name(t.name)}
        for t in img.tags
    ]
    return jsonify(
        {
            "message": "ok",
            "tags": [t.name for t in img.tags],
            "tag_objects": tag_objs,
            "item": _serialize_image(img),
        }
    )


@images_bp.patch("/<int:image_id>/meta")
def update_meta(image_id: int):
    user_id = _current_user_id()
    img = _get_user_image(image_id, user_id, include_deleted=False)
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()
    visibility = (data.get("visibility") or img.visibility).strip()
    folder = (data.get("folder") or img.folder or "默认图库").strip() or "默认图库"
    is_featured = data.get("is_featured")

    if name:
        img.name = name
    img.description = description or None
    img.visibility = "public" if visibility == "public" else "private"
    img.folder = folder
    if is_featured is not None:
        img.is_featured = bool(is_featured)

    db.session.commit()
    return jsonify({"message": "ok", "item": _serialize_image(img)})


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
