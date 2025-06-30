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
            # Subscriptions
            c.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    sub_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    paket TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    cancelled INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(username) REFERENCES users(username)
                )
            ''')
            # Keys (ECM/EMM)
            c.execute('''
                CREATE TABLE IF NOT EXISTS keys (
                    key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_value TEXT NOT NULL,
                    valid_until TEXT NOT NULL,
                    username TEXT NOT NULL,
                    paket TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(username) REFERENCES users(username)
                )
            ''')
            # Watermarks
            c.execute('''
                CREATE TABLE IF NOT EXISTS watermarks (
                    wm_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    path TEXT,
                    position TEXT,
                    visible INTEGER NOT NULL DEFAULT 1
                )
            ''')
            # Payments
            c.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    pay_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT NOT NULL,
                    status TEXT NOT NULL,
                    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(username) REFERENCES users(username)
                )
            ''')
            conn.commit()

    # --- User Management ---
    def add_user(self, username, password, hwid, paket, token, email=''):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO users
                (username,password,hwid,paket,token,email)
                VALUES (?,?,?,?,?,?)
            ''', (username, password, hwid, paket, token, email))
            conn.commit()

    def delete_user(self, username):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM users WHERE username=?', (username,))
            conn.commit()

    def delete_user_by_token(self, token):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM users WHERE token=?', (token,))
            conn.commit()

    def get_user_by_username(self, username):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                'SELECT username,hwid,paket,token,email FROM users WHERE username=?',
                (username,)
            ).fetchone()

    def get_user_by_token(self, token):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                'SELECT username,hwid,paket,token,email FROM users WHERE token=?',
                (token,)
            ).fetchone()

    def get_user_by_hwid(self, hwid):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                'SELECT username,hwid,paket,token,email FROM users WHERE hwid=?',
                (hwid,)
            ).fetchone()

    def list_users(self, paket_filter=None, hwid_filter='', token_filter=''):
        query = 'SELECT username,hwid,paket,token,email FROM users WHERE 1=1'
        params = []
        if paket_filter:
            query += ' AND paket=?'
            params.append(paket_filter)
        if hwid_filter:
            query += ' AND hwid LIKE ?'
            params.append(f'%{hwid_filter}%')
        if token_filter:
            query += ' AND token LIKE ?'
            params.append(f'%{token_filter}%')
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute(query, params).fetchall()

    def get_all_users(self):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                'SELECT username,hwid,paket,token,email FROM users'
            ).fetchall()

    def update_user_details(self, username, paket, hwid, email):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE users SET paket=?,hwid=?,email=? WHERE username=?
            ''', (paket, hwid, email, username))
            conn.commit()

    def update_user_token(self, username, new_token):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('UPDATE users SET token=? WHERE username=?',
                         (new_token, username))
            conn.commit()

    def get_token_by_username(self, username):
        row = self.get_user_by_username(username)
        return row[3] if row else None

    # --- Subscriptions ---
    def add_subscription(self, username, paket, start_date, end_date):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO subscriptions
                (username,paket,start_date,end_date)
                VALUES (?,?,?,?)
            ''', (username, paket, start_date, end_date))
            conn.commit()

    def cancel_subscription(self, username):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE subscriptions
                SET cancelled=1
                WHERE username=? AND cancelled=0
            ''', (username,))
            conn.commit()

    def get_active_subscriptions(self, username):
        today = datetime.date.today().isoformat()
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute('''
                SELECT sub_id,username,paket,start_date,end_date,cancelled
                FROM subscriptions
                WHERE username=?
                  AND date(start_date)<=date(?)
                  AND date(end_date)>=date(?)
                  AND cancelled=0
                ORDER BY end_date DESC
            ''', (username, today, today)).fetchall()

    def get_active_subscription(self, username):
        subs = self.get_active_subscriptions(username)
        return subs[0] if subs else None

    def has_active_subscription(self, username):
        return bool(self.get_active_subscriptions(username))

    def get_best_active_package(self, username):
        rank = {'Premium':3, 'Basis+':2, 'Basis':1}
        subs = self.get_active_subscriptions(username)
        best = None
        best_rank = 0
        for _,_,paket,_,_,_ in subs:
            r = rank.get(paket,0)
            if r>best_rank:
                best_rank, best = r, paket
        return best

    # --- Keys (ECM/EMM) ---
    def store_key(self, key_value, valid_until, username, paket):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO keys
                (key_value,valid_until,username,paket)
                VALUES (?,?,?,?)
            ''', (key_value, valid_until, username, paket))
            conn.commit()
            return c.lastrowid

    def get_valid_keys(self, username=None, paket=None):
        now = datetime.datetime.utcnow().isoformat()
        query = '''
            SELECT key_id,key_value,valid_until,username,paket
            FROM keys
            WHERE valid_until>?
        '''
        params = [now]
        if username:
            query += ' AND username=?'
            params.append(username)
        if paket:
            query += ' AND paket=?'
            params.append(paket)
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute(query, params).fetchall()

    def get_valid_key_for_user(self, username):
        rows = self.get_valid_keys(username=username)
        return rows[0][1] if rows else None

    def get_recent_keys(self, limit=20):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute('''
                SELECT key_id,key_value,created_at,username,paket
                FROM keys
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,)).fetchall()

    # --- Watermarks ---
    def add_watermark(self, name, path, position, visible=True):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO watermarks (name,path,position,visible)
                VALUES (?,?,?,?)
            ''', (name, path, position, int(visible)))
            conn.commit()

    def get_watermarks(self):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute('''
                SELECT wm_id,name,path,position,visible FROM watermarks
            ''').fetchall()

    def update_watermark(self, wm_id, visible):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE watermarks SET visible=? WHERE wm_id=?
            ''', (int(visible), wm_id))
            conn.commit()

    # --- Payments ---
    def add_payment(self, username, amount, currency, status):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO payments
                (username,amount,currency,status)
                VALUES (?,?,?,?)
            ''', (username, amount, currency, status))
            conn.commit()
            return c.lastrowid

    def get_payments_by_user(self, username):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            return conn.execute('''
                SELECT pay_id,amount,currency,status,timestamp
                FROM payments
                WHERE username=?
                ORDER BY timestamp DESC
            ''', (username,)).fetchall()
