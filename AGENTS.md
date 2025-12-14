# Market Research Application

This is a Flask application that automates stock market research using Google Gemini and DuckDuckGo.

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
    - Edit `config.py`.
    - **Important:** Set `GOOGLE_API_KEY` in `config.py` or your environment variables to enable Gemini analysis.

4.  **Set up the database:**
    - Create a `.flaskenv` file:
      ```
      FLASK_APP=run.py
      ```
    - Initialize the database migrations (if not already done):
      ```bash
      flask db init
      ```
    - Apply the migrations to the database:
      ```bash
      flask db upgrade
      ```

## Running the application

To run the application, use the following command:

```bash
flask run
```
or
```bash
python run.py
```

## Features

- **Deep Research:** Enter a stock symbol (e.g., AAPL) to fetch news from the last 48 hours.
- **AI Predictions:** Gemini predicts movement (Rise/Fall) for Day, Week, Month, and Quarter.
- **Storage:** Predictions and sources are stored in the database.
