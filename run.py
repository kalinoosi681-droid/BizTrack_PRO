
# ========================================
# 8. UPDATE: run.py
# ========================================
from biztrack import create_app
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

config_name = os.environ.get('FLASK_ENV', 'development')
app = create_app(config_name)

if __name__ == "__main__":
    if config_name == 'production':
        print("⚠️  For production, use: gunicorn -w 4 -b 0.0.0.0:5000 run:app")
        print("Running development server...")
    
    app.run(debug=(config_name == 'development'), port=5000)
# ========================================