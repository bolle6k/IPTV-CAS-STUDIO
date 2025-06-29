from flask import Flask, request, jsonify, abort
import config
from db_helper import DBHelper

app = Flask(__name__)
db = DBHelper(config.DB_PATH)

# Payment-Adapter Loader
if config.PAYMENT_PROVIDER == "stripe":
    from payment_providers.stripe_adapter import StripeAdapter as PaymentAdapter
elif config.PAYMENT_PROVIDER == "paypal":
    from payment_providers.paypal_adapter import PaypalAdapter as PaymentAdapter
else:
    raise Exception(f"Unsupported payment provider: {config.PAYMENT_PROVIDER}")

payment_adapter = PaymentAdapter()

@app.route('/create_payment_session', methods=['POST'])
def create_payment_session():
    data = request.json or {}
    username = data.get('username')
    paket = data.get('paket')
    zyklus = data.get('zyklus')  # '1m', '6m', '12m'

    if not username or not paket or zyklus not in ('1m', '6m', '12m'):
        return jsonify({"error": "Missing or invalid parameters"}), 400

    try:
        session_id = payment_adapter.create_payment_session(username, paket, zyklus)
        return jsonify({"session_id": session_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    # Der Adapter kümmert sich um die Verarbeitung und DB-Updates
    try:
        return payment_adapter.handle_webhook(request)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/payment_status/<payment_id>', methods=['GET'])
def payment_status(payment_id):
    try:
        status = payment_adapter.check_payment_status(payment_id)
        return jsonify({"status": status})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host=config.HOST, port=config.PORT_PAYMENT_API, debug=True)
