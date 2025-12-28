import io
import os
import re
import shutil
import uuid
import json
import base64
from datetime import datetime, date, time, timedelta
from fractions import Fraction
from typing import List

import requests  
from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from pillow_heif import read_heif, register_heif_opener
from PIL import ExifTags, Image as PILImage, ImageEnhance, ImageOps
from sqlalchemy import func, or_, and_, exists, cast, String
from openai import OpenAI

from .extensions import db
from .models import Album, Image, ImageVersion, Tag, image_tags, album_images, ImageAIAnalysis

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


def _parse_tag_payload(raw_tags) -> tuple[list[str], dict[str, str]]:
    names: list[str] = []
    color_map: dict[str, str] = {}
    if isinstance(raw_tags, list):
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
    return uniq_names, color_map


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
    """过滤磁盘缺失的图片；若缺失且未标记删除，则软删除以避免重复 404"""
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


def _serialize_image(img: Image, include_albums: bool = False) -> dict:
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

    ai = getattr(img, "ai_analysis", None)
    data["ai_tags"] = ai.labels if ai else []
    data["ai_description"] = ai.caption if ai else ""
    data["ai_status"] = ai.status if ai else None
    data["ai_model"] = ai.model if ai else None
    data["ai_updated_at"] = ai.updated_at.isoformat() if ai else None
    if include_albums:
        try:
            albums = img.albums.order_by(Album.created_at.desc()).all()
        except Exception:
            albums = img.albums.all()
        data["album_ids"] = [a.id for a in albums]
        data["album_objects"] = [{"id": a.id, "title": a.title, "visibility": a.visibility} for a in albums]
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


# === AI (Qwen / DashScope) ===
def _qwen_cfg():
    """读取通义千问 / 百炼（DashScope）的配置。"""
    return {
        "api_key": current_app.config.get("QWEN_API_KEY", ""),
        "api_base": (current_app.config.get("QWEN_API_BASE") or "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip(
            "/"
        ),
        "vision_model": current_app.config.get("QWEN_VISION_MODEL", "qwen-vl-max"),
        "chat_model": current_app.config.get("QWEN_CHAT_MODEL", "qwen-turbo"),
        "timeout": int(current_app.config.get("AI_TIMEOUT", 60)),
        "max_tags": int(current_app.config.get("AI_MAX_TAGS", 6)),
    }


def _qwen_request_chat(model: str, messages: list[dict], extra_body: dict | None = None) -> dict:
    """调用 DashScope OpenAI 兼容接口的 chat.completions，返回完整 JSON。"""
    cfg = _qwen_cfg()
    if not cfg["api_key"]:
        raise RuntimeError("缺少 QWEN_API_KEY")

    url = cfg["api_base"].rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if extra_body:
        payload.update(extra_body)

    resp = requests.post(url, json=payload, headers=headers, timeout=cfg["timeout"])
    resp.raise_for_status()
    return resp.json()


def _qwen_vision(prompt: str, image_b64: str) -> str:
    """使用 Qwen-VL 模型进行图像理解，返回模型原始文本输出。"""
    cfg = _qwen_cfg()
    data = _qwen_request_chat(
        model=cfg["vision_model"],
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                ],
            }
        ],
        extra_body={"temperature": 0.2},
    )
    choice = (data.get("choices") or [{}])[0].get("message", {})
    content = choice.get("content", "")

    # OpenAI 兼容接口下，content 可能是字符串或富文本数组
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                txt = part.get("text")
                if txt:
                    parts.append(txt)
        return "".join(parts)
    return str(content or "")


def _qwen_chat(messages: list[dict]) -> str:
    """使用通义千问文本模型进行对话，返回 assistant 文本内容。"""
    cfg = _qwen_cfg()
    data = _qwen_request_chat(
        model=cfg["chat_model"],
        messages=messages,
        extra_body={"temperature": 0.3},
    )
    choice = (data.get("choices") or [{}])[0].get("message", {})
    content = choice.get("content", "")
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                txt = part.get("text")
                if txt:
                    parts.append(txt)
        return "".join(parts)
    return str(content or "")


def _parse_ai_json(text: str) -> tuple[list[str], str]:
    """容错解析大模型输出，提取 tags 与 caption。"""
    try_blocks: list[str] = []
    if "```" in text:
        for part in text.split("```"):
            if "{" in part and "}" in part:
                try_blocks.append(part)
    try_blocks.append(text)

    for block in try_blocks:
        try:
            obj = json.loads(block[block.index("{") : block.rindex("}") + 1])
            tags = obj.get("tags") or obj.get("labels") or obj.get("keywords") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.replace("，", ",").split(",") if t.strip()]
            caption = obj.get("caption") or obj.get("summary") or obj.get("reply") or ""
            return tags, caption
        except Exception:
            continue

    # 兜底：用换行或逗号切分
    lines = [x.strip() for x in re.split(r"[\n,，]", text) if x.strip()]
    caption = lines[0] if lines else ""
    tags = lines[1:6]
    return tags, caption


def _run_ai_analysis(img: Image) -> tuple[list[str], str]:
    """真正跑图片分析（生成标签 + 描述）的函数，内部已经改用 Qwen-VL。"""
    cfg = _qwen_cfg()
    rel = _normalize_rel_path(img.filename)
    disk_path = os.path.join(current_app.config["UPLOAD_DIR"], rel) if rel else None
    if not disk_path or not os.path.exists(disk_path):
        raise FileNotFoundError("文件不存在")

    with open(disk_path, "rb") as f:
        b64_img = base64.b64encode(f.read()).decode()

    prompt = (
        "你是专业图片标注助手。请只输出 JSON："
        '{"tags":["tag1","tag2",...],"caption":"用一句中文描述图片"}。'
        f"标签请控制在 {cfg['max_tags']} 个以内，重点包括风景/人物/动物/场景等。"
    )
    raw = _qwen_vision(prompt, b64_img)
    tags, caption = _parse_ai_json(raw)
    return tags[: cfg["max_tags"]], caption.strip()


def _upsert_ai_analysis(img: Image, tags: list[str], caption: str) -> ImageAIAnalysis:
    """把 AI 生成的结果写回 image_ai_analysis 表。"""
    ai = ImageAIAnalysis.query.filter_by(image_id=img.id).first()
    if not ai:
        ai = ImageAIAnalysis(image_id=img.id)
        db.session.add(ai)
    cfg = _qwen_cfg()
    ai.model = cfg.get("vision_model") or "qwen-vl-max"
    ai.labels = tags
    ai.caption = caption
    ai.status = "done"
    ai.updated_at = datetime.utcnow()
    return ai


def _ai_parse_date_range(text: str) -> tuple[datetime | None, datetime | None, str]:
    """从文本解析日期区间，返回 (开始, 结束, 字段类型: created|taken)"""
    text = _normalize_query_text(text)
    lowered = text.lower()
    field = "created"
    # 出现“拍摄/摄于/taken/capture”等，优先认为是拍摄时间
    if any(k in text for k in ["拍摄", "摄于"]) or "taken" in lowered or "capture" in lowered:
        field = "taken"
    # 明确提到“上传/upload”时覆盖为上传时间
    if "上传" in text or "upload" in lowered:
        field = "created"

    def _to_dt(token: str) -> datetime | None:
        # 支持 2025-12-4 / 2025/12/4 / 2025年12月4日 等
        cleaned = re.sub(r"[年月/.]", "-", token).replace("日", "").replace("号", "")
        parts = [p for p in cleaned.split("-") if p]
        if len(parts) < 3:
            return None
        try:
            y, mm, dd = int(parts[0]), int(parts[1]), int(parts[2])
            return datetime(y, mm, dd, 0, 0, 0)
        except Exception:
            return None

    
    tokens = re.findall(r"\d{4}[-./年]\d{1,2}[-./月]\d{1,2}", text)
    dates = [_to_dt(t) for t in tokens]
    dates = [d for d in dates if d]

    if len(dates) >= 2:
        dates = sorted(dates[:2])
        start = dates[0].replace(hour=0, minute=0, second=0, microsecond=0)
        end = dates[1].replace(hour=23, minute=59, second=59, microsecond=999999)
        return start, end, field
    if len(dates) == 1:
        d = dates[0]
        start = d.replace(hour=0, minute=0, second=0, microsecond=0)
        end = d.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start, end, field
    return None, None, field



def _ai_parse_size(text: str) -> tuple[int | None, int | None]:
    """解析大小范围，返回字节数区间"""
    if not text:
        return None, None
    # 规避把日期里的 “2025-12-4” 误识别成 “2025-12 MB” 这种大小范围
    text = _normalize_query_text(text)
    text_wo_dates = re.sub(r"\d{4}[-./年]\d{1,2}[-./月]\d{1,2}", " ", text)

    unit_map = {
        "kb": 1024,
        "k": 1024,
        "mb": 1024 * 1024,
        "m": 1024 * 1024,
        "gb": 1024 * 1024 * 1024,
        "g": 1024 * 1024 * 1024,
        "兆": 1024 * 1024,
    }

    def _to_bytes(num: str, unit: str | None) -> int | None:
        if not unit:
            return None
        factor = unit_map.get((unit or "").lower())
        if not factor:
            return None
        return int(float(num) * factor)

    range_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(k|kb|m|mb|g|gb|兆)?\s*(?:-|~|到|至|—|–)\s*(\d+(?:\.\d+)?)\s*(k|kb|m|mb|g|gb|兆)?",
        text_wo_dates,
        flags=re.IGNORECASE,
    )
    if range_match:
        # 至少一侧带单位，否则大概率是日期/编号区间
        unit_left = range_match.group(2)
        unit_right = range_match.group(4)
        if not (unit_left or unit_right):
            return None, None
        min_b = _to_bytes(range_match.group(1), unit_left or unit_right)
        max_b = _to_bytes(range_match.group(3), unit_right or unit_left)
        if min_b is None or max_b is None:
            return None, None
        if min_b > max_b:
            min_b, max_b = max_b, min_b
        return min_b, max_b

    # 单值也要求显式单位，避免把年份/编号当成大小（例如 2025）
    m = re.search(r"(\d+(?:\.\d+)?)\s*(k|kb|m|mb|g|gb|兆)\s*b?", text_wo_dates, flags=re.IGNORECASE)
    if not m:
        return None, None
    val_bytes = _to_bytes(m.group(1), m.group(2))
    if val_bytes is None:
        return None, None
    if any(k in text for k in ["以上", "大于", ">", "不少于", "至少", "greater"]):
        return val_bytes, None
    if any(k in text for k in ["以下", "小于", "<", "不超过", "最多", "不大于", "at most"]):
        return None, val_bytes
    return val_bytes, val_bytes


def _ai_parse_resolution(text: str) -> dict:
    """解析分辨率阈值（像素数、宽/高下限）"""
    res: dict = {"pixels": None, "width": None, "height": None}
    m = re.search(r"(\d{3,5})\s*[xX×*]\s*(\d{3,5})", text, flags=re.IGNORECASE)
    if m:
        res["width"] = int(m.group(1))
        res["height"] = int(m.group(2))
        res["pixels"] = res["width"] * res["height"]
        return res
    m_px = re.search(r"(\d{3,8})\s*(?:像素|px)", text, flags=re.IGNORECASE)
    if m_px:
        res["pixels"] = int(m_px.group(1))
        return res
    low = text.lower()
    if "4k" in low:
        res["width"], res["height"], res["pixels"] = 3840, 2160, 3840 * 2160
        return res
    if "2k" in low:
        res["width"], res["height"], res["pixels"] = 2560, 1440, 2560 * 1440
        return res
    m_p = re.search(r"(\d{3,4})p", low)
    if m_p:
        h = int(m_p.group(1))
        w = int(h * 16 / 9)
        res["height"] = h
        res["width"] = w
        res["pixels"] = w * h
    return res


def _ai_parse_album(text: str) -> str | None:
    """从文本中提取相册/专辑/文件夹名称"""

    def _clean(name: str) -> str:
        cleaned = name
        cleaned = re.sub(r"[“”\"'‘’]", "", cleaned)
        cleaned = re.sub(r"(相册|专辑|文件夹)$", "", cleaned)
        cleaned = re.sub(r"[的之]+.*$", "", cleaned)
        return cleaned.strip(" ，。,:： ")

    # “名为/叫做 XX 的相册”
    m_named = re.search(
        r"(?:名为|叫做|叫|名称为|标题为)\s*[“\"'‘]?([\u4e00-\u9fa5A-Za-z0-9_\- ]{1,40})[”\"'’]?\s*的?(?:相册|专辑|文件夹)",
        text,
    )
    if m_named:
        return _clean(m_named.group(1))

    # “相册名称为/相册名为/相册叫/相册标题为 XXX”
    m0 = re.search(
        r"(?:相册名称为|相册名为|相册叫|相册标题为|相册名|相册叫做|专辑为|专辑叫做|文件夹为)[“\"'‘]?([\u4e00-\u9fa5A-Za-z0-9_\- ]{1,40})[”\"'’]?",
        text,
    )
    if m0:
        return _clean(m0.group(1))

    # 引号里的内容（例如：在“风景”相册中）
    for pat in [r"“([^”]+)”", r"\"([^\"]+)\"", r"'([^']+)'", r"‘([^’]+)’"]:
        m = re.search(pat, text)
        if m:
            return _clean(m.group(1) or "")

    # “在 XX 相册 / XX 专辑 / XX 文件夹” 或 “XX 相册”
    m2 = re.search(r"在?([\u4e00-\u9fa5A-Za-z0-9_\-]{1,30})[的之]?(?:相册|专辑|文件夹)", text)
    if m2:
        return _clean(m2.group(1))

    # 英文 album: xxx
    m4 = re.search(r"album[:：\s]*([\w\u4e00-\u9fa5\- ]{2,40})", text, flags=re.IGNORECASE)
    if m4:
        return _clean(m4.group(1))

    return None



def _ai_infer_combine_logic(text: str) -> str:
    """推断组合方式，默认 AND，出现“或/或者/还是”时放宽为 OR"""
    if not text:
        return "and"
    
    or_words = r"(或者是|或者|或是|或则|还是|或)"
    and_words = r"(并且|且|同时|以及|又)"
    tag_words = r"(标签|标记|包含|关键词|关键字|描述|说明|caption)"
    struct_words = r"(上传|拍摄|相机|镜头|机型|相册|专辑|文件夹|分辨率|像素|大小|容量)"
    if re.search(or_words, text) and (re.search(tag_words, text) or re.search(struct_words, text)):
        return "or"
    if re.search(and_words, text) and (re.search(tag_words, text) or re.search(struct_words, text)):
        return "and"
    return "and"

def _ai_detect_logic_mode(text: str) -> str:
    """根据自然语言里的连接词，推断结构化条件和关键词之间用 AND 还是 OR."""
    if not text:
        return "auto"
    t = text
    # 更偏向“二选一”的用词
    
    if re.search(r"(或者是|或者|或是|或则|还是|或)", t):
        return "or"
    # 更偏向“同时满足”的用词
    if re.search(r"(并且|而且|同时|以及|又|并且还|并且同时)", t):
        return "and"
    return "auto"


def _normalize_query_text(text: str) -> str:
    return (
        (text or "")
        .replace("－", "-")
        .replace("–", "-")
        .replace("—", "-")
        .replace("‑", "-")
        .replace("−", "-")
    )


def _is_noise_keyword(token: str) -> bool:
    if not token:
        return True
    low = str(token).lower().strip()
    if low in {"and", "or"}:
        return True
    # 结构化字段名（避免出现 "album: 风景" 时把 "album" 当普通关键词导致结果被误缩小）
    if low in {"album"}:
        return True
    # 区间/范围等常见后缀词（尤其是文件大小“400KB-1MB之间”会遗留“之间”）
    if low in {"之间", "区间", "范围", "以内"}:
        return True
    if low in {"并且", "而且", "同时", "以及", "且", "和", "或者", "或是", "或则", "还是", "或"}:
        return True
    # 如果 token 自身包含结构化触发词，基本不应作为普通关键词参与过滤
    if any(
        k in low
        for k in [
            "相册",
            "专辑",
            "文件夹",
            "上传",
            "拍摄",
            "摄于",
            "相机",
            "镜头",
            "机型",
            "分辨率",
            "像素",
            "大小",
            "容量",
            "文件大小",
            "小于",
            "大于",
            "以上",
            "以下",
            "不超过",
            "不少于",
            "至少",
            "最多",
            "名为",
            "叫做",
            "名称为",
            "标题为",
            "并且",
            "而且",
            "同时",
            "以及",
            "或者",
        ]
    ):
        return True
    # 常见口头/指令词、结构化触发词：不应作为普通关键词参与过滤
    noise_patterns = [
        r"^(所有|全部|全部的|所有的|都|全部都|所有都)$",
        r"^(并且|而且|同时|以及|且|和|或者|或是|或则|还是|或)$",
        r"^(上传|上传于|上传的|拍摄|拍摄于|拍的|摄于)$",
        r"^(相册|专辑|文件夹|相机|镜头|机型)$",
        r"^(分辨率|像素|大小|容量|文件大小)$",
        r"^(小于|大于|以上|以下|不超过|不少于|至少|最多)$",
        r"^(之间|区间|范围|以内)$",
        r"^(图片|照片|相片)$",
        r"^(帮我|为我|我要|我想|请|麻烦|帮忙|查找|搜索|检索|找|找出|列出|显示)$",
        r"^(相关|相应)$",
        r"^上传.*(图片|照片|相片)$",
    ]
    for pat in noise_patterns:
        if re.search(pat, low, flags=re.IGNORECASE):
            return True
    return False


def _ai_parse_camera_keyword(text: str) -> str | None:
    """从自然语言中提取相机/镜头/机型关键字（用于结构化过滤），避免被当成普通关键词导致过度收缩。"""
    if not text:
        return None

    # “相机 XXX / 镜头 XXX”
    if "相机" in text or "镜头" in text or "机型" in text:
        m = re.search(r"(?:相机|机型)[^\w\u4e00-\u9fa5]*([\w\u4e00-\u9fa5\- ]{2,40})", text)
        if not m:
            m = re.search(r"镜头[^\w\u4e00-\u9fa5]*([\w\u4e00-\u9fa5\- ]{2,40})", text)
        if m:
            return (m.group(1) or "").strip() or None

    # “用 XXX 拍的”
    m = re.search(r"(?:用|使用)([\w\u4e00-\u9fa5\- ]{2,40}?)(?:拍摄|拍的|拍照|拍)", text)
    if m:
        return (m.group(1) or "").strip() or None
    return None


def _keyword_term_condition(user_id: int, term: str):
    term = (term or "").strip()
    if not term:
        return None
    like = f"%{term}%"
    return or_(
        Image.name.ilike(like),
        Image.description.ilike(like),
        Image.original_name.ilike(like),
        Image.folder.ilike(like),
        Image.tags.any(Tag.name.ilike(like)),
        Image.albums.any(and_(Album.user_id == user_id, Album.title.ilike(like))),
        Image.ai_analysis.has(ImageAIAnalysis.caption.ilike(like)),
        Image.ai_analysis.has(cast(ImageAIAnalysis.labels, String).ilike(like)),
    )


def _nl_extract_keyword_groups(text: str, exclude_terms: set[str] | None = None) -> list[list[str]]:
    """把自然语言文本拆成 (AND 组) 的 (OR 组)。

    规则：
    - 明确出现“并且/以及/和/and/&” => 组内 AND；
    - 明确出现“或/或者/or/|” => 组间 OR；
    - 未出现 AND 连接词时，默认把多个词按 OR 处理（保持更宽松的召回）。
    """
    if not text:
        return []

    exclude_terms = {t.strip() for t in (exclude_terms or set()) if (t or "").strip()}

    t = str(text)
    # 标点归一化为空格，避免粘连
    t = re.sub(r"[，。,.；;:：!！?？()（）\\[\\]{}《》<>]+", " ", t)
    # 连接词归一化
    t = re.sub(r"(或者是|或者|或是|或则|还是|\\bor\\b|\\|)", " __OR__ ", t, flags=re.IGNORECASE)
    t = re.sub(r"(并且|而且|同时|以及|和|且|\\band\\b|&)", " __AND__ ", t, flags=re.IGNORECASE)

    raw_tokens = [x.strip() for x in t.split() if x.strip()]
    if not raw_tokens:
        return []

    # 结构化/停用词（避免被当成关键词导致排空）
    stop_tokens = {
        "__OR__",
        "__AND__",
        "上传",
        "拍摄",
        "摄于",
        "相册",
        "专辑",
        "文件夹",
        "相机",
        "镜头",
        "机型",
        "分辨率",
        "像素",
        "大小",
        "容量",
        "文件大小",
        "小于",
        "大于",
        "以上",
        "以下",
        "不超过",
        "不少于",
        "至少",
        "最多",
        "照片",
        "图片",
        "帮我",
        "我要",
        "找",
        "搜索",
        "检索",
    }

    def _looks_structured_token(tok: str) -> bool:
        if not tok:
            return True
        low = tok.lower()
        if tok in stop_tokens or low in stop_tokens:
            return True
        if re.search(r"\d{4}[-./年]\d{1,2}[-./月]\d{1,2}", tok):
            return True
        if re.search(r"\d+(?:\.\d+)?\s*(?:k|kb|m|mb|g|gb|兆)\\b", tok, flags=re.IGNORECASE):
            return True
        if re.search(r"\d{3,5}\\s*[xX×*]\\s*\\d{3,5}", tok):
            return True
        if re.search(r"\d{3,8}\\s*(?:像素|px)\\b", tok, flags=re.IGNORECASE):
            return True
        if re.search(r"\\b\\d{3,4}p\\b", low):
            return True
        return False

    explicit_and_used = False
    or_groups: list[list[str]] = [[]]
    for tok in raw_tokens:
        if tok == "__OR__":
            if or_groups[-1]:
                or_groups.append([])
            continue
        if tok == "__AND__":
            explicit_and_used = True
            continue

        tok = tok.strip("“”\"'‘’")
        if tok.startswith("#"):
            tok = tok[1:]
        tok = tok.strip()
        if not tok:
            continue
        if tok in exclude_terms:
            continue
        if _looks_structured_token(tok):
            continue
        or_groups[-1].append(tok)

    # 去空组、去重
    cleaned: list[list[str]] = []
    for group in or_groups:
        uniq: list[str] = []
        for term in group:
            if term and term not in uniq:
                uniq.append(term)
        if uniq:
            cleaned.append(uniq)

    if not cleaned:
        return []

    if not explicit_and_used:
        # 默认 OR：把一个组里的多个词拆开，避免“空格导致 AND 过强”
        flat: list[str] = []
        for group in cleaned:
            for term in group:
                if term and term not in flat:
                    flat.append(term)
        return [[t] for t in flat]

    return cleaned


def _build_keyword_groups_condition(user_id: int, keyword_groups: list[list[str]]):
    """把关键词组转换成 SQLAlchemy 条件： (A AND B) OR (C AND D) ..."""
    if not keyword_groups:
        return None
    or_conds = []
    for group in keyword_groups:
        and_terms = []
        for term in group:
            cond = _keyword_term_condition(user_id, term)
            if cond is not None:
                and_terms.append(cond)
        if and_terms:
            or_conds.append(and_(*and_terms) if len(and_terms) > 1 else and_terms[0])
    if not or_conds:
        return None
    return or_(*or_conds) if len(or_conds) > 1 else or_conds[0]


def _heuristic_keywords_from_text(text: str, max_terms: int = 6) -> list[str]:
    """不依赖大模型的兜底关键词提取（用于 AI 工作台检索稳定性）。"""
    t = _normalize_query_text(text)
    if not t.strip():
        return []

    # 如果明确在描述相册/文件夹范围，先剔除相册名相关片段，避免把“名为XX的相册中”当成关键词
    if re.search(r"(相册|专辑|文件夹)", t):
        album = _ai_parse_album(t)
        if album:
            t = re.sub(
                rf"(?:在|于|从)?\s*(?:名为|叫做|叫|名称为|标题为)?\s*[“\"'‘’]?\s*{re.escape(album)}\s*[”\"'‘’]?\s*(?:的)?\s*(?:相册|专辑|文件夹)(?:中|里|里面)?",
                " ",
                t,
            )

    # 去掉日期/尺寸/分辨率等结构化片段，避免干扰
    t = re.sub(r"\d{4}[-./年]\d{1,2}[-./月]\d{1,2}", " ", t)
    # 去掉文件大小区间（例如 400KB-1MB），避免把区间当作关键词导致“结果被排空”
    t = re.sub(
        r"\d+(?:\.\d+)?\s*(?:k|kb|m|mb|g|gb|兆)\s*(?:-|~|到|至|—|–)\s*\d+(?:\.\d+)?\s*(?:k|kb|m|mb|g|gb|兆)",
        " ",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r"\d+(?:\.\d+)?\s*(?:k|kb|m|mb|g|gb|兆)\b", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\d{3,5}\s*[xX×*]\s*\d{3,5}", " ", t)
    t = re.sub(r"\d{3,4}p\b", " ", t, flags=re.IGNORECASE)

    # 常见语气/指令/助词裁剪
    for w in [
        "帮我",
        "请",
        "麻烦",
        "我要",
        "我想",
        "我需要",
        "能不能",
        "可以",
        "帮忙",
        "所有",
        "全部",
        "并且",
        "而且",
        "同时",
        "以及",
        "或者",
        "或是",
        "还是",
        "找",
        "查找",
        "搜索",
        "检索",
        "列出",
        "显示",
        "看看",
        "一下",
        "相关",
        "相应",
        "包含",
        "主题",
        "之间",
        "区间",
        "范围",
        "以内",
        "的",
        "图片",
        "照片",
        "相片",
        "一下子",
    ]:
        t = t.replace(w, " ")

    t = re.sub(r"[，。,.；;:：!！?？()（）\[\]{}《》<>]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    tokens = re.findall(r"[\u4e00-\u9fa5A-Za-z0-9_\-]{2,20}", t)
    uniq: list[str] = []
    for tok in tokens:
        tok = tok.strip("“”\"'‘’ ").strip()
        if not tok:
            continue
        if _is_noise_keyword(tok):
            continue
        # 过滤掉明显的“后缀粘连”（例如：相册中/文件夹里）
        if any(tok.endswith(suf) for suf in ["相册中", "相册里", "专辑中", "专辑里", "文件夹中", "文件夹里"]):
            continue
        if tok not in uniq:
            uniq.append(tok)
        if len(uniq) >= max_terms:
            break
    return uniq


def _split_or_segments(text: str) -> list[str]:
    """按“或/或者/还是/or/|”把文本拆成多个片段，用于实现结构化条件之间的 OR。"""
    if not text:
        return []
    t = _normalize_query_text(text)
    parts = re.split(r"(?:或者是|或者|或是|或则|还是|或|\bor\b|\|)", t, flags=re.IGNORECASE)
    cleaned = [p.strip(" ，。;；:：\n\t") for p in parts if (p or "").strip()]
    return cleaned or [t.strip()]


def _ai_build_clause_condition(user_id: int, text: str, keywords: list[str]):
    """把单个片段解析成 SQLAlchemy 条件：结构化条件与关键词默认用 AND 组合。"""
    text = _normalize_query_text(text)

    # 结构化条件
    start_dt, end_dt, date_field = _ai_parse_date_range(text)
    size_min, size_max = _ai_parse_size(text)
    res_info = _ai_parse_resolution(text)
    album_title = _ai_parse_album(text)
    camera_kw = _ai_parse_camera_keyword(text)

    def _looks_like_date(s: str) -> bool:
        return bool(re.search(r"\d{4}[-./年]\d{1,2}[-./月]\d{1,2}", s))

    def _looks_like_size(s: str) -> bool:
        # 不能用 \b 依赖“单词边界”，中文属于 \w，导致 "1MB之间" 无法命中
        return bool(
            re.search(
                r"(\d+(?:\.\d+)?\s*(?:k|kb|m|mb|g|gb|兆)\s*(?:-|~|到|至|—|–)\s*\d+(?:\.\d+)?\s*(?:k|kb|m|mb|g|gb|兆))|(\d+(?:\.\d+)?\s*(?:k|kb|m|mb|g|gb|兆))",
                s,
                flags=re.IGNORECASE,
            )
        )

    def _looks_like_resolution(s: str) -> bool:
        return bool(re.search(r"\d{3,5}\s*[xX×*]\s*\d{3,5}", s)) or bool(
            re.search(r"\d{3,4}p\b", s, flags=re.IGNORECASE)
        )

    # 关键词（过滤掉结构化/噪声/明显结构化 token）
    valid_keywords: list[str] = []
    for kw in keywords or []:
        kw = (kw or "").strip()
        if not kw:
            continue
        if len(kw) > 40:
            continue
        if _is_noise_keyword(kw):
            continue
        if _looks_like_date(kw) or _looks_like_size(kw) or _looks_like_resolution(kw):
            continue
        if kw not in valid_keywords:
            valid_keywords.append(kw)

    # 相册条件：优先用文本解析结果
    album_cond = None
    if album_title:
        valid_keywords = [kw for kw in valid_keywords if kw.strip() != album_title]
        album_cond = or_(
            Image.folder.ilike(f"%{album_title}%"),
            Image.albums.any(and_(Album.title.ilike(f"%{album_title}%"), Album.user_id == user_id)),
            exists().where(
                and_(
                    album_images.c.image_id == Image.id,
                    album_images.c.album_id == Album.id,
                    Album.user_id == user_id,
                    Album.title.ilike(f"%{album_title}%"),
                )
            ),
        )

    structured_conds = []
    if album_cond is not None:
        structured_conds.append(album_cond)

    if start_dt and end_dt:
        dt_col = Image.taken_at if date_field == "taken" else Image.created_at
        structured_conds.append(and_(dt_col >= start_dt, dt_col <= end_dt))

    if size_min is not None or size_max is not None:
        min_b = size_min
        max_b = size_max
        if min_b is not None and max_b is not None and min_b == max_b:
            tol = max(int(min_b * 0.1), 500 * 1024)
            min_b = max(0, min_b - tol)
            max_b = max_b + tol
        if min_b is not None:
            structured_conds.append(Image.size >= min_b)
        if max_b is not None:
            structured_conds.append(Image.size <= max_b)

    if res_info:
        if res_info.get("pixels"):
            res_expr = func.coalesce(Image.width, 0) * func.coalesce(Image.height, 0)
            structured_conds.append(res_expr >= res_info["pixels"])
        if res_info.get("width"):
            structured_conds.append(Image.width >= res_info["width"])
        if res_info.get("height"):
            structured_conds.append(Image.height >= res_info["height"])

    if camera_kw:
        structured_conds.append(or_(Image.camera.ilike(f"%{camera_kw}%"), Image.lens.ilike(f"%{camera_kw}%")))

    keyword_cond = None
    if valid_keywords:
        conds = []
        for kw in valid_keywords:
            cond = _keyword_term_condition(user_id, kw)
            if cond is not None:
                conds.append(cond)
        if conds:
            keyword_cond = or_(*conds)

    if structured_conds and keyword_cond is not None:
        return and_(and_(*structured_conds), keyword_cond)
    if structured_conds:
        return and_(*structured_conds)
    if keyword_cond is not None:
        return keyword_cond
    return None




def _ai_advanced_search(user_id: int, text: str, keywords: list[str], limit: int | None = 12) -> list[dict]:
    """结合关键词与简单结构化条件进行搜索。

    支持：
    - 上传时间 / 拍摄时间；
    - 文件大小；
    - 分辨率；
    - 相册名 / 文件夹；
    - 相机 / 镜头；
    - 名称 / 描述 / 原始文件名 / 标签 的关键词匹配；
    并且可以通过“并且/或者”等词控制结构化条件与关键词的 AND / OR 关系。
    """
    q = _query_user_images(user_id, include_deleted=False)
    logic_mode = _ai_detect_logic_mode(text)
    if logic_mode == "or":
        clause_conds = []
        for seg in _split_or_segments(text):
            seg_kws: list[str] = []
            seg_kws.extend(_heuristic_keywords_from_text(seg, max_terms=6))
            for kw in keywords or []:
                kw = (kw or "").strip()
                if kw and kw in seg and kw not in seg_kws:
                    seg_kws.append(kw)
            cond = _ai_build_clause_condition(user_id, seg, seg_kws)
            if cond is not None:
                clause_conds.append(cond)
        if clause_conds:
            q = q.filter(or_(*clause_conds))
        else:
            return []
    else:
        cond = _ai_build_clause_condition(user_id, text, keywords or [])
        if cond is not None:
            q = q.filter(cond)

    if current_app.config.get("AI_SEARCH_DEBUG"):
        try:
            from sqlalchemy.dialects import mysql

            current_app.logger.info(
                "AI_SEARCH_DEBUG user_id=%s text=%s parsed_date=%s..%s field=%s album=%s camera=%s size=%s..%s res=%s valid_keywords=%s has_structured=%s has_keyword=%s logic=%s",
                user_id,
                text,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                keywords,
                None,
                None,
                logic_mode,
            )
            current_app.logger.info(
                "AI_SEARCH_DEBUG SQL=%s",
                str(q.statement.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True})),
            )
        except Exception:
            current_app.logger.exception("AI_SEARCH_DEBUG failed")

    q = q.order_by(Image.created_at.desc())
    if limit is None or int(limit) <= 0:
        items = q.all()
    else:
        items = q.limit(int(limit)).all()
    return [
        {
            "id": it.id,
            "name": it.name or it.original_name,
            "tags": [t.name for t in it.tags],
            "thumb_url": f"/api/v1/images/{it.id}/thumb",
            "raw_url": f"/api/v1/images/{it.id}/raw",
            "description": it.description,
        }
        for it in items
    ]




def _search_by_keywords(user_id: int, keywords: list[str], limit: int = 8) -> list[dict]:
    """按关键词在当前用户图片中检索。"""
    q = _query_user_images(user_id, include_deleted=False)
    conds = []
    for kw in keywords:
        if not kw:
            continue
        cond = _keyword_term_condition(user_id, kw)
        if cond is not None:
            conds.append(cond)
    if conds:
        q = q.filter(or_(*conds))
    items = q.order_by(Image.created_at.desc()).limit(limit).all()
    return [
        {
            "id": it.id,
            "name": it.name or it.original_name,
            "tags": [t.name for t in it.tags],
            "thumb_url": f"/api/v1/images/{it.id}/thumb",
            "raw_url": f"/api/v1/images/{it.id}/raw",
            "description": it.description,
        }
        for it in items
    ]



def _query_user_images(user_id: int, include_deleted=False):
    q = Image.query.filter_by(user_id=user_id)
    if not include_deleted:
        q = q.filter(Image.deleted_at.is_(None))
    return q


def _get_user_image(image_id: int, user_id: int, include_deleted: bool) -> Image:
    return _query_user_images(user_id, include_deleted).filter(Image.id == image_id).first_or_404()


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
    try:
        
        versions = img.versions.all() if hasattr(img.versions, "all") else (img.versions or [])
        for ver in versions:
            try:
                rel = _normalize_rel_path(getattr(ver, "filename", None))
                if rel:
                    disk_path = os.path.join(current_app.config["UPLOAD_DIR"], rel)
                    if os.path.exists(disk_path):
                        os.remove(disk_path)
            except Exception:
                pass
            try:
                rel = _normalize_rel_path(getattr(ver, "thumb_path", None))
                if rel:
                    thumb_path = os.path.join(current_app.config["THUMB_DIR"], rel)
                    if os.path.exists(thumb_path):
                        os.remove(thumb_path)
            except Exception:
                pass
    except Exception:
        pass


def purge_expired_recycle(retention_days: int | None = None, batch_size: int = 200, user_id: int | None = None) -> int:
    
    days = retention_days if retention_days is not None else int(current_app.config.get("RECYCLE_RETENTION_DAYS", 7))
    if days <= 0:
        return 0
    cutoff = datetime.utcnow() - timedelta(days=days)

    total = 0
    while True:
        q = Image.query.filter(Image.deleted_at.isnot(None), Image.deleted_at <= cutoff)
        if user_id is not None:
            q = q.filter(Image.user_id == int(user_id))
        expired = q.order_by(Image.deleted_at.asc()).limit(batch_size).all()
        if not expired:
            break

        for img in expired:
            _remove_files(img)
            db.session.delete(img)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        total += len(expired)
        if len(expired) < batch_size:
            break

    if total:
        current_app.logger.info("purged expired recycle images: %s", total)
    return total


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
    pan = payload.get("pan") or {}
    crop = payload.get("crop") or {}
    crop_box = payload.get("crop_box") or {}
    adjustments = payload.get("adjustments") or {}

    img = pil.convert("RGB")

    if rotation:
        img = img.rotate(-rotation, expand=True)

    # 统一的裁剪/缩放逻辑：
    # - base_box: 由自由框选(crop_box)或比例预设(crop.preset)确定输出裁剪框（输出尺寸=base_box）
    # - 再基于 zoom+pan 在 base_box 内取更小区域，并缩放回输出尺寸（保证“缩放不改变导出尺寸”）
    preset = crop.get("preset") or crop.get("cropPreset") or "free"
    aspect_w = crop.get("width") or crop.get("w")
    aspect_h = crop.get("height") or crop.get("h")
    ratio = None
    if preset and preset not in ("free", "auto"):
        if preset == "custom" and aspect_w and aspect_h:
            try:
                ratio = float(aspect_w) / float(aspect_h)
            except Exception:
                ratio = None
        elif ":" in str(preset):
            try:
                a, b = str(preset).split(":")
                ratio = float(a) / float(b)
            except Exception:
                ratio = None
        elif "/" in str(preset):
            try:
                a, b = str(preset).split("/")
                ratio = float(a) / float(b)
            except Exception:
                ratio = None
    if ratio is not None and ratio <= 0:
        ratio = None

    try:
        zoom_f = float(zoom or 1)
    except Exception:
        zoom_f = 1.0
    if zoom_f < 1:
        zoom_f = 1.0

    try:
        pan_x = float((pan or {}).get("x", 0) or 0)
        pan_y = float((pan or {}).get("y", 0) or 0)
    except Exception:
        pan_x = 0.0
        pan_y = 0.0
    pan_x = max(-1.0, min(1.0, pan_x))
    pan_y = max(-1.0, min(1.0, pan_y))

    w0, h0 = img.size

    def _parse_norm_box(box: dict) -> tuple[float, float, float, float] | None:
        try:
            x = float(box.get("x", 0) or 0)
            y = float(box.get("y", 0) or 0)
            bw = float(box.get("w", 0) or 0)
            bh = float(box.get("h", 0) or 0)
        except Exception:
            return None
        if bw <= 0 or bh <= 0:
            return None
        x = max(0.0, min(1.0, x))
        y = max(0.0, min(1.0, y))
        bw = max(0.0, min(1.0, bw))
        bh = max(0.0, min(1.0, bh))
        if x + bw > 1.0:
            bw = 1.0 - x
        if y + bh > 1.0:
            bh = 1.0 - y
        if bw <= 0 or bh <= 0:
            return None
        return (x, y, bw, bh)

    base_norm = _parse_norm_box(crop_box) if isinstance(crop_box, dict) else None
    if base_norm is None and ratio:
        if w0 / max(h0, 1) >= ratio:
            base_h = h0
            base_w = int(round(base_h * ratio))
        else:
            base_w = w0
            base_h = int(round(base_w / ratio))
        base_w = max(1, min(w0, base_w))
        base_h = max(1, min(h0, base_h))
        base_left = int(round((w0 - base_w) / 2.0))
        base_top = int(round((h0 - base_h) / 2.0))
    elif base_norm is None:
        base_left, base_top, base_w, base_h = 0, 0, w0, h0
    else:
        x, y, bw, bh = base_norm
        base_left = int(round(x * w0))
        base_top = int(round(y * h0))
        base_w = max(1, int(round(bw * w0)))
        base_h = max(1, int(round(bh * h0)))
        base_left = max(0, min(w0 - base_w, base_left))
        base_top = max(0, min(h0 - base_h, base_top))

    out_w, out_h = base_w, base_h
    crop_w = max(1, min(base_w, int(round(base_w / zoom_f))))
    crop_h = max(1, min(base_h, int(round(base_h / zoom_f))))
    slack_x = max(0.0, (base_w - crop_w) / 2.0)
    slack_y = max(0.0, (base_h - crop_h) / 2.0)
    left = int(round(base_left + slack_x + pan_x * slack_x))
    top = int(round(base_top + slack_y + pan_y * slack_y))
    left = max(0, min(w0 - crop_w, left))
    top = max(0, min(h0 - crop_h, top))
    img = img.crop((left, top, left + crop_w, top + crop_h))
    if (crop_w, crop_h) != (out_w, out_h):
        try:
            resample = PILImage.Resampling.LANCZOS
        except Exception:
            resample = PILImage.LANCZOS
        img = img.resize((out_w, out_h), resample=resample)

    bright = float(adjustments.get("brightness") or 0)
    exposure = float(adjustments.get("exposure") or 0)
    contrast = float(adjustments.get("contrast") or 0)
    saturation = float(adjustments.get("saturation") or 0)

    if bright:
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1 + bright / 100)
    if exposure:
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1 + exposure / 50)
    if contrast:
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1 + contrast / 100)
    if saturation:
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1 + saturation / 100)

    return img


# ================= 路由 =================

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
    album_ids_raw = request.form.getlist("album_ids")
    if not album_ids_raw:
        fallback_album_ids = request.form.get("album_ids") or request.form.get("albumIds") or request.form.get("album_id")
        if fallback_album_ids:
            album_ids_raw = [fallback_album_ids]
    custom_name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip()
    auto_ai_raw = request.form.get("auto_ai")
    auto_ai = True if auto_ai_raw is None else str(auto_ai_raw).lower() in ("1", "true", "yes", "on")

    _ensure_user_dirs(user_id)
    album_ids: list[int] = []
    seen_album_ids: set[int] = set()
    for raw in album_ids_raw:
        for part in str(raw).split(","):
            try:
                album_id = int(part)
            except Exception:
                continue
            if album_id in seen_album_ids:
                continue
            seen_album_ids.add(album_id)
            album_ids.append(album_id)
    albums: list[Album] = []
    if album_ids:
        albums = Album.query.filter(Album.user_id == user_id, Album.id.in_(album_ids)).all()

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
            if albums:
                for album in albums:
                    image_row.albums.append(album)
            db.session.add(image_row)
            saved.append(image_row)

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("image upload failed")
        return jsonify({"message": "上传失败，请稍后再试"}), 500

    ai_failed = 0
    if auto_ai:
        for img in saved:
            try:
                tags, caption = _run_ai_analysis(img)
                _upsert_ai_analysis(img, tags, caption)
            except Exception:
                ai_failed += 1
                current_app.logger.exception("auto ai analyze failed for image %s", getattr(img, "id", None))
        if ai_failed < len(saved):
            try:
                db.session.commit()
            except Exception:
                ai_failed = len(saved)
                db.session.rollback()
                current_app.logger.exception("auto ai commit failed")

    resp = {"message": "上传成功", "items": [_serialize_image(i) for i in saved]}
    if auto_ai:
        resp["ai_auto"] = True
        resp["ai_failed"] = ai_failed
    return jsonify(resp), 201


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
    album_titles = _list_param("albums")
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
        structured_conds = []
        exclude_terms: set[str] = set()

        # 从自然语言里推断结构化条件（不覆盖用户显式传入的参数）
        inferred_album = _ai_parse_album(keyword)
        if inferred_album and not album_titles:
            exclude_terms.add(inferred_album)
            structured_conds.append(
                or_(
                    Image.albums.any(and_(Album.user_id == user_id, Album.title.ilike(f"%{inferred_album}%"))),
                    Image.folder.ilike(f"%{inferred_album}%"),
                )
            )

        camera_param = _list_param("camera")
        lens_param = _list_param("lens")
        inferred_camera = _ai_parse_camera_keyword(keyword)
        if inferred_camera and not (camera_param or lens_param):
            exclude_terms.add(inferred_camera)
            structured_conds.append(
                or_(
                    Image.camera.ilike(f"%{inferred_camera}%"),
                    Image.lens.ilike(f"%{inferred_camera}%"),
                )
            )

        start_dt, end_dt, date_field = _ai_parse_date_range(keyword)
        if start_dt and end_dt:
            if date_field == "taken":
                if captured_start is None and captured_end is None:
                    structured_conds.append(Image.taken_at.isnot(None))
                    structured_conds.append(Image.taken_at >= start_dt)
                    structured_conds.append(Image.taken_at <= end_dt)
            else:
                if uploaded_start is None and uploaded_end is None:
                    structured_conds.append(Image.created_at >= start_dt)
                    structured_conds.append(Image.created_at <= end_dt)

        size_min_b, size_max_b = _ai_parse_size(keyword)
        if size_min_b is not None or size_max_b is not None:
            min_b = size_min_b
            max_b = size_max_b
            if min_b is not None and max_b is not None and min_b == max_b:
                tol = max(int(min_b * 0.1), 500 * 1024)
                min_b = max(0, min_b - tol)
                max_b = max_b + tol
            if min_b is not None:
                structured_conds.append(Image.size >= min_b)
            if max_b is not None:
                structured_conds.append(Image.size <= max_b)

        res_info = _ai_parse_resolution(keyword)
        if res_info:
            if res_info.get("pixels"):
                res_expr = func.coalesce(Image.width, 0) * func.coalesce(Image.height, 0)
                structured_conds.append(res_expr >= res_info["pixels"])
            if res_info.get("width"):
                structured_conds.append(Image.width >= res_info["width"])
            if res_info.get("height"):
                structured_conds.append(Image.height >= res_info["height"])

        # 把剩余内容当关键词（支持 AND/OR，自带停用词与结构化 token 过滤）
        keyword_groups = _nl_extract_keyword_groups(keyword, exclude_terms=exclude_terms)
        keyword_cond = _build_keyword_groups_condition(user_id, keyword_groups)

        logic_mode = _ai_detect_logic_mode(keyword)
        if structured_conds and keyword_cond is not None:
            if logic_mode == "or":
                query = query.filter(or_(and_(*structured_conds), keyword_cond))
            else:
                query = query.filter(and_(*structured_conds)).filter(keyword_cond)
        elif structured_conds:
            query = query.filter(and_(*structured_conds))
        elif keyword_cond is not None:
            query = query.filter(keyword_cond)
        else:
            # 用户确实输入了 keyword，但内容全是连接词/结构化触发词时，不应退化为“返回全部”
            query = query.filter(Image.id == -1)

    for tag_name in tag_names:
        query = query.filter(Image.tags.any(Tag.name == tag_name))

    for album_title in album_titles:
        query = query.filter(
            Image.albums.any(and_(Album.user_id == user_id, Album.title == album_title))
        )

    if format_list:
        format_aliases = {
            "jpg": ["jpg", "jpeg"],
            "jpeg": ["jpeg", "jpg"],
            "heic": ["heic", "heif"],
            "heif": ["heif", "heic"],
            "raw": [
                "raw",
                "dng",
                "nef",
                "cr2",
                "cr3",
                "arw",
                "raf",
                "rw2",
                "orf",
                "srw",
                "pef",
            ],
        }
        mime_aliases = {
            "jpg": ["jpeg", "jpg"],
            "jpeg": ["jpeg", "jpg"],
            "heic": ["heic", "heif"],
            "heif": ["heif", "heic"],
            "raw": ["dng", "raw", "x-adobe-dng", "x-canon", "x-nikon", "x-sony", "x-fuji", "x-panasonic", "x-olympus"],
        }

        conds = []
        for fmt in format_list:
            fmt = (fmt or "").strip().lstrip(".").lower()
            if not fmt:
                continue
            exts = format_aliases.get(fmt, [fmt])
            mimes = mime_aliases.get(fmt, [fmt])
            for ext in exts:
                conds.append(func.lower(Image.filename).like(f"%.{ext}"))
                conds.append(func.lower(Image.original_name).like(f"%.{ext}"))
            for mt in mimes:
                conds.append(func.lower(Image.mime_type).like(f"%{mt}%"))
        if conds:
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
        vals = _list_param(key)
        if not vals:
            continue
        like_conds = [col.ilike(f"%{v.strip()}%") for v in vals if (v or "").strip()]
        if like_conds:
            query = query.filter(or_(*like_conds))

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
        "name_desc": Image.name.desc(),
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


@images_bp.get("/exif-options")
def exif_options():
    user_id = _current_user_id()
    field = (request.args.get("field") or "").strip()
    keyword = (request.args.get("keyword") or "").strip()
    limit = _positive_int(request.args.get("limit"), 20, 100)

    field_map = {
        "camera": Image.camera,
        "lens": Image.lens,
        "iso": Image.iso,
        "aperture": Image.aperture,
        "focal_length": Image.focal,
        "shutter": Image.exposure,
    }
    col = field_map.get(field)
    if col is None:
        return jsonify({"message": "invalid field"}), 400

    q = (
        db.session.query(col)
        .filter(Image.user_id == user_id)
        .filter(Image.deleted_at.is_(None))
        .filter(col.isnot(None))
        .filter(func.length(func.trim(col)) > 0)
    )
    if keyword:
        q = q.filter(col.ilike(f"%{keyword}%"))
    rows = q.distinct().order_by(col.asc()).limit(limit).all()
    items = [r[0] for r in rows if r and r[0]]
    return jsonify({"items": items})


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


@images_bp.get("/quota")
def image_quota():
    user_id = _current_user_id()
    image_count, used_bytes = (
        db.session.query(
            func.count(Image.id),
            func.coalesce(func.sum(Image.size), 0),
        )
        .filter(Image.user_id == user_id, Image.deleted_at.is_(None))
        .one()
    )
    return jsonify({"message": "ok", "image_count": int(image_count or 0), "used_bytes": int(used_bytes or 0)})


@images_bp.get("/recycle")
def list_recycle():
    user_id = _current_user_id()
    
    purge_expired_recycle(user_id=user_id)
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
    return jsonify(_serialize_image(img, include_albums=True))


@images_bp.post("/<int:image_id>/export")
def export_image(image_id: int):
    user_id = _current_user_id()
    img = _get_user_image(image_id, user_id, include_deleted=False)

    rel = _normalize_rel_path(img.filename)
    if not rel:
        return jsonify({"message": "文件不存在"}), 404
    disk_path = os.path.join(current_app.config["UPLOAD_DIR"], rel)
    if not os.path.exists(disk_path):
        return jsonify({"message": "文件不存在"}), 404

    payload = request.get_json() or {}
    option = str(payload.get("option") or "override").lower()
    option = "new" if option == "new" else "override"
    name = (payload.get("name") or img.name or img.original_name).strip() or img.name
    folder = (payload.get("folder") or img.folder or "默认图库").strip() or "默认图库"
    tag_names, color_map = _parse_tag_payload(payload.get("tags") or [])
    old_thumb_rel = _normalize_rel_path(img.thumb_path)

    _ensure_user_dirs(user_id)

    album_ids = None
    if isinstance(payload, dict):
        if "album_ids" in payload:
            album_ids = payload.get("album_ids")
        elif "albumIds" in payload:
            album_ids = payload.get("albumIds")

    def _coerce_id_list(raw) -> list[int] | None:
        if raw is None:
            return None
        if isinstance(raw, str):
            parts = [p.strip() for p in raw.split(",") if p.strip()]
        elif isinstance(raw, (list, tuple, set)):
            parts = list(raw)
        else:
            parts = [raw]
        ids: list[int] = []
        seen: set[int] = set()
        for p in parts:
            try:
                i = int(p)
            except Exception:
                continue
            if i in seen:
                continue
            seen.add(i)
            ids.append(i)
        return ids

    album_ids_coerced = _coerce_id_list(album_ids)

    def _apply_albums(image_obj: Image):
        if album_ids_coerced is None:
            return
        # 替换为当前选择的相册集合（空列表表示清空）
        if getattr(image_obj, "id", None):
            existing = image_obj.albums.all()
            for a in existing:
                image_obj.albums.remove(a)
        if not album_ids_coerced:
            return
        albums = Album.query.filter(Album.user_id == user_id, Album.id.in_(album_ids_coerced)).all()
        for a in albums:
            image_obj.albums.append(a)

    try:
        with PILImage.open(disk_path) as src:
            src = ImageOps.exif_transpose(src)
            exif_bytes = src.info.get("exif")
            edited = _apply_edits(src, payload)
    except Exception:
        current_app.logger.exception("export apply edits failed")
        return jsonify({"message": "处理图片失败"}), 500

    ext = os.path.splitext(rel)[1].lower().lstrip(".") or "jpg"
    fmt_map = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "gif": "GIF", "webp": "WEBP", "bmp": "BMP"}
    fmt = fmt_map.get(ext, "JPEG")
    mime_map = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "GIF": "image/gif",
        "WEBP": "image/webp",
        "BMP": "image/bmp",
    }

    def _save_with_exif(pil_img: PILImage.Image, dest_disk: str):
        os.makedirs(os.path.dirname(dest_disk), exist_ok=True)
        save_kwargs = {"format": fmt}
        if fmt == "JPEG" and exif_bytes:
            save_kwargs["exif"] = exif_bytes
            save_kwargs["quality"] = 95
        pil_img.save(dest_disk, **save_kwargs)

    def _save_new_thumb(src_disk: str, rel_hint: str | None = None) -> str:
        thumb_rel = rel_hint or _normalize_rel_path(os.path.join(f"user_{user_id}", f"{uuid.uuid4().hex}_thumb.jpg"))
        thumb_disk = os.path.join(current_app.config["THUMB_DIR"], thumb_rel)
        os.makedirs(os.path.dirname(thumb_disk), exist_ok=True)
        _save_thumb(src_disk, thumb_disk)
        return thumb_rel

    try:
        if option == "override":
            backup_token = uuid.uuid4().hex
            ver_rel = _normalize_rel_path(os.path.join(f"user_{user_id}", "versions", f"{backup_token}.{ext}"))
            os.makedirs(os.path.join(current_app.config["UPLOAD_DIR"], f"user_{user_id}", "versions"), exist_ok=True)
            shutil.copyfile(disk_path, os.path.join(current_app.config["UPLOAD_DIR"], ver_rel))
            ver_thumb_rel = None
            try:
                os.makedirs(os.path.join(current_app.config["THUMB_DIR"], f"user_{user_id}", "versions"), exist_ok=True)
                ver_thumb_rel = _normalize_rel_path(
                    os.path.join(f"user_{user_id}", "versions", f"{backup_token}_thumb.jpg")
                )
                _save_thumb(disk_path, os.path.join(current_app.config["THUMB_DIR"], ver_thumb_rel))
            except Exception:
                ver_thumb_rel = None

            version_row = ImageVersion(
                image_id=img.id,
                name=img.name or img.original_name,
                note="覆盖前版本",
                filename=ver_rel,
                thumb_path=ver_thumb_rel,
            )
            db.session.add(version_row)

            _save_with_exif(edited, disk_path)
            thumb_rel = _save_new_thumb(disk_path)
            exif_data = _extract_exif(edited, exif_bytes)

            img.name = name
            img.folder = folder
            img.width, img.height = edited.size
            img.size = os.path.getsize(disk_path)
            img.exif_json = json.dumps(exif_data.get("raw") or {})
            img.taken_at = _parse_taken_at(exif_data.get("taken_at"))
            img.camera = exif_data.get("camera") or None
            img.lens = exif_data.get("lens") or None
            img.iso = exif_data.get("iso") or None
            img.exposure = exif_data.get("exposure") or None
            img.aperture = exif_data.get("aperture") or None
            img.focal = exif_data.get("focal") or None
            img.latitude = exif_data.get("latitude")
            img.longitude = exif_data.get("longitude")
            img.mime_type = mime_map.get(fmt, img.mime_type)
            img.thumb_path = thumb_rel
            if tag_names is not None:
                img.tags = _get_or_create_tags(tag_names, user_id=user_id, color_map=color_map)
            _apply_albums(img)
            db.session.commit()

            if old_thumb_rel and old_thumb_rel != thumb_rel:
                old_disk = os.path.join(current_app.config["THUMB_DIR"], old_thumb_rel)
                if os.path.exists(old_disk):
                    try:
                        os.remove(old_disk)
                    except Exception:
                        pass

            return jsonify({"message": "ok", "item": _serialize_image(img, include_albums=True)})

        token = uuid.uuid4().hex
        rel_new = _normalize_rel_path(os.path.join(f"user_{user_id}", f"{token}.{ext}"))
        disk_new = os.path.join(current_app.config["UPLOAD_DIR"], rel_new)
        _save_with_exif(edited, disk_new)
        thumb_rel = _save_new_thumb(disk_new)
        exif_data = _extract_exif(edited, exif_bytes)
        lat = exif_data.get("latitude")
        lon = exif_data.get("longitude")
        if (lat is None or lon is None) and exif_data.get("gps"):
            lat, lon = _gps_to_decimal(exif_data.get("gps"))

        new_img = Image(
            user_id=user_id,
            name=name,
            description=img.description,
            filename=rel_new,
            original_name=img.original_name,
            mime_type=mime_map.get(fmt, img.mime_type),
            size=os.path.getsize(disk_new),
            width=edited.size[0],
            height=edited.size[1],
            taken_at=_parse_taken_at(exif_data.get("taken_at")),
            camera=exif_data.get("camera"),
            lens=exif_data.get("lens"),
            iso=exif_data.get("iso"),
            exposure=exif_data.get("exposure"),
            aperture=exif_data.get("aperture"),
            focal=exif_data.get("focal"),
            latitude=lat,
            longitude=lon,
            exif_json=json.dumps(exif_data.get("raw") or {}),
            thumb_path=thumb_rel,
            visibility=img.visibility,
            is_featured=False,
            folder=folder,
        )
        new_img.tags = _get_or_create_tags(tag_names, user_id=user_id, color_map=color_map)
        db.session.add(new_img)
        _apply_albums(new_img)
        db.session.commit()
        return jsonify({"message": "ok", "item": _serialize_image(new_img, include_albums=True)})
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("export failed")
        return jsonify({"message": "保存失败", "error": str(exc)}), 500


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


# === AI 路由 ===
@images_bp.get("/<int:image_id>/ai")
def get_ai_result(image_id: int):
    user_id = _current_user_id()
    img = _get_user_image(image_id, user_id, include_deleted=False)
    ai = img.ai_analysis
    return jsonify(
        {
            "message": "ok",
            "tags": ai.labels if ai else [],
            "caption": ai.caption if ai else "",
            "status": ai.status if ai else "none",
            "item": _serialize_image(img),
        }
    )


@images_bp.post("/<int:image_id>/ai/analyze")
def analyze_image(image_id: int):
    user_id = _current_user_id()
    img = _get_user_image(image_id, user_id, include_deleted=False)
    try:
        tags, caption = _run_ai_analysis(img)
        ai = _upsert_ai_analysis(img, tags, caption)
        db.session.commit()
        return jsonify(
            {
                "message": "ok",
                "tags": ai.labels or [],
                "caption": ai.caption or "",
                "item": _serialize_image(img),
            }
        )
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("ai analyze failed")
        return jsonify({"message": "AI 分析失败", "error": str(exc)}), 500


@images_bp.post("/ai/chat")
def ai_chat_search():
    user_id = _current_user_id()
    data = request.get_json() or {}
    messages = data.get("messages") or []
    user_text = ""
    for m in reversed(messages):
        if str(m.get("role")) == "user":
            user_text = str(m.get("content") or "")
            break
    if not user_text:
        return jsonify({"message": "缺少用户输入"}), 400

    # 关键词：本地兜底优先，避免外部模型抖动导致“明明有图却搜不到”
    keywords_local = _heuristic_keywords_from_text(user_text, max_terms=6)
    keywords_ai: list[str] = []
    try:
        kw_prompt = (
            "请把这句话提炼 3~5 个中文关键词，用 JSON 返回："
            '{"keywords":["k1","k2"],"style":[]}。'
            f"输入：{user_text}"
        )
        kw_raw = _qwen_chat(
            [
                {"role": "system", "content": "你是检索关键词提取器，只返回 JSON。"},
                {"role": "user", "content": kw_prompt},
            ]
        )
        keywords_ai, _ = _parse_ai_json(kw_raw)
    except Exception:
        current_app.logger.exception("ai keyword extraction failed")
        keywords_ai = []

    keywords: list[str] = []
    for kw in (keywords_local or []) + (keywords_ai or []):
        kw = (kw or "").strip()
        if not kw:
            continue
        if len(kw) > 40:
            continue
        if _is_noise_keyword(kw):
            continue
        if kw not in keywords:
            keywords.append(kw)
        if len(keywords) >= 8:
            break
    if not keywords:
        keywords = [user_text.strip()][:3]

    # 默认返回全部匹配结果（前端会完整展示）；如需限制可传 limit（<=0 表示不限制）
    req_limit = data.get("limit")
    try:
        limit = int(req_limit) if req_limit is not None and str(req_limit).strip() != "" else None
    except Exception:
        limit = None
    try:
        results = _ai_advanced_search(user_id, user_text, keywords, limit=limit)
    except Exception as exc:
        current_app.logger.exception("ai search failed")
        return jsonify({"message": "AI 检索失败", "error": str(exc)}), 500

    # 回复：优先调用大模型总结；失败时用本地兜底，保证可用性
    reply = ""
    try:
        reply_prompt = (
            "你是图片管家，根据候选图片用中文简短回复。\n"
            "规则：\n"
            "1) 只能引用候选里的图片 id 和 name，不要编造。\n"
            "2) 如果候选非空：必须至少列出 1 张（最多 5 张），不要说“没有/未找到”。\n"
            "3) 如果候选为空：才可以说没有找到。\n"
            f"用户问：{user_text}\n候选数量：{len(results)}\n候选：{json.dumps(results, ensure_ascii=False)}"
        )
        reply = _qwen_chat(
            [
                {"role": "system", "content": "你是照片助理，口吻简洁、友好。"},
                {"role": "user", "content": reply_prompt},
            ]
        )
    except Exception:
        current_app.logger.exception("ai reply generation failed")
        reply = ""

    if not reply:
        if not results:
            reply = "没有找到相关图片。"
        else:
            top = results[: min(5, len(results))]
            reply = "我找到了这些图片：" + "，".join([f"{it.get('id')} {it.get('name')}" for it in top if it.get("id")])

    # 兜底：候选非空但模型仍回复“没有”，避免前端出现“有图但说没图”的矛盾体验
    if results and re.search(r"(没有|未找到|找不到|无相关)", reply or ""):
        top = results[: min(5, len(results))]
        reply = "我找到了这些图片：" + "，".join([f"{it.get('id')} {it.get('name')}" for it in top if it.get("id")])

    return jsonify({"message": "ok", "reply": reply, "keywords": keywords, "total": len(results), "images": results})
