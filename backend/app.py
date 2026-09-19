"""
Application entry point. Run with:  python app.py
Serves the JSON API under /api/*, the redirect engine under /r/*, the
public bio pages under /bio/*, and the vanilla-JS frontend as static files.
"""
import os
from flask import Flask, abort, send_from_directory
from flask_cors import CORS

from config import Config
from extensions import db, limiter
from error_handlers import register_error_handlers

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")


def create_app():
    app = Flask(
        __name__,
        static_folder=FRONTEND_DIR,
        static_url_path="",
        template_folder="templates",
    )
    app.config.from_object(Config)

    db.init_app(app)
    limiter.init_app(app)
    CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": app.config["FRONTEND_URL"]}})

    from routes.auth import auth_bp
    from routes.links import links_bp
    from routes.analytics import analytics_bp
    from routes.bio import bio_bp
    from routes.redirect import redirect_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(links_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(bio_bp)
    app.register_blueprint(redirect_bp)

    register_error_handlers(app)

    # --- Serve the vanilla-JS frontend (dashboard, auth pages) ---
    @app.route("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/<path:filename>")
    def frontend_files(filename):
        # Blueprints above are matched first by Flask's routing, so this
        # catch-all only serves frontend routes/files, never API-like paths.
        if filename.startswith(("api/", "r/", "bio/")):
            abort(404, description="Resource not found.")
        if os.path.exists(os.path.join(FRONTEND_DIR, filename)):
            return send_from_directory(FRONTEND_DIR, filename)
        return send_from_directory(FRONTEND_DIR, "index.html")

    with app.app_context():
        os.makedirs(os.path.join(os.path.dirname(__file__), "instance"), exist_ok=True)
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
