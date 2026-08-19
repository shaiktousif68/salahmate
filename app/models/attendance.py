from datetime import datetime
from app import db


class Attendance(db.Model):
    """Daily attendance summary for a user."""

    __tablename__ = 'attendance'

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

    total_completed = db.Column(
        db.Integer,
        default=0
    )

    total_qaza = db.Column(
        db.Integer,
        default=0
    )

    total_missed = db.Column(
        db.Integer,
        default=0
    )

    total_excused = db.Column(
        db.Integer,
        default=0
    )

    completion_percentage = db.Column(
        db.Float,
        default=0.0
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
            name='uq_user_attendance_date'
        ),
    )

    def __repr__(self):
        return (
            f'<Attendance {self.user_id} - '
            f'{self.date} - '
            f'{self.total_completed}/5>'
        )