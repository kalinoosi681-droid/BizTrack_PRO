# run.py
import os
from biztrack import create_app

def create_flask_app():
    """
    Creates and configures the Flask application using the factory.
    This is the primary entry point for running the web app.
    """
    config_name = os.environ.get('FLASK_ENV', 'development')
    app = create_app(config_name)
    return app

# Create the app instance
app = create_flask_app()

if __name__ == '__main__':
    # Run the development server
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"🚀 Starting BizTrack PRO on http://localhost:{port}")
    print(f"📊 Debug mode: {debug}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        use_reloader=debug
    )