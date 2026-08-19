from datetime import datetime
from app import db


class Dhikr(db.Model):
    """Daily Dhikr (Tasbeeh) counter for a user.

    Each row stores one user's count for one Dhikr on one date.
    The count is capped at 100 (the daily target).
    """

    __tablename__ = 'dhikr'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False,
        index=True
    )

    date = db.Column(
        db.Date,
        nullable=False,
        index=True
    )

    # Dhikr identifier: subhanallah, alhamdulillah, allahuakbar,
    # astaghfirullah, lailahaillallah
    dhikr = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )

    count = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint(
            'user_id',
            'date',
            'dhikr',
            name='uq_user_date_dhikr'
        ),
    )

    def __repr__(self):
        return (
            f'<Dhikr {self.user_id} - '
            f'{self.date} - '
            f'{self.dhikr} - '
            f'{self.count}/100>'
        )