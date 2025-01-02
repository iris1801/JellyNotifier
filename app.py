from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from flask import Blueprint, jsonify

app = Flask(__name__)
app.secret_key = 'your_secret_key'

from apscheduler.schedulers.background import BackgroundScheduler
import requests
import logging

# Configura logging per debug
logging.basicConfig(level=logging.INFO)

# Funzioni per chiamate API
def monitor_media_added():
    service = Service.query.first()
    if service and service.monitor_media_added:
        try:
            response = requests.get(
                f"{service.jellyfin_url}/Library/MediaAdded",
                headers={"X-Emby-Token": service.jellyfin_api_key},
            )
            logging.info(f"Media Aggiunti: {response.json()}")
        except Exception as e:
            logging.error(f"Errore nella chiamata API Media Aggiunti: {e}")

def monitor_media_removed():
    service = Service.query.first()
    if service and service.monitor_media_removed:
        try:
            response = requests.get(
                f"{service.jellyfin_url}/Library/MediaRemoved",
                headers={"X-Emby-Token": service.jellyfin_api_key},
            )
            logging.info(f"Media Rimossi: {response.json()}")
        except Exception as e:
            logging.error(f"Errore nella chiamata API Media Rimossi: {e}")

def monitor_stream_started():
    service = Service.query.first()
    if service and service.monitor_stream_started:
        try:
            response = requests.get(
                f"{service.jellyfin_url}/Sessions",
                headers={"X-Emby-Token": service.jellyfin_api_key},
            )
            logging.info(f"Stream Avviati: {response.json()}")
        except Exception as e:
            logging.error(f"Errore nella chiamata API Stream Avviati: {e}")


# Funzione recupero librerie
def get_jellyfin_libraries():
    # Recupera le configurazioni dal database
    service_config = ServiceConfig.query.first()
    if not service_config:
        return {"error": "Configurazione non trovata. Compila il menu Servizi."}

    url = service_config.url
    api_key = service_config.api_key

    # Effettua la chiamata all'endpoint
    headers = {"X-Emby-Token": api_key}
    try:
        # Recupera l'ID utente
        response = requests.get(f"{url}/Users", headers=headers)
        response.raise_for_status()
        users = response.json()

        # Usa il primo utente per semplicità
        user_id = users[0]["Id"]

        # Recupera le librerie
        response = requests.get(f"{url}/Users/{user_id}/Views", headers=headers)
        response.raise_for_status()
        libraries = response.json()["Items"]

        return libraries

    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def monitor_transcoding():
    service = Service.query.first()
    if service and service.monitor_transcoding:
        try:
            response = requests.get(
                f"{service.jellyfin_url}/Transcoding",
                headers={"X-Emby-Token": service.jellyfin_api_key},
            )
            logging.info(f"Transcodifica: {response.json()}")
        except Exception as e:
            logging.error(f"Errore nella chiamata API Transcodifica: {e}")

# Configura APScheduler
scheduler = BackgroundScheduler()


# Funzione di Sync manuale
def sync_libraries():
    """
    Sincronizza le librerie da Jellyfin.
    """
    logging.info("Sincronizzazione delle librerie in corso...")
    try:
        libraries = get_jellyfin_libraries()
        if "error" in libraries:
            logging.error(f"Errore durante il recupero delle librerie: {libraries['error']}")
        else:
            logging.info(f"Librerie sincronizzate con successo: {libraries}")
    except Exception as e:
        logging.error(f"Errore nella sincronizzazione delle librerie: {str(e)}")

# Funzione per pianificare le attività
def schedule_tasks():
    global scheduler
    if not scheduler.running:  # Evita di avviare lo scheduler più volte
        scheduler.start()

    # Aggiungi i job alla coda
    scheduler.add_job(
        func=sync_libraries,  # Deve essere riconosciuta qui
        trigger="interval",
        minutes=get_sync_timeframe(),
        id="sync_libraries",
        replace_existing=True
    )
    service = Service.query.first()
    if service:
        # Rimuovi i job esistenti
        scheduler.remove_all_jobs()

        # Media aggiunti
        if service.monitor_media_added:
            scheduler.add_job(
                monitor_media_added,
                'interval',
                minutes=get_timeframe_in_minutes(service.media_added_timeframe),
                id='media_added',
            )

        # Media rimossi
        if service.monitor_media_removed:
            scheduler.add_job(
                monitor_media_removed,
                'interval',
                minutes=get_timeframe_in_minutes(service.media_removed_timeframe),
                id='media_removed',
            )

        # Stream avviati
        if service.monitor_stream_started:
            scheduler.add_job(
                monitor_stream_started,
                'interval',
                minutes=get_timeframe_in_minutes(service.stream_started_timeframe),
                id='stream_started',
            )

        # Transcodifica
        if service.monitor_transcoding:
            scheduler.add_job(
                monitor_transcoding,
                'interval',
                minutes=get_timeframe_in_minutes(service.transcoding_timeframe),
                id='transcoding',
            )

        scheduler.start()

# Convertitore per i timeframe
def get_timeframe_in_minutes(timeframe):
    mapping = {
        "15 min": 15,
        "30 min": 30,
        "1 hour": 60,
        "4 hours": 240,
    }
    return mapping.get(timeframe, 15)

# Avvio dello scheduler
@app.before_first_request
def start_scheduler():
    schedule_tasks()

# Configurazione del database per memorizzare le impostazioni SMTP
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///settings.db'
db = SQLAlchemy(app)


# Classe unificata Service
class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jellyfin_url = db.Column(db.String(255), nullable=False)
    jellyfin_api_key = db.Column(db.String(255), nullable=False)
    monitor_media_added = db.Column(db.Boolean, default=False)
    monitor_media_removed = db.Column(db.Boolean, default=False)
    monitor_stream_started = db.Column(db.Boolean, default=False)
    monitor_transcoding = db.Column(db.Boolean, default=False)
    media_added_timeframe = db.Column(db.String(20), default="15 min")
    media_removed_timeframe = db.Column(db.String(20), default="15 min")
    stream_started_timeframe = db.Column(db.String(20), default="15 min")
    transcoding_timeframe = db.Column(db.String(20), default="15 min")

#Classe per config servizi
class ServiceConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(255), nullable=False)
    api_key = db.Column(db.String(255), nullable=False)


# Modello per le impostazioni SMTP
class SMTPSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server = db.Column(db.String(120), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    encryption = db.Column(db.String(20), nullable=False)
    username = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(120), nullable=False)
    from_email = db.Column(db.String(120), nullable=False)


class AutoSend(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    schedule_name = db.Column(db.String(100), nullable=False)
    is_recurring = db.Column(db.Boolean, default=False)
    frequency = db.Column(db.String(50), nullable=True)
    schedule_time = db.Column(db.String(50), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    recipients = db.Column(db.Text, nullable=False)  # Salviamo gli indirizzi email separati da virgola


class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)

    def __repr__(self):
        return f'<Person {self.first_name} {self.last_name}>'

# Home Page per l'invio manuale delle email
@app.route('/')
def index():
    return render_template('index.html')

# Configurazione SMTP
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    settings = SMTPSettings.query.first()

    if not settings:
        settings = SMTPSettings(
            server="",
            port=0,
            encryption="SSL",
            username="",
            password="",
            from_email=""
        )
        db.session.add(settings)
        db.session.commit()

    if request.method == 'POST':
        settings.server = request.form['server']
        settings.port = int(request.form['port'])
        settings.encryption = request.form['encryption']
        settings.username = request.form['username']
        settings.password = request.form['password']
        settings.from_email = request.form['from_email']
        db.session.commit()
        flash('Settings updated!', 'success')
    return render_template('settings.html', settings=settings)

# Route per la gestione degli invii automatici
@app.route('/auto-sends', methods=['GET', 'POST'])
def auto_sends():
    if request.method == 'POST':
        schedule_name = request.form['schedule_name']
        is_recurring = 'is_recurring' in request.form
        frequency = request.form.get('frequency', None)
        schedule_time = request.form['schedule_time']
        subject = request.form['subject']
        content = request.form['content']
        recipients = request.form.getlist('recipients')
        manual_recipients = request.form.get('manual_recipients', '').split(',')

        # Combina destinatari
        all_recipients = recipients + [email.strip() for email in manual_recipients if email.strip()]
        recipients_str = ','.join(all_recipients)

        # Salva nel database
        new_schedule = AutoSend(
            schedule_name=schedule_name,
            is_recurring=is_recurring,
            frequency=frequency,
            schedule_time=schedule_time,
            subject=subject,
            content=content,
            recipients=recipients_str,
        )
        db.session.add(new_schedule)
        db.session.commit()

        return "Programmazione Salvata!"

    # Recupera persone dal database per il menu a tendina
    people = Person.query.all()  # Sostituisci con il tuo modello per le persone
    return render_template('auto_sends.html', people=people)

#Route aggiunta eventi in dashboard
@app.route('/dashboard', methods=['GET'])
def dashboard():
    schedules = AutoSend.query.all()
    return render_template('dashboard.html', schedules=schedules)
    service = Service.query.first()
    return render_template('dashboard.html', service=service)

# Route per Sync manuale Jellyfin
@app.route('/services/sync-now', methods=['POST'])
def sync_now():
    try:
        sync_libraries()  # Chiama la funzione per sincronizzare le librerie
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


#Persone
@app.route('/people', methods=['GET', 'POST'])
def people():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone_number = request.form['phone_number']
        email = request.form['email']

        # Aggiungi la nuova persona al database
        new_person = Person(first_name=first_name, last_name=last_name, phone_number=phone_number, email=email)
        db.session.add(new_person)
        db.session.commit()

        flash('Persona aggiunta con successo!', 'success')
        return redirect(url_for('people'))

    # Recupera tutte le persone dal database
    people = Person.query.all()
    return render_template('people.html', people=people)

# Elimina Persone
@app.route('/delete_person/<int:person_id>', methods=['POST'])
def delete_person(person_id):
    person = Person.query.get_or_404(person_id)
    db.session.delete(person)
    db.session.commit()
    flash('Persona eliminata con successo!', 'danger')
    return redirect(url_for('people'))

# Route Servizi unificata
@app.route('/services', methods=['GET', 'POST'])
def services():
    service = Service.query.first()

    if request.method == 'POST':
        jellyfin_url = request.form['jellyfin_url']
        jellyfin_api_key = request.form['jellyfin_api_key']
        monitor_media_added = 'monitor_media_added' in request.form
        monitor_media_removed = 'monitor_media_removed' in request.form
        monitor_stream_started = 'monitor_stream_started' in request.form
        monitor_transcoding = 'monitor_transcoding' in request.form
        media_added_timeframe = request.form['media_added_timeframe']
        media_removed_timeframe = request.form['media_removed_timeframe']
        stream_started_timeframe = request.form['stream_started_timeframe']
        transcoding_timeframe = request.form['transcoding_timeframe']

        if service:
            # Aggiorna i dati
            service.jellyfin_url = jellyfin_url
            service.jellyfin_api_key = jellyfin_api_key
            service.monitor_media_added = monitor_media_added
            service.monitor_media_removed = monitor_media_removed
            service.monitor_stream_started = monitor_stream_started
            service.monitor_transcoding = monitor_transcoding
            service.media_added_timeframe = media_added_timeframe
            service.media_removed_timeframe = media_removed_timeframe
            service.stream_started_timeframe = stream_started_timeframe
            service.transcoding_timeframe = transcoding_timeframe
        else:
            # Crea un nuovo record
            service = Service(
                jellyfin_url=jellyfin_url,
                jellyfin_api_key=jellyfin_api_key,
                monitor_media_added=monitor_media_added,
                monitor_media_removed=monitor_media_removed,
                monitor_stream_started=monitor_stream_started,
                monitor_transcoding=monitor_transcoding,
                media_added_timeframe=media_added_timeframe,
                media_removed_timeframe=media_removed_timeframe,
                stream_started_timeframe=stream_started_timeframe,
                transcoding_timeframe=transcoding_timeframe,
            )
            db.session.add(service)

        db.session.commit()

        # Riattiva lo scheduler
        schedule_tasks()

        flash('Dati del servizio aggiornati con successo!', 'success')
        return redirect(url_for('services'))

    return render_template('services.html', service=service)



# Modifica persone
@app.route('/edit_person/<int:person_id>', methods=['GET', 'POST'])
def edit_person(person_id):
    person = Person.query.get_or_404(person_id)

    if request.method == 'POST':
        person.first_name = request.form['first_name']
        person.last_name = request.form['last_name']
        person.phone_number = request.form['phone_number']
        person.email = request.form['email']

        db.session.commit()
        flash('Persona aggiornata con successo!', 'success')
        return redirect(url_for('people'))

    return render_template('edit_person.html', person=person)



# endpoint Dashboard
dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/dashboard/libraries", methods=["GET"])
def get_libraries():
    libraries = get_jellyfin_libraries()
    if "error" in libraries:
        return jsonify({"error": libraries["error"]}), 400
    return jsonify(libraries)


# Invio manuale di email
@app.route('/send_email', methods=['GET', 'POST'])
def send_email():
    if request.method == 'POST':
        # Codice per inviare l'email
        pass
    return render_template('send_email.html')

    subject = request.form['subject']
    body = request.form['body']
    recipients = request.form['recipients'].split(',')

    settings = SMTPSettings.query.first()
    msg = MIMEMultipart()
    msg['From'] = settings.from_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    # Connessione SMTP e invio della mail
    try:

        print(f"Connecting to SMTP server: {settings.server}, Port: {settings.port}")

        with smtplib.SMTP_SSL(settings.server, settings.port) if settings.encryption == 'SSL' else smtplib.SMTP(settings.server, settings.port) as server:
            if settings.encryption == 'TLS':
                server.starttls()
            server.login(settings.username, settings.password)

            print(f"Logged in as {settings.username}")

            for recipient in recipients:
                msg['To'] = recipient
                server.sendmail(settings.from_email, recipient, msg.as_string())
                print(f"Email sent to {recipient}")
        flash('Email sent successfully!', 'success')
    except Exception as e:
        print(f"Error during sending email: {e}")
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():  # Aggiungi questo contesto per assicurarti che il database venga creato correttamente
        db.create_all()
    app.run(debug=True)
