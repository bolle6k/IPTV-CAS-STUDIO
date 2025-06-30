import os
import uuid
import datetime
from flask import Flask, request, render_template_string, redirect, url_for, flash
import config
from db_helper import DBHelper

app = Flask(__name__)
app.secret_key = config.MASTER_KEY

db = DBHelper(config.DB_PATH)

# Template
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
        <li style="color: {% if category == 'error' %}red{% else %}green{% endif %}">{{ message }}</li>
      {% endfor %}
      </ul>
    {% endif %}
  {% endwith %}

  {% if user %}
    <p><b>Benutzername:</b> {{ user.username }}</p>
    <p><b>HWID:</b> {{ user.hwid }}</p>
    <p><b>Bestes aktives Paket:</b> {{ user.paket }}</p>

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
          <option value="{{ p }}" {% if p == user.paket %}selected{% endif %}>{{ p }}</option>
        {% endfor %}
      </select>
      <label for="zyklus">Laufzeit:</label>
      <select name="zyklus" id="zyklus" required>
        <option value="1m">1 Monat - {{ prices[user.paket]['1m'] }}€</option>
        <option value="6m">6 Monate - {{ prices[user.paket]['6m'] }}€</option>
        <option value="12m">1 Jahr - {{ prices[user.paket]['12m'] }}€</option>
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
  // Restlaufzeit berechnen
  function showRemainingDays() {
    const endDateStr = "{{ subscription.end_date if subscription else '' }}";
    if (!endDateStr) {
      document.getElementById('remaining-days').innerText = '0';
      return;
    }
    const endDate = new Date(endDateStr);
    const now = new Date();
    const diffTime = endDate - now;
    const diffDays = Math.max(0, Math.ceil(diffTime / (1000 * 60 * 60 * 24)));
    document.getElementById('remaining-days').innerText = diffDays;
  }
  showRemainingDays();
</script>
</body>
</html>
'''

# Paket-Prioritäten
PAKET_ORDER = {'Basis':1, 'Basis+':2, 'Premium':3}

def compute_subscription_period(username, new_paket, zyklus):
    """Berechnet Start- und Enddatum eines neuen Abos basierend auf bestehendem besten Abo."""
    days_map = {'1m':30, '6m':183, '12m':365}
    period = days_map[zyklus]
    today = datetime.date.today()

    # Beste aktive Subscription holen
    sub = db.get_active_subscription(username)
    if sub:
        current_paket = sub[2]
        current_end = datetime.date.fromisoformat(sub[4])
        # wenn neues Paket höher priorisiert wird, sofort starten
        if PAKET_ORDER[new_paket] > PAKET_ORDER[current_paket]:
            start = today
        else:
            # sonst erst nach aktuellem Ende
            start = current_end
    else:
        start = today
    end = start + datetime.timedelta(days=period)
    return start.isoformat(), end.isoformat()

@app.route('/selfservice', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        token = request.form.get('token','').strip()
        if not token:
            return render_template_string(SELF_SERVICE_TEMPLATE, user=None, error="Bitte Token eingeben", prices=config.PRICES)
        user_data = db.get_user_by_token(token)
        if not user_data:
            return render_template_string(SELF_SERVICE_TEMPLATE, user=None, error="Ungültiger Token", prices=config.PRICES)
        user = {
            'username': user_data[0],
            'hwid': user_data[1],
            'paket': user_data[2],
            'token': user_data[3],
            'email': user_data[4]
        }
        # Beste aktive Subscription und Restlaufzeit
        sub = db.get_active_subscription(user['username'])
        subscription = None
        if sub:
            subscription = {
                'id': sub[0],
                'username': sub[1],
                'paket': sub[2],
                'start_date': sub[3],
                'end_date': sub[4],
                'active': sub[5]
            }
            user['paket'] = subscription['paket']
        return render_template_string(SELF_SERVICE_TEMPLATE, user=user, subscription=subscription, prices=config.PRICES, error=None)

    # GET-Formular
    return render_template_string(SELF_SERVICE_TEMPLATE, user=None, subscription=None, prices=config.PRICES, error=None)

@app.route('/selfservice/renew_token', methods=['POST'])
def renew_token():
    username = request.form.get('username','')
    user = db.get_user_by_username(username)
    if not user:
        flash("Benutzer nicht gefunden","error")
        return redirect(url_for('login'))
    new_token = uuid.uuid4().hex[:16]
    db.update_user_token(username, new_token)
    flash("Token erfolgreich erneuert","success")
    return redirect(f"{url_for('login')}?token={new_token}")

@app.route('/selfservice/subscribe', methods=['POST'])
def subscribe():
    username = request.form.get('username')
    paket = request.form.get('paket')
    zyklus = request.form.get('zyklus')
    if not username or not paket or zyklus not in ('1m','6m','12m'):
        flash("Ungültige Eingaben","error")
        return redirect(url_for('login'))

    # Start- und Enddatum berechnen
    start, end = compute_subscription_period(username, paket, zyklus)
    db.add_subscription(username, paket, start, end)
    # Paket in User-Tabelle updaten auf bestes Paket
    db.update_user_details(username, paket, None, None)
    flash(f"Paket {paket} gebucht von {start} bis {end}","success")
    token = db.get_user_by_username(username)[4]  # neues oder altes Token
    return redirect(f"{url_for('login')}?token={token}")

@app.route('/selfservice/cancel', methods=['POST'])
def cancel():
    username = request.form.get('username')
    if not username:
        flash("Benutzername fehlt","error")
        return redirect(url_for('login'))
    # Subscription auf inaktiv setzen (bleibt aber bis Enddatum gültig)
    db.cancel_subscription(username)
    flash("Abo gekündigt. Es läuft bis zum offiziellen Enddatum weiter.","success")
    token = db.get_user_by_username(username)[4]
    return redirect(f"{url_for('login')}?token={token}")

if __name__ == '__main__':
    app.run(host=config.HOST, port=config.PORT_SELF_SERVICE, debug=True)
