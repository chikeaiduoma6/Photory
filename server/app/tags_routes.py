import re
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from sqlalchemy import func

from .extensions import db
from .models import Image, Tag, image_tags

tags_bp = Blueprint("tags", __name__, url_prefix="/api/v1/tags")

PALETTE = ["#ff9db8", "#8ed0ff", "#ffd27f", "#9dd0a5", "#c3a0ff", "#f7a3ff"]


def _current_user_id() -> int:
    verify_jwt_in_request(optional=False, locations=["headers", "query_string"])
    return int(get_jwt_identity())


def _tag_query(user_id: int):
    return Tag.query.filter(Tag.user_id == user_id)


def _sanitize_color(raw: str | None) -> str:
    default = "#ff9db8"
    if not raw:
        return default
    val = raw.strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?", val)
    if m:
        return f"#{m.group(1)}"
    m = re.fullmatch(r"rgba?\((\d{1,3}),\s*(\d{1,3}),\s*(\d{1,3})(?:,\s*[\d\.]+)?\)", val)
    if m:
        r, g, b = [max(0, min(255, int(x))) for x in m.groups()]
        return f"#{r:02x}{g:02x}{b:02x}"
    return default


def _fallback_color(name: str, idx: int) -> str:
    code = sum(ord(c) for c in name) if name else idx
    return PALETTE[code % len(PALETTE)]


@tags_bp.get("")
def list_tags():
    user_id = _current_user_id()
    page = _positive_int(request.args.get("page"), 1)
    page_size = _positive_int(request.args.get("page_size"), 6, 50)
    keyword = (request.args.get("keyword") or "").strip()
    sort = request.args.get("sort", "recent")

    count_subq = (
        db.session.query(image_tags.c.tag_id, func.count(Image.id).label("image_count"))
        .join(Image, image_tags.c.image_id == Image.id)
        .filter(Image.user_id == user_id, Image.deleted_at.is_(None))
        .group_by(image_tags.c.tag_id)
        .subquery()
    )

    query = (
        _tag_query(user_id)
        .outerjoin(count_subq, Tag.id == count_subq.c.tag_id)
        .add_columns(count_subq.c.image_count)
    )
    if keyword:
        query = query.filter(Tag.name.ilike(f"%{keyword}%"))

    if sort == "name":
        query = query.order_by(Tag.name.asc())
    elif sort == "count":
        query = query.order_by(count_subq.c.image_count.desc().nullslast(), Tag.created_at.desc())
    else:
        query = query.order_by(Tag.created_at.desc())

    pagination = query.paginate(page=page, per_page=page_size, error_out=False)
    items = []
    for idx, (tag, image_count) in enumerate(pagination.items):
        color = _sanitize_color(tag.color) if tag.color else _fallback_color(tag.name, idx)
        obj = tag.to_dict(include_count=True, image_count=image_count or 0)
        obj["color"] = color
        items.append(obj)

    return jsonify(
        {
            "items": items,
            "total": pagination.total,
            "page": page,
            "page_size": page_size,
        }
    )


@tags_bp.get("/summary")
def tag_summary():
    user_id = _current_user_id()
    count_subq = (
        db.session.query(image_tags.c.tag_id, func.count(Image.id).label("image_count"))
        .join(Image, image_tags.c.image_id == Image.id)
        .filter(Image.user_id == user_id, Image.deleted_at.is_(None))
        .group_by(image_tags.c.tag_id)
        .subquery()
    )
    rows = (
        _tag_query(user_id)
        .outerjoin(count_subq, Tag.id == count_subq.c.tag_id)
        .add_columns(count_subq.c.image_count)
        .all()
    )
    distribution = []
    total_images = 0
    for idx, (tag, image_count) in enumerate(rows):
        count = image_count or 0
        total_images += count
        distribution.append(
            {
                "id": tag.id,
                "name": tag.name,
                "color": _sanitize_color(tag.color) if tag.color else _fallback_color(tag.name, idx),
                "count": count,
                "created_at": tag.created_at.isoformat(),
            }
        )
    distribution.sort(key=lambda x: x["count"], reverse=True)
    max_count = max([d["count"] for d in distribution], default=1)
    word_cloud = [
        {**d, "size": 14 + int((d["count"] / max_count) * 18)} for d in distribution[:30]
    ]
    return jsonify(
        {
            "total_tags": len(rows),
            "total_images": total_images,
            "distribution": distribution,
            "word_cloud": word_cloud,
        }
    )


@tags_bp.post("")
def create_tag():
    user_id = _current_user_id()
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    color = _sanitize_color(data.get("color"))
    if not name:
        return jsonify({"message": "请输入标签名称"}), 400
    if _tag_query(user_id).filter_by(name=name).first():
        return jsonify({"message": "标签已存在"}), 409
    tag = Tag(name=name, color=color, user_id=user_id)
    db.session.add(tag)
    db.session.commit()
    return jsonify({"message": "ok", "tag": tag.to_dict(include_count=True, image_count=0)}), 201


@tags_bp.put("/<int:tag_id>")
def update_tag(tag_id: int):
    user_id = _current_user_id()
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    color = _sanitize_color(data.get("color"))
    if not name:
        return jsonify({"message": "请输入标签名称"}), 400
    tag = _tag_query(user_id).filter_by(id=tag_id).first_or_404()
    dup = _tag_query(user_id).filter(Tag.id != tag_id, Tag.name == name).first()
    if dup:
        return jsonify({"message": "同名标签已存在"}), 409
    tag.name = name
    tag.color = color
    db.session.commit()
    return jsonify({"message": "ok", "tag": tag.to_dict(include_count=True)})


@tags_bp.delete("/<int:tag_id>")
def delete_tag(tag_id: int):
    user_id = _current_user_id()
    tag = _tag_query(user_id).filter_by(id=tag_id).first_or_404()
    db.session.execute(image_tags.delete().where(image_tags.c.tag_id == tag_id))
    db.session.delete(tag)
    db.session.commit()
    return jsonify({"message": "已删除"})


@tags_bp.post("/batch-delete")
def batch_delete():
    user_id = _current_user_id()
    data = request.get_json() or {}
    ids = data.get("ids") or []
    if not ids:
        return jsonify({"message": "请选择要删除的标签"}), 400
    owned_ids = [t.id for t in _tag_query(user_id).filter(Tag.id.in_(ids)).all()]
    if not owned_ids:
        return jsonify({"message": "未找到对应标签"}), 404
    db.session.execute(image_tags.delete().where(image_tags.c.tag_id.in_(owned_ids)))
    Tag.query.filter(Tag.id.in_(owned_ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({"message": "已批量删除", "count": len(owned_ids)})


@tags_bp.post("/merge")
def merge_tags():
    user_id = _current_user_id()
    data = request.get_json() or {}
    source_ids = data.get("source_ids") or []
    target_id = data.get("target_id")
    if not source_ids or not target_id:
        return jsonify({"message": "请选择来源和目标标签"}), 400
    if target_id in source_ids:
        return jsonify({"message": "目标标签不能与来源相同"}), 400

    tags = _tag_query(user_id).filter(Tag.id.in_(source_ids + [target_id])).all()
    tag_map = {t.id: t for t in tags}
    target = tag_map.get(target_id)
    if not target:
        return jsonify({"message": "目标标签不存在"}), 404
    missing = [tid for tid in source_ids if tid not in tag_map]
    if missing:
        return jsonify({"message": f"无权操作标签 {missing}"}), 404

    img_ids = {
        row.image_id
        for row in db.session.query(image_tags.c.image_id)
        .filter(image_tags.c.tag_id.in_(source_ids))
        .all()
    }
    for img_id in img_ids:
        exists = (
            db.session.query(image_tags)
            .filter(image_tags.c.image_id == img_id, image_tags.c.tag_id == target_id)
            .first()
        )
        if not exists:
            db.session.execute(image_tags.insert().values(image_id=img_id, tag_id=target_id))

    db.session.execute(image_tags.delete().where(image_tags.c.tag_id.in_(source_ids)))
    Tag.query.filter(Tag.id.in_(source_ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({"message": "合并完成"})


@tags_bp.get("/<int:tag_id>/images")
def images_by_tag(tag_id: int):
    user_id = _current_user_id()
    tag = _tag_query(user_id).filter_by(id=tag_id).first_or_404()

    page = _positive_int(request.args.get("page"), 1)
    page_size = _positive_int(request.args.get("page_size"), 12, 50)
    sort = request.args.get("sort", "newest")

    query = _query_user_images(user_id, include_deleted=False).join(image_tags).filter(image_tags.c.tag_id == tag_id)
    order_by = Image.created_at.asc() if sort == "oldest" else Image.created_at.desc()
    pagination = query.order_by(order_by).paginate(page=page, per_page=page_size, error_out=False)

    return jsonify(
        {
            "items": [_serialize_image(img) for img in pagination.items],
            "total": pagination.total,
            "page": page,
            "page_size": page_size,
            "tag": {**tag.to_dict(include_count=True, image_count=pagination.total), "color": _sanitize_color(tag.color)},
        }
    )


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


def _serialize_image(img: Image) -> dict:
    data = img.to_dict()
    data["raw_url"] = f"/api/v1/images/{img.id}/raw"
    data["thumb_url"] = f"/api/v1/images/{img.id}/thumb"
    return data
