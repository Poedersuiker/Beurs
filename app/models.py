from . import db # Import the db instance from app/__init__.py
from datetime import datetime

class User(db.Model):
    """
    Example User model.
    """
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.username}>'

# You can add more models here as your application grows.
# For example:
#
# class Post(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     title = db.Column(db.String(100), nullable=False)
#     content = db.Column(db.Text, nullable=False)
#     user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
#     author = db.relationship('User', backref=db.backref('posts', lazy=True))
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)
#
#     def __repr__(self):
#         return f'<Post {self.title}>'
