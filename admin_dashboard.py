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

# --- Template gekürzt; bleibt unverändert ---
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
    <!-- hier kommt dein Filter-Form und User-Tabelle rein wie gehabt -->
    {{ /* deine bestehende Benutzerverwaltung-Tabellen-HTML */ }}
  </div>

  <div class="card p-4 mb-4 bg-light text-dark">
    <h3>Watermark & DRM Logo Verwaltung</h3>
    <!-- dein Watermark-Form und Tabelle -->
    {{ /* Watermark-Upload und Liste */ }}
  </div>

  <div class="card p-4 mb-4 bg-light text-dark">
    <h3>ECM / EMM Schlüssel</h3>
    <!-- deine Schlüssel-Tabelle -->
    {{ /* ECM/EMM-Tabelle */ }}
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
    const logArea = document.getElementById('logArea');
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

    # ECM/EMM Historie aus DB holen (muss db.get_recent_keys implementieren)
    ecm_emm_records = db.get_recent_keys(limit=20)

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
    if username and paket is not None and hwid is not None and email is not None:
        db.update_user_details(username, paket, hwid, email)
        log_event("EDIT_USER", username)
    return redirect(url_for("admin"))

@app.route("/admin/rotate_key", methods=["POST"])
@login_required
def rotate_key():
    global last_key_rotation
    # Neu erzeugen und speichern in DB (Positions-Parameter, keine Keywords)
    new_key = os.urandom(16).hex()
    valid_until = None  # oder datetime... if gewünscht

    # So aufrufen, damit es zur Signatur von DBHelper passt:
    key_id = db.store_key(new_key, valid_until, 'admin', 'all')

    last_key_rotation = datetime.datetime.now(datetime.timezone.utc)
    log_event("MANUAL_KEY_ROTATION", f"key_id={key_id}")
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
    file = request.files.get('file')
    name = request.form.get('name', 'Unnamed')
    position = request.form.get('position', 'bottom-right')
    visible = 'visible' in request.form

    if not file or file.filename == '':
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
    db.update_watermark(int(wm_id), visible=(visible == '1'))
    log_event("TOGGLE_WATERMARK", wm_id)
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
    file = request.files.get('backup_file')
    if not file or file.filename == '':
        flash("Keine Datei ausgewählt", "danger")
        return redirect(url_for("admin"))

    filename = secure_filename(file.filename)
    save_path = os.path.join(BACKUP_DIR, filename)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    file.save(save_path)

    if restore_backup_file(save_path):
        flash(f"Backup {filename} wiederhergestellt", "success")
    else:
        flash(f"Fehler beim Wiederherstellen von {filename}", "danger")

    return redirect(url_for("admin"))

@socketio.on('connect')
def socket_connect():
    emit('log_update', {'msg': 'Verbunden mit Admin-Dashboard'})

if __name__ == "__main__":
    socketio.run(app, host=config.HOST, port=config.PORT_ADMIN, debug=True)
