from app import create_app, db
from app.models import User # Import models to allow easy access in flask shell

app = create_app()

@app.shell_context_processor
def make_shell_context():
    """
    Makes variables available in the Flask shell context for convenience.
    To use: `flask shell`
    """
    return {'db': db, 'User': User}

if __name__ == '__main__':
    # The host '0.0.0.0' makes the app accessible from other devices on the network.
    # Debug mode should be False in production. It's controlled by the DEBUG config var.
    app.run(host='0.0.0.0', port=5000, debug=app.config.get('DEBUG', False))
