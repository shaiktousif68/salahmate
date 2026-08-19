from datetime import datetime
from app import db


class Prayer(db.Model):
    """Model representing a prayer record for a user on a specific date."""
    __tablename__ = 'prayers'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    prayer_name = db.Column(db.String(20), nullable=False)  # Fajr, Dhuhr, Asr, Maghrib, Isha
    date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), default='not_recorded')  # jamaat, alone, qaza, missed, not_recorded
    prayed_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'prayer_name', 'date', name='uq_user_prayer_date'),
    )

    @property
    def status_display(self):
        """Return a human-readable status."""
        status_map = {
            'jamaat': 'Jamaat',
            'alone': 'Alone',
            'qaza': 'Qaza',
            'missed': 'Missed',
            'not_recorded': 'Not Recorded'
        }
        return status_map.get(self.status, self.status)

    @property
    def is_completed(self):
        """Check if the prayer was completed (jamaat or alone)."""
        return self.status in ['jamaat', 'alone']

    def __repr__(self):
        return f'<Prayer {self.prayer_name} - {self.date} - {self.status}>'