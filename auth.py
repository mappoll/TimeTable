"""Single-owner WebAuthn. Persistent public credentials live outside the source tree."""
from contextlib import contextmanager
from datetime import timedelta
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import secrets
import sqlite3
import time
from urllib.parse import urlsplit

from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, session, url_for
from webauthn import (base64url_to_bytes, generate_authentication_options,
                      generate_registration_options, options_to_json,
                      verify_authentication_response, verify_registration_response)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor,
                                    ResidentKeyRequirement, UserVerificationRequirement)

auth = Blueprint("auth", __name__)
CEREMONY_SECONDS = 300
PUBLIC_ENDPOINTS = {"static", "auth.login", "auth.setup", "auth.registration_options",
                    "auth.registration_verify", "auth.authentication_options", "auth.authentication_verify"}


@contextmanager
def database(path=None):
    connection = sqlite3.connect(path or current_app.config["AUTH_DB_PATH"], timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_auth(app):
    enabled = os.environ.get("TIMETABLE_AUTH_ENABLED") != "0"
    app.config["AUTH_ENABLED"] = enabled
    app.register_blueprint(auth)
    app.before_request(require_authentication)
    app.after_request(protect_response)
    app.context_processor(lambda: {"csrf_token": csrf_token})
    if not enabled:
        return

    secret = os.environ.get("SECRET_KEY", "")
    if len(secret) < 32:
        raise RuntimeError("SECRET_KEY must be set to a random value of at least 32 characters")
    setup_token = os.environ.get("PASSKEY_SETUP_TOKEN", "")
    if setup_token and len(setup_token) < 32:
        raise RuntimeError("PASSKEY_SETUP_TOKEN must be empty or a random value of at least 32 characters")
    db_value = os.environ.get("TIMETABLE_AUTH_DB_PATH", "")
    if not db_value or not Path(db_value).is_absolute():
        raise RuntimeError("TIMETABLE_AUTH_DB_PATH must be an absolute external file path")
    db_path = Path(db_value).resolve()
    if db_path.is_relative_to(Path(app.root_path).resolve()):
        raise RuntimeError("TIMETABLE_AUTH_DB_PATH must be outside the source directory")
    if not db_path.parent.is_dir():
        raise RuntimeError("TIMETABLE_AUTH_DB_PATH parent directory must already exist")

    rp_id = os.environ.get("WEBAUTHN_RP_ID", "")
    origin = os.environ.get("WEBAUTHN_ORIGIN", "")
    try:
        parsed = urlsplit(origin)
        valid_origin = (parsed.scheme == "https" and parsed.hostname == rp_id and
                        not parsed.path and not parsed.query and not parsed.fragment and
                        not parsed.username and not parsed.password and parsed.port != 0)
    except ValueError:
        valid_origin = False
    if not rp_id or any(c in rp_id for c in "/:@ ") or not valid_origin:
        raise RuntimeError("WEBAUTHN_RP_ID must be a hostname; WEBAUTHN_ORIGIN its HTTPS origin without a path")
    cookie_path = os.environ.get("TIMETABLE_SESSION_COOKIE_PATH", "/")
    if not cookie_path.startswith("/") or any(c in cookie_path for c in ";\r\n?#"):
        raise RuntimeError("TIMETABLE_SESSION_COOKIE_PATH must be a URL path")
    try:
        hours = float(os.environ.get("TIMETABLE_SESSION_HOURS", "16"))
        if not math.isfinite(hours) or not 0 < hours <= 8760:
            raise ValueError
    except ValueError:
        raise RuntimeError("TIMETABLE_SESSION_HOURS must be positive and at most 8760") from None
    app.config.update(SECRET_KEY=secret, AUTH_DB_PATH=str(db_path), WEBAUTHN_RP_ID=rp_id,
                      WEBAUTHN_ORIGIN=origin, PASSKEY_SETUP_TOKEN=setup_token,
                      SESSION_COOKIE_NAME="timetable_session", SESSION_COOKIE_SECURE=True,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      SESSION_COOKIE_PATH=cookie_path, PERMANENT_SESSION_LIFETIME=timedelta(hours=hours),
                      SESSION_REFRESH_EACH_REQUEST=False, MAX_CONTENT_LENGTH=65536)
    try:
        with database(str(db_path)) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE IF NOT EXISTS auth_owner (
                id INTEGER PRIMARY KEY CHECK(id = 1), user_handle BLOB NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            db.execute("""CREATE TABLE IF NOT EXISTS credentials (
                id INTEGER PRIMARY KEY, credential_id BLOB NOT NULL UNIQUE,
                credential_public_key BLOB NOT NULL, sign_count INTEGER NOT NULL,
                transports TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            db.execute("""CREATE TABLE IF NOT EXISTS auth_challenges (
                digest BLOB PRIMARY KEY, expires_at REAL NOT NULL)""")
            db.execute("INSERT OR IGNORE INTO auth_owner (id, user_handle) VALUES (1, ?)", (secrets.token_bytes(32),))
            # A write transaction also verifies directory/journal permissions on each startup.
            db.execute("DELETE FROM auth_challenges WHERE expires_at < ?", (time.time(),))
    except (sqlite3.Error, OSError):
        raise RuntimeError("Authentication DB initialization failed; check file and parent read/write permissions") from None


def is_authenticated():
    issued = session.get("authenticated_at")
    return (session.get("authenticated") is True and isinstance(issued, (int, float)) and
            0 <= time.time() - issued < current_app.permanent_session_lifetime.total_seconds())


def require_authentication():
    if not current_app.config["AUTH_ENABLED"]:
        return
    if session.get("authenticated") and not is_authenticated():
        session.clear()
    if request.endpoint not in PUBLIC_ENDPOINTS and not is_authenticated():
        return redirect(url_for("auth.login"))


def protect_response(response):
    if current_app.config["AUTH_ENABLED"] and request.endpoint != "static":
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
    return response


@auth.before_request
def protect_auth_posts():
    if not current_app.config["AUTH_ENABLED"]:
        abort(404)
    if request.method == "POST":
        token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        if not expected or not hmac.compare_digest(token.encode(), expected.encode()):
            abort(400, "操作をやり直してください。")
        if request.headers.get("Origin") not in (None, current_app.config["WEBAUTHN_ORIGIN"]):
            abort(400, "操作をやり直してください。")


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def has_credentials(db):
    return db.execute("SELECT 1 FROM credentials LIMIT 1").fetchone() is not None


def setup_allowed():
    issued = session.get("setup_authorized_at", 0)
    with database() as db:
        return (bool(current_app.config["PASSKEY_SETUP_TOKEN"]) and
                0 <= time.time() - issued < CEREMONY_SECONDS and not has_credentials(db))


def save_challenge(challenge, kind):
    previous = session.pop("challenge", None)
    with database() as db:
        if previous:
            db.execute("DELETE FROM auth_challenges WHERE digest = ?", (hashlib.sha256(base64url_to_bytes(previous)).digest(),))
        db.execute("DELETE FROM auth_challenges WHERE expires_at < ?", (time.time(),))
        db.execute("INSERT INTO auth_challenges VALUES (?, ?)",
                   (hashlib.sha256(challenge).digest(), time.time() + CEREMONY_SECONDS))
    session["challenge"] = bytes_to_base64url(challenge)
    session["ceremony"] = kind


def consume_challenge(kind):
    encoded = session.pop("challenge", None)
    ceremony = session.pop("ceremony", None)
    if not encoded:
        raise ValueError("Missing ceremony")
    challenge = base64url_to_bytes(encoded)
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        digest = hashlib.sha256(challenge).digest()
        row = db.execute("SELECT expires_at FROM auth_challenges WHERE digest = ?", (digest,)).fetchone()
        db.execute("DELETE FROM auth_challenges WHERE digest = ?", (digest,))
    if ceremony != kind or row is None or row["expires_at"] < time.time():
        raise ValueError("Expired ceremony")
    return challenge


def finish_login():
    session.clear()
    session["authenticated"] = True
    session["authenticated_at"] = time.time()
    session.permanent = True
    return jsonify(redirect=url_for("index"))


@auth.get("/login")
def login():
    if is_authenticated():
        return redirect(url_for("index"))
    return render_template("auth.html", mode="login")


@auth.route("/setup", methods=["GET", "POST"])
def setup():
    with database() as db:
        if has_credentials(db):
            return render_template("auth.html", mode="closed", message="Passkeyは登録済みです。ログインしてください。"), 403
    message = None
    if request.method == "POST":
        expected = current_app.config["PASSKEY_SETUP_TOKEN"]
        supplied = request.form.get("setup_token", "")
        session.pop("setup_authorized_at", None)
        if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
            return render_template("auth.html", mode="setup", message="登録を許可できません。トークンを確認してください。"), 403
        session["setup_authorized_at"] = time.time()
        return redirect(url_for("auth.setup"))
    return render_template("auth.html", mode="register" if setup_allowed() else "setup", message=message)


@auth.post("/auth/register/options")
def registration_options():
    if not setup_allowed():
        abort(403)
    with database() as db:
        owner = db.execute("SELECT user_handle FROM auth_owner WHERE id = 1").fetchone()
    options = generate_registration_options(
        rp_id=current_app.config["WEBAUTHN_RP_ID"], rp_name="TimeTable",
        user_id=owner["user_handle"], user_name="owner", user_display_name="TimeTable owner",
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED))
    save_challenge(options.challenge, "registration")
    return current_app.response_class(options_to_json(options), mimetype="application/json")


@auth.post("/auth/register/verify")
def registration_verify():
    try:
        challenge = consume_challenge("registration")
        if not setup_allowed():
            raise ValueError("Setup closed")
        credential = request.get_json(silent=True)
        if not isinstance(credential, dict):
            raise ValueError("Invalid response")
        verified = verify_registration_response(
            credential=credential, expected_challenge=challenge,
            expected_rp_id=current_app.config["WEBAUTHN_RP_ID"],
            expected_origin=current_app.config["WEBAUTHN_ORIGIN"], require_user_verification=True)
        transports = credential.get("response", {}).get("transports", [])
        if not isinstance(transports, list) or any(t not in ("usb", "nfc", "ble", "internal", "hybrid", "smart-card") for t in transports):
            transports = []
        with database() as db:
            db.execute("BEGIN IMMEDIATE")
            if has_credentials(db):
                raise ValueError("Already registered")
            db.execute("""INSERT INTO credentials
                (credential_id, credential_public_key, sign_count, transports) VALUES (?, ?, ?, ?)""",
                       (verified.credential_id, verified.credential_public_key, verified.sign_count, json.dumps(transports)))
    except (WebAuthnException, ValueError, TypeError, KeyError):
        return jsonify(error="登録できませんでした。操作をやり直してください。"), 400
    finally:
        session.pop("setup_authorized_at", None)
    return finish_login()


@auth.post("/auth/login/options")
def authentication_options():
    with database() as db:
        rows = db.execute("SELECT credential_id FROM credentials").fetchall()
    if not rows:
        return jsonify(error="登録されているPasskeyで認証してください。"), 400
    options = generate_authentication_options(
        rp_id=current_app.config["WEBAUTHN_RP_ID"],
        allow_credentials=[PublicKeyCredentialDescriptor(id=row["credential_id"]) for row in rows],
        user_verification=UserVerificationRequirement.REQUIRED)
    save_challenge(options.challenge, "authentication")
    return current_app.response_class(options_to_json(options), mimetype="application/json")


@auth.post("/auth/login/verify")
def authentication_verify():
    try:
        challenge = consume_challenge("authentication")
        credential = request.get_json(silent=True)
        if (not isinstance(credential, dict) or not isinstance(credential.get("id"), str)
                or not isinstance(credential.get("response"), dict)):
            raise ValueError("Invalid response")
        credential_id = base64url_to_bytes(credential["id"])
        with database() as db:
            # Serialize counter checks/updates from simultaneous assertions.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM credentials WHERE credential_id = ?", (credential_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown credential")
            handle = credential.get("response", {}).get("userHandle")
            if handle is not None:
                owner = db.execute("SELECT user_handle FROM auth_owner WHERE id = 1").fetchone()
                if not hmac.compare_digest(base64url_to_bytes(handle), owner["user_handle"]):
                    raise ValueError("Unknown user")
            verified = verify_authentication_response(
                credential=credential, expected_challenge=challenge,
                expected_rp_id=current_app.config["WEBAUTHN_RP_ID"],
                expected_origin=current_app.config["WEBAUTHN_ORIGIN"],
                credential_public_key=row["credential_public_key"],
                credential_current_sign_count=row["sign_count"], require_user_verification=True)
            db.execute("UPDATE credentials SET sign_count = ? WHERE id = ?", (verified.new_sign_count, row["id"]))
    except (WebAuthnException, ValueError, TypeError, KeyError):
        return jsonify(error="登録されているPasskeyで認証してください。"), 400
    return finish_login()


@auth.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
