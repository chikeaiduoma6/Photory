from flask import Blueprint, jsonify, request

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


@auth_bp.post("/register")
def register():
  """注册接口占位"""
  data = request.get_json() or {}
  return jsonify({"message": "stub register ok", "data": data}), 201


@auth_bp.post("/login")
def login():
  """登录接口占位"""
  data = request.get_json() or {}
  email = data.get("email", "")
  return jsonify(
      {
          "access_token": "fake-token",
          "user": {
              "id": 1,
              "email": email,
              "username": "Demo User",
          },
      }
  )


@auth_bp.post("/send-register-code")
def send_register_code():
  """发送注册验证码占位。"""
  return jsonify({"message": "验证码发送成功"})


@auth_bp.post("/send-reset-code")
def send_reset_code():
  """发送重置密码验证码占位。"""
  return jsonify({"message": "重置验证码发送成功"})


@auth_bp.post("/verify-reset-code")
def verify_reset_code():
  """校验重置验证码占位。"""
  return jsonify({"message": "验证码验证通过"})
