from flask import render_template, request, redirect, url_for, flash
from app.main import bp
from app import db
from app.models import Stock, Prediction, Source
from app.services.research import get_market_news, analyze_with_gemini

@bp.route('/', methods=['GET'])
def dashboard():
    # List the latest predictions
    predictions = Prediction.query.order_by(Prediction.timestamp.desc()).limit(20).all()
    return render_template('dashboard.html', predictions=predictions)

@bp.route('/research', methods=['POST'])
def research():
    symbol = request.form.get('symbol')
    if not symbol:
        flash('Please enter a stock symbol or market name.')
        return redirect(url_for('main.dashboard'))

    # 1. Get News
    news = get_market_news(symbol)

    # 2. Analyze
    analysis = analyze_with_gemini(symbol, news)

    if not analysis:
        flash('Analysis failed. Please try again or check API Key.')
        return redirect(url_for('main.dashboard'))

    # 3. Save to DB
    try:
        # Check if stock exists
        stock_symbol = analysis.get('stock', symbol).upper()
        stock = Stock.query.filter_by(symbol=stock_symbol).first()
        if not stock:
            stock = Stock(symbol=stock_symbol)
            db.session.add(stock)
            db.session.commit()

        # Save predictions
        for pred_data in analysis.get('predictions', []):
            prediction = Prediction(
                stock_id=stock.id,
                time_frame=pred_data.get('timeframe'),
                prediction_type=pred_data.get('prediction'),
                confidence=pred_data.get('confidence'),
                emotion=analysis.get('emotion'),
                reasoning=pred_data.get('reasoning'),
                status='pending'
            )
            db.session.add(prediction)
            db.session.commit() # Commit to get ID

            # Save sources for this prediction
            relevant_sources = analysis.get('relevant_sources', [])
            for src in relevant_sources:
                source = Source(
                    prediction_id=prediction.id,
                    url=src.get('url'),
                    title=src.get('title'),
                    snippet=src.get('snippet')
                )
                db.session.add(source)

        db.session.commit()
        flash(f'Analysis complete for {stock.symbol}')

    except Exception as e:
        db.session.rollback()
        flash(f'Error saving results: {e}')
        print(f"Database error: {e}")

    return redirect(url_for('main.dashboard'))
