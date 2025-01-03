from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class JellyfinSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(200), nullable=False)
    api_key = db.Column(db.String(200), nullable=False)
