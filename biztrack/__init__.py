# biztrack/__init__.py
from flask import Flask
from biztrack.routes import main_bp
from biztrack.auth import auth_bp
from biztrack.biztrack_db import init_db, seed_default_data

def create_app():
    """
    Flask application factory.
    Initializes app, registers blueprints, sets up DB.
    """
    app = Flask(__name__, template_folder='templates')
    app.secret_key = "supersecretkey"  # Replace in production

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)

    # Initialize database
    init_db()
    seed_default_data()

    return app
