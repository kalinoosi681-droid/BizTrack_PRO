
# ========================================
# 2. UPDATE: biztrack/__init__.py
# ========================================
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from biztrack.routes import main
from biztrack.auth import auth_bp
from biztrack.biztrack_db import init_db, seed_default_data
from biztrack.config import config_map
import logging
import os

csrf = CSRFProtect(app=None)

def create_app(config_name=None):
    
    """Flask application factory with proper configuration"""
    
    # Determine config from environment
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__, template_folder='templates', static_folder='static')
    
    # Load configuration
    app.config.from_object(config_map[config_name])
    
    # Initialize security extensions
    csrf = CSRFProtect(app)
    
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://"
    )
    
    # Register blueprints
    app.register_blueprint(main)
    app.register_blueprint(auth_bp)
    
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
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            'logs/biztrack.log',
            maxBytes=10240000,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('BizTrack PRO startup')
    
    # Initialize database
    with app.app_context():
        init_db()
        seed_default_data()
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        from biztrack.biztrack_db import execute_query
        try:
            execute_query("SELECT 1;", fetchone=True)
            return {"status": "healthy"}, 200
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}, 500
    
    return app