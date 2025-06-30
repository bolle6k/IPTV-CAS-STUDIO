import os
import threading
import math
import datetime
import zipfile
from functools import wraps
from flask import (
    Flask, render_template_string, request, redirect,
    url_for, send_file, session, flash
)
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit
import config
from db_helper import DBHelper

app = Flask(__name__)
app.secret_key = config.MASTER_KEY
socketio = SocketIO(app, async_mode='eventlet')

db = DBHelper(config.DB_PATH)

LOGFILE = config.LOG_FILE
PER_PAGE = 50
KEY_ROTATION_INTERVAL = config.ROTATION_INTERVAL
last_key_rotation = datetime.datetime.now(datetime.timezone.utc)

BACKUP_DIR = "./backups"
DB_PATH = config.DB_PATH
KEYS_DIR = config.KEYS_DIR

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def log_event(action, username):
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    message = f"{timestamp} | {action} | {username}"
    with open(LOGFILE, "a") as f:
        f.write(message + "\n")
    socketio.emit('log_update', {'msg': message})

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def create_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"iptv_backup_{timestamp}.zip"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        if os.path.exists(DB_PATH):
            zipf.write(DB_PATH, os.path.basename(DB_PATH))
        if os.path.isdir(KEYS_DIR):
            for foldername, _, filenames in os.walk(KEYS_DIR):
                for filename in filenames:
                    filepath = os.path.join(foldername, filename)
                    arcname = os.path.relpath(filepath, start='.')
                    zipf.write(filepath, arcname)
    log_event("Backup erstellt", "system")
    return backup_name

def restore_backup_file(backup_file):
    if not os.path.exists(backup_file):
        return False
    with zipfile.ZipFile(backup_file, 'r') as zipf:
        zipf.extractall()
    log_event("Backup wiederhergestellt", "system")
    return True

TEMPLATE = '''<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Thunder IPTV CAS – Admin Dashboard</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.4.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body {
      background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
      color: #fff;
    }
    .navbar-brand {
      font-weight: bold;
      font-size: 1.5rem;
      letter-spacing: 1px;
    }
    .card {
      border-radius: 1rem;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    .footer {
      margin-top: 2rem;
      text-align: center;
      font-size: 0.9rem;
      color: rgba(255,255,255,0.6);
    }
    h2, h3 {
      color: #ffd700;
    }
    .btn-thunder {
      background: #ff6f61;
      border: none;
      color: #fff;
    }
    .btn-thunder:hover {
      background: #ff3b2e;
    }
  </style>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark bg-dark mb-4">
  <div class="container-fluid">
    <a class="navbar-brand" href="{{ url_for('admin') }}">⚡️ Thunder IPTV CAS</a>
    <div class="d-flex">
      <a href="{{ url_for('logout') }}" class="btn btn-outline-light">Logout</a>
    </div>
  </div>
</nav>

<div class="container">

  <div class="card p-4 mb-4 bg-light text-dark">
    <h2>Benutzerverwaltung</h2>
    <form method="get" class="row g-3 mb-3 align-items-center">
      <div class="col-auto"><label for="paket" class="col-form-label">Paket-Filter</label></div>
      <div class="col-auto">
        <select id="paket" name="paket" class="form-select">
          <option value="" {% if not paket_filter %}selected{% endif %}>Alle</option>
          <option value="Basis" {% if paket_filter=='Basis' %}selected{% endif %}>Basis</option>
          <option value="Basis+" {% if paket_filter=='Basis+' %}selected{% endif %}>Basis+</option>
          <option value="Premium" {% if paket_filter=='Premium' %}selected{% endif %}>Premium</option>
        </select>
      </div>
      <div class="col-auto">
        <input type="text" name="hwid_filter" class="form-control" placeholder="HWID" value="{{ hwid_filter }}">
      </div>
      <div class="col-auto">
        <input type="text" name="token_filter" class="form-control" placeholder="Token" value="{{ token_filter }}">
      </div>
      <div class="col-auto">
        <button type="submit" class="btn btn-primary">Filter anwenden</button>
      </div>
    </form>
    <div class="table-responsive">
      <table class="table table-striped table-hover align-middle">
        <thead class="table-dark">
          <tr><th>Username</th><th>HWID</th><th>Paket</th><th>Token</th><th>Email</th><th>Aktionen</th></tr>
        </thead>
        <tbody>
          {% for u in users %}
          <tr>
            <td>{{ u[0] }}</td>
            <td>{{ u[1] }}</td>
            <td>{{ u[2] }}</td>
            <td><code>{{ u[3] }}</code></td>
            <td>{{ u[4] }}</td>
            <td>
              <form method="post" action="{{ url_for('delete_user') }}" class="d-inline" onsubmit="return confirm('Benutzer wirklich löschen?');">
                <input type="hidden" name="username" value="{{ u[0] }}">
                <button type="submit" class="btn btn-sm btn-danger">Löschen</button>
              </form>
              <form method="post" action="{{ url_for('edit_user') }}" class="d-inline">
                <input type="hidden" name="username" value="{{ u[0] }}">
                <select name="paket" class="form-select form-select-sm d-inline w-auto">
                  <option value="Basis" {% if u[2]=='Basis' %}selected{% endif %}>Basis</option>
                  <option value="Basis+" {% if u[2]=='Basis+' %}selected{% endif %}>Basis+</option>
                  <option value="Premium" {% if u[2]=='Premium' %}selected{% endif %}>Premium</option>
                </select>
                <input type="text" name="hwid" value="{{ u[1] }}" size="15" class="form-control form-control-sm d-inline w-auto" required>
                <input type="email" name="email" value="{{ u[4] }}" size="20" class="form-control form-control-sm d-inline w-auto">
                <button type="submit" class="btn btn-sm btn-success">Aktualisieren</button>
              </form>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    {% if total_pages>1 %}
    <nav><ul class="pagination justify-content-center">
      <li class="page-item {% if page==1 %}disabled{% endif %}"><a class="page-link" href="{{ url_for('admin', paket=paket_filter, hwid_filter=hwid_filter, token_filter=token_filter, page=page-1) }}">←</a></li>
      <li class="page-item disabled"><a class="page-link">Seite {{ page }} / {{ total_pages }}</a></li>
      <li class="page-item {% if page==total_pages %}disabled{% endif %}"><a class="page-link" href="{{ url_for('admin', paket=paket_filter, hwid_filter=hwid_filter, token_filter=token_filter, page=page+1) }}">→</a></li>
    </ul></nav>
    {% endif %}
  </div>

  <div class="card p-4 mb-4 bg-light text-dark">
    <h3>Watermark & DRM Logo Verwaltung</h3>
    <form method="post" action="{{ url_for('upload_watermark') }}" enctype="multipart/form-data" class="mb-3">
      <div class="mb-2"><label class="form-label">Name</label><input type="text" name="name" class="form-control" required></div>
      <div class="mb-2"><label class="form-label">Datei</label><input type="file" name="file" accept="image/*" class="form-control" required></div>
      <div class="mb-2"><label class="form-label">Position</label>
        <select name="position" class="form-select">
          <option value="top-left">Oben Links</option>
          <option value="top-right">Oben Rechts</option>
          <option value="bottom-left">Unten Links</option>
          <option value="bottom-right" selected>Unten Rechts</option>
        </select>
      </div>
      <div class="form-check mb-3"><input class="form-check-input" type="checkbox" name="visible" checked><label class="form-check-label">Sichtbar</label></div>
      <button class="btn btn-primary">Hochladen</button>
    </form>
    <div class="table-responsive">
      <table class="table table-bordered align-middle">
        <thead class="table-light"><tr><th>ID</th><th>Name</th><th>Bild</th><th>Position</th><th>Sichtbar</th><th>Aktion</th></tr></thead>
        <tbody>
          {% for wm in watermarks %}
          <tr>
            <td>{{ wm[0] }}</td>
            <td>{{ wm[1] }}</td>
            <td><img src="{{ url_for('static', filename=wm[2].split('static/')[-1]) }}" style="max-height:40px;"></td>
            <td>{{ wm[3] }}</td>
            <td>{{ 'Ja' if wm[4] else 'Nein' }}</td>
            <td>
              <form method="post" action="{{ url_for('toggle_watermark') }}" class="d-inline">
                <input type="hidden" name="wm_id" value="{{ wm[0] }}">
                <input type="hidden" name="visible" value="{{ 0 if wm[4] else 1 }}">
                <button class="btn btn-sm btn-outline-secondary">{{ 'Deaktivieren' if wm[4] else 'Aktivieren' }}</button>
              </form>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>

  <div class="card p-4 mb-4 bg-light text-dark">
    <h3>ECM / EMM Schlüssel</h3>
    <table class="table table-striped table-sm">
      <thead class="table-dark"><tr><th>Typ</th><th>Key</th><th>Erstellt</th><th>User</th><th>Paket</th></tr></thead>
      <tbody>
        {% for e in ecm_emm_records %}
        <tr>
          <td>{{ e['type'] }}</td>
          <td><code>{{ e['key'] }}</code></td>
          <td>{{ e['timestamp'] }}</td>
          <td>{{ e['user'] }}</td>
          <td>{{ e['paket'] }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    <p>Nächste Rotation: {{ next_rotation }}</p>
    <form method="post" action="{{ url_for('rotate_key') }}">
      <button class="btn btn-thunder">🔁 Manuelle Rotation</button>
    </form>
  </div>

  <div class="card p-4 mb-4 bg-light text-dark">
    <h3>Backup & Restore</h3>
    <form method="post" action="{{ url_for('trigger_backup') }}" class="mb-2">
      <button class="btn btn-success">Backup erstellen</button>
    </form>
    {% if last_backup %}
      <a href="{{ url_for('download_backup', filename=last_backup) }}" class="btn btn-primary mb-2">Backup herunterladen</a>
    {% endif %}
    <form method="post" action="{{ url_for('restore_backup') }}" enctype="multipart/form-data">
      <input type="file" name="backup_file" accept=".zip" required class="form-control mb-2">
      <button class="btn btn-warning">Backup wiederherstellen</button>
    </form>
  </div>

  <div class="card p-4 mb-4 bg-light text-dark">
    <h3>Live Logs</h3>
    <pre id="logArea" style="background:#000; color:#0f0; padding:1rem; height:200px; overflow:auto;"></pre>
  </div>

  <div class="footer">
    &copy; 2025 Produkt “Thunder” – Robert Schilke
  </div>
</div>

<script src="//cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
<script>
  var socket = io();
  socket.on('log_update', function(data) {
    var logArea = document.getElementById('logArea');
    logArea.textContent += data.msg + "\\n";
    logArea.scrollTop = logArea.scrollHeight;
  });
</script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.4.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>'''

@app.route("/")
def index():
    return redirect(url_for("admin"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uname = request.form["username"]
        pwd = request.form["password"]
        if uname=="admin" and pwd==config.MASTER_KEY:
            session["logged_in"] = True
            log_event("LOGIN", uname)
            return redirect(url_for("admin"))
        return "Ungültige Anmeldedaten", 403
    return '''
      <form method="post">
        Benutzername: <input name="username"><br>
        Passwort: <input type="password" name="password"><br>
        <input type="submit" value="Login">
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
    paket = request.args.get("paket") or None
    hwid_filter = request.args.get("hwid_filter") or ""
    token_filter = request.args.get("token_filter") or ""
    page = int(request.args.get("page",1))
    all_users = db.list_users(paket, hwid_filter, token_filter)
    total_pages = math.ceil(len(all_users)/PER_PAGE)
    users = all_users[(page-1)*PER_PAGE:page*PER_PAGE]
    watermarks = db.get_watermarks()
    ecm_emm_records = db.get_recent_keys(limit=20)
    next_rotation = (last_key_rotation + datetime.timedelta(seconds=KEY_ROTATION_INTERVAL)).strftime("%Y-%m-%d %H:%M:%S")
    last_backup = None
    if os.path.isdir(BACKUP_DIR):
        backs = [f for f in os.listdir(BACKUP_DIR) if f.endswith('.zip')]
        if backs: last_backup=sorted(backs)[-1]
    return render_template_string(
        TEMPLATE,
        users=users, paket_filter=paket,
        hwid_filter=hwid_filter, token_filter=token_filter,
        page=page, total_pages=total_pages,
        watermarks=watermarks,
        ecm_emm_records=ecm_emm_records,
        next_rotation=next_rotation,
        last_backup=last_backup
    )

@app.route("/admin/delete", methods=["POST"])
@login_required
def delete_user():
    db.delete_user(request.form["username"])
    log_event("DELETE_USER", request.form["username"])
    return redirect(url_for("admin"))

@app.route("/admin/edit", methods=["POST"])
@login_required
def edit_user():
    db.update_user_details(
        request.form["username"],
        request.form["paket"],
        request.form["hwid"],
        request.form["email"]
    )
    log_event("EDIT_USER", request.form["username"])
    return redirect(url_for("admin"))

@app.route("/admin/rotate_key", methods=["POST"])
@login_required
def rotate_key():
    global last_key_rotation
    new_key = os.urandom(16).hex()
    last_key_rotation = datetime.datetime.now(datetime.timezone.utc)
    db.store_key(new_key, valid_until=None)  # store_key ohne user/paket-Flags
    log_event("MANUAL_KEY_ROTATION", "admin")
    return redirect(url_for("admin"))

@app.route("/admin/download_log")
@login_required
def download_log():
    if os.path.exists(LOGFILE):
        return send_file(LOGFILE, as_attachment=True)
    return "Logfile nicht gefunden", 404

@app.route("/admin/upload_watermark", methods=["POST"])
@login_required
def upload_watermark():
    file = request.files.get("file")
    if not file or not allowed_file(file.filename):
        return "Invalid file", 400
    name = request.form.get("name","")
    position = request.form.get("position","bottom-right")
    visible = "visible" in request.form
    filename = secure_filename(file.filename)
    save_path = os.path.join("static","watermarks", filename)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    file.save(save_path)
    db.add_watermark(name, save_path, position, visible)
    log_event("UPLOAD_WATERMARK", name)
    return redirect(url_for("admin"))

@app.route("/admin/toggle_watermark", methods=["POST"])
@login_required
def toggle_watermark():
    wm_id = int(request.form["wm_id"])
    visible = request.form["visible"]=="1"
    db.update_watermark(wm_id, visible=visible)
    log_event("TOGGLE_WATERMARK", f"WM {wm_id}")
    return redirect(url_for("admin"))

@app.route("/admin/create_backup", methods=["POST"])
@login_required
def trigger_backup():
    name = create_backup()
    flash(f"Backup {name} erstellt", "success")
    return redirect(url_for("admin"))

@app.route("/admin/download_backup/<filename>")
@login_required
def download_backup(filename):
    path = os.path.join(BACKUP_DIR, filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "Nicht gefunden", 404

@app.route("/admin/restore_backup", methods=["POST"], endpoint="restore_backup")
@login_required
def restore_backup():
    f = request.files.get("backup_file")
    if not f:
        flash("Keine Datei", "error"); return redirect(url_for("admin"))
    fname = secure_filename(f.filename)
    save_path = os.path.join(BACKUP_DIR, fname)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    f.save(save_path)
    ok = restore_backup_file(save_path)
    flash("Wiederhergestellt" if ok else "Fehler", "success" if ok else "error")
    return redirect(url_for("admin"))

@socketio.on('connect')
def on_connect():
    emit('log_update', {'msg':'Verbunden mit Thunder Dashboard'})

if __name__ == "__main__":
    socketio.run(app, host=config.HOST, port=config.PORT_ADMIN, debug=True)
