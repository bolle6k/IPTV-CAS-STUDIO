import os
import uuid
import datetime
from flask import Flask, request, render_template_string, redirect, url_for, flash
import config
from db_helper import DBHelper

app = Flask(__name__)
app.secret_key = config.MASTER_KEY

db = DBHelper(config.DB_PATH)

SELF_SERVICE_TEMPLATE = '''
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <title>Self-Service-Portal</title>
</head>
<body>
  <h1>Self-Service-Portal</h1>

  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      <ul>
      {% for category, message in messages %}
        <li style="color: {% if category == 'error' %}red{% else %}green{% endif %};">
          {{ message }}
        </li>
      {% endfor %}
      </ul>
    {% endif %}
  {% endwith %}

  {% if user %}
    <p><b>Benutzername:</b> {{ user.username }}</p>
    <p><b>HWID:</b> {{ user.hwid }}</p>
    <p><b>Bestes aktives Paket:</b> {{ best_paket }}</p>

    {% if subscription %}
      <p><b>Abo gültig bis:</b> {{ subscription.end_date }}</p>
      <p><b>Restlaufzeit:</b> <span id="remaining-days"></span> Tage</p>
    {% else %}
      <p><i>Kein aktives Abo</i></p>
    {% endif %}

    <p><b>Token:</b> {{ user.token }}</p>
    <p><b>Email:</b> {{ user.email }}</p>

    <form method="post" action="{{ url_for('renew_token') }}">
      <input type="hidden" name="username" value="{{ user.username }}">
      <button type="submit">Token erneuern</button>
    </form>

    <h3>Paket buchen / verlängern</h3>
    <form method="post" action="{{ url_for('subscribe') }}">
      <input type="hidden" name="username" value="{{ user.username }}">
      <label for="paket">Paket:</label>
      <select name="paket" id="paket" required>
        {% for p in prices.keys() %}
          <option value="{{ p }}">{{ p }}</option>
        {% endfor %}
      </select>
      <label for="zyklus">Laufzeit:</label>
      <select name="zyklus" id="zyklus" required>
        <option value="1m">1 Monat – {{ prices[p]['1m'] }}€</option>
        <option value="6m">6 Monate – {{ prices[p]['6m'] }}€</option>
        <option value="12m">1 Jahr – {{ prices[p]['12m'] }}€</option>
      </select>
      <button type="submit">Buchen / Verlängern</button>
    </form>

    <h3>Abo kündigen</h3>
    <form method="post" action="{{ url_for('cancel') }}">
      <input type="hidden" name="username" value="{{ user.username }}">
      <button type="submit" style="color:red;">Abo kündigen</button>
    </form>

  {% else %}
    <form method="post" action="{{ url_for('login') }}">
      <label>Token: <input name="token" required></label>
      <button type="submit">Anmelden</button>
    </form>
    {% if error %}
      <p style="color:red;">{{ error }}</p>
    {% endif %}
  {% endif %}

<script>
  // Resttage-Rechner
  const endDateStr = "{{ subscription.end_date if subscription else '' }}";
  function showRemainingDays() {
    if (!endDateStr) { document.getElementById('remaining-days').innerText = '0'; return; }
    const end = new Date(endDateStr);
    const now = new Date();
    const diff = Math.max(0, Math.ceil((end - now) / (1000*60*60*24)));
    document.getElementById('remaining-days').innerText = diff;
  }
  if (document.getElementById('remaining-days')) showRemainingDays();
</script>
</body>
</html>
'''

@app.route('/selfservice', methods=['GET', 'POST'])
def login():
    # Anmeldung per Token
    token = request.values.get('token', '').strip()
    if request.method == 'POST' and token:
        user_row = db.get_user_by_token(token)
        if not user_row:
            return render_template_string(SELF_SERVICE_TEMPLATE, user=None, error="Ungültiger Token", prices=config.PRICES)
        user = {
            'username': user_row[0],
            'hwid': user_row[1],
            'paket': user_row[2],
            'token': user_row[3],
            'email': user_row[4]
        }
        # beste Paket und aktuelle Subscription
        best = db.get_best_active_package(user['username'])
        sub = db.get_active_subscription(user['username'])
        subscription = None
        if sub:
            subscription = {
                'sub_id': sub[0], 'username': sub[1], 'paket': sub[2],
                'start_date': sub[3], 'end_date': sub[4], 'active': sub[5]
            }
        return render_template_string(
            SELF_SERVICE_TEMPLATE,
            user=user,
            best_paket=best,
            subscription=subscription,
            prices=config.PRICES,
            error=None
        )
    # erster Aufruf oder GET
    return render_template_string(SELF_SERVICE_TEMPLATE, user=None, error=None, prices=config.PRICES)

@app.route('/selfservice/renew_token', methods=['POST'])
def renew_token():
    username = request.form.get('username','').strip()
    if not db.get_user_by_username(username):
        flash("Benutzer nicht gefunden", "error")
    else:
        new_token = uuid.uuid4().hex[:16]
        db.update_user_token(username, new_token)
        flash("Token erneuert", "success")
    return redirect(url_for('login'))

@app.route('/selfservice/subscribe', methods=['POST'])
def subscribe():
    username = request.form.get('username','').strip()
    paket   = request.form.get('paket','').strip()
    zyklus  = request.form.get('zyklus','')
    if not username or not paket or zyklus not in ('1m','6m','12m'):
        flash("Ungültige Eingaben", "error")
        return redirect(url_for('login'))

    # Berechne neuen End-Datum (anhängen an Restlaufzeit)
    today = datetime.datetime.utcnow().date()
    sub = db.get_active_subscription(username)
    if sub and datetime.date.fromisoformat(sub[4]) >= today:
        base = datetime.date.fromisoformat(sub[4])
    else:
        base = today

    if zyklus=='1m':
        new_end = base + datetime.timedelta(days=30)
    elif zyklus=='6m':
        new_end = base + datetime.timedelta(days=183)
    else:
        new_end = base + datetime.timedelta(days=365)

    # Anlage
    db.add_subscription(username, paket, today.isoformat(), new_end.isoformat())
    flash(f"Paket {paket} bis {new_end.isoformat()} gebucht", "success")
    return redirect(url_for('login') + f"?token={db.get_token_by_username(username)}")

@app.route('/selfservice/cancel', methods=['POST'])
def cancel():
    username = request.form.get('username','').strip()
    if not username:
        flash("Benutzername fehlt", "error")
    else:
        # Setze active=0, bleibt aber bis Ablauf gültig
        db.cancel_subscription(username)
        flash("Abo gekündigt – läuft bis Ablauf weiter", "success")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host=config.HOST, port=config.PORT_SELF_SERVICE, debug=True)
