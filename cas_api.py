import os
import threading
import datetime
import hashlib
import hmac
import logging

from flask import Flask, request, jsonify, abort
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from db_helper import DBHelper
import config

app = Flask(__name__)
db = DBHelper(config.DB_PATH)

API_SECRET_KEY = os.getenv('API_SECRET_KEY', 'supersecretapikey')
MASTER_KEY = os.getenv('MASTER_KEY', 'supermasterkey')

logging.basicConfig(
    filename='api_access.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
limiter.init_app(app)

def verify_signature(data, signature):
    computed = hmac.new(API_SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)

def log_request(user_id, action, success=True, ip=None):
    if ip is None:
        ip = 'system'
    status = "SUCCESS" if success else "FAILURE"
    logging.info(f"{status} User:{user_id} IP:{ip} Action:{action}")

def generate_ecm_key():
    return os.urandom(16).hex()

def create_key_for_user(username, paket, valid_until):
    new_key = generate_ecm_key()
    db.store_key(new_key, valid_until, username, paket)
    return new_key

@app.route('/api/authenticate', methods=['POST'])
@limiter.limit("10/minute")
def authenticate():
    content = request.json or {}
    hwid = content.get('hwid', '')
    token = content.get('token', '')
    signature = request.headers.get('X-Signature', '')

    if not signature or not verify_signature(f'{hwid}{token}', signature):
        log_request('unknown', 'authenticate', False, ip=request.remote_addr)
        abort(403, "Invalid signature")

    user = db.get_user_by_token(token) if token else db.get_user_by_hwid(hwid)
    if not user:
        log_request('unknown', 'authenticate', False, ip=request.remote_addr)
        abort(404, "User not found")

    if not db.has_active_subscription(user[0]):
        log_request(user[0], 'authenticate', False, ip=request.remote_addr)
        abort(403, "Subscription expired or inactive")

    log_request(user[0], 'authenticate', True, ip=request.remote_addr)

    ecm_key = db.get_valid_key_for_user(user[0])
    if not ecm_key:
        abo = db.get_active_subscription(user[0])
        valid_until = abo[4] if abo else (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).isoformat()
        ecm_key = create_key_for_user(user[0], user[2], valid_until)

    return jsonify({
        'status': 'ok',
        'user': {
            'username': user[0],
            'hwid': user[1],
            'paket': user[2],
            'token': user[3],
            'email': user[4]
        },
        'keys': [ecm_key]
    })

@app.route('/api/stream_info', methods=['GET'])
@limiter.limit("30/minute")
def stream_info():
    token = request.args.get('token', '')
    signature = request.headers.get('X-Signature', '')

    if not token or not signature or not verify_signature(token, signature):
        log_request('unknown', 'stream_info', False)
        abort(403, "Invalid or missing token/signature")

    user = db.get_user_by_token(token)
    if not user:
        log_request('unknown', 'stream_info', False)
        abort(404, "User not found")

    if not db.has_active_subscription(user[0]):
        log_request(user[0], 'stream_info', False)
        abort(403, "Subscription expired or inactive")

    ecm_key = db.get_valid_key_for_user(user[0])
    if not ecm_key:
        abo = db.get_active_subscription(user[0])
        valid_until = abo[4] if abo else (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).isoformat()
        ecm_key = create_key_for_user(user[0], user[2], valid_until)

    log_request(user[0], 'stream_info')

    stream_data = {
        'stream_url': 'https://example.com/hls/stream.m3u8',
        'aes_key': ecm_key,
        'watermark': 'UserWatermark123',
        'logo_url': 'https://example.com/logos/logo.png'
    }
    return jsonify({'status': 'ok', 'stream_info': stream_data})

@app.route('/api/token/create', methods=['POST'])
@limiter.limit("5/minute")
def create_token():
    auth_header = request.headers.get('Authorization', '')
    if auth_header != f"Bearer {MASTER_KEY}":
        log_request('unknown', 'create_token', False)
        abort(403, "Unauthorized - master key required")

    content = request.json or {}
    username = content.get('username', '')
    hwid = content.get('hwid', '')
    paket = content.get('paket', 'Basis')

    if not username or not hwid:
        abort(400, "Missing username or hwid")

    token = os.urandom(16).hex()
    db.add_user(username, '', hwid, paket, token, email='')

    abo = db.get_active_subscription(username)
    valid_until = abo[4] if abo else (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).isoformat()
    create_key_for_user(username, paket, valid_until)

    log_request(username, 'create_token')
    return jsonify({'status': 'ok', 'token': token})

@app.route('/api/token/revoke', methods=['POST'])
@limiter.limit("5/minute")
def revoke_token():
    auth_header = request.headers.get('Authorization', '')
    if auth_header != f"Bearer {MASTER_KEY}":
        log_request('unknown', 'revoke_token', False)
        abort(403, "Unauthorized - master key required")

    content = request.json or {}
    token = content.get('token', '')
    if not token:
        abort(400, "Missing token")

    user = db.get_user_by_token(token)
    if user:
        db.delete_user(user[0])
    log_request('unknown', 'revoke_token')
    return jsonify({'status': 'ok'})

def automatic_key_rotation():
    ROTATION_INTERVAL = 3600  # 1 Stunde
    while True:
        now = datetime.datetime.utcnow()
        valid_until = (now + datetime.timedelta(seconds=ROTATION_INTERVAL)).isoformat()

        users = db.get_all_users()
        for user in users:
            username = user[0]
            if not db.has_active_subscription(username):
                continue

            paket = db.get_best_active_package(username)
            new_key = generate_ecm_key()
            db.store_key(new_key, valid_until, username, paket)
            log_request(username, 'auto_key_rotate', ip='system')

        threading.Event().wait(ROTATION_INTERVAL)

if __name__ == '__main__':
    threading.Thread(target=automatic_key_rotation, daemon=True).start()
    app.run(host='0.0.0.0', port=config.PORT_CAS_API, debug=False, use_reloader=False)
