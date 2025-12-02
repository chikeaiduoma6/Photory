from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from sqlalchemy import func
from .extensions import db
from .models import Album, Image, album_images

albums_bp = Blueprint("albums", __name__, url_prefix="/api/v1/albums")

def _current_user_id() -> int:
    verify_jwt_in_request(optional=False, locations=["headers", "query_string"])
    return int(get_jwt_identity())

def _positive_int(val, default=0, max_val=None):
    try:
        result = max(0, int(val))
        if max_val is not None:
            return min(result, max_val)
        return result
    except (ValueError, TypeError):
        return default

def _album_query(user_id: int):
    return Album.query.filter(Album.user_id == user_id)

@albums_bp.post("")
def create_album():
    user_id = _current_user_id()
    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    visibility = data.get("visibility") or "private"
    
    if not title:
        return jsonify({"message": "请输入相册名称"}), 400
    
    if Album.query.filter(Album.user_id == user_id, Album.title == title).first():
        return jsonify({"message": "相册已存在"}), 409
    
    album = Album(
        user_id=user_id,
        title=title,
        visibility=visibility
    )
    
    db.session.add(album)
    db.session.commit()
    
    return jsonify({"message": "ok", "album": album.to_dict()}), 201

@albums_bp.delete("/<int:album_id>")
def delete_album(album_id):
    user_id = _current_user_id()
    
    album = Album.query.filter(Album.id == album_id, Album.user_id == user_id).first()
    if not album:
        return jsonify({"message": "相册不存在"}), 404
    
    db.session.delete(album)
    db.session.commit()
    
    return jsonify({"message": "删除成功"}), 200

@albums_bp.get("")
def list_albums():
    user_id = _current_user_id()
    page = _positive_int(request.args.get("page"), 1)
    page_size = _positive_int(request.args.get("page_size"), 6, 50)
    keyword = (request.args.get("keyword") or "").strip()
    sort = request.args.get("sort", "recent")
    
    count_subq = (
        db.session.query(album_images.c.album_id, func.count(Image.id).label("image_count"))
        .join(Image, album_images.c.image_id == Image.id)
        .filter(Image.user_id == user_id, Image.deleted_at.is_(None))
        .group_by(album_images.c.album_id)
        .subquery()
    )
    
    # 获取相册封面图片（最新上传的一张）
    cover_subq = (
        db.session.query(
            album_images.c.album_id,
            Image.id.label("image_id"),
            Image.thumb_path.label("thumb_path"),
            Image.created_at.label("created_at")
        )
        .join(Image, album_images.c.image_id == Image.id)
        .filter(Image.user_id == user_id, Image.deleted_at.is_(None))
        .order_by(album_images.c.album_id, Image.created_at.desc())
        .subquery()
    )
    
    cover_rank_subq = (
        db.session.query(
            cover_subq.c.album_id,
            cover_subq.c.image_id,
            cover_subq.c.thumb_path,
            func.row_number().over(
                partition_by=cover_subq.c.album_id,
                order_by=cover_subq.c.created_at.desc()
            ).label("rn")
        )
        .subquery()
    )
    
    cover_final_subq = (
        db.session.query(
            cover_rank_subq.c.album_id,
            cover_rank_subq.c.image_id,
            cover_rank_subq.c.thumb_path
        )
        .filter(cover_rank_subq.c.rn == 1)
        .subquery()
    )
    
    query = (
        _album_query(user_id)
        .outerjoin(count_subq, Album.id == count_subq.c.album_id)
        .outerjoin(cover_final_subq, Album.id == cover_final_subq.c.album_id)
        .add_columns(
            count_subq.c.image_count,
            cover_final_subq.c.image_id,
            cover_final_subq.c.thumb_path
        )
    )
    
    if keyword:
        query = query.filter(Album.title.ilike(f"%{keyword}%"))
    
    if sort == "title":
        query = query.order_by(Album.title.asc())
    elif sort == "count":
        query = query.order_by(count_subq.c.image_count.desc().nullslast(), Album.created_at.desc())
    else:
        query = query.order_by(Album.created_at.desc())
    
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)
    items = []
    
    for album, image_count, cover_image_id, cover_thumb_path in pagination.items:
        cover_image = {
            "id": cover_image_id,
            "thumb_url": f"/api/v1/images/{cover_image_id}/thumb" if cover_image_id else None
        } if cover_image_id else None
        
        items.append(album.to_dict(
            include_count=True,
            image_count=image_count or 0,
            cover_image=cover_image
        ))
    
    return jsonify({
        "items": items,
        "total": pagination.total,
        "page": page,
        "page_size": page_size,
    })

@albums_bp.get("/<int:album_id>/images")
def get_album_images(album_id):
    user_id = _current_user_id()
    
    album = Album.query.filter(Album.id == album_id, Album.user_id == user_id).first()
    if not album:
        return jsonify({"message": "相册不存在"}), 404
    
    page = _positive_int(request.args.get("page"), 1)
    page_size = _positive_int(request.args.get("page_size"), 12, 50)
    sort = request.args.get("sort", "newest")
    
    # 使用join查询以支持按关联表中的字段排序
    query = (
        Image.query
        .join(album_images, Image.id == album_images.c.image_id)
        .filter(
            album_images.c.album_id == album_id,
            Image.deleted_at.is_(None)
        )
    )
    
    if sort == "oldest":
        query = query.order_by(Image.created_at.asc())
    elif sort == "name_asc":
        query = query.order_by(Image.name.asc())
    elif sort == "name_desc":
        query = query.order_by(Image.name.desc())
    elif sort == "taken_asc":
        query = query.order_by(Image.taken_at.asc().nullslast(), Image.created_at.asc())
    elif sort == "taken_desc":
        query = query.order_by(Image.taken_at.desc().nullslast(), Image.created_at.desc())
    elif sort == "added_asc":
        query = query.order_by(album_images.c.created_at.asc())
    elif sort == "added_desc":
        query = query.order_by(album_images.c.created_at.desc())
    else:  # created_desc (newest)
        query = query.order_by(Image.created_at.desc())
    
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)
    
    return jsonify({
        "items": [img.to_dict() for img in pagination.items],
        "total": pagination.total,
        "page": page,
        "page_size": page_size,
        "album": album.to_dict(include_count=True)
    })

@albums_bp.post("/<int:album_id>/images/<int:image_id>")
def add_image_to_album(album_id, image_id):
    user_id = _current_user_id()
    
    album = Album.query.filter(Album.id == album_id, Album.user_id == user_id).first()
    if not album:
        return jsonify({"message": "相册不存在"}), 404
    
    image = Image.query.filter(Image.id == image_id, Image.user_id == user_id, Image.deleted_at.is_(None)).first()
    if not image:
        return jsonify({"message": "图片不存在"}), 404
    
    if image in album.images:
        return jsonify({"message": "图片已在相册中"}), 409
    
    album.images.append(image)
    db.session.commit()
    
    return jsonify({"message": "ok"}), 200

@albums_bp.delete("/<int:album_id>/images/<int:image_id>")
def remove_image_from_album(album_id, image_id):
    user_id = _current_user_id()
    
    album = Album.query.filter(Album.id == album_id, Album.user_id == user_id).first()
    if not album:
        return jsonify({"message": "相册不存在"}), 404
    
    image = Image.query.filter(Image.id == image_id, Image.user_id == user_id).first()
    if not image:
        return jsonify({"message": "图片不存在"}), 404
    
    if image not in album.images:
        return jsonify({"message": "图片不在相册中"}), 404
    
    album.images.remove(image)
    db.session.commit()
    
    return jsonify({"message": "ok"}), 200

@albums_bp.get("/<int:album_id>")
def get_album(album_id):
    user_id = _current_user_id()
    
    album = Album.query.filter(Album.id == album_id, Album.user_id == user_id).first()
    if not album:
        return jsonify({"message": "相册不存在"}), 404
    
    # 获取图片数量
    image_count = album.images.filter(Image.deleted_at.is_(None)).count()
    
    # 获取封面图片（最新上传的一张）
    cover_image = album.images.filter(Image.deleted_at.is_(None)).order_by(Image.created_at.desc()).first()
    cover_image_dict = None
    if cover_image:
        cover_image_dict = {
            "id": cover_image.id,
            "thumb_url": f"/api/v1/images/{cover_image.id}/thumb"
        }
    
    return jsonify({
        "album": album.to_dict(
            include_count=True,
            image_count=image_count,
            cover_image=cover_image_dict
        )
    })