from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError
import os

# Attempt to import the configuration.
# In a real deployment, config.py would be generated from config.py.example.
# This needs to be available for get_db_uri() which might be called early.
try:
    import config
except ImportError:
    print("WARN: config.py not found. Using default SQLite settings. "
          "Copy config.py.example to config.py and customize it for production.")
    # Define default fallbacks if config.py is missing
    class DefaultConfig:
        DB_BACKEND = "sqlite"
        SQLITE_DB_NAME = "default_app.db" # Should match the example for consistency
        MARIADB_USER = ""
        MARIADB_PASSWORD = ""
        MARIADB_HOST = ""
        MARIADB_PORT = 3306
        MARIADB_DB_NAME = ""
    config = DefaultConfig()

def get_db_uri():
    """
    Constructs the database URI based on the configuration.
    This function is used by app.py to set SQLALCHEMY_DATABASE_URI.
    """
    # Ensure config is loaded if it was defaulted (e.g., if this module is imported before app fully sets up)
    # However, standard import should handle this. The primary concern is that `config` module is correct.
    # If DefaultConfig was used, config object is already set.

    # Determine the base directory for SQLite path (project root)
    # __file__ in database.py refers to the location of database.py
    # If app.py is in root and database.py is in root, then os.path.dirname(os.path.abspath(__file__)) is root.
    # If SQLITE_DB_NAME is 'app.db', it becomes '<project_root>/app.db'
    project_root = os.path.dirname(os.path.abspath(__file__)) # Assumes database.py is in project root

    if config.DB_BACKEND == "sqlite":
        # For SQLite, the path is relative to the project root or an absolute path.
        db_path = os.path.join(project_root, config.SQLITE_DB_NAME)
        return f"sqlite:///{db_path}"
    elif config.DB_BACKEND == "mariadb":
        if not all([config.MARIADB_USER, config.MARIADB_PASSWORD, config.MARIADB_HOST, config.MARIADB_DB_NAME]):
            raise ValueError("MariaDB configuration is incomplete. Please check config.py.")
        return (
            f"mysql+pymysql://{config.MARIADB_USER}:{config.MARIADB_PASSWORD}@"
            f"{config.MARIADB_HOST}:{config.MARIADB_PORT}/{config.MARIADB_DB_NAME}"
        )
    else:
        raise ValueError(f"Unsupported DB_BACKEND: {config.DB_BACKEND}. Choose 'sqlite' or 'mariadb'.")


def get_db_status_and_tables(db_instance):
    """
    Checks database connectivity and retrieves a list of table names using Flask-SQLAlchemy instance.
    Returns a dictionary with 'status' and 'tables' (or 'error_message').
    'db_instance' is the SQLAlchemy object from Flask-SQLAlchemy (app.db).
    """
    if not db_instance or not db_instance.engine:
        return {"status": "Error", "error_message": "Flask-SQLAlchemy db object not available or engine not initialized.", "tables": []}

    current_config_backend = "Unknown"
    try:
        # Try to get the backend from the live engine, or fall back to config
        # This is a bit indirect; usually, we'd just trust the engine is configured correctly.
        if db_instance.engine.name == 'sqlite':
            current_config_backend = "sqlite"
        elif db_instance.engine.name == 'mysql': # PyMySQL driver makes engine name 'mysql'
            current_config_backend = "mariadb (or mysql)"
        else:
            current_config_backend = db_instance.engine.name
    except Exception: # If engine access fails for some reason
        pass


    try:
        # Flask-SQLAlchemy's engine is available via db_instance.engine
        with db_instance.engine.connect() as connection:
            inspector = inspect(db_instance.engine)
            table_names = inspector.get_table_names()
            # Try to determine backend from config for display, as engine might not be fully initialized
            # if there was an issue earlier.
            try:
                # Re-access config to display what backend it *thinks* it's using
                # This is mainly for the status message.
                cfg_backend_display = config.DB_BACKEND
            except Exception:
                cfg_backend_display = current_config_backend # fallback

            return {"status": f"Connected to {cfg_backend_display}", "tables": table_names, "error_message": None}
    except OperationalError as e:
        # Try to get password from config to redact if it's a MariaDB connection error
        db_uri_display = "URI not available"
        try:
            db_uri_for_error = get_db_uri() # Construct it again for error display
            if config.DB_BACKEND == 'mariadb' and hasattr(config, 'MARIADB_PASSWORD'):
                db_uri_display = db_uri_for_error.replace(config.MARIADB_PASSWORD, '********')
            else:
                db_uri_display = db_uri_for_error
        except Exception:
            pass # Keep "URI not available"

        return {"status": "Error",
                "error_message": f"Failed to connect to database ({config.DB_BACKEND} backend). URI: {db_uri_display}. Error: {str(e)}",
                "tables": []}
    except Exception as e: # Catch any other unexpected errors
        return {"status": "Error", "error_message": f"An unexpected error occurred: {str(e)}", "tables": []}


# The old if __name__ == "__main__": block is removed as it's no longer relevant
# for initializing or testing this version of database.py.
# Flask-SQLAlchemy handles initialization, and testing would be done through the app.
