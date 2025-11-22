import re
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token
from .extensions import db
from .models import User

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
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"message": "邮箱或密码错误"}), 401

    # PyJWT 2.8+ 要求 sub/identity 为字符串
    token = create_access_token(identity=str(user.id), additional_claims={"username": user.username})
    return jsonify({"access_token": token, "user": user.to_dict()})
