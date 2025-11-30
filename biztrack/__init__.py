import os
from flask import Flask
from datetime import datetime, timezone

def create_app(config_name='development'):
    """
    Application factory pattern for creating Flask app instances.
    """
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='static')
    
    # Load configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['TESTING'] = config_name == 'testing'
    
    # Database configuration
    if config_name == 'testing':
        app.config['DATABASE'] = ':memory:'
        os.environ['BIZTRACK_DB'] = ':memory:'
    else:
        app.config['DATABASE'] = os.environ.get('BIZTRACK_DB', 'biztrack.db')
    
    # CSRF Configuration
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_TIME_LIMIT'] = None  # No time limit for CSRF tokens
    
    # Session configuration
    app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
    
    # Rate limiting
    app.config['RATELIMIT_STORAGE_URL'] = 'memory://'
    
    # Initialize extensions
    from .extensions import limiter, csrf, db, login_manager
    
    limiter.init_app(app)
    csrf.init_app(app)
    db.init_app(app)
    login_manager.init_app(app)
    
    # Register blueprints
    from .routes import main
    from .auth import auth_bp
    from .ai_routes import ai_bp
    
    app.register_blueprint(main)
    app.register_blueprint(auth_bp)
    app.register_blueprint(ai_bp)
    
    # Register teardown handler for database connections
    from .biztrack_db import close_connection
    app.teardown_appcontext(close_connection)
    
    # Add template context processors
    @app.context_processor
    def inject_datetime():
        """Make datetime available in all templates"""
        return {
            'datetime': datetime,
            'timezone': timezone
        }
    
    # Register error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        from flask import render_template
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        from .biztrack_db import get_connection
        # Rollback any failed database transactions
        try:
            conn = get_connection()
            conn.rollback()
        except:
            pass
        return render_template('500.html'), 500
    
    # CLI commands
    @app.cli.command()
    def init_db_command():
        """Initialize the database."""
        from .biztrack_db import init_db, migrate_schema, seed_default_data
        init_db()
        migrate_schema()
        seed_default_data()
        print('✅ Database initialized successfully.')
    
    @app.cli.command()
    def compute_metrics():
        """Compute daily metrics for store and products."""
        from .biztrack_db import compute_daily_store_metrics, compute_daily_product_metrics
        compute_daily_store_metrics()
        compute_daily_product_metrics()
        print('✅ Daily metrics computed successfully.')
    
    return app