from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError
import os

# Attempt to import the configuration.
# In a real deployment, config.py would be generated from config.py.example.
try:
    import config
except ImportError:
    print("WARN: config.py not found. Using default SQLite settings. "
          "Copy config.py.example to config.py and customize it for production.")
    # Define default fallbacks if config.py is missing
    class DefaultConfig:
        DB_BACKEND = "sqlite"
        SQLITE_DB_NAME = "default_app.db"
        MARIADB_USER = ""
        MARIADB_PASSWORD = ""
        MARIADB_HOST = ""
        MARIADB_PORT = 3306
        MARIADB_DB_NAME = ""
    config = DefaultConfig()

# Define the SQLAlchemy base for declarative models
Base = declarative_base()

# Global engine and session variables
engine = None
SessionLocal = None

def get_db_uri():
    """
    Constructs the database URI based on the configuration.
    """
    if config.DB_BACKEND == "sqlite":
        # For SQLite, the path is relative to the project root or an absolute path.
        # If SQLITE_DB_NAME is just a filename, it will be in the current working directory.
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.SQLITE_DB_NAME)
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

def init_db():
    """
    Initializes the database engine and session.
    This function should be called once when the application starts.
    """
    global engine, SessionLocal

    db_uri = get_db_uri()

    try:
        if config.DB_BACKEND == "sqlite":
            # For SQLite, connect_args is used to ensure foreign key constraints are enabled.
            engine = create_engine(db_uri, connect_args={"check_same_thread": False})
        else:
            # For MariaDB (and other remote databases), connection pooling is generally desired.
            engine = create_engine(db_uri, pool_pre_ping=True)

        # Test the connection
        with engine.connect() as connection:
            pass # Connection successful if no exception
        print(f"Successfully connected to {config.DB_BACKEND} database.")

    except OperationalError as e:
        print(f"Error connecting to the database: {e}")
        print(f"Database URI used: {db_uri.replace(config.MARIADB_PASSWORD, '********') if config.DB_BACKEND == 'mariadb' else db_uri}")
        raise
    except ValueError as e:
        print(f"Configuration error: {e}")
        raise

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    print("Database engine and session initialized.")

def get_db_status_and_tables():
    """
    Checks database connectivity and retrieves a list of table names.
    Returns a dictionary with 'status' and 'tables' (or 'error_message').
    """
    global engine
    if not engine:
        try:
            # Attempt to initialize if not already done.
            # This is a fallback, proper initialization should happen at app start.
            print("WARN: Engine not initialized. Attempting to init_db() from get_db_status_and_tables.")
            init_db()
        except Exception as e:
            return {"status": "Error", "error_message": f"Failed to initialize database: {str(e)}", "tables": []}

    try:
        with engine.connect() as connection:
            # Connection successful
            from sqlalchemy import inspect
            inspector = inspect(engine)
            table_names = inspector.get_table_names()
            return {"status": f"Connected to {config.DB_BACKEND}", "tables": table_names, "error_message": None}
    except OperationalError as e:
        return {"status": "Error", "error_message": f"Failed to connect to database: {str(e)}", "tables": []}
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
# def create_tables():
#     if not engine:
#         raise RuntimeError("Database not initialized. Call init_db() first.")
#     Base.metadata.create_all(bind=engine)
#     print("Tables created (if they didn't exist).")

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

    except Exception as e:
        print(f"An error occurred during database initialization or example usage: {e}")

    finally:
        # Clean up the dummy config.py if it was created
        if os.path.exists("config.py") and "example_app.db" in open("config.py").read():
             if config.SQLITE_DB_NAME == "example_app.db" : #be careful
                os.remove("config.py")
                print("Temporary config.py removed.")
        if os.path.exists("example_app.db"):
            os.remove("example_app.db")
            print("Temporary example_app.db removed.")
