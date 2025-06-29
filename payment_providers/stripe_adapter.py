import stripe
import config
from flask import jsonify

stripe.api_key = config.STRIPE_API_KEY

class StripeAdapter:
    def __init__(self):
        pass

    def create_payment_session(self, username, paket, zyklus):
        # Preis in Cent
        price_map = {
            'Basis': {'1m': 1000, '6m': 5500, '12m': 10000},
            'Basis+': {'1m': 1500, '6m': 8000, '12m': 15000},
            'Premium': {'1m': 2000, '6m': 11000, '12m': 21000}
        }

        amount = price_map.get(paket, {}).get(zyklus)
        if amount is None:
            raise ValueError("Ungültiges Paket oder Zyklus")

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': f'{paket} Abo ({zyklus})'},
                    'unit_amount': amount,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f'{config.SUCCESS_URL}?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=config.CANCEL_URL,
            metadata={'username': username, 'paket': paket, 'zyklus': zyklus}
        )
        return session.id

    def handle_webhook(self, request):
        payload = request.data
        sig_header = request.headers.get('stripe-signature')
        endpoint_secret = config.STRIPE_WEBHOOK_SECRET

        import stripe.error
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except ValueError:
            return jsonify({'error': 'Invalid payload'}), 400
        except stripe.error.SignatureVerificationError:
            return jsonify({'error': 'Invalid signature'}), 400

        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            username = session['metadata']['username']
            paket = session['metadata']['paket']
            zyklus = session['metadata']['zyklus']
            payment_id = session['id']
            amount = session['amount_total']
            currency = session['currency']
            status = 'paid'

            # Zahl in DB speichern (db_helper.py)
            db = config.db if hasattr(config, 'db') else None
            if db is not None:
                db.add_payment(payment_id, username, paket, zyklus, amount, currency, status)
                # Abo aktualisieren oder neu anlegen
                from datetime import datetime, timedelta
                today = datetime.utcnow().date()
                if zyklus == '1m':
                    new_end = today + timedelta(days=30)
                elif zyklus == '6m':
                    new_end = today + timedelta(days=183)
                else:
                    new_end = today + timedelta(days=365)
                db.add_subscription(username, paket, today.isoformat(), new_end.isoformat())
                db.update_user_package(username, paket)

        return jsonify({'status': 'success'})

    def check_payment_status(self, payment_id):
        payment = db.get_payment_by_id(payment_id)
        if payment:
            return payment[6]  # status
        return 'unknown'
