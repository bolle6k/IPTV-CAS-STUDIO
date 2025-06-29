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

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

BACKUP_DIR = "./backups"
DB_PATH = config.DB_PATH
KEYS_DIR = config.KEYS_DIR

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
            for foldername, subfolders, filenames in os.walk(KEYS_DIR):
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
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Admin Dashboard</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.4.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <script src="//cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
  <style>
    img.preview {
      max-height: 40px;
      max-width: 80px;
    }
  </style>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark bg-dark mb-4">
  <div class="container-fluid">
    <a class="navbar-brand" href="{{ url_for('admin') }}">Admin Dashboard</a>
    <div class="d-flex">
      <a href="{{ url_for('logout') }}" class="btn btn-outline-light">Logout</a>
    </div>
  </div>
</nav>
<div class="container">

  <h2>Benutzerverwaltung</h2>
  <form method="get" class="row g-3 mb-3 align-items-center">
    <div class="col-auto">
      <label for="paket" class="col-form-label">Paket-Filter</label>
    </div>
    <div class="col-auto">
      <select id="paket" name="paket" class="form-select">
        <option value="" {% if not paket_filter %}selected{% endif %}>Alle</option>
        <option value="Basis" {% if paket_filter == 'Basis' %}selected{% endif %}>Basis</option>
        <option value="Basis+" {% if paket_filter == 'Basis+' %}selected{% endif %}>Basis+</option>
        <option value="Premium" {% if paket_filter == 'Premium' %}selected{% endif %}>Premium</option>
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
        <tr>
          <th>Username</th><th>HWID</th><th>Paket</th><th>Token</th><th>Email</th><th>Aktionen</th>
        </tr>
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
                <option value="Basis" {% if u[2] == 'Basis' %}selected{% endif %}>Basis</option>
                <option value="Basis+" {% if u[2] == 'Basis+' %}selected{% endif %}>Basis+</option>
                <option value="Premium" {% if u[2] == 'Premium' %}selected{% endif %}>Premium</option>
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

  {% if total_pages > 1 %}
  <nav aria-label="Seiten Navigation">
    <ul class="pagination justify-content-center">
      <li class="page-item {% if page == 1 %}disabled{% endif %}">
        <a class="page-link" href="{{ url_for('admin', paket=paket_filter, hwid_filter=hwid_filter, token_filter=token_filter, page=page-1) }}">← Zurück</a>
      </li>
      <li class="page-item disabled"><a class="page-link">Seite {{ page }} von {{ total_pages }}</a></li>
      <li class="page-item {% if page == total_pages %}disabled{% endif %}">
        <a class="page-link" href="{{ url_for('admin', paket=paket_filter, hwid_filter=hwid_filter, token_filter=token_filter, page=page+1) }}">Weiter →</a>
      </li>
    </ul>
  </nav>
  {% endif %}

  <hr>

  <h3>Watermark & DRM Logo Verwaltung</h3>
  <form method="post" action="{{ url_for('upload_watermark') }}" enctype="multipart/form-data" class="mb-3">
    <div class="mb-2">
      <label for="wmName" class="form-label">Name</label>
      <input type="text" id="wmName" name="name" class="form-control" required>
    </div>
    <div class="mb-2">
      <label for="wmFile" class="form-label">Datei</label>
      <input type="file" id="wmFile" name="file" class="form-control" accept="image/*" required>
    </div>
    <div class="mb-2">
      <label for="wmPosition" class="form-label">Position</label>
      <select id="wmPosition" name="position" class="form-select">
        <option value="top-left">Oben Links</option>
        <option value="top-right">Oben Rechts</option>
        <option value="bottom-left">Unten Links</option>
        <option value="bottom-right" selected>Unten Rechts</option>
      </select>
    </div>
    <div class="form-check mb-3">
      <input class="form-check-input" type="checkbox" id="wmVisible" name="visible" checked>
      <label class="form-check-label" for="wmVisible">Sichtbar</label>
    </div>
    <button type="submit" class="btn btn-primary">Hochladen</button>
  </form>

  <div class="table-responsive">
    <table class="table table-bordered align-middle">
      <thead class="table-light">
        <tr>
          <th>ID</th><th>Name</th><th>Bild</th><th>Position</th><th>Sichtbar</th><th>Aktion</th>
        </tr>
      </thead>
      <tbody>
        {% for wm in watermarks %}
        <tr>
          <td>{{ wm[0] }}</td>
          <td>{{ wm[1] }}</td>
          <td><img src="{{ url_for('static', filename=wm[2].split('static/')[-1]) }}" class="preview"></td>
          <td>{{ wm[3] }}</td>
          <td>{{ 'Ja' if wm[4] else 'Nein' }}</td>
          <td>
            <form method="post" action="{{ url_for('toggle_watermark') }}" style="display:inline;">
              <input type="hidden" name="wm_id" value="{{ wm[0] }}">
              <input type="hidden" name="visible" value="{{ 0 if wm[4] else 1 }}">
              <button type="submit" class="btn btn-sm btn-outline-secondary">
                {{ 'Deaktivieren' if wm[4] else 'Aktivieren' }}
              </button>
            </form>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <hr>

  <h3>ECM / EMM Schlüssel</h3>
  <table class="table table-striped table-sm">
    <thead class="table-dark">
      <tr><th>Typ</th><th>Key</th><th>Erstellt</th><th>User</th><th>Paket</th></tr>
    </thead>
    <tbody>
      {% for e in ecm_emm_records %}
      <tr>
        <td>ECM/EMM</td>
        <td><code>{{ e[1] }}</code></td>
        <td>{{ e[5] }}</td>
        <td>{{ e[3] }}</td>
        <td>{{ e[4] }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <p>Nächste Key-Rotation: {{ next_rotation }}</p>
  <form method="post" action="{{ url_for('rotate_key') }}">
    <button type="submit" class="btn btn-warning">🔁 Manuelle Rotation</button>
  </form>

  <hr>

  <h3>Backup & Restore</h3>
  <form method="post" action="{{ url_for('trigger_backup') }}">
    <button type="submit" class="btn btn-success mb-2">Backup erstellen</button>
  </form>

  {% if last_backup %}
    <p>Letztes Backup: {{ last_backup }}</p>
    <a href="{{ url_for('download_backup', filename=last_backup) }}" class="btn btn-primary mb-3">Backup herunterladen</a>
  {% endif %}

  <form method="post" action="{{ url_for('restore_backup') }}" enctype="multipart/form-data" class="mb-3">
    <label>Backup hochladen zum Wiederherstellen:</label>
    <input type="file" name="backup_file" accept=".zip" required>
    <button type="submit" class="btn btn-warning">Backup wiederherstellen</button>
  </form>

  <hr>

  <h3>Live Logs</h3>
  <pre id="logArea" style="background:#f8f9fa; padding:1rem; height:200px; overflow:auto;"></pre>

</div>

<script>
  var socket = io();
  var logArea = document.getElementById('logArea');
  socket.on('log_update', function(data) {
    logArea.textContent += data.msg + "\\n";
    logArea.scrollTop = logArea.scrollHeight;
  });
</script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.4.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>'''

# Routen-Implementierungen

@app.route("/")
def index():
    return redirect(url_for("admin"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == "admin" and password == config.MASTER_KEY:
            session["logged_in"] = True
            log_event("LOGIN", username)
            return redirect(url_for("admin"))
        else:
            return "Ungültige Anmeldedaten", 403
    return '''
        <form method="post">
            Benutzername: <input name="username" required><br>
            Passwort: <input type="password" name="password" required><br>
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
    page = int(request.args.get("page", 1))
    offset = (page - 1) * PER_PAGE

    all_users = db.list_users(paket_filter=paket, hwid_filter=hwid_filter, token_filter=token_filter)
    total_users = len(all_users)
    total_pages = math.ceil(total_users / PER_PAGE)
    users = all_users[offset:offset+PER_PAGE]

    log_content = ""
    if os.path.exists(LOGFILE):
        with open(LOGFILE, "r") as f:
            lines = f.readlines()[-20:]
            log_content = "".join(lines)

    watermarks = db.get_watermarks()

    next_rotation = last_key_rotation + datetime.timedelta(seconds=KEY_ROTATION_INTERVAL)

    ecm_emm_records = db.get_keys(limit=20)

    last_backup = None
    if os.path.exists(BACKUP_DIR):
        backups = [f for f in os.listdir(BACKUP_DIR) if f.endswith('.zip')]
        if backups:
            last_backup = sorted(backups)[-1]

    return render_template_string(
        TEMPLATE,
        users=users,
        paket_filter=paket,
        hwid_filter=hwid_filter,
        token_filter=token_filter,
        page=page,
        total_pages=total_pages,
        watermarks=watermarks,
        log_content=log_content,
        ecm_emm_records=ecm_emm_records,
        next_rotation=next_rotation.strftime("%Y-%m-%d %H:%M:%S"),
        last_backup=last_backup
    )

@app.route("/admin/delete", methods=["POST"])
@login_required
def delete_user():
    username = request.form.get("username")
    if username:
        db.delete_user(username)
        log_event("DELETE_USER", username)
    return redirect(url_for("admin"))

@app.route("/admin/edit", methods=["POST"])
@login_required
def edit_user():
    username = request.form.get("username")
    paket = request.form.get("paket")
    hwid = request.form.get("hwid")
    email = request.form.get("email")
    if username and paket and hwid is not None and email is not None:
        db.update_user_details(username, paket, hwid, email)
        log_event("EDIT_USER", username)
    return redirect(url_for("admin"))

@app.route("/admin/rotate_key", methods=["POST"])
@login_required
def rotate_key():
    global last_key_rotation

    new_key = os.urandom(16).hex()
    valid_until = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=KEY_ROTATION_INTERVAL)).isoformat()

    db.store_key(new_key, valid_until, user='admin', paket='all')
    last_key_rotation = datetime.datetime.now(datetime.timezone.utc)

    log_event("MANUAL_KEY_ROTATION", "admin")

    return redirect(url_for("admin"))

@app.route("/admin/download-log", methods=["GET"])
@login_required
def download_log():
    if os.path.exists(LOGFILE):
        return send_file(LOGFILE, as_attachment=True)
    return "Logfile nicht gefunden", 404

@app.route("/admin/upload_watermark", methods=["POST"])
@login_required
def upload_watermark():
    if 'file' not in request.files:
        return "Keine Datei hochgeladen", 400
    file = request.files['file']
    name = request.form.get('name', 'Unnamed')
    position = request.form.get('position', 'bottom-right')
    visible = 'visible' in request.form
    if file.filename == '':
        return "Keine Datei ausgewählt", 400
    if not allowed_file(file.filename):
        return "Dateityp nicht erlaubt", 400

    filename = secure_filename(file.filename)
    save_path = os.path.join('static', 'watermarks', filename)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    file.save(save_path)

    db.add_watermark(name, save_path, position, visible)
    log_event("UPLOAD_WATERMARK", name)
    return redirect(url_for("admin"))

@app.route("/admin/toggle_watermark", methods=["POST"])
@login_required
def toggle_watermark():
    wm_id = request.form.get('wm_id')
    visible = request.form.get('visible')
    if wm_id is None or visible is None:
        return "Fehlende Parameter", 400
    visible_bool = visible == '1'
    db.update_watermark(int(wm_id), visible=visible_bool)
    log_event("TOGGLE_WATERMARK", f"ID {wm_id} -> {'sichtbar' if visible_bool else 'unsichtbar'}")
    return redirect(url_for("admin"))

@app.route("/admin/create_backup", methods=["POST"])
@login_required
def trigger_backup():
    backup_name = create_backup()
    flash(f"Backup erstellt: {backup_name}", "success")
    return redirect(url_for("admin"))

@app.route("/admin/download_backup/<filename>")
@login_required
def download_backup(filename):
    path = os.path.join(BACKUP_DIR, filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "Backup nicht gefunden", 404

@app.route("/admin/restore_backup", methods=["POST"], endpoint='restore_backup')
@login_required
def restore_backup():
    if 'backup_file' not in request.files:
        flash("Keine Datei ausgewählt", "danger")
        return redirect(url_for("admin"))

    file = request.files['backup_file']
    if file.filename == '':
        flash("Keine Datei ausgewählt", "danger")
        return redirect(url_for("admin"))

    filename = secure_filename(file.filename)
    save_path = os.path.join(BACKUP_DIR, filename)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    file.save(save_path)

    success = restore_backup_file(save_path)
    if success:
        flash(f"Backup {filename} erfolgreich wiederhergestellt", "success")
    else:
        flash(f"Fehler beim Wiederherstellen von {filename}", "danger")

    return redirect(url_for("admin"))

@socketio.on('connect')
def socket_connect():
    emit('log_update', {'msg': 'Verbunden mit Admin-Dashboard'})

if __name__ == "__main__":
    socketio.run(app, host=config.HOST, port=config.PORT_ADMIN, debug=True)
