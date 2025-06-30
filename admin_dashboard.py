# admin_dashboard.py

import os
import threading
import math
import datetime
import zipfile
from functools import wraps
from flask import (
    Flask, render_template_string, request, redirect,
    url_for, send_file, session, flash, abort
)
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit
import config
from db_helper import DBHelper

app = Flask(__name__)
app.secret_key = config.MASTER_KEY
socketio = SocketIO(app, async_mode='threading')

# Konfiguration
LOGFILE = config.LOG_FILE
PER_PAGE = 50
KEY_ROTATION_INTERVAL = config.ROTATION_INTERVAL
last_key_rotation = datetime.datetime.now(datetime.timezone.utc)
DB_PATH = config.DB_PATH
KEYS_DIR = config.KEYS_DIR
BACKUP_DIR = "./backups"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

db = DBHelper(DB_PATH)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def log_event(action, username):
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    entry = f"{timestamp} | {action} | {username}\n"
    with open(LOGFILE, "a") as f:
        f.write(entry)
    socketio.emit('log_update', {'msg': entry})

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def create_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"iptv_backup_{ts}.zip"
    path = os.path.join(BACKUP_DIR, name)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        if os.path.exists(DB_PATH):
            zipf.write(DB_PATH, os.path.basename(DB_PATH))
        if os.path.isdir(KEYS_DIR):
            for root, _, files in os.walk(KEYS_DIR):
                for fn in files:
                    fp = os.path.join(root, fn)
                    arc = os.path.relpath(fp, start='.')
                    zipf.write(fp, arc)
    log_event("BACKUP_CREATED", "system")
    return name

def restore_backup_file(backup_file):
    if not os.path.exists(backup_file):
        return False
    with zipfile.ZipFile(backup_file, 'r') as zipf:
        zipf.extractall()
    log_event("BACKUP_RESTORED", "system")
    return True

TEMPLATE = '''<!doctype html>
<html lang="de"><head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Admin Dashboard</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.4.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <script src="//cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
  <style>img.preview{max-height:40px;max-width:80px;}</style>
</head><body>
<nav class="navbar navbar-dark bg-dark mb-4">
  <div class="container-fluid">
    <a class="navbar-brand" href="{{ url_for('admin') }}">Admin Dashboard</a>
    <a class="btn btn-outline-light" href="{{ url_for('logout') }}">Logout</a>
  </div>
</nav>
<div class="container">

  <h2>Benutzerverwaltung</h2>
  <form method="get" class="row g-3 mb-3">
    <div class="col-auto"><select name="paket" class="form-select">
      <option value="" {% if not paket_filter %}selected{% endif %}>Alle</option>
      <option value="Basis" {% if paket_filter=='Basis' %}selected{% endif %}>Basis</option>
      <option value="Basis+" {% if paket_filter=='Basis+' %}selected{% endif %}>Basis+</option>
      <option value="Premium" {% if paket_filter=='Premium' %}selected{% endif %}>Premium</option>
    </select></div>
    <div class="col-auto"><input name="hwid_filter" class="form-control" placeholder="HWID" value="{{ hwid_filter }}"></div>
    <div class="col-auto"><input name="token_filter" class="form-control" placeholder="Token" value="{{ token_filter }}"></div>
    <div class="col-auto"><button class="btn btn-primary">Filter</button></div>
  </form>

  <div class="table-responsive">
    <table class="table table-striped align-middle">
      <thead class="table-dark">
        <tr>
          <th>Username</th><th>HWID</th><th>Aktive Pakete</th><th>Token</th><th>Email</th><th>Aktionen</th>
        </tr>
      </thead>
      <tbody>
        {% for u in users %}
        <tr>
          <td>{{ u.user[0] }}</td>
          <td>{{ u.user[1] }}</td>
          <td>
            {% for abo in u.subscriptions %}
              {{ abo.paket }} ({{ abo.rest_days }} Tage){% if not loop.last %}, {% endif %}
            {% endfor %}
          </td>
          <td><code>{{ u.user[3] }}</code></td>
          <td>{{ u.user[4] }}</td>
          <td>
            <form method="post" action="{{ url_for('delete_user') }}" class="d-inline" onsubmit="return confirm('Löschen?');">
              <input type="hidden" name="username" value="{{ u.user[0] }}">
              <button class="btn btn-sm btn-danger">Löschen</button>
            </form>
            <form method="post" action="{{ url_for('edit_user') }}" class="d-inline ms-1">
              <input type="hidden" name="username" value="{{ u.user[0] }}">
              <select name="paket" class="form-select form-select-sm d-inline w-auto">
                <option value="Basis" {% if u.best=='Basis' %}selected{% endif %}>Basis</option>
                <option value="Basis+" {% if u.best=='Basis+' %}selected{% endif %}>Basis+</option>
                <option value="Premium" {% if u.best=='Premium' %}selected{% endif %}>Premium</option>
              </select>
              <input type="text" name="hwid" value="{{ u.user[1] }}" class="form-control form-control-sm d-inline w-auto" required>
              <input type="email" name="email" value="{{ u.user[4] }}" class="form-control form-control-sm d-inline w-auto">
              <button class="btn btn-sm btn-success">Aktualisieren</button>
            </form>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  {% if total_pages>1 %}
  <nav><ul class="pagination">
    <li class="page-item {% if page==1 %}disabled{% endif %}">
      <a class="page-link" href="{{ url_for('admin', paket=paket_filter, hwid_filter=hwid_filter, token_filter=token_filter, page=page-1) }}">←</a>
    </li>
    <li class="page-item disabled"><span class="page-link">{{ page }} / {{ total_pages }}</span></li>
    <li class="page-item {% if page==total_pages %}disabled{% endif %}">
      <a class="page-link" href="{{ url_for('admin', paket=paket_filter, hwid_filter=hwid_filter, token_filter=token_filter, page=page+1) }}">→</a>
    </li>
  </ul></nav>
  {% endif %}

  <hr>
  <h3>ECM/EMM Schlüssel-Historie</h3>
  <table class="table table-sm">
    <thead class="table-dark"><tr><th>Typ</th><th>Key</th><th>Zeitpunkt</th><th>User</th><th>Paket</th></tr></thead>
    <tbody>
      {% for e in ecm_emm_records %}
      <tr>
        <td>{{ e.type }}</td>
        <td><code>{{ e.key }}</code></td>
        <td>{{ e.timestamp }}</td>
        <td>{{ e.user }}</td>
        <td>{{ e.paket }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  <p>Nächste Rotation: {{ next_rotation }}</p>
  <form method="post" action="{{ url_for('rotate_key') }}">
    <button class="btn btn-warning">🔁 Manuelle Rotation</button>
  </form>

  <hr>
  <h3>Backup & Restore</h3>
  <form method="post" action="{{ url_for('trigger_backup') }}">
    <button class="btn btn-success">Backup erstellen</button>
  </form>
  {% if last_backup %}
    <p>Letztes Backup: {{ last_backup }}</p>
    <a class="btn btn-primary" href="{{ url_for('download_backup', filename=last_backup) }}">Herunterladen</a>
  {% endif %}
  <form method="post" action="{{ url_for('restore_backup') }}" enctype="multipart/form-data" class="mt-2">
    <input type="file" name="backup_file" accept=".zip" required>
    <button class="btn btn-warning">Wiederherstellen</button>
  </form>

  <hr>
  <h3>Live Logs</h3>
  <pre id="logArea" style="height:200px;overflow:auto;background:#f8f9fa;padding:1rem;"></pre>

</div>

<script>
  const socket = io();
  const logArea = document.getElementById('logArea');
  socket.on('log_update', data => {
    logArea.textContent += data.msg;
    logArea.scrollTop = logArea.scrollHeight;
  });
</script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.4.3/dist/js/bootstrap.bundle.min.js"></script>
</body></html>
'''

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u = request.form["username"]
        p = request.form["password"]
        if u=="admin" and p==config.MASTER_KEY:
            session["logged_in"]=True
            log_event("LOGIN",u)
            return redirect(url_for("admin"))
        flash("Ungültige Zugangsdaten","error")
    return '''
      <form method="post">
        Benutzername: <input name="username"><br>
        Passwort: <input type="password" name="password"><br>
        <button>Login</button>
      </form>
    '''

@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/admin", methods=["GET"])
@login_required
def admin():
    global last_key_rotation
    paket_filter = request.args.get("paket") or None
    hwid_filter  = request.args.get("hwid_filter") or ""
    token_filter= request.args.get("token_filter") or ""
    page = int(request.args.get("page",1))

    # Hole alle Nutzer mit ihren aktiven Abos
    raw = db.list_users(paket_filter, hwid_filter, token_filter)
    total = len(raw)
    total_pages = math.ceil(total/ PER_PAGE)
    slice_ = raw[(page-1)*PER_PAGE : page*PER_PAGE]

    users=[]
    today = datetime.datetime.now(datetime.timezone.utc).date()

    for u in slice_:
        subs = []
        for abo in db.get_active_subscriptions(u[0]):
            end_field = abo[4]
            # Typunterschiede abfangen:
            if isinstance(end_field, datetime.datetime):
                end_date = end_field.date()
            elif isinstance(end_field, datetime.date):
                end_date = end_field
            else:
                end_date = datetime.datetime.fromisoformat(str(end_field)).date()
            rest = max((end_date - today).days, 0)
            subs.append({'paket': abo[2], 'rest_days': rest})
        best = db.get_best_active_package(u[0])
        users.append({'user':u, 'subscriptions':subs, 'best':best})

    # ECM/EMM History
    ecm_emm_records = [
        {'type':r[0],'key':r[1],'timestamp':r[2],'user':r[3],'paket':r[4]}
        for r in db.get_recent_keys(limit=20)
    ]

    # Backup
    last_backup = None
    if os.path.isdir(BACKUP_DIR):
        lst = [f for f in os.listdir(BACKUP_DIR) if f.endswith('.zip')]
        if lst:
            last_backup = sorted(lst)[-1]

    next_rotation = (last_key_rotation + datetime.timedelta(seconds=KEY_ROTATION_INTERVAL)) \
        .strftime("%Y-%m-%d %H:%M:%S")

    return render_template_string(TEMPLATE,
        users=users,
        paket_filter=paket_filter,
        hwid_filter=hwid_filter,
        token_filter=token_filter,
        page=page,
        total_pages=total_pages,
        ecm_emm_records=ecm_emm_records,
        next_rotation=next_rotation,
        last_backup=last_backup
    )

@app.route("/admin/delete", methods=["POST"])
@login_required
def delete_user():
    u = request.form["username"]
    db.delete_user(u)
    log_event("DELETE_USER",u)
    return redirect(url_for("admin"))

@app.route("/admin/edit", methods=["POST"])
@login_required
def edit_user():
    u = request.form["username"]
    p = request.form["paket"]
    h = request.form["hwid"]
    e = request.form["email"]
    db.update_user_details(u,p,h,e)
    log_event("EDIT_USER",u)
    return redirect(url_for("admin"))

@app.route("/admin/rotate_key", methods=["POST"])
@login_required
def rotate_key():
    global last_key_rotation
    new_key = os.urandom(16).hex()
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.store_key(new_key, valid_until=None, user='admin', paket='all')
    last_key_rotation = datetime.datetime.now(datetime.timezone.utc)
    log_event("KEY_ROTATION","admin")
    return redirect(url_for("admin"))

@app.route("/admin/trigger_backup", methods=["POST"])
@login_required
def trigger_backup():
    name = create_backup()
    flash(f"Backup {name} erstellt","success")
    return redirect(url_for("admin"))

@app.route("/admin/download_backup/<filename>")
@login_required
def download_backup(filename):
    path = os.path.join(BACKUP_DIR, filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    abort(404)

@app.route("/admin/restore_backup", methods=["POST"])
@login_required
def restore_backup():
    f = request.files.get("backup_file")
    if not f:
        flash("Keine Datei","error")
        return redirect(url_for("admin"))
    fn = secure_filename(f.filename)
    dst = os.path.join(BACKUP_DIR, fn)
    f.save(dst)
    ok = restore_backup_file(dst)
    flash("Wiederhergestellt" if ok else "Fehler","success" if ok else "error")
    return redirect(url_for("admin"))

@socketio.on('connect')
def sock_connect():
    emit('log_update', {'msg':'Verbunden mit Admin-Dashboard\n'})

if __name__ == "__main__":
    socketio.run(app, host=config.HOST, port=config.PORT_ADMIN, debug=True)
