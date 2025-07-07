from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base
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

# Define the SQLAlchemy base for declarative models
Base = declarative_base()

# Import necessary types for defining models
from sqlalchemy import Column, Integer, String, Text, REAL, Date, ForeignKey
from sqlalchemy.orm import relationship

class Security(Base):
    __tablename__ = "securities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(Text, nullable=False, unique=True)
    name = Column(Text)
    type = Column(Text)
    exchange = Column(Text)
    currency = Column(Text)

    daily_prices = relationship("DailyPrice", back_populates="security")

class DailyPrice(Base):
    __tablename__ = "daily_prices"

    security_id = Column(Integer, ForeignKey("securities.id"), primary_key=True)
    date = Column(Date, primary_key=True)
    open = Column(REAL)
    high = Column(REAL)
    low = Column(REAL)
    close = Column(REAL)
    adj_close = Column(REAL)
    volume = Column(Integer)

    security = relationship("Security", back_populates="daily_prices")


# Global engine and session variables
engine = None
SessionLocal = None


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

def get_db():
    """
    Dependency to get a database session.
    Ensures the session is closed after use.
    """
    if not SessionLocal:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Example of how to create tables (optional, can be managed by Alembic or similar tools)
def create_tables():
    if not engine:
        # Attempt to initialize if not already done, useful for standalone script usage
        print("WARN: Engine not initialized in create_tables. Attempting to init_db().")
        try:
            init_db()
        except Exception as e:
            print(f"Failed to initialize database in create_tables: {e}")
            raise RuntimeError("Database not initialized. Call init_db() first.") from e
    Base.metadata.create_all(bind=engine)
    print("Tables created (if they didn't exist).")

if __name__ == "__main__":
    # This is an example of how to initialize and use the database setup.
    # In a real application, init_db() would be called at startup.

    # Create a dummy config.py for this example to run, if it doesn't exist
    if not os.path.exists("config.py"):
        print("Creating a temporary config.py for example run (SQLite default)")
        with open("config.py", "w") as f:
            f.write("DB_BACKEND = \"sqlite\"\n")
            f.write("SQLITE_DB_NAME = \"example_app.db\"\n")
            # Add dummy MariaDB vars so import config doesn't fail if those are accessed
            f.write("MARIADB_USER = \"\"\n")
            f.write("MARIADB_PASSWORD = \"\"\n")
            f.write("MARIADB_HOST = \"\"\n")
            f.write("MARIADB_PORT = 3306\n")
            f.write("MARIADB_DB_NAME = \"\"\n")
        # Re-import config if it was just created
        import importlib
        import sys
        if 'config' in sys.modules:
            importlib.reload(sys.modules['config'])
        else:
            import config


    print("Attempting to initialize database...")
    try:
        init_db()
        print("Database initialization successful.")

        # Example usage:
        # from sqlalchemy import Column, Integer, String
        # class Item(Base):
        #     __tablename__ = "items"
        #     id = Column(Integer, primary_key=True, index=True)
        #     name = Column(String, index=True)
        #     description = Column(String)
        #
        # create_tables() # Create tables if they don't exist
        #
        # db_session = next(get_db())
        # new_item = Item(name="Test Item", description="This is a test item.")
        # db_session.add(new_item)
        # db_session.commit()
        # db_session.refresh(new_item)
        # print(f"Added new item: {new_item.id}, {new_item.name}")
        #
        # retrieved_item = db_session.query(Item).filter(Item.name == "Test Item").first()
        # print(f"Retrieved item: {retrieved_item.name}")
        # db_session.close()

        # Create the tables defined in this file
        print("Attempting to create tables...")
        create_tables()
        print("Finished create_tables().")

        # Verify tables by listing them
        status_info = get_db_status_and_tables()
        if status_info["error_message"]:
            print(f"Error checking table status: {status_info['error_message']}")
        else:
            print(f"Database status: {status_info['status']}")
            print(f"Tables found: {status_info['tables']}")
            if "securities" in status_info["tables"] and "daily_prices" in status_info["tables"]:
                print("Successfully created 'securities' and 'daily_prices' tables.")
            else:
                print("ERROR: 'securities' or 'daily_prices' or both tables not found after creation attempt.")


    except Exception as e:
        print(f"An error occurred during database initialization or example usage: {e}")

    finally:
        # Clean up the dummy config.py if it was created
        # Also clean up the dummy database file if it was created and is the default example one
        db_file_to_remove = None
        if os.path.exists("config.py"):
            # Read the config to check which db file was used if it was sqlite
            temp_config_lines = open("config.py").read()
            if "DB_BACKEND = \"sqlite\"" in temp_config_lines and \
               "SQLITE_DB_NAME = \"example_app.db\"" in temp_config_lines:
                db_file_to_remove = "example_app.db"
                os.remove("config.py")
                print("Temporary config.py removed.")

        if db_file_to_remove and os.path.exists(db_file_to_remove):
            # Special check to avoid deleting a user's actual database if they changed SQLITE_DB_NAME
            # in the temporary config.py to something other than example_app.db
            if config.DB_BACKEND == "sqlite" and config.SQLITE_DB_NAME == "example_app.db":
                 os.remove(db_file_to_remove)
                 print(f"Temporary {db_file_to_remove} removed.")
            else:
                print(f"WARN: Temporary config.py was used, but SQLITE_DB_NAME was not 'example_app.db'. "
                      f"Not removing {config.SQLITE_DB_NAME}.")

# The old if __name__ == "__main__": block is removed as it's no longer relevant
# for initializing or testing this version of database.py.
# Flask-SQLAlchemy handles initialization, and testing would be done through the app.
