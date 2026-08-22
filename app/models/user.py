from datetime import datetime
from flask_login import UserMixin
from app import db, bcrypt


class User(UserMixin, db.Model):
    """User model for authentication and profile."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    full_name = db.Column(db.String(120))
    gender = db.Column(db.String(10), nullable=False, server_default='male') # male, female
    city = db.Column(db.String(100), default='Madanapalle')
    country = db.Column(db.String(100), default='India')
    latitude = db.Column(db.Float, default=13.929)
    longitude = db.Column(db.Float, default=78.534)
    calculation_method = db.Column(db.Integer, default=4)  # Umm Al-Qura University
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    prayers = db.relationship('Prayer', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    attendance = db.relationship('Attendance', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    bookmarks = db.relationship('Bookmark', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    quran_readings = db.relationship('QuranReading', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def __init__(self, username, email, password, full_name=None, gender='male', **kwargs):
        self.username = username
        self.email = email
        self.password = password
        self.full_name = full_name
        self.gender = gender
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def password(self):
        """Prevent password from being accessed."""
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        """Set password to a hashed value."""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def verify_password(self, password):
        """Check if the provided password matches the hash."""
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'