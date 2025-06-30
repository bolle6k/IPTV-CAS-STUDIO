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
app.secret_key = config.MASTER_KEY

# DBHelper initialisieren
db = DBHelper(config.DB_PATH)

# Logging
logging.basicConfig(filename=config.LOG_FILE, level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

# Rate Limiter (Redis empfohlen)
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}",
    default_limits=["200 per day", "50 per hour"]
)
limiter.init_app(app)

ROTATION_INTERVAL = config.ROTATION_INTERVAL

def verify_signature(data, signature):
    computed = hmac.new(config.API_SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)

def log_request(user_id, action, success=True):
    ip = request.remote_addr if request else 'system'
    status = "SUCCESS" if success else "FAILURE"
    logging.info(f"{status} User:{user_id} IP:{ip} Action:{action}")

def save_keyfile(key_hex, filepath):
    key_bytes = bytes.fromhex(key_hex)
    with open(filepath, 'wb') as f:
        f.write(key_bytes)

@app.route('/api/authenticate', methods=['POST'])
@limiter.limit("10/minute")
def authenticate():
    content = request.json or {}
    hwid = content.get('hwid','')
    token = content.get('token','')
    signature = request.headers.get('X-Signature','')

    if not signature or not verify_signature(f'{hwid}{token}', signature):
        log_request('unknown','authenticate',False)
        abort(403, "Invalid signature")

    user = db.get_user_by_token(token) or db.get_user_by_hwid(hwid)
    if not user:
        log_request('unknown','authenticate',False)
        abort(404, "User not found")

    # Prüfen auf aktives Abo
    if not db.get_active_subscription(user[0]):
        log_request(user[0],'authenticate',False)
        abort(403, "Subscription expired or inactive")

    log_request(user[0],'authenticate',True)

    # ECM-Key holen oder neu erzeugen
    key = db.get_valid_key_for_user(user[0])
    if not key:
        key_id = db.store_key(
            key_value = os.urandom(16).hex(),
            valid_until = (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).isoformat(),
            user = user[0],
            paket = user[2]
        )
        key = db.get_key_by_id(key_id)[1]

    return jsonify({
        'status':'ok',
        'user': {
            'username': user[0],
            'hwid': user[1],
            'paket': user[2],
            'token': user[3],
            'email': user[4]
        },
        'ecm_key': key
    })

@app.route('/api/stream_info', methods=['GET'])
@limiter.limit("30/minute")
def stream_info():
    token = request.args.get('token','')
    signature = request.headers.get('X-Signature','')

    if not token or not signature or not verify_signature(token, signature):
        log_request('unknown','stream_info',False)
        abort(403, "Invalid or missing token/signature")

    user = db.get_user_by_token(token)
    if not user:
        log_request('unknown','stream_info',False)
        abort(404, "User not found")

    if not db.get_active_subscription(user[0]):
        log_request(user[0],'stream_info',False)
        abort(403, "Subscription expired or inactive")

    # Aktuellen ECM-Key holen
    key = db.get_valid_key_for_user(user[0])
    if not key:
        key_id = db.store_key(
            key_value = os.urandom(16).hex(),
            valid_until = (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).isoformat(),
            user = user[0],
            paket = user[2]
        )
        key = db.get_key_by_id(key_id)[1]

    log_request(user[0],'stream_info',True)

    return jsonify({
        'status':'ok',
        'stream_info': {
            'stream_url': f"{config.BASE_STREAM_URL}{user[0]}/stream.m3u8",
            'aes_key': key,
            'watermark': f"User-{user[0]}-WM",
            'logo_url': f"{config.BASE_STREAM_URL}logos/logo.png"
        }
    })

@app.route('/api/token/create', methods=['POST'])
@limiter.limit("5/minute")
def create_token():
    auth = request.headers.get('Authorization','')
    if auth != f"Bearer {config.MASTER_KEY}":
        log_request('unknown','create_token',False)
        abort(403, "Master key required")

    data = request.json or {}
    username = data.get('username')
    hwid     = data.get('hwid')
    paket    = data.get('paket','Basis')
    email    = data.get('email','')

    if not username or not hwid:
        abort(400, "Missing username or hwid")

    token = os.urandom(16).hex()
    db.add_user(username, '', hwid, paket, token, email)

    # Ersten ECM-Key erzeugen
    db.store_key(
        key_value = os.urandom(16).hex(),
        valid_until = (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).isoformat(),
        user = username,
        paket = paket
    )

    log_request(username,'create_token',True)
    return jsonify({'status':'ok','token':token})

@app.route('/api/token/revoke', methods=['POST'])
@limiter.limit("5/minute")
def revoke_token():
    auth = request.headers.get('Authorization','')
    if auth != f"Bearer {config.MASTER_KEY}":
        log_request('unknown','revoke_token',False)
        abort(403, "Master key required")

    token = (request.json or {}).get('token')
    if not token:
        abort(400, "Missing token")

    db.delete_user_by_token(token)
    log_request('unknown','revoke_token',True)
    return jsonify({'status':'ok'})

def automatic_key_rotation():
    while True:
        # Alle Nutzer mit aktivem Abo holen
        users = db.get_all_users()
        for u in users:
            username = u[0]
            if db.get_active_subscription(username):
                new_key = os.urandom(16).hex()
                valid_until = (datetime.datetime.utcnow() + datetime.timedelta(seconds=ROTATION_INTERVAL)).isoformat()
                db.store_key(new_key, valid_until, username, u[2])
                log_request(username,'auto_key_rotate',True)
        time.sleep(ROTATION_INTERVAL)

if __name__ == '__main__':
    # Starte Rotation-Thread
    threading.Thread(target=automatic_key_rotation, daemon=True).start()
    # Starte API
    app.run(host=config.HOST, port=config.PORT_API, debug=False)
