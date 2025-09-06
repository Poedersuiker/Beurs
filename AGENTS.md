# Beurs Application

This is a Flask application with websockets and a MariaDB backend.

## Setup

1.  **Create a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up the configuration:**
    - Copy `config.py.example` to `config.py`:
      ```bash
      cp config.py.example config.py
      ```
    - Edit `config.py` with your database credentials.

4.  **Set up the database:**
    - Create a `.flaskenv` file with the following content:
      ```
      FLASK_APP=run.py
      ```
    - Initialize the database migrations (only the first time):
      ```bash
      flask db init
      ```
    - Create an initial migration:
      ```bash
      flask db migrate -m "Initial migration."
      ```
    - Apply the migrations to the database:
      ```bash
      flask db upgrade
      ```

## Running the application

To run the application, use the following command:

```bash
python run.py
```
