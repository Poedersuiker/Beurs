from flask import Blueprint, render_template, current_app, url_for, request
# from .models import User # Example: Import models if you need to query the DB in your routes
from . import db # Example: Import db instance if you need to commit changes
from sqlalchemy.exc import SQLAlchemyError # Import SQLAlchemyError for exception handling

# Using a Blueprint to organize routes.
# 'main' is the name of the blueprint. This will be used when generating URLs e.g. url_for('main.home')
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def home():
    """Homepage route."""
    # You can pass data to your template like this:
    # users = User.query.all()
    # return render_template('home.html', users=users)
    return render_template('home.html')

@main_bp.route('/admin')
def admin():
    """Admin page route."""
    # Example of accessing config:
    # secret_key = current_app.config.get('SECRET_KEY')
    # print(f"Admin page accessed. Secret key starts with: {secret_key[:5] if secret_key else 'Not Set'}")
    try:
        # Attempt to execute a simple query to check the database connection.
        db.session.execute('SELECT 1')
        db_connection_status = "Successfully connected to the database."
    except SQLAlchemyError as e:
        db_connection_status = f"Failed to connect to the database: {e}"
    return render_template('admin.html', db_connection_status=db_connection_status)

# Example of a route that interacts with the database:
# @main_bp.route('/add_user/<username>/<email>')
# def add_user(username, email):
#     """Example route to add a new user."""
#     if not User.query.filter_by(username=username).first() and not User.query.filter_by(email=email).first():
#         new_user = User(username=username, email=email)
#         db.session.add(new_user)
#         db.session.commit()
#         return f"User {username} added successfully!"
#     return f"User {username} or email {email} already exists."

@main_bp.app_context_processor
def inject_active_tab():
    """Injects the active_tab variable into the context for all templates."""
    active_tab = None
    if request.endpoint:
        if 'main.home' in request.endpoint:
            active_tab = 'home'
        elif 'main.admin' in request.endpoint:
            active_tab = 'admin'
    return dict(active_tab=active_tab)
