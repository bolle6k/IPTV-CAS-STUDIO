# cas_api.py

import os
import threading
import datetime
import hashlib
import hmac
import logging
import time
from flask import Flask, request, jsonify, abort, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import config
from db_helper import DBHelper

app = Flask(__name__)
db = DBHelper(config.DB_PATH)

# Logger setup
logging.basicConfig(
    filename=config.LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# Rate limiter (using Redis backend)
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}",
    default_limits=["200 per day", "50 per hour"]
)
limiter.init_app(app)

def verify_signature(data: str, signature: str) -> bool:
    """HMAC-SHA256 signature verification."""
    expected = hmac.new(
        config.API_SECRET_KEY.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")

def log_request(user_id: str, action: str, success: bool = True):
    """Log each API request."""
    ip = request.remote_addr if request else "system"
    status = "SUCCESS" if success else "FAILURE"
    logging.info(f"{status} User:{user_id} IP:{ip} Action:{action}")

def generate_control_word() -> str:
    """Generate a new 16-byte hex control word."""
    return os.urandom(16).hex()

def automatic_key_rotation():
    """Background thread to rotate ECM keys for all active subscriptions."""
    while True:
        time.sleep(config.ROTATION_INTERVAL)
        users = db.get_all_users()
        now = datetime.datetime.utcnow().date()
        for user in users:
            username, hwid, paket, token, email = user
            sub = db.get_active_subscription(username)
            if not sub:
                continue
            _, _, sub_paket, start_str, end_str, active = sub
            end_date = datetime.date.fromisoformat(end_str)
            if end_date < now:
                continue
            cw = generate_control_word()
            db.store_key(cw, end_str, username, paket)
            log_request(username, "auto_key_rotate")

@app.route("/api/authenticate", methods=["POST"])
@limiter.limit("10/minute")
def authenticate():
    payload   = request.json or {}
    hwid      = payload.get("hwid", "")
    token     = payload.get("token", "")
    signature = request.headers.get("X-Signature", "")
    if not verify_signature(f"{hwid}{token}", signature):
        log_request("unknown", "authenticate", False)
        abort(403, "Invalid signature")

    user = db.get_user_by_token(token) if token else db.get_user_by_hwid(hwid)
    if not user:
        log_request("unknown", "authenticate", False)
        abort(404, "User not found")

    # Check active subscription
    sub = db.get_active_subscription(user[0])
    if not sub:
        log_request(user[0], "authenticate", False)
        abort(403, "Subscription expired or inactive")

    # Fetch or generate ECM key for this user
    key_record = db.get_valid_key_for_user(user[0])
    if key_record:
        cw = key_record[1]
    else:
        cw = generate_control_word()
        db.store_key(cw, sub[4], user[0], user[2])

    log_request(user[0], "authenticate")
    return jsonify({
        "status": "ok",
        "user": {
            "username": user[0],
            "hwid":     user[1],
            "paket":    user[2],
            "token":    user[3],
            "email":    user[4]
        },
        "ecm_key": cw
    })

@app.route("/api/stream_info", methods=["GET"])
@limiter.limit("30/minute")
def stream_info():
    token     = request.args.get("token", "")
    signature = request.headers.get("X-Signature", "")
    if not verify_signature(token, signature):
        log_request("unknown", "stream_info", False)
        abort(403, "Invalid or missing token/signature")

    user = db.get_user_by_token(token)
    if not user:
        log_request("unknown", "stream_info", False)
        abort(404, "User not found")

    sub = db.get_active_subscription(user[0])
    if not sub:
        log_request(user[0], "stream_info", False)
        abort(403, "Subscription expired or inactive")

    # Ensure an ECM key
    key_record = db.get_valid_key_for_user(user[0])
    if key_record:
        cw = key_record[1]
    else:
        cw = generate_control_word()
        db.store_key(cw, sub[4], user[0], user[2])

    log_request(user[0], "stream_info")
    return jsonify({
        "status": "ok",
        "stream_info": {
            "stream_url":  f"{config.BASE_STREAM_URL}{user[0]}/stream.m3u8",
            "aes_key":     cw,
            "watermark":   f"User-{user[0]}-WM",
            "logo_url":    f"{config.BASE_STREAM_URL}logos/logo.png"
        }
    })

@app.route("/api/token/create", methods=["POST"])
@limiter.limit("5/minute")
def create_token():
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {config.MASTER_KEY}":
        log_request("unknown", "create_token", False)
        abort(403, "Master key required")

    data     = request.json or {}
    username = data.get("username")
    hwid     = data.get("hwid")
    paket    = data.get("paket", "Basis")
    email    = data.get("email", "")

    if not username or not hwid:
        abort(400, "Missing username or hwid")

    token = os.urandom(16).hex()
    db.add_user(username, "", hwid, paket, token, email)

    # Immediately generate first ECM key
    sub = db.get_active_subscription(username)
    if sub:
        cw = generate_control_word()
        db.store_key(cw, sub[4], username, paket)

    log_request(username, "create_token")
    return jsonify({"status": "ok", "token": token})

@app.route("/api/token/revoke", methods=["POST"])
@limiter.limit("5/minute")
def revoke_token():
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {config.MASTER_KEY}":
        log_request("unknown", "revoke_token", False)
        abort(403, "Master key required")

    token = (request.json or {}).get("token")
    if not token:
        abort(400, "Missing token")

    db.delete_user_by_token(token)
    log_request("unknown", "revoke_token")
    return jsonify({"status": "ok"})

def run_api_server():
    app.run(host=config.HOST, port=config.PORT_API, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Start automatic rotation thread
    threading.Thread(target=automatic_key_rotation, daemon=True).start()
    run_api_server()
