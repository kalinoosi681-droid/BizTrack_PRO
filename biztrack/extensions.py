from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from .biztrack_db import init_db, migrate_schema, seed_default_data

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