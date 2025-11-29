# webapp.py
from biztrack import create_app
from biztrack.biztrack_db import init_db, seed_default_data, migrate_schema
import os

def create_flask_app():
    """
    Creates and configures the Flask application using the factory.
    This is the primary entry point for running the web app.
    """
    config_name = os.environ.get('FLASK_ENV', 'development')
    app = create_app(config_name)
    return app
