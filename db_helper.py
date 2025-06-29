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

            c.execute('''
                CREATE TABLE IF NOT EXISTS keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT,
                    valid_until TEXT,
                    user TEXT,
                    paket TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            c.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    paket TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    active INTEGER,
                    canceled INTEGER DEFAULT 0
                )
            ''')

            c.execute('''
                CREATE TABLE IF NOT EXISTS watermarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    filepath TEXT,
                    position TEXT,
                    visible INTEGER
                )
            ''')

            conn.commit()

    # Nutzerverwaltung
    def add_user(self, username, password, hwid, paket, token, email=''):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT OR REPLACE INTO users (username, password, hwid, paket, token, email)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, password, hwid, paket, token, email))
            conn.commit()

    def get_user_by_token(self, token):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT username, hwid, paket, token, email FROM users WHERE token = ?', (token,))
            return c.fetchone()

    def get_user_by_hwid(self, hwid):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT username, hwid, paket, token, email FROM users WHERE hwid = ?', (hwid,))
            return c.fetchone()

    def get_user_by_username(self, username):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT username, hwid, paket, token, email FROM users WHERE username = ?', (username,))
            return c.fetchone()

    def get_token_by_username(self, username):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT token FROM users WHERE username = ?', (username,))
            res = c.fetchone()
            return res[0] if res else None

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
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(query, params)
            return c.fetchall()

    def update_user_token(self, username, token):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('UPDATE users SET token = ? WHERE username = ?', (token, username))
            conn.commit()

    def update_user_package(self, username, paket):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('UPDATE users SET paket = ? WHERE username = ?', (paket, username))
            conn.commit()

    def update_user_details(self, username, paket, hwid, email):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('UPDATE users SET paket = ?, hwid = ?, email = ? WHERE username = ?', (paket, hwid, email, username))
            conn.commit()

    def delete_user(self, username):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM users WHERE username = ?', (username,))
            conn.commit()

    def get_all_users(self):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT username, hwid, paket, token, email FROM users')
            return c.fetchall()

    # Wasserzeichen
    def add_watermark(self, name, filepath, position, visible=True):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('INSERT INTO watermarks (name, filepath, position, visible) VALUES (?, ?, ?, ?)',
                      (name, filepath, position, 1 if visible else 0))
            conn.commit()

    def get_watermarks(self):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT id, name, filepath, position, visible FROM watermarks')
            return c.fetchall()

    def update_watermark(self, wm_id, visible=None, position=None, name=None):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            updates = []
            params = []
            if visible is not None:
                updates.append('visible = ?')
                params.append(1 if visible else 0)
            if position is not None:
                updates.append('position = ?')
                params.append(position)
            if name is not None:
                updates.append('name = ?')
                params.append(name)
            if not updates:
                return
            params.append(wm_id)
            sql = 'UPDATE watermarks SET ' + ', '.join(updates) + ' WHERE id = ?'
            c.execute(sql, params)
            conn.commit()

    # Schlüssel (ECM/EMM)
    def store_key(self, key, valid_until, user, paket):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('INSERT INTO keys (key, valid_until, user, paket) VALUES (?, ?, ?, ?)', (key, valid_until, user, paket))
            conn.commit()
            return c.lastrowid

    def get_keys(self, limit=50):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT id, key, valid_until, user, paket, created_at FROM keys ORDER BY created_at DESC LIMIT ?', (limit,))
            return c.fetchall()

    def get_valid_key_for_user(self, username):
        jetzt = datetime.datetime.utcnow().isoformat()
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT key FROM keys WHERE user = ? AND valid_until >= ? ORDER BY valid_until DESC LIMIT 1', (username, jetzt))
            row = c.fetchone()
            return row[0] if row else None

    def get_valid_keys_for_user(self, username):
        jetzt = datetime.datetime.utcnow().isoformat()
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT DISTINCT k.key FROM keys k
                JOIN subscriptions s ON k.user = s.username AND k.paket = s.paket
                WHERE k.user = ? 
                  AND s.active = 1
                  AND (s.canceled = 0 OR (s.canceled = 1 AND DATE(s.end_date) >= DATE(?)))
                  AND DATE(s.end_date) >= DATE(?)
                  AND k.valid_until >= ?
            ''', (username, jetzt, jetzt, jetzt))
            rows = c.fetchall()
            return [row[0] for row in rows] if rows else []

    # Abonnement
    def add_subscription(self, username, paket, start_date, end_date, active=1, canceled=0):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('INSERT INTO subscriptions (username, paket, start_date, end_date, active, canceled) VALUES (?, ?, ?, ?, ?, ?)',
                      (username, paket, start_date, end_date, active, canceled))
            conn.commit()

    def add_or_extend_subscription(self, username, paket, zyklus_tage):
        heute = datetime.datetime.utcnow().date()
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT id, end_date FROM subscriptions
                WHERE username = ? AND paket = ? AND active = 1 AND canceled = 0 AND DATE(end_date) >= DATE(?)
                ORDER BY end_date DESC LIMIT 1
            ''', (username, paket, heute.isoformat()))
            row = c.fetchone()
            if row:
                abo_id, end_date_str = row
                end_date = datetime.datetime.fromisoformat(end_date_str).date()
                neuer_ablauf = end_date + datetime.timedelta(days=zyklus_tage)
                c.execute('UPDATE subscriptions SET end_date = ? WHERE id = ?', (neuer_ablauf.isoformat(), abo_id))
            else:
                start_date = heute.isoformat()
                end_date = heute + datetime.timedelta(days=zyklus_tage)
                c.execute('''
                    INSERT INTO subscriptions (username, paket, start_date, end_date, active, canceled)
                    VALUES (?, ?, ?, ?, 1, 0)
                ''', (username, paket, start_date, end_date.isoformat()))
            conn.commit()

    def cancel_subscription(self, username, paket=None):
        heute = datetime.datetime.utcnow().date().isoformat()
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            if paket:
                c.execute('''
                    UPDATE subscriptions
                    SET canceled = 1
                    WHERE username = ? AND paket = ? AND active = 1 AND canceled = 0 AND DATE(end_date) > DATE(?)
                ''', (username, paket, heute))
            else:
                c.execute('''
                    UPDATE subscriptions
                    SET canceled = 1
                    WHERE username = ? AND active = 1 AND canceled = 0 AND DATE(end_date) > DATE(?)
                ''', (username, heute))
            conn.commit()

    def get_active_subscription(self, username):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT * FROM subscriptions
                WHERE username = ? AND active = 1 AND canceled = 0
                ORDER BY end_date DESC LIMIT 1
            ''', (username,))
            return c.fetchone()

    def get_active_subscriptions(self, username):
        heute = datetime.datetime.utcnow().date()
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT id, paket, start_date, end_date, canceled FROM subscriptions
                WHERE username = ? AND active = 1 AND (canceled = 0 OR (canceled = 1 AND DATE(end_date) >= DATE(?)))
                  AND DATE(end_date) >= DATE(?)
                ORDER BY end_date DESC
            ''', (username, heute.isoformat(), heute.isoformat()))
            return c.fetchall()

    def has_active_subscription(self, username):
        heute = datetime.datetime.utcnow().date()
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT COUNT(*) FROM subscriptions
                WHERE username = ? AND active = 1 AND (canceled = 0 OR (canceled = 1 AND DATE(end_date) >= DATE(?)))
                  AND DATE(end_date) >= DATE(?)
            ''', (username, heute.isoformat(), heute.isoformat()))
            result = c.fetchone()
            return result[0] > 0 if result else False

    def get_best_active_package(self, username):
        paket_prioritaet = {'Kein Abo': 0, 'Basis': 1, 'Basis+': 2, 'Premium': 3}
        heute = datetime.datetime.utcnow().date()
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT paket, start_date, end_date, canceled FROM subscriptions
                WHERE username = ? AND active = 1 AND (canceled = 0 OR (canceled = 1 AND DATE(end_date) >= DATE(?)))
                  AND DATE(end_date) >= DATE(?)
            ''', (username, heute.isoformat(), heute.isoformat()))
            abos = c.fetchall()
            gueltige_abos = [a for a in abos if datetime.datetime.fromisoformat(a[2]).date() >= heute]
            if not gueltige_abos:
                return 'Kein Abo'
            bestes = max(gueltige_abos, key=lambda a: paket_prioritaet.get(a[0], 0))
            return bestes[0]
