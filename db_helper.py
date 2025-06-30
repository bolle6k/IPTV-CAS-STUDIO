import sqlite3
import threading
import datetime

class DBHelper:
    def __init__(self, db_path='iptv_users.db'):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._create_tables()
        self._migrate_tables()

    def _connect(self):
        return sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)

    def _create_tables(self):
        with self.lock, self._connect() as conn:
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
            # Subscriptions
            c.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    sub_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    paket TEXT NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY(username) REFERENCES users(username)
                )
            ''')
            # Keys (ECM/EMM)
            c.execute('''
                CREATE TABLE IF NOT EXISTS keys (
                    key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    valid_until TIMESTAMP,
                    username TEXT,
                    paket TEXT
                )
            ''')
            # Watermarks
            c.execute('''
                CREATE TABLE IF NOT EXISTS watermarks (
                    wm_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    path TEXT,
                    position TEXT,
                    visible INTEGER DEFAULT 1
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

    def _migrate_tables(self):
        """Fügt fehlende Spalten nachträglich ein (Migration bei Schema-Änderung)."""
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            # Prüfe keys-Tabelle auf username/paket
            cols = [r[1] for r in c.execute("PRAGMA table_info(keys)")]
            if 'username' not in cols:
                c.execute("ALTER TABLE keys ADD COLUMN username TEXT")
            if 'paket' not in cols:
                c.execute("ALTER TABLE keys ADD COLUMN paket TEXT")
            conn.commit()

    # --- User-Methoden ---
    def add_user(self, username, password, hwid, paket, token, email=''):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT OR REPLACE INTO users (username, password, hwid, paket, token, email)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, password, hwid, paket, token, email))
            conn.commit()

    def delete_user(self, username):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM users WHERE username = ?', (username,))
            conn.commit()

    def delete_user_by_token(self, token):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM users WHERE token = ?', (token,))
            conn.commit()

    def get_all_users(self):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute('SELECT username, hwid, paket, token, email FROM users')
            return c.fetchall()

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
            c = conn.cursor()
            c.execute(query, params)
            return c.fetchall()

    def get_user_by_token(self, token):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute('SELECT username, hwid, paket, token, email FROM users WHERE token = ?', (token,))
            return c.fetchone()

    def get_user_by_hwid(self, hwid):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute('SELECT username, hwid, paket, token, email FROM users WHERE hwid = ?', (hwid,))
            return c.fetchone()

    def get_user_by_username(self, username):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute('SELECT username, hwid, paket, token, email FROM users WHERE username = ?', (username,))
            return c.fetchone()

    def update_user_details(self, username, paket, hwid, email):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute('''
                UPDATE users SET paket = ?, hwid = ?, email = ? WHERE username = ?
            ''', (paket, hwid, email, username))
            conn.commit()

    def update_user_token(self, username, token):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute('UPDATE users SET token = ? WHERE username = ?', (token, username))
            conn.commit()

    def update_user_package(self, username, paket):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute('UPDATE users SET paket = ? WHERE username = ?', (paket, username))
            conn.commit()

    # --- Subscription-Methoden ---
    def add_subscription(self, username, paket, start_date, end_date):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            # alles alte Abos deaktivieren, die überschneidend aktiv sind
            c.execute('''
                UPDATE subscriptions
                SET active = 0
                WHERE username = ? AND active = 1 AND end_date >= ?
            ''', (username, start_date))
            c.execute('''
                INSERT INTO subscriptions (username, paket, start_date, end_date, active)
                VALUES (?, ?, ?, ?, 1)
            ''', (username, paket, start_date, end_date))
            conn.commit()

    def get_active_subscriptions(self, username):
        today = datetime.date.today().isoformat()
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute('''
                SELECT sub_id, username, paket, start_date, end_date, active
                FROM subscriptions
                WHERE username = ? AND active = 1 AND end_date >= ?
                ORDER BY end_date DESC
            ''', (username, today))
            return c.fetchall()

    def get_active_subscription(self, username):
        subs = self.get_active_subscriptions(username)
        return subs[0] if subs else None

    def get_best_active_package(self, username):
        """Wählt das 'stärkste' aktive Abo (Premium > Basis+ > Basis)."""
        subs = self.get_active_subscriptions(username)
        order = {'Premium':3, 'Basis+':2, 'Basis':1}
        subs.sort(key=lambda s: order.get(s[2], 0), reverse=True)
        return subs[0][2] if subs else None

    def cancel_subscription(self, username):
        """Kennzeichnet alle aktiven Abos zum Ablaufdatum als inactive, ohne Restzeit zu löschen."""
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            # setze active=0 erst nach dem Ablaufdatum
            c.execute('''
                UPDATE subscriptions
                SET active = 0
                WHERE username = ? AND end_date < ?
            ''', (username, datetime.date.today().isoformat()))
            conn.commit()

    # --- Key-Methoden ---
    def store_key(self, key_value, valid_until=None, username=None, paket=None):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO keys (key_value, valid_until, username, paket)
                VALUES (?, ?, ?, ?)
            ''', (key_value, valid_until, username, paket))
            conn.commit()
            return c.lastrowid

    def get_valid_keys(self, username=None, paket=None):
        now = datetime.datetime.utcnow().isoformat()
        query = '''
            SELECT key_id, key_value, created_at, valid_until, username, paket
            FROM keys
            WHERE (valid_until IS NULL OR valid_until > ?)
        '''
        params = [now]
        if username:
            query += ' AND username = ?'
            params.append(username)
        if paket:
            query += ' AND paket = ?'
            params.append(paket)
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute(query, params)
            return c.fetchall()

    def get_valid_key_for_user(self, username):
        rows = self.get_valid_keys(username=username)
        return rows[0][1] if rows else None

    def get_recent_keys(self, limit=20):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute(f'''
                SELECT key_id, key_value, created_at, valid_until, username, paket
                FROM keys
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))
            return c.fetchall()

    # --- Watermark-Methoden ---
    def add_watermark(self, name, path, position, visible=True):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO watermarks (name, path, position, visible)
                VALUES (?, ?, ?, ?)
            ''', (name, path, position, int(visible)))
            conn.commit()

    def get_watermarks(self):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute('SELECT wm_id, name, path, position, visible FROM watermarks')
            return c.fetchall()

    def update_watermark(self, wm_id, visible):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute('UPDATE watermarks SET visible = ? WHERE wm_id = ?', (int(visible), wm_id))
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
            c = conn.cursor()
            c.execute('''
                SELECT payment_id, amount, currency, status, timestamp
                FROM payments
                WHERE username = ?
                ORDER BY timestamp DESC
            ''', (username,))
            return c.fetchall()
