from datetime import datetime
from .extensions import bcrypt, db

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(raw_password).decode("utf-8")

    def check_password(self, raw_password: str) -> bool:
        if not self.password_hash:
            return False
        try:
            if self.password_hash.startswith("$2"):
                return bcrypt.check_password_hash(self.password_hash, raw_password)
        except ValueError:
            pass
        return self.password_hash == raw_password

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat(),
        }


image_tags = db.Table(
    "image_tags",
    db.Column("image_id", db.Integer, db.ForeignKey("images.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
)


class Tag(db.Model):
    __tablename__ = "tags"
    __table_args__ = (db.UniqueConstraint("name", "user_id", name="uq_tags_name_user"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    name = db.Column(db.String(64), nullable=False)
    color = db.Column(db.String(16), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    images = db.relationship("Image", secondary=image_tags, back_populates="tags", lazy="dynamic")

    def to_dict(self, include_count: bool = False, image_count: int | None = None) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "created_at": self.created_at.isoformat(),
        }
        if include_count:
            data["count"] = image_count if image_count is not None else self.images.filter_by(deleted_at=None).count()
        return data


class ImageVersion(db.Model):
    __tablename__ = "image_versions"
    id = db.Column(db.Integer, primary_key=True)
    image_id = db.Column(db.Integer, db.ForeignKey("images.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    note = db.Column(db.String(255), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    thumb_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Image(db.Model):
    __tablename__ = "images"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(64), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    taken_at = db.Column(db.DateTime, nullable=True)
    camera = db.Column(db.String(128), nullable=True)
    lens = db.Column(db.String(128), nullable=True)
    iso = db.Column(db.String(32), nullable=True)
    exposure = db.Column(db.String(32), nullable=True)
    aperture = db.Column(db.String(32), nullable=True)
    focal = db.Column(db.String(32), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    exif_json = db.Column(db.Text, nullable=True)
    thumb_path = db.Column(db.String(255), nullable=True)
    visibility = db.Column(db.String(16), default="private", nullable=False)
    folder = db.Column(db.String(128), default="默认图库", nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref=db.backref("images", lazy=True))
    tags = db.relationship("Tag", secondary=image_tags, back_populates="images", lazy="joined")
    versions = db.relationship("ImageVersion", backref="image", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "filename": self.filename,
            "original_name": self.original_name,
            "mime_type": self.mime_type,
            "size": self.size,
            "width": self.width,
            "height": self.height,
            "taken_at": self.taken_at.isoformat() if self.taken_at else None,
            "camera": self.camera,
            "lens": self.lens,
            "iso": self.iso,
            "exposure": self.exposure,
            "aperture": self.aperture,
            "focal": self.focal,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "exif_json": self.exif_json,
            "thumb_path": self.thumb_path,
            "visibility": self.visibility,
            "folder": self.folder or "默认图库",
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "tags": [t.name for t in self.tags],
            "tag_objects": [{"id": t.id, "name": t.name, "color": t.color} for t in self.tags],
        }
