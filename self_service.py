import datetime
from flask import Flask, request, session, redirect, url_for, render_template_string, flash
from db_helper import DBHelper
import config

app = Flask(__name__)
app.secret_key = config.MASTER_KEY

db = DBHelper(config.DB_PATH)

SELF_SERVICE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Self-Service-Portal</title>
</head>
<body>
<h1>Self-Service-Portal</h1>

{% with messages = get_flashed_messages(with_categories=true) %}
  {% if messages %}
    <ul>
    {% for category, message in messages %}
      <li style="color: {% if category == 'error' %}red{% else %}green{% endif %}">{{ message }}</li>
    {% endfor %}
    </ul>
  {% endif %}
{% endwith %}

{% if user %}
  <p><b>Benutzername:</b> {{ user[0] }}</p>
  <p><b>HWID:</b> {{ user[1] }}</p>
  <p><b>Aktives Paket:</b> {{ best_paket }}</p>

  {% if active_subscriptions %}
    <h3>Abonnements (inkl. Warteschlange):</h3>
    <ul>
    {% for abo in active_subscriptions %}
      <li>
        {{ abo[1] }} - gültig von {{ abo[2] }} bis {{ abo[3] }}
        ({{ abo[5] }} Tage Restlaufzeit) {% if abo[4] == 1 %}(Aktiv){% else %}(In Warteschlange){% endif %}
      </li>
    {% endfor %}
    </ul>
  {% else %}
    <p><i>Kein aktives Abo</i></p>
  {% endif %}

  <p><b>Token:</b> {{ user[3] }}</p>
  <p><b>Email:</b> {{ user[4] }}</p>

  <h3>Paket buchen / verlängern</h3>
  <form method="post" action="{{ url_for('subscribe') }}">
    <input type="hidden" name="username" value="{{ user[0] }}">
    <label for="paket">Paket:</label>
    <select name="paket" id="paket" required>
      {% for p in prices.keys() %}
        <option value="{{ p }}" {% if p == best_paket %}selected{% endif %}>{{ p }}</option>
      {% endfor %}
    </select>

    <label for="zyklus">Laufzeit:</label>
    <select name="zyklus" id="zyklus" required>
      <option value="1m">1 Monat - {{ prices[best_paket]['1m'] }}€</option>
      <option value="6m">6 Monate - {{ prices[best_paket]['6m'] }}€</option>
      <option value="12m">1 Jahr - {{ prices[best_paket]['12m'] }}€</option>
    </select>

    <button type="submit">Buchen / Verlängern</button>
  </form>

  <h3>Abo kündigen</h3>
  <form method="post" action="{{ url_for('cancel') }}">
    <input type="hidden" name="username" value="{{ user[0] }}">
    <label for="cancel_paket">Paket kündigen:</label>
    <select name="cancel_paket" id="cancel_paket" required>
      {% for abo in active_subscriptions if abo[4] == 1 %}
        <option value="{{ abo[1] }}">{{ abo[1] }}</option>
      {% endfor %}
    </select>
    <button type="submit" style="color:red;">Abo kündigen</button>
  </form>

  <p><a href="{{ url_for('logout') }}">Logout</a></p>

{% else %}
  <form method="post" action="{{ url_for('login') }}">
    <label>Token: <input name="token" required></label>
    <button type="submit">Anmelden</button>
  </form>
  {% if error %}
    <p style="color:red;">{{ error }}</p>
  {% endif %}
{% endif %}

</body>
</html>
'''

def calculate_remaining_days(end_date_str):
    try:
        end_date = datetime.datetime.fromisoformat(end_date_str).date()
        today = datetime.datetime.utcnow().date()
        delta = (end_date - today).days
        return max(delta, 0)
    except:
        return 0

@app.route('/selfservice', methods=['GET', 'POST'])
def selfservice():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    user = db.get_user_by_username(username)
    if not user:
        return render_template_string(SELF_SERVICE_TEMPLATE, user=None, error="Benutzer nicht gefunden", prices=config.PRICES)

    best_paket = db.get_best_active_package(username)
    abos = db.get_active_subscriptions(username)
    active_subscriptions = []
    for abo in abos:
        resttage = calculate_remaining_days(abo[3])
        # abo: (id, paket, start_date, end_date, canceled, active)
        active_subscriptions.append((abo[0], abo[1], abo[2], abo[3], abo[4], abo[5], resttage))

    return render_template_string(SELF_SERVICE_TEMPLATE,
                                  user=user,
                                  best_paket=best_paket,
                                  active_subscriptions=active_subscriptions,
                                  prices=config.PRICES)

@app.route('/subscribe', methods=['POST'])
def subscribe():
    username = request.form.get('username')
    paket = request.form.get('paket')
    zyklus = request.form.get('zyklus')

    if not username or not paket or zyklus not in ('1m', '6m', '12m'):
        flash("Ungültige Eingaben", "error")
        return redirect(url_for('selfservice'))

    zyklus_map = {'1m': 30, '6m': 180, '12m': 365}
    zyklus_tage = zyklus_map.get(zyklus, 30)

    db.add_or_upgrade_subscription(username, paket, zyklus_tage)

    flash(f"Paket {paket} gebucht/verlängert für {zyklus_tage} Tage.", "success")
    return redirect(url_for('selfservice'))

@app.route('/cancel', methods=['POST'])
def cancel():
    username = request.form.get('username')
    paket = request.form.get('cancel_paket')

    if not username or not paket:
        flash("Ungültige Kündigungsdaten.", "error")
        return redirect(url_for('selfservice'))

    db.cancel_subscription(username, paket)
    flash(f"Abo {paket} wurde gekündigt.", "success")
    return redirect(url_for('selfservice'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        token = request.form.get('token')
        if not token:
            return render_template_string(SELF_SERVICE_TEMPLATE, user=None, error="Token erforderlich", prices=config.PRICES)
        user = db.get_user_by_token(token)
        if not user:
            return render_template_string(SELF_SERVICE_TEMPLATE, user=None, error="Ungültiger Token", prices=config.PRICES)

        session['username'] = user[0]
        return redirect(url_for('selfservice'))

    return render_template_string(SELF_SERVICE_TEMPLATE, user=None, error=None, prices=config.PRICES)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(port=config.PORT_SELF_SERVICE, debug=True)
