from datetime import datetime
from app import db


class QuranReading(db.Model):
    """Model tracking user's Quran reading progress."""
    __tablename__ = 'quran_readings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    surah_number = db.Column(db.Integer, nullable=False)
    ayah_number = db.Column(db.Integer, nullable=False)
    para_number = db.Column(db.Integer, nullable=False)
    page_number = db.Column(db.Integer)
    read_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)

    __table_args__ = (
        db.UniqueConstraint(
            'user_id',
            'surah_number',
            'ayah_number',
            name='uq_user_surah_ayah'
        ),
    )

    def __repr__(self):
        return f'<QuranReading Surah {self.surah_number}:{self.ayah_number}>'


class Bookmark(db.Model):
    """Model for saving Quran reading positions."""
    __tablename__ = 'bookmarks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    surah_number = db.Column(db.Integer, nullable=False)
    ayah_number = db.Column(db.Integer, nullable=False)
    para_number = db.Column(db.Integer, nullable=False)
    page_number = db.Column(db.Integer)
    label = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            'user_id',
            'surah_number',
            'ayah_number',
            name='uq_user_bookmark_surah_ayah'
        ),
    )

    def __repr__(self):
        return f'<Bookmark Surah {self.surah_number}:{self.ayah_number}>'