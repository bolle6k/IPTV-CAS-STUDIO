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
<head><meta charset="utf-8"><title>Self-Service-Portal</title></head>
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

    <!-- Token erneuern -->
    <form method="post" action="{{ url_for('renew_token') }}">
      <input type="hidden" name="username" value="{{ user.username }}">
      <button type="submit">Token erneuern</button>
    </form>

    <!-- Paket buchen / verlängern -->
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

    <!-- Abo kündigen -->
    <h3>Abo kündigen</h3>
    <form method="post" action="{{ url_for('cancel') }}">
      <input type="hidden" name="username" value="{{ user.username }}">
      <button type="submit" style="color:red;">Abo kündigen</button>
    </form>

  {% else %}
    <!-- Login Form -->
    <form method="post" action="{{ url_for('selfservice') }}">
      <label>Token: <input name="token" required></label>
      <button type="submit">Anmelden</button>
    </form>
    {% if error %}
      <p style="color:red;">{{ error }}</p>
    {% endif %}
  {% endif %}

  <script>
    // Dynamische Preis-Labels
    const prices = {{ prices | tojson }};
    const paketSelect = document.getElementById('paket');
    const zyklusSelect = document.getElementById('zyklus');
    function updatePrices() {
      const paket = paketSelect.value;
      const opts = {
        '1m': `1 Monat - ${prices[paket]['1m']}€`,
        '6m': `6 Monate - ${prices[paket]['6m']}€`,
        '12m': `1 Jahr - ${prices[paket]['12m']}€`
      };
      for (let o of zyklusSelect.options) o.text = opts[o.value];
    }
    function showRemainingDays() {
      const endDateStr = "{{ subscription.end_date if subscription else '' }}";
      if (!endDateStr) return document.getElementById('remaining-days').innerText = '0';
      const d = new Date(endDateStr);
      const now = new Date();
      const diff = Math.max(0, Math.ceil((d - now)/(1000*60*60*24)));
      document.getElementById('remaining-days').innerText = diff;
    }
    if (paketSelect) {
      paketSelect.addEventListener('change', updatePrices);
      updatePrices();
    }
    showRemainingDays();
  </script>
</body>
</html>
'''

@app.route('/selfservice', methods=['GET','POST'])
def selfservice():
    error = None
    if request.method == 'POST':
        token = request.form.get('token','').strip()
        if not token:
            error = 'Bitte Token eingeben'
        else:
            user_data = db.get_user_by_token(token)
            if not user_data:
                error = 'Ungültiger Token'
            else:
                # Aufbau User-Objekt
                user = {
                    'username': user_data[0],
                    'hwid': user_data[1],
                    'paket': None,
                    'token': user_data[3],
                    'email': user_data[4]
                }
                # Aktive Subscriptions
                subs = db.get_active_subscriptions(user['username'])
                # Bestes Paket ermitteln (Premium > Basis+ > Basis)
                best = db.get_best_active_package(user['username'])
                user['paket'] = best or 'Kein Abo'
                # Aktuelle Subscription zum Anzeigen
                current = next((s for s in subs if s['paket']==best), None)
                return render_template_string(
                    SELF_SERVICE_TEMPLATE,
                    user=user,
                    subscription=current,
                    error=None,
                    prices=config.PRICES
                )
    # GET oder Fehlerfall
    return render_template_string(
        SELF_SERVICE_TEMPLATE,
        user=None,
        subscription=None,
        error=error,
        prices=config.PRICES
    )

@app.route('/selfservice/renew_token', methods=['POST'])
def renew_token():
    username = request.form.get('username','')
    if not db.get_user_by_username(username):
        flash('Benutzer nicht gefunden','error')
        return redirect(url_for('selfservice'))
    new_token = uuid.uuid4().hex[:16]
    db.update_user_token(username,new_token)
    flash('Token erfolgreich erneuert','success')
    return redirect(url_for('selfservice')+f'?token={new_token}')

@app.route('/selfservice/subscribe', methods=['POST'])
def subscribe():
    username = request.form.get('username')
    paket = request.form.get('paket')
    zyklus = request.form.get('zyklus')
    if not username or paket not in config.PRICES or zyklus not in ('1m','6m','12m'):
        flash('Ungültige Eingaben','error')
        return redirect(url_for('selfservice'))
    # Datum berechnen
    today = datetime.datetime.utcnow().date()
    # Existierende aktive Enddatum
    active = db.get_active_subscriptions(username)
    end = max((datetime.date.fromisoformat(s['end_date']) for s in active), default=today)
    # Add Duration
    if zyklus=='1m': delta=30
    elif zyklus=='6m': delta=183
    else: delta=365
    new_end = end + datetime.timedelta(days=delta)
    # Speichern
    db.add_subscription(username,paket,today.isoformat(),new_end.isoformat())
    flash(f'Paket {paket} gebucht bis {new_end}','success')
    return redirect(url_for('selfservice')+f'?token={db.get_token_by_username(username)}')

@app.route('/selfservice/cancel', methods=['POST'])
def cancel():
    username = request.form.get('username')
    # Nur Auto-Renew deaktivieren, Sub bleibt bis Enddatum gültig
    db.cancel_auto_renew(username)
    flash('Abo gekündigt (wird nicht verlängert)','success')
    return redirect(url_for('selfservice'))

if __name__=='__main__':
    app.run(host=config.HOST, port=config.PORT_SELF_SERVICE, debug=True)
