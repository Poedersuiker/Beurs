from flask import Flask, render_template, current_app, redirect, url_for, request, flash, g
from flask.globals import request_ctx
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, upgrade
import os
import click # For CLI arguments
import database # Assuming database.py contains get_db_uri and get_db_status_and_tables
import yfinance as yf
from datetime import datetime, timedelta
# from database import Security, DailyPrice # Models are now defined in this file
import pandas as pd


app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a_default_secret_key') # Needed for flash messages

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

# Define application-specific models
class Security(db.Model):
    __tablename__ = "securities"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticker = db.Column(db.Text, nullable=False, unique=True)
    name = db.Column(db.Text)
    type = db.Column(db.Text)
    exchange = db.Column(db.Text)
    currency = db.Column(db.Text)
    daily_prices = db.relationship("DailyPrice", back_populates="security", lazy=True)

    def __repr__(self):
        return f'<Security {self.ticker}>'

class DailyPrice(db.Model):
    __tablename__ = "daily_prices"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True) # Added for potential ease of use, though composite PK is fine
    security_id = db.Column(db.Integer, db.ForeignKey("securities.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    open = db.Column(db.Float)
    high = db.Column(db.Float)
    low = db.Column(db.Float)
    close = db.Column(db.Float)
    adj_close = db.Column(db.Float)
    volume = db.Column(db.Integer)
    security = db.relationship("Security", back_populates="daily_prices")

    __table_args__ = (db.UniqueConstraint('security_id', 'date', name='uq_security_date'),)

    def __repr__(self):
        return f'<DailyPrice {self.security.ticker} {self.date}>'


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
    # Fetch securities that have at least one entry in DailyPrice for the filter dropdown
    securities_with_prices = Security.query.join(DailyPrice, Security.id == DailyPrice.security_id)\
                                           .distinct(Security.id)\
                                           .order_by(Security.name)\
                                           .all()

    # Get filter parameters from request arguments
    selected_ticker = request.args.get('security_ticker', '')
    filter_date_option = request.args.get('date_option', 'all') # 'all', 'specific', 'last_year', 'range'
    specific_date_str = request.args.get('specific_date', '')
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')

    query = DailyPrice.query.join(Security)

    if selected_ticker:
        query = query.filter(Security.ticker == selected_ticker)

    if filter_date_option == 'specific' and specific_date_str:
        try:
            specific_date = datetime.strptime(specific_date_str, '%Y-%m-%d').date()
            query = query.filter(DailyPrice.date == specific_date)
        except ValueError:
            flash('Invalid specific date format. Please use YYYY-MM-DD.', 'error')
    elif filter_date_option == 'last_year':
        one_year_ago = datetime.now().date() - timedelta(days=365)
        query = query.filter(DailyPrice.date >= one_year_ago)
    elif filter_date_option == 'range' and start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            if start_date > end_date:
                flash('Start date cannot be after end date.', 'error')
            else:
                query = query.filter(DailyPrice.date.between(start_date, end_date))
        except ValueError:
            flash('Invalid date format for range. Please use YYYY-MM-DD.', 'error')

    # Order by date ascending for charting purposes, then reverse for display if needed
    query = query.order_by(DailyPrice.date.asc()) # Ascending for chart
    prices_for_chart = query.all()

    # Prepare data for the chart
    chart_datasets = [] # Will hold dataset objects for Chart.js
    all_dates = set() # To collect all unique dates for the x-axis

    if prices_for_chart:
        if selected_ticker: # Single security selected
            points = [{'x': price.date.strftime('%Y-%m-%d'), 'y': price.close} for price in prices_for_chart if price.close is not None]
            if points: # Ensure there are valid points to plot
                chart_datasets.append({
                    'label': selected_ticker,
                    'data': points
                })
        else: # "All securities" or no specific ticker selected - prepare for multi-line
            prices_by_security = {}
            for price in prices_for_chart:
                if price.close is None: # Skip data points where close price is None
                    continue
                ticker = price.security.ticker
                if ticker not in prices_by_security:
                    prices_by_security[ticker] = []
                # Data is already sorted by date overall, so append will maintain order per security
                prices_by_security[ticker].append({'x': price.date.strftime('%Y-%m-%d'), 'y': price.close})

            for ticker, points in prices_by_security.items():
                if points: # Ensure there are valid points for this security
                    chart_datasets.append({
                        'label': ticker,
                        'data': points
                    })

    # For table display, prices are usually shown most recent first
    prices_for_table = sorted(prices_for_chart, key=lambda p: p.date, reverse=True)

    # chart_x_labels is no longer needed as Chart.js infers from {x,y} data
    return render_template('index.html',
                           securities=securities_with_prices,
                           prices=prices_for_table,
                           selected_ticker=selected_ticker,
                           filter_date_option=filter_date_option,
                           specific_date_str=specific_date_str,
                           start_date_str=start_date_str,
                           end_date_str=end_date_str,
                           chart_datasets=chart_datasets # Data now in [{label:'TICKER', data:[{x:'date',y:value},...]},...] format
                           )

@app.route('/admin')
def admin():
    db_status_info = database.get_db_status_and_tables(db)

    # Ensure predefined securities are in the database
    predefined_securities_list = [
        # AEX Index
        {'ticker': '^AEX', 'name': 'AEX Index', 'type': 'Index', 'exchange': 'AEB', 'currency': 'EUR'},

        # Euronext Amsterdam Stocks
        {'ticker': 'ADYEN.AS', 'name': 'Adyen', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'},
        {'ticker': 'ASML.AS', 'name': 'ASML Holding', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'},
        {'ticker': 'INGA.AS', 'name': 'ING Groep', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'},
        {'ticker': 'PHIA.AS', 'name': 'Philips', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'},
        {'ticker': 'HEIA.AS', 'name': 'Heineken', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'},
        {'ticker': 'UNA.AS', 'name': 'Unilever PLC', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'}, # Unilever has multiple listings, .AS is Amsterdam
        {'ticker': 'DSM.AS', 'name': 'DSM Firmenich AG', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'},
        {'ticker': 'KPN.AS', 'name': 'KPN', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'},
        {'ticker': 'RAND.AS', 'name': 'Randstad NV', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'},
        {'ticker': 'WKL.AS', 'name': 'Wolters Kluwer', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'},
        {'ticker': 'SHELL.AS', 'name': 'Shell PLC', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'},
        {'ticker': 'ABN.AS', 'name': 'ABN AMRO Bank', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'},
        {'ticker': 'AGN.AS', 'name': 'Aegon NV', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'},
        {'ticker': 'AKZA.AS', 'name': 'Akzo Nobel NV', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'},
        {'ticker': 'MT.AS', 'name': 'ArcelorMittal', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'}, # Also listed elsewhere
        {'ticker': 'BESI.AS', 'name': 'BE Semiconductor Industries NV', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'},
        {'ticker': 'IMCD.AS', 'name': 'IMCD NV', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'},
        {'ticker': 'NN.AS', 'name': 'NN Group NV', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'},
        {'ticker': 'PRX.AS', 'name': 'Prosus NV', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'},
        {'ticker': 'REN.AS', 'name': 'RELX PLC', 'type': 'Stock', 'exchange': 'AEB', 'currency': 'EUR'},


        # Major Worldwide Indices
        {'ticker': '^GSPC', 'name': 'S&P 500 (USA)', 'type': 'Index', 'exchange': 'SNP', 'currency': 'USD'},
        {'ticker': '^DJI', 'name': 'Dow Jones Industrial Average (USA)', 'type': 'Index', 'exchange': 'DJI', 'currency': 'USD'},
        {'ticker': '^IXIC', 'name': 'NASDAQ Composite (USA)', 'type': 'Index', 'exchange': 'NAS', 'currency': 'USD'},
        {'ticker': '^FTSE', 'name': 'FTSE 100 (UK)', 'type': 'Index', 'exchange': 'FTS', 'currency': 'GBP'},
        {'ticker': '^GDAXI', 'name': 'DAX (Germany)', 'type': 'Index', 'exchange': 'GER', 'currency': 'EUR'},
        {'ticker': '^FCHI', 'name': 'CAC 40 (France)', 'type': 'Index', 'exchange': 'PAR', 'currency': 'EUR'},
        {'ticker': '^STOXX50E', 'name': 'Euro Stoxx 50 (Eurozone)', 'type': 'Index', 'exchange': 'STOXX', 'currency': 'EUR'},
        {'ticker': '^N225', 'name': 'Nikkei 225 (Japan)', 'type': 'Index', 'exchange': 'N225', 'currency': 'JPY'},
        {'ticker': '^HSI', 'name': 'Hang Seng Index (Hong Kong)', 'type': 'Index', 'exchange': 'HKG', 'currency': 'HKD'},
        {'ticker': '000001.SS', 'name': 'SSE Composite (Shanghai)', 'type': 'Index', 'exchange': 'SHH', 'currency': 'CNY'}
    ]

    existing_tickers = [s.ticker for s in Security.query.all()]
    added_to_session = False
    for sec_data in predefined_securities_list:
        if sec_data['ticker'] not in existing_tickers:
            security = Security(
                ticker=sec_data['ticker'],
                name=sec_data['name'],
                type=sec_data.get('type', 'Unknown'),
                exchange=sec_data.get('exchange', 'Unknown'),
                currency=sec_data.get('currency', 'USD') # Default to USD if not specified
            )
            db.session.add(security)
            existing_tickers.append(sec_data['ticker']) # Add to list to prevent re-adding in same session if duplicate in predefined_securities_list
            added_to_session = True

    if added_to_session:
        try:
            db.session.commit()
            flash('New predefined securities added to the database.', 'info')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding predefined securities: {str(e)}', 'error')


    securities = Security.query.order_by(Security.name).all() # Fetch all, now including predefined ones, ordered by name
    return render_template('admin.html', db_status=db_status_info, securities=securities)

@app.route('/admin/import_yahoo_finance', methods=['POST'])
def import_yahoo_finance():
    security_id = request.form.get('security_id')
    time_period = request.form.get('time_period')

    if not security_id:
        flash('Please select a security.', 'error')
        return redirect(url_for('admin'))

    security = Security.query.get(security_id)
    if not security:
        flash('Selected security not found.', 'error')
        return redirect(url_for('admin'))

    ticker_symbol = security.ticker
    ticker = yf.Ticker(ticker_symbol)

    try:
        if time_period == '25_years':
            start_date = datetime.now() - timedelta(days=25*365)
            hist_data = ticker.history(start=start_date.strftime('%Y-%m-%d'))
        elif time_period == '1_year':
            start_date = datetime.now() - timedelta(days=365)
            hist_data = ticker.history(start=start_date.strftime('%Y-%m-%d'))
        elif time_period == 'current_price':
            # Get the most recent trading day's data
            hist_data = ticker.history(period="1d")
            if hist_data.empty: # If no data for "1d" (e.g. market closed, new stock)
                 # Try to get the last known close from info
                info = ticker.info
                if 'previousClose' in info and info['previousClose'] is not None:
                     # Create a DataFrame like structure for consistency
                    hist_data = pd.DataFrame([{
                        'Open': info.get('open', None), # Might be None if market hasn't opened
                        'High': info.get('dayHigh', None), # Might be None
                        'Low': info.get('dayLow', None), # Might be None
                        'Close': info.get('previousClose'), # This is the most reliable for "current" if market closed
                        'Adj Close': info.get('previousClose'), # Often same as close for current price
                        'Volume': info.get('volume', 0) # Might be 0 or from previous day
                    }], index=[pd.to_datetime(datetime.now().date() - timedelta(days=1))]) # Approximate date
                else: # If still no data
                    flash(f'Could not fetch current price for {ticker_symbol}. The ticker might be delisted or data unavailable.', 'error')
                    return redirect(url_for('admin'))
        else:
            flash('Invalid time period selected.', 'error')
            return redirect(url_for('admin'))

        if hist_data.empty:
            flash(f'No historical data found for {ticker_symbol} for the selected period.', 'warning')
            return redirect(url_for('admin'))

        for index, row in hist_data.iterrows():
            # Check if record already exists
            existing_price = DailyPrice.query.filter_by(security_id=security.id, date=index.date()).first()
            if existing_price:
                # Update existing record
                existing_price.open = row['Open']
                existing_price.high = row['High']
                existing_price.low = row['Low']
                existing_price.close = row['Close']
                existing_price.adj_close = row.get('Adj Close', row['Close']) # yfinance might not always have 'Adj Close'
                existing_price.volume = row['Volume']
            else:
                # Create new record
                daily_price = DailyPrice(
                    security_id=security.id,
                    date=index.date(),
                    open=row['Open'],
                    high=row['High'],
                    low=row['Low'],
                    close=row['Close'],
                    adj_close=row.get('Adj Close', row['Close']),
                    volume=row['Volume']
                )
                db.session.add(daily_price)

        db.session.commit()
        flash(f'Successfully imported data for {ticker_symbol}.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error importing data for {ticker_symbol}: {str(e)}', 'error')

    return redirect(url_for('admin'))

@app.cli.command("seed_securities")
def seed_securities_command():
    """Seeds the database with initial security data."""
    initial_securities = [
        {'ticker': 'AAPL', 'name': 'Apple Inc.', 'type': 'Stock', 'exchange': 'NASDAQ', 'currency': 'USD'},
        {'ticker': 'MSFT', 'name': 'Microsoft Corporation', 'type': 'Stock', 'exchange': 'NASDAQ', 'currency': 'USD'},
        {'ticker': 'GOOGL', 'name': 'Alphabet Inc. (Class A)', 'type': 'Stock', 'exchange': 'NASDAQ', 'currency': 'USD'},
        {'ticker': 'AMZN', 'name': 'Amazon.com, Inc.', 'type': 'Stock', 'exchange': 'NASDAQ', 'currency': 'USD'},
        {'ticker': '^GSPC', 'name': 'S&P 500', 'type': 'Index', 'exchange': 'INDEX', 'currency': 'USD'},
        {'ticker': 'BTC-USD', 'name': 'Bitcoin USD', 'type': 'Cryptocurrency', 'exchange': 'CCC', 'currency': 'USD'},
    ]

    with app.app_context():
        existing_tickers = [s.ticker for s in Security.query.all()]
        added_count = 0
        for sec_data in initial_securities:
            if sec_data['ticker'] not in existing_tickers:
                security = Security(**sec_data)
                db.session.add(security)
                added_count += 1

        if added_count > 0:
            db.session.commit()
            print(f"Successfully seeded {added_count} new securities.")
        else:
            print("No new securities to seed. Database might already contain them.")

@app.cli.command("inspect_prices")
@click.argument("ticker_symbol")
def inspect_prices_command(ticker_symbol):
    """Inspects stored prices for a given security ticker."""
    with app.app_context():
        security = Security.query.filter_by(ticker=ticker_symbol).first()
        if not security:
            print(f"Security with ticker {ticker_symbol} not found.")
            return

        prices = DailyPrice.query.filter_by(security_id=security.id).order_by(DailyPrice.date.desc()).limit(5).all()

        if not prices:
            print(f"No prices found for {ticker_symbol}.")
            return

        print(f"Last 5 prices for {ticker_symbol} (Security ID: {security.id}):")
        for price in prices:
            print(f"  Date: {price.date}, Open: {price.open}, High: {price.high}, Low: {price.low}, Close: {price.close}, Volume: {price.volume}")

@app.cli.command("test_import")
@click.argument("ticker_symbol")
@click.argument("period") # e.g., "1_year", "25_years", "current_price"
def test_import_command(ticker_symbol, period):
    """Tests the Yahoo Finance import logic for a given ticker and period."""
    with app.app_context():
        security = Security.query.filter_by(ticker=ticker_symbol).first()
        if not security:
            print(f"Security {ticker_symbol} not found. Seed it first.")
            return

        # Simulate form data
        class MockForm:
            def __init__(self, security_id, time_period):
                self.security_id = security_id
                self.time_period = time_period

        # Mock request object with the form
        mock_request = type('Request', (), {'form': MockForm(security.id, period)})

        # Temporarily replace global request for the call
        # This is a bit of a hack for testing outside actual web request context
        original_request = None
        if request_ctx and hasattr(request_ctx, 'request'):
             original_request = request_ctx.request

        # from flask import g # g is already imported
        g._request = mock_request # Simulate request context for flash and request.form

        # Need to ensure 'request' object used by import_yahoo_finance is the mocked one
        # The import_yahoo_finance function uses flask.request directly.
        # A better way would be to refactor import_yahoo_finance to accept params,
        # but for a quick test, we can try to ensure the context is right.
        # The most reliable way is to call the function with parameters if possible.
        # Since import_yahoo_finance directly uses request.form, we have to mock it globally or pass params.
        # For now, let's assume flash messages won't break anything critical if request context is imperfect.

        print(f"Attempting to import data for {ticker_symbol}, period {period}...")

        # Directly calling the function's core logic is safer if it can be refactored.
        # As it is, we will call it and see.
        # To make `request.form.get` work as expected inside `import_yahoo_finance`,
        # we need to push a request context with our mocked form.
        with app.test_request_context(method='POST', data={'security_id': str(security.id), 'time_period': period}):
            # app.preprocess_request() # If you have before_request handlers

            # Call the function that contains the import logic
            # We need to get security_id and time_period from the form in the function
            # The function `import_yahoo_finance` is designed as a route handler.
            # For a CLI test, it's better to extract its core logic into a helper function.
            # However, for now, let's try to call it.
            # This direct call will fail because it's a view function expecting a real request.
            # A better test would be to use app.test_client()

            # Re-evaluating: The easiest way to test the logic is to call the function that does the work
            # *if* it were separated from the request handling. Since it's not,
            # the `inspect_prices` after a manual trigger (if possible) or just relying on the CLI seed
            # and then inspecting is the most pragmatic here.

            # Let's simplify: this command will just call the yfinance part and db commit
            # This means duplicating some logic from import_yahoo_finance route,
            # which is not ideal but serves the testing purpose in this constrained env.

            ticker_obj = yf.Ticker(security.ticker)
            hist_data = None
            try:
                if period == '25_years':
                    start_date = datetime.now() - timedelta(days=25*365)
                    hist_data = ticker_obj.history(start=start_date.strftime('%Y-%m-%d'))
                elif period == '1_year':
                    start_date = datetime.now() - timedelta(days=365)
                    hist_data = ticker_obj.history(start=start_date.strftime('%Y-%m-%d'))
                elif period == 'current_price':
                    hist_data = ticker_obj.history(period="1d")
                    if hist_data.empty:
                        info = ticker_obj.info
                        if 'previousClose' in info and info['previousClose'] is not None:
                            hist_data = pd.DataFrame([{
                                'Open': info.get('open'), 'High': info.get('dayHigh'), 'Low': info.get('dayLow'),
                                'Close': info.get('previousClose'), 'Adj Close': info.get('previousClose'),
                                'Volume': info.get('volume',0)
                            }], index=[pd.to_datetime(datetime.now().date() - timedelta(days=1))])
                        else:
                            print(f"Could not fetch current price for {security.ticker} via test_import.")
                            return
                else:
                    print(f"Invalid period: {period}")
                    return

                if hist_data.empty:
                    print(f"No data fetched for {security.ticker} for period {period}.")
                    return

                for index, row in hist_data.iterrows():
                    existing_price = DailyPrice.query.filter_by(security_id=security.id, date=index.date()).first()
                    if existing_price:
                        existing_price.open = row['Open']
                        existing_price.high = row['High']
                        existing_price.low = row['Low']
                        existing_price.close = row['Close']
                        existing_price.adj_close = row.get('Adj Close', row['Close'])
                        existing_price.volume = row['Volume']
                    else:
                        daily_price = DailyPrice(
                            security_id=security.id, date=index.date(), open=row['Open'], high=row['High'],
                            low=row['Low'], close=row['Close'], adj_close=row.get('Adj Close', row['Close']),
                            volume=row['Volume']
                        )
                        db.session.add(daily_price)
                db.session.commit()
                print(f"Data import successful for {security.ticker}, period {period}.")
            except Exception as e:
                db.session.rollback()
                print(f"Error during test import for {security.ticker}: {str(e)}")


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
