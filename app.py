from flask import Flask, render_template, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, upgrade
import os
import database # Assuming database.py contains get_db_uri and get_db_status_and_tables

app = Flask(__name__)

# Load configuration for database URI
try:
    app.config['SQLALCHEMY_DATABASE_URI'] = database.get_db_uri()
except ValueError as e:
    print(f"Configuration error for SQLALCHEMY_DATABASE_URI: {e}")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///./app_error_fallback.db'


app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy()
migrate = Migrate()

# Initialize extensions
db.init_app(app)
migrate.init_app(app, db)


# Define a simple model for testing migrations
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'

@app.cli.command("initdb_custom")
def initdb_command():
    """Initializes the database and runs migrations."""
    print("Initializing database and running migrations...")
    with app.app_context():
        # Ensure migrations directory exists, as 'flask db init' might not have been run in all envs
        migrations_dir = os.path.join(current_app.root_path, 'migrations')
        if not os.path.exists(migrations_dir):
            print(f"Migrations directory not found at {migrations_dir}. "
                  "Attempting to run 'flask db init' equivalent...")
            from flask_migrate.cli import _init_cmd as init_command_func
            try:
                init_command_func(directory='migrations', multidb=False)
                print("Migrations directory initialized.")
            except Exception as e_init:
                print(f"Error initializing migrations directory: {e_init}")
                print("Please run 'flask db init' manually if startup fails.")
                # Do not proceed with upgrade if init failed catastrophically
                return

        upgrade(directory=current_app.extensions['migrate'].directory)
    print("Database initialized and migrations applied.")


def run_migrations_on_startup():
    """Runs database migrations at application startup."""
    with app.app_context():
        print("Checking for database migrations at startup...")
        try:
            # Ensure the migrations directory exists.
            migrations_dir = os.path.join(current_app.root_path, 'migrations')
            if not os.path.exists(migrations_dir):
                 print(f"Migrations directory not found at {migrations_dir}. ")
                 print("This is expected if 'flask db init' has not been run yet.")
                 print("Attempting to initialize migrations directory automatically...")
                 # This is a simplified way to call the core logic of 'flask db init'
                 # Requires Flask-Migrate >= 2.7.0 for _init_cmd
                 from flask_migrate.cli import _init_cmd as init_command_func
                 try:
                     init_command_func(directory='migrations', multidb=False)
                     print("Migrations directory initialized automatically.")
                 except Exception as e_init:
                     print(f"Automatic initialization of migrations directory failed: {e_init}")
                     print("Please run 'flask db init' manually if issues persist.")
                     # If init fails, upgrade will likely also fail or be incorrect.
                     # Depending on the error, might want to return or raise.
                     # For now, let it proceed to upgrade, which will then likely fail informatively.


            # Now attempt upgrade
            upgrade(directory=current_app.extensions['migrate'].directory)
            print("Database migrations checked/applied successfully.")
        except Exception as e:
            print(f"Error running migrations at startup: {e}")
            print("This might be expected if it's the very first run and no models existed "
                  "when 'flask db migrate' was last run (or if it wasn't run).")
            print("If you have new models or changes, run 'flask db migrate' and then 'flask db upgrade' manually.")


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/admin')
def admin():
    db_status_info = database.get_db_status_and_tables(db)
    return render_template('admin.html', db_status=db_status_info)

# Create the application instance and run migrations before starting the server
# This ensures that 'flask run' or 'python app.py' will attempt migrations.
# The app_context is crucial here.
with app.app_context():
    # Attempt to run migrations on startup.
    # This needs to be before the first request and before app.run if __name__ == '__main__'
    # However, putting it here means it runs when the module is imported if app is global.
    # A common pattern is to use an app factory and call this within the factory
    # or right after creating the app instance if not using a factory.
    # For this structure, we'll call it conditionally for 'python app.py' execution
    # and rely on flask commands (like 'flask run') to have the app context.
    # The `flask db init/migrate/upgrade` commands provide their own context.
    pass # Delaying the direct call to run_migrations_on_startup() to __main__

if __name__ == '__main__':
    # Call migrations when app is run directly via "python app.py"
    run_migrations_on_startup()
    app.run(debug=True)
