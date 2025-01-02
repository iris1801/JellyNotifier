from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'your_secret_key'

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
