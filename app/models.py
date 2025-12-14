from app import db
from datetime import datetime

class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), unique=True, nullable=False)
    predictions = db.relationship('Prediction', backref='stock', lazy=True)

    def __repr__(self):
        return f'<Stock {self.symbol}>'

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    time_frame = db.Column(db.String(20), nullable=False) # 'day', 'week', 'month', 'quarter'
    prediction_type = db.Column(db.String(10), nullable=False) # 'Rise', 'Fall', 'Neutral'
    confidence = db.Column(db.Float)
    emotion = db.Column(db.String(50)) # e.g., 'Optimistic', 'Fearful'
    reasoning = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending') # pending, verified
    actual_outcome = db.Column(db.String(10)) # 'Rise', 'Fall', 'Neutral'
    rightness_score = db.Column(db.Float)

    sources = db.relationship('Source', backref='prediction', lazy=True)

    def __repr__(self):
        return f'<Prediction {self.id} for {self.stock_id}>'

class Source(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prediction_id = db.Column(db.Integer, db.ForeignKey('prediction.id'), nullable=False)
    url = db.Column(db.String(500))
    title = db.Column(db.String(500))
    snippet = db.Column(db.Text)

    def __repr__(self):
        return f'<Source {self.url}>'
