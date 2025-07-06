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
