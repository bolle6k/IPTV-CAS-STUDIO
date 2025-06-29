# config.py

# Server- und Netzwerkeinstellungen
HOST = "127.0.0.1"
PORT_API = 6060          # Port für API (cas_api.py)
PORT_ADMIN = 5000        # Port für Admin-Dashboard (admin_dashboard.py)
PORT_SELF_SERVICE = 7000 # Port für Self-Service-Portal (self_service.py)
PORT_PAYMENT_API = 7070  # Port für Payment-API (payment_api.py)
PORT_CAS_API = 5555
# Sicherheits-Keys (im Produktivbetrieb ändern!)
MASTER_KEY = "supersecretmasterkey123"
API_SECRET_KEY = "supersecretapikey123"

# Datenbank
DB_PATH = "iptv_users.db"

# Logs
LOG_FILE = "admin_events.log"

# Schlüssel-Speicherpfad
KEYS_DIR = "keys"

# Redis für Rate Limiting
REDIS_HOST = "localhost"
REDIS_PORT = 6379

# Basis-URL für Streaming (HLS, Key-Downloads, Logos, etc.)
BASE_STREAM_URL = "https://stream.example.com/"

# Intervall für automatische Schlüsselrotation in Sekunden (z.B. 3600 = 1 Stunde)
ROTATION_INTERVAL = 3600

# Payment Provider (z.B. "stripe", "paypal")
PAYMENT_PROVIDER = "stripe"

# Stripe Einstellungen
STRIPE_API_KEY = "sk_test_deinkey"
STRIPE_WEBHOOK_SECRET = "whsec_deinsecret"
SUCCESS_URL = "https://deine-domain.de/selfservice/success"
CANCEL_URL = "https://deine-domain.de/selfservice/cancel"

# Paketpreise in Euro
PRICES = {
    "Kein Abo": {
        "1m": 0,
        "6m": 0,
        "12m": 0
    },
    "Basis": {
        "1m": 10,
        "6m": 55,
        "12m": 100
    },
    "Basis+": {
        "1m": 15,
        "6m": 80,
        "12m": 150
    },
    "Premium": {
        "1m": 20,
        "6m": 110,
        "12m": 210
    }
}
