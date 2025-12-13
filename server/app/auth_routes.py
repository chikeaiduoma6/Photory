import re
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, verify_jwt_in_request
from sqlalchemy import or_
from .extensions import db
from .models import User, LoginEvent

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def _validate_registration(data: dict) -> tuple[bool, str]:
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    confirm_password = data.get("confirmPassword") or data.get("confirm_password") or ""
    if not username:
        return False, "用户名必填"
    if len(password) < 6:
        return False, "密码至少 6 位"
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        return False, "密码需包含字母和数字"
    if not EMAIL_RE.fullmatch(email):
        return False, "邮箱格式不正确"
    if password != confirm_password:
        return False, "两次密码不一致"
    return True, ""

def _validate_password_strength(password: str) -> tuple[bool, str]:
    if not password:
        return False, "密码不能为空"
    if len(password) < 6:
        return False, "密码至少 6 位"
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        return False, "密码需包含字母和数字"
    return True, ""


def _current_user() -> User:
    verify_jwt_in_request(optional=False, locations=["headers", "query_string"])
    uid = int(get_jwt_identity())
    return User.query.get_or_404(uid)


def _client_ip() -> str | None:
    xff = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return xff or request.remote_addr


def _record_login(user_id: int) -> None:
    try:
        evt = LoginEvent(
            user_id=user_id,
            ip=_client_ip(),
            user_agent=(request.headers.get("User-Agent") or "")[:255] or None,
        )
        db.session.add(evt)
        db.session.commit()
    except Exception:
        db.session.rollback()


@auth_bp.post("/register")
def register():
    data = request.get_json() or {}
    ok, msg = _validate_registration(data)
    if not ok:
        return jsonify({"message": msg}), 400

    username = data["username"].strip()
    email = data["email"].strip().lower()

    if User.query.filter_by(username=username).first():
        return jsonify({"message": "用户名已存在"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"message": "邮箱已存在"}), 409

    user = User(username=username, email=email)
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "注册成功", "user": user.to_dict()}), 201

@auth_bp.post("/login")
def login():
    data = request.get_json() or {}
    identifier = (data.get("identifier") or data.get("email") or "").strip()
    password = data.get("password") or ""

    if not identifier:
        return jsonify({"message": "请输入邮箱或用户名"}), 400

    user = User.query.filter(
        or_(User.email == identifier.lower(), User.username == identifier)
    ).first()

    if not user or not user.check_password(password):
        return jsonify({"message": "账号或密码错误"}), 401

    token = create_access_token(identity=str(user.id), additional_claims={"username": user.username})
    _record_login(user.id)
    return jsonify({"access_token": token, "user": user.to_dict()})


@auth_bp.get("/me")
def me():
    user = _current_user()
    events = (
        LoginEvent.query.filter_by(user_id=user.id)
        .order_by(LoginEvent.created_at.desc())
        .limit(5)
        .all()
    )
    return jsonify({"message": "ok", "user": user.to_dict(), "login_events": [e.to_dict() for e in events]})


@auth_bp.post("/change-password")
def change_password():
    user = _current_user()
    data = request.get_json() or {}
    current_password = data.get("current_password") or ""
    new_password = data.get("new_password") or ""

    if not user.check_password(current_password):
        return jsonify({"message": "当前密码不正确"}), 400
    ok, msg = _validate_password_strength(new_password)
    if not ok:
        return jsonify({"message": msg}), 400

    user.set_password(new_password)
    db.session.commit()
    return jsonify({"message": "ok"})
