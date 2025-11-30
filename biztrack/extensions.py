from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager
from .biztrack_db import init_db, migrate_schema, seed_default_data
from .auth_models import User # User model is still needed for type hints if any

class DatabaseManager:
    def __init__(self, app=None):
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        with app.app_context():
            init_db()
            migrate_schema()
            seed_default_data()
        app.teardown_appcontext(self.teardown)

    def teardown(self, exception):
        pass # Connection is closed by biztrack_db.close_connection

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

csrf = CSRFProtect()
db = DatabaseManager()

login_manager = LoginManager()
login_manager.login_view = "auth.login"  # The route to redirect to for login
login_manager.login_message_category = "info" # Bootstrap category for flash message

@login_manager.user_loader
def load_user(user_id):
    """
    Loads a user from the database for Flask-Login.
    This function is called on every request for an authenticated user.
    """
    # This now delegates user loading to the User model itself.
    return User.get(user_id)