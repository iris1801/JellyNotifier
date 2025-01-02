from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

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

def schedule_tasks():
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

# Modello per le impostazioni SMTP
class SMTPSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server = db.Column(db.String(120), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    encryption = db.Column(db.String(20), nullable=False)
    username = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(120), nullable=False)
    from_email = db.Column(db.String(120), nullable=False)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jellyfin_url = db.Column(db.String(255), nullable=False)
    jellyfin_api_key = db.Column(db.String(255), nullable=False)

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
@app.route('/auto_sends', methods=['GET', 'POST'])
def auto_sends():
    if request.method == 'POST':
        # Qui gestisci la logica per salvare gli invii automatici, ad esempio salvi l'orario e il contenuto
        schedule_time = request.form['schedule_time']
        content = request.form['content']
        # Logica per pianificare l'invio dell'email (es. salvare in DB o usare un task scheduler)
        pass
    return render_template('auto_sends.html')


# Route per chiamate api
@app.route('/services', methods=['GET', 'POST'])
def services():
    service = Service.query.first()

    if request.method == 'POST':
        # Aggiorna i dati come prima
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

# Scheda servizi
@app.route('/services', methods=['GET', 'POST'])
def services():
    service = Service.query.first()

    if request.method == 'POST':
        jellyfin_url = request.form['jellyfin_url']
        jellyfin_api_key = request.form['jellyfin_api_key']

        if service:
            # Aggiorna i dati esistenti
            service.jellyfin_url = jellyfin_url
            service.jellyfin_api_key = jellyfin_api_key
        else:
            # Crea un nuovo record
            service = Service(jellyfin_url=jellyfin_url, jellyfin_api_key=jellyfin_api_key)
            db.session.add(service)

        db.session.commit()
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


# Dashboard
@app.route('/dashboard')
def dashboard():
    # Qui puoi raccogliere i dati sugli invii automatici (da un database o file)
    # Per ora simuliamo dei dati
    auto_sends = [
        {"time": "2025-01-03 10:00", "content": "Email di esempio 1"},
        {"time": "2025-01-05 12:00", "content": "Email di esempio 2"}
    ]
    
    total_sent = len(auto_sends)  # Totale invii
    return render_template('dashboard.html', auto_sends=auto_sends, total_sent=total_sent)


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
