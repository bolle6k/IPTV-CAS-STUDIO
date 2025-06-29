# api_cas.py

from flask import Flask, request, jsonify, abort
from datetime import datetime, timedelta
import secrets

app = Flask(__name__)

# Dummy-Datenbank
TOKENS = {
    "ABC123": {
        "user": "admin",
        "expires": datetime.utcnow() + timedelta(hours=1),
        "hwid": "HWID-1234"
    }
}

@app.route("/validate", methods=["POST"])
def validate_token():
    data = request.json
    token = data.get("token")
    hwid = data.get("hwid")

    if token not in TOKENS:
        return abort(403, description="Ungültiger Token")

    info = TOKENS[token]
    if info["expires"] < datetime.utcnow():
        return abort(403, description="Token abgelaufen")

    if info["hwid"] != hwid:
        return abort(403, description="HWID stimmt nicht überein")

    return jsonify({"status": "ok", "user": info["user"]})

@app.route("/get_key", methods=["GET"])
def get_stream_key():
    token = request.args.get("token")
    if token not in TOKENS:
        return abort(403, description="Token ungültig")

    key = secrets.token_hex(16)
    return jsonify({"key": key})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
