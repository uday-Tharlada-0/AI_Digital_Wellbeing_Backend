import re

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import or_

from extensions import db
from models import User


auth_bp = Blueprint("auth", __name__)
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _validate_registration(data):
    name = str(data.get("name", "")).strip()
    username = str(data.get("username", "")).strip().lower()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not name or not username or not email or not password:
        return "Name, username, email, and password are required."
    if len(username) < 3:
        return "Username must contain at least 3 characters."
    if not EMAIL_PATTERN.match(email):
        return "Enter a valid email address."
    if len(password) < 8:
        return "Password must contain at least 8 characters."
    if User.query.filter(or_(User.username == username, User.email == email)).first():
        return "That username or email is already registered."
    return None


def _login_user(user):
    session.clear()
    session["user_id"] = user.id
    session["user_name"] = user.name


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter(
            or_(User.username == identifier, User.email == identifier)
        ).first()
        if not user or not user.check_password(password):
            error = "Incorrect username/email or password."
        else:
            _login_user(user)
            return redirect(url_for("index"))

    return render_template("login.html", error=error)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        data = request.form.to_dict()
        error = _validate_registration(data)
        if not error and data.get("password") != data.get("confirm_password"):
            error = "Passwords do not match."
        if not error:
            user = User(
                name=data["name"].strip(),
                username=data["username"].strip().lower(),
                email=data["email"].strip().lower(),
            )
            user.set_password(data["password"])
            db.session.add(user)
            db.session.commit()
            _login_user(user)
            return redirect(url_for("index"))

    return render_template("register.html", error=error)


@auth_bp.post("/logout")
def logout():
    session.clear()
    if request.is_json:
        return jsonify({"message": "Signed out successfully."})
    return redirect(url_for("auth.login"))


@auth_bp.get("/api/auth/me")
def current_user():
    user = User.query.get(session.get("user_id"))
    if not user:
        session.clear()
        return jsonify({"authenticated": False}), 401
    return jsonify({"authenticated": True, "user": user.to_dict()})