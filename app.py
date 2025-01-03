from flask import Flask, render_template, request, redirect, url_for
import requests
from models import db, JellyfinSettings

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jellyfin_settings.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

@app.route('/')
def index():
    settings = JellyfinSettings.query.first()
    if settings:
        try:
            # Chiamata per ottenere il conteggio degli oggetti
            items_counts_response = requests.get(f"{settings.url}/Items/Counts", headers={"X-Emby-Token": settings.api_key})
            if items_counts_response.status_code == 200:
                items_counts = items_counts_response.json()
                movie_count = items_counts.get("MovieCount", 0)
                series_count = items_counts.get("SeriesCount", 0)
                episode_count = items_counts.get("EpisodeCount", 0)
            else:
                movie_count = series_count = episode_count = 0


            # Chiamata per ottenere la lista degli utenti
            users_response = requests.get(f"{settings.url}/Users", headers={"X-Emby-Token": settings.api_key})
            users = users_response.json() if users_response.status_code == 200 else []

        except Exception as e:
            error = f"Errore nella richiesta API: {e}"
            return render_template('dashboard.html', error=error)

        return render_template('dashboard.html', users=users, movie_count=movie_count, series_count=series_count, episode_count=episode_count)
    else:
        return redirect(url_for('settings'))


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    settings = JellyfinSettings.query.first()
    if request.method == 'POST':
        url = request.form['url']
        api_key = request.form['api_key']
        if settings:
            settings.url = url
            settings.api_key = api_key
        else:
            new_settings = JellyfinSettings(url=url, api_key=api_key)
            db.session.add(new_settings)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('settings.html', settings=settings)




if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Crea il database e la tabella
    app.run(debug=True)
