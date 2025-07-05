import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

# Initialize SQLAlchemy so it can be imported by models.py
db = SQLAlchemy()

def create_app():
    """Construct the core application."""
    app = Flask(__name__, instance_relative_config=False)

    # Determine config file path
    # Prefer config.py if it exists, otherwise use config.py.example
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.py')
    if not os.path.exists(config_path):
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.py.example')
        print(f"INFO: 'config/config.py' not found. Using '{os.path.basename(config_path)}' for configuration.")

    # Load environment variables from .env file if present, for sensitive data not in config files
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

    # Load configuration from the chosen file
    app.config.from_pyfile(config_path)

    # Construct SQLALCHEMY_DATABASE_URI based on DB_TYPE
    db_type = app.config.get("DB_TYPE", "sqlite").lower()

    if db_type == "sqlite":
        sqlite_db_name = app.config.get("SQLITE_DB_NAME", "app.db")
        db_dir = os.path.join(os.path.dirname(__file__), '..', 'db')
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
        app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(db_dir, sqlite_db_name)}"
    elif db_type == "mariadb":
        user = app.config.get("MARIADB_USER")
        password = app.config.get("MARIADB_PASSWORD")
        host = app.config.get("MARIADB_HOST")
        dbname = app.config.get("MARIADB_DB_NAME")
        if not all([user, password, host, dbname]):
            raise ValueError("For MariaDB, MARIADB_USER, MARIADB_PASSWORD, MARIADB_HOST, and MARIADB_DB_NAME must be set in config.")
        app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+mysqlclient://{user}:{password}@{host}/{dbname}"
    else:
        raise ValueError(f"Unsupported DB_TYPE: {db_type}. Choose 'sqlite' or 'mariadb'.")

    # Initialize extensions
    db.init_app(app)

    with app.app_context():
        # Import parts of our application
        from . import routes
        from . import models # Import models now that they are defined

        # Register Blueprints
        app.register_blueprint(routes.main_bp)

        # Create database tables for our data models
        db.create_all() # Now we can create tables

        return app
