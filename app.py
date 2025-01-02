from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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
