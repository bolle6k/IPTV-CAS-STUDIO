import sqlite3
import threading
import datetime

class DBHelper:
    def __init__(self, db_path='iptv_users.db'):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._create_tables()

    def _connect(self):
        return sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)

    def _create_tables(self):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            # Nutzer
            c.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password TEXT,
                    hwid TEXT,
                    paket TEXT,
                    token TEXT UNIQUE,
                    email TEXT
                )
            ''')
            # Schlüssel (ECM/EMM)
            c.execute('''
                CREATE TABLE IF NOT EXISTS keys (
                    key_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_value  TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    valid_until TIMESTAMP,
                    user       TEXT,
                    paket      TEXT
                )
            ''')
            # Watermarks
            c.execute('''
                CREATE TABLE IF NOT EXISTS watermarks (
                    wm_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                    name     TEXT,
                    path     TEXT,
                    position TEXT,
                    visible  INTEGER DEFAULT 1
                )
            ''')
            # Abonnements
            c.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    sub_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                    username   TEXT,
                    paket      TEXT,
                    start_date DATE,
                    end_date   DATE,
                    cancelled  INTEGER DEFAULT 0
                )
            ''')
            # Payments
            c.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username   TEXT,
                    amount     REAL,
                    currency   TEXT,
                    status     TEXT,
                    timestamp  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    # --- User-Methoden ---
    def add_user(self, username, password, hwid, paket, token, email=''):
        with self.lock, self._connect() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO users (username, password, hwid, paket, token, email)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, password, hwid, paket, token, email))
            conn.commit()

    def delete_user(self, username):
        with self.lock, self._connect() as conn:
            conn.execute('DELETE FROM users WHERE username = ?', (username,))
            conn.commit()

    def delete_user_by_token(self, token):
        with self.lock, self._connect() as conn:
            conn.execute('DELETE FROM users WHERE token = ?', (token,))
            conn.commit()

    def update_user_details(self, username, paket, hwid, email):
        with self.lock, self._connect() as conn:
            conn.execute('''
                UPDATE users SET paket = ?, hwid = ?, email = ? WHERE username = ?
            ''', (paket, hwid, email, username))
            conn.commit()

    def list_users(self, paket_filter=None, hwid_filter='', token_filter=''):
        query = 'SELECT username, hwid, paket, token, email FROM users WHERE 1=1'
        params = []
        if paket_filter:
            query += ' AND paket = ?'
            params.append(paket_filter)
        if hwid_filter:
            query += ' AND hwid LIKE ?'
            params.append(f'%{hwid_filter}%')
        if token_filter:
            query += ' AND token LIKE ?'
            params.append(f'%{token_filter}%')
        with self.lock, self._connect() as conn:
            return conn.execute(query, params).fetchall()

    def get_user_by_token(self, token):
        with self.lock, self._connect() as conn:
            return conn.execute(
                'SELECT username, hwid, paket, token, email FROM users WHERE token = ?', (token,)
            ).fetchone()

    def get_user_by_username(self, username):
        with self.lock, self._connect() as conn:
            return conn.execute(
                'SELECT username, hwid, paket, token, email FROM users WHERE username = ?', (username,)
            ).fetchone()

    def get_user_by_hwid(self, hwid):
        with self.lock, self._connect() as conn:
            return conn.execute(
                'SELECT username, hwid, paket, token, email FROM users WHERE hwid = ?', (hwid,)
            ).fetchone()

    def get_all_users(self):
        with self.lock, self._connect() as conn:
            return conn.execute(
                'SELECT username, hwid, paket, token, email FROM users'
            ).fetchall()

    def update_user_token(self, username, new_token):
        with self.lock, self._connect() as conn:
            conn.execute('UPDATE users SET token = ? WHERE username = ?', (new_token, username))
            conn.commit()

    def update_user_package(self, username, paket):
        with self.lock, self._connect() as conn:
            conn.execute('UPDATE users SET paket = ? WHERE username = ?', (paket, username))
            conn.commit()

    # --- Key-Methoden ---
    def store_key(self, key_value, valid_until=None, user=None, paket=None):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO keys (key_value, valid_until, user, paket) VALUES (?, ?, ?, ?)
            ''', (key_value, valid_until, user, paket))
            conn.commit()
            return c.lastrowid

    def get_key_by_id(self, key_id):
        with self.lock, self._connect() as conn:
            return conn.execute(
                'SELECT key_id, key_value, created_at, valid_until, user, paket FROM keys WHERE key_id = ?',
                (key_id,)
            ).fetchone()

    def get_valid_keys(self, user=None, paket=None):
        query = 'SELECT key_id, key_value FROM keys WHERE (valid_until IS NULL OR valid_until > CURRENT_TIMESTAMP)'
        params = []
        if user:
            query += ' AND user = ?'; params.append(user)
        if paket:
            query += ' AND paket = ?'; params.append(paket)
        with self.lock, self._connect() as conn:
            return conn.execute(query, params).fetchall()

    def get_recent_keys(self, limit=20):
        with self.lock, self._connect() as conn:
            return conn.execute(
                'SELECT key_id, key_value, created_at, user, paket FROM keys ORDER BY created_at DESC LIMIT ?',
                (limit,)
            ).fetchall()

    def get_valid_key_for_user(self, username):
        # Liefert den jüngsten, noch gültigen Key für diesen Nutzer
        rec = self.get_valid_keys(user=username)
        return rec[0][1] if rec else None

    # --- Subscription-Methoden ---
    def add_subscription(self, username, paket, start_date, end_date):
        with self.lock, self._connect() as conn:
            conn.execute('''
                INSERT INTO subscriptions (username, paket, start_date, end_date)
                VALUES (?, ?, ?, ?)
            ''', (username, paket, start_date, end_date))
            conn.commit()

    def cancel_subscription(self, username):
        # Markiert alle aktiven Abos als 'cancelled' – Laufzeit bleibt erhalten
        with self.lock, self._connect() as conn:
            conn.execute('''
                UPDATE subscriptions SET cancelled = 1
                WHERE username = ? AND end_date > DATE('now')
            ''', (username,))
            conn.commit()

    def get_active_subscriptions(self, username):
        # Liefert alle nicht-cancelled Abos, deren end_date >= heute
        with self.lock, self._connect() as conn:
            return conn.execute('''
                SELECT sub_id, username, paket, start_date, end_date, cancelled
                FROM subscriptions
                WHERE username = ?
                  AND cancelled = 0
                  AND DATE(end_date) >= DATE('now')
                ORDER BY end_date DESC
            ''', (username,)).fetchall()

    def get_active_subscription(self, username):
        subs = self.get_active_subscriptions(username)
        return subs[0] if subs else None

    def get_best_active_package(self, username):
        # Sortierreihenfolge: Premium > Basis+ > Basis > Kein Abo
        priority = {'Premium':3, 'Basis+':2, 'Basis':1}
        subs = self.get_active_subscriptions(username)
        if not subs:
            return 'Kein Abo'
        # Wähle das Paket mit der höchsten Priorität
        best = max(subs, key=lambda s: priority.get(s[2], 0))
        return best[2]

    # --- Watermark-Methoden ---
    def add_watermark(self, name, path, position, visible=True):
        with self.lock, self._connect() as conn:
            conn.execute('''
                INSERT INTO watermarks (name, path, position, visible)
                VALUES (?, ?, ?, ?)
            ''', (name, path, position, int(visible)))
            conn.commit()

    def get_watermarks(self):
        with self.lock, self._connect() as conn:
            return conn.execute('''
                SELECT wm_id, name, path, position, visible FROM watermarks
            ''').fetchall()

    def update_watermark(self, wm_id, visible):
        with self.lock, self._connect() as conn:
            conn.execute('''
                UPDATE watermarks SET visible = ? WHERE wm_id = ?
            ''', (int(visible), wm_id))
            conn.commit()

    # --- Payment-Methoden ---
    def add_payment(self, username, amount, currency, status):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO payments (username, amount, currency, status)
                VALUES (?, ?, ?, ?)
            ''', (username, amount, currency, status))
            conn.commit()
            return c.lastrowid

    def get_payments_by_user(self, username):
        with self.lock, self._connect() as conn:
            return conn.execute('''
                SELECT payment_id, amount, currency, status, timestamp
                FROM payments WHERE username = ?
                ORDER BY timestamp DESC
            ''', (username,)).fetchall()
