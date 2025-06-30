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

# Logging
logging.basicConfig(
    filename=config.LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# Rate limiter (Redis-Backend)
limiter = Limiter(
    app,
    key_func=get_remote_address,
    storage_uri=f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}",
    default_limits=["200 per day", "50 per hour"]
)

def verify_signature(data: str, signature: str) -> bool:
    expected = hmac.new(
        config.API_SECRET_KEY.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

def log_request(user_id: str, action: str, success: bool = True):
    ip = request.remote_addr if request else "system"
    status = "SUCCESS" if success else "FAILURE"
    logging.info(f"{status} User:{user_id} IP:{ip} Action:{action}")

def generate_control_word() -> str:
    """Neuen Control Word (ECM-Key) erzeugen."""
    return os.urandom(16).hex()

def automatic_key_rotation():
    """Periodisch für alle Nutzer mit aktivem Abo neue Keys erstellen."""
    while True:
        time.sleep(config.ROTATION_INTERVAL)
        users = db.get_all_users()
        now = datetime.datetime.utcnow().date().isoformat()
        for u in users:
            username, hwid, paket, token, email = u
            sub = db.get_active_subscription(username)
            if not sub:
                continue
            # Erzeuge und speichere neuen CW
            cw = generate_control_word()
            valid_until = (datetime.date.fromisoformat(sub[4])  # end_date
                           ).isoformat()
            db.store_key(cw, valid_until, username, paket)
            log_request(username, "auto_key_rotate")

# --- API Endpoints ---

@app.route("/api/authenticate", methods=["POST"])
@limiter.limit("10/minute")
def authenticate():
    data = request.json or {}
    hwid = data.get("hwid", "")
    token = data.get("token", "")
    sig   = request.headers.get("X-Signature", "")
    if not (hwid or token) or not verify_signature(f"{hwid}{token}", sig):
        log_request("unknown", "authenticate", False)
        abort(403, "Invalid signature or missing credentials")

    # Nutzer suchen
    user = db.get_user_by_token(token) if token else db.get_user_by_hwid(hwid)
    if not user:
        log_request("unknown", "authenticate", False)
        abort(404, "User not found")

    username = user[0]
    # Abo prüfen
    if not db.get_active_subscription(username):
        log_request(username, "authenticate", False)
        abort(403, "Subscription inactive or expired")

    # Key holen / neu anlegen
    key = db.get_valid_key_for_user(username)
    if not key:
        key = generate_control_word()
        end = db.get_active_subscription(username)[4]
        db.store_key(key, end, username, user[2])

    log_request(username, "authenticate")
    return jsonify({
        "status": "ok",
        "user": {
            "username": user[0],
            "hwid": user[1],
            "paket": user[2],
            "token": user[3],
            "email": user[4]
        },
        "ecm_key": key
    })

@app.route("/api/stream_info", methods=["GET"])
@limiter.limit("30/minute")
def stream_info():
    token = request.args.get("token", "")
    sig   = request.headers.get("X-Signature", "")
    if not token or not verify_signature(token, sig):
        log_request("unknown", "stream_info", False)
        abort(403, "Invalid or missing token/signature")

    user = db.get_user_by_token(token)
    if not user:
        log_request("unknown", "stream_info", False)
        abort(404, "User not found")

    username = user[0]
    if not db.get_active_subscription(username):
        log_request(username, "stream_info", False)
        abort(403, "Subscription inactive or expired")

    # Key holen oder neu erzeugen
    key = db.get_valid_key_for_user(username)
    if not key:
        key = generate_control_word()
        end = db.get_active_subscription(username)[4]
        db.store_key(key, end, username, user[2])

    log_request(username, "stream_info")
    return jsonify({
        "status": "ok",
        "stream_url": f"{config.BASE_STREAM_URL}{username}/stream.m3u8",
        "aes_key": key,
        "watermark": f"WM-{username}",
        "logo_url": config.BASE_STREAM_URL + "logos/logo.png"
    })

@app.route("/api/token/create", methods=["POST"])
@limiter.limit("5/minute")
def create_token():
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {config.MASTER_KEY}":
        log_request("unknown", "create_token", False)
        abort(403, "Master key required")

    data = request.json or {}
    username = data.get("username", "")
    hwid     = data.get("hwid", "")
    paket    = data.get("paket", "Basis")
    email    = data.get("email", "")

    if not (username and hwid):
        abort(400, "Missing username or hwid")

    token = os.urandom(16).hex()
    db.add_user(username, "", hwid, paket, token, email)
    # Sofort einen Key anlegen
    cw = generate_control_word()
    # Laufzeit aus default-Abo (heute + 30 Tage)
    end = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    db.store_key(cw, end, username, paket)

    log_request(username, "create_token")
    return jsonify({"status": "ok", "token": token})

@app.route("/api/token/revoke", methods=["POST"])
@limiter.limit("5/minute")
def revoke_token():
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {config.MASTER_KEY}":
        log_request("unknown", "revoke_token", False)
        abort(403, "Master key required")

    data = request.json or {}
    token = data.get("token", "")
    if not token:
        abort(400, "Missing token")

    db.delete_user_by_token(token)
    log_request("unknown", "revoke_token")
    return jsonify({"status": "ok"})

# Starte Auto-Rotation im Hintergrund
if __name__ == "__main__":
    threading.Thread(target=automatic_key_rotation, daemon=True).start()
    app.run(host=config.HOST, port=config.PORT_API, debug=False)
