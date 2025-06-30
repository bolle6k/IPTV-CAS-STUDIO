import sqlite3
import threading
import datetime

class DBHelper:
    def __init__(self, db_path='iptv_users.db'):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._create_tables()

    def _create_tables(self):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            # Users
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
            # Keys (ECM/EMM)
            c.execute('''
                CREATE TABLE IF NOT EXISTS keys (
                    key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    valid_until TIMESTAMP,
                    owner TEXT,
                    paket TEXT
                )
            ''')
            # Subscriptions
            c.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    sub_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    paket TEXT NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    active INTEGER DEFAULT 1,
                    FOREIGN KEY(username) REFERENCES users(username)
                )
            ''')
            # Watermarks / Logos
            c.execute('''
                CREATE TABLE IF NOT EXISTS watermarks (
                    wm_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    position TEXT NOT NULL,
                    visible INTEGER NOT NULL DEFAULT 1
                )
            ''')
            # Payments
            c.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT NOT NULL,
                    status TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(username) REFERENCES users(username)
                )
            ''')
            conn.commit()

    # --- User-Methoden ---

    def add_user(self, username, password, hwid, paket, token, email=''):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO users(username, password, hwid, paket, token, email)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, password, hwid, paket, token, email))
            conn.commit()

    def delete_user(self, username):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM users WHERE username = ?', (username,))
            conn.commit()

    def delete_user_by_token(self, token):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM users WHERE token = ?', (token,))
            conn.commit()

    def update_user_details(self, username, paket, hwid, email):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE users
                SET paket = ?, hwid = ?, email = ?
                WHERE username = ?
            ''', (paket, hwid, email, username))
            conn.commit()

    def update_user_token(self, username, new_token):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE users SET token = ? WHERE username = ?
            ''', (new_token, username))
            conn.commit()

    def get_user_by_token(self, token):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute('''
                SELECT username, hwid, paket, token, email
                FROM users WHERE token = ?
            ''', (token,)).fetchone()

    def get_user_by_hwid(self, hwid):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute('''
                SELECT username, hwid, paket, token, email
                FROM users WHERE hwid = ?
            ''', (hwid,)).fetchone()

    def get_user_by_username(self, username):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute('''
                SELECT username, hwid, paket, token, email
                FROM users WHERE username = ?
            ''', (username,)).fetchone()

    def get_token_by_username(self, username):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            row = conn.execute('SELECT token FROM users WHERE username = ?', (username,)).fetchone()
            return row[0] if row else None

    def list_users(self, paket_filter=None, hwid_filter='', token_filter=''):
        query = 'SELECT username, hwid, paket, token, email FROM users WHERE 1=1'
        params = []
        if paket_filter:
            query += ' AND paket = ?'; params.append(paket_filter)
        if hwid_filter:
            query += ' AND hwid LIKE ?'; params.append(f'%{hwid_filter}%')
        if token_filter:
            query += ' AND token LIKE ?'; params.append(f'%{token_filter}%')
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute(query, params).fetchall()

    def get_all_users(self):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute('SELECT username, hwid, paket, token, email FROM users').fetchall()

    # --- Key-Methoden ---

    def store_key(self, key_value, valid_until, owner, paket):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO keys(key_value, valid_until, owner, paket)
                VALUES (?, ?, ?, ?)
            ''', (key_value, valid_until, owner, paket))
            conn.commit()
            return c.lastrowid

    def get_valid_keys(self, owner=None, paket=None):
        now = datetime.datetime.utcnow().isoformat()
        query = 'SELECT key_id, key_value, created_at, valid_until, owner, paket FROM keys WHERE valid_until IS NULL OR valid_until > ?'
        params = [now]
        if owner:
            query += ' AND owner = ?'; params.append(owner)
        if paket:
            query += ' AND paket = ?'; params.append(paket)
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute(query, params).fetchall()

    def get_key_by_id(self, key_id):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute('SELECT key_id, key_value, created_at, valid_until, owner, paket FROM keys WHERE key_id = ?', (key_id,)).fetchone()

    def get_recent_keys(self, limit=20):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute('''
                SELECT key_id, key_value, created_at, valid_until, owner, paket
                FROM keys ORDER BY created_at DESC LIMIT ?
            ''', (limit,)).fetchall()

    # --- Subscription-Methoden ---

    def add_subscription(self, username, paket, start_date, end_date):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO subscriptions(username, paket, start_date, end_date, active)
                VALUES (?, ?, ?, ?, 1)
            ''', (username, paket, start_date, end_date))
            conn.commit()

    def get_active_subscriptions(self, username):
        today = datetime.date.today().isoformat()
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute('''
                SELECT sub_id, username, paket, start_date, end_date, active
                FROM subscriptions
                WHERE username = ? AND active = 1 AND end_date >= ?
                ORDER BY end_date DESC
            ''', (username, today)).fetchall()

    def get_active_subscription(self, username):
        subs = self.get_active_subscriptions(username)
        return subs[0] if subs else None

    def get_best_active_package(self, username):
        # Priorität: Premium > Basis+ > Basis
        order = {'Premium':3, 'Basis+':2, 'Basis':1}
        subs = self.get_active_subscriptions(username)
        if not subs:
            return None
        best = max(subs, key=lambda s: order.get(s[2], 0))
        return best[2]

    def cancel_subscription(self, username):
        # Markiere alle aktiven Subs als inactive, aber lasse end_date unangetastet
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE subscriptions SET active = 0
                WHERE username = ? AND active = 1
            ''', (username,))
            conn.commit()

    # --- Watermark-Methoden ---

    def add_watermark(self, name, path, position, visible=True):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO watermarks(name, path, position, visible)
                VALUES (?, ?, ?, ?)
            ''', (name, path, position, int(visible)))
            conn.commit()

    def get_watermarks(self):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute('''
                SELECT wm_id, name, path, position, visible
                FROM watermarks
            ''').fetchall()

    def update_watermark(self, wm_id, visible):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE watermarks SET visible = ?
                WHERE wm_id = ?
            ''', (int(visible), wm_id))
            conn.commit()

    # --- Payment-Methoden ---

    def add_payment(self, username, amount, currency, status):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO payments(username, amount, currency, status)
                VALUES (?, ?, ?, ?)
            ''', (username, amount, currency, status))
            conn.commit()
            return c.lastrowid

    def get_payments_by_user(self, username):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute('''
                SELECT payment_id, amount, currency, status, timestamp
                FROM payments WHERE username = ?
                ORDER BY timestamp DESC
            ''', (username,)).fetchall()
