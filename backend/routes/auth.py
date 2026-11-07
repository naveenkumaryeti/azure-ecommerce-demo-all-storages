from flask import Blueprint, g, jsonify, request

from services import auth_service as auth

bp = Blueprint("auth", __name__)


@bp.post("/api/auth/register")
def register():
    d = request.get_json(silent=True) or {}
    u = auth.create_user(d.get("email"), d.get("name"), d.get("password"), "customer")
    token, pub = auth.login(d.get("email"), d.get("password"))
    return jsonify({"token": token, "user": pub}), 201


@bp.post("/api/auth/login")
def login():
    d = request.get_json(silent=True) or {}
    token, pub = auth.login(d.get("email"), d.get("password"))
    return jsonify({"token": token, "user": pub})


@bp.get("/api/auth/me")
@auth.require()
def me():
    return jsonify(g.user)
