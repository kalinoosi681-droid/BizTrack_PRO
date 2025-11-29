
# Standard Library
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

# Third-party Libraries
from flask import Flask, g, jsonify
import click

# Local Application Imports
from biztrack.config import config_map
from biztrack.routes import main
from biztrack.auth import auth_bp
from .ai_routes import ai_bp
from .extensions import limiter, csrf, db
from .biztrack_db import get_connection, close_connection, init_db, seed_default_data, migrate_schema


def create_app(config_name=None):
    
    """Flask application factory with proper configuration"""
    
    # Determine config from environment
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__, template_folder='templates', static_folder='static')
    
    # Load configuration
    app.config.from_object(config_map[config_name])
    
    # Initialize security extensions
    csrf.init_app(app)
    db.init_app(app)
    limiter.init_app(app)

    # Register blueprints
    app.register_blueprint(main)
    app.register_blueprint(auth_bp)
    app.register_blueprint(ai_bp)
    
    # Context processor to inject datetime into templates
    @app.context_processor
    def inject_datetime():
        """Injects datetime into all templates."""
        return {'datetime': datetime, 'timezone': timezone}

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        if app.config['SESSION_COOKIE_SECURE']:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response
    
    # Logging setup
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/biztrack.log', maxBytes=10240000, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('BizTrack PRO startup')

    # Register teardown function to close DB connection
    app.teardown_appcontext(close_connection)

    # Register custom CLI command for DB initialization
    @app.cli.command("init-db")
    def init_db_command():
        """Clears existing data and creates new tables."""
        init_db()
        migrate_schema()
        seed_default_data()
        click.echo("✅ Database initialized, migrated, and seeded.")

    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Checks database connectivity for monitoring."""
        with app.app_context():
            try:
                # Use the connection from the app context
                conn = get_connection()
                conn.execute("SELECT 1;")
                return jsonify({"status": "healthy"}), 200
            except Exception as e:
                app.logger.error(f"Health check failed: {e}")
                return jsonify({"status": "unhealthy", "error": str(e)}), 500
    
    return app