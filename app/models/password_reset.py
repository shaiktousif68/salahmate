"""Password reset token model for secure password recovery."""
from datetime import datetime, timedelta
import secrets

from app import db


class PasswordResetToken(db.Model):
    """One-time password reset token with expiry."""
    __tablename__ = 'password_reset_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    token_hash = db.Column(db.String(128), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)

    # Token validity period: 30 minutes
    TOKEN_TTL_MINUTES = 30

    @classmethod
    def generate_for_user(cls, user_id):
        """Generate a new reset token for a user.

        Returns the raw token (to be sent by email) and creates the DB record
        storing only the SHA-256 hash of the token.
        """
        raw_token = secrets.token_urlsafe(32)
        token_hash = cls._hash_token(raw_token)
        now = datetime.utcnow()
        token = cls(
            user_id=user_id,
            token_hash=token_hash,
            created_at=now,
            expires_at=now + timedelta(minutes=cls.TOKEN_TTL_MINUTES)
        )
        db.session.add(token)
        db.session.commit()
        return raw_token

    @classmethod
    def _hash_token(cls, raw_token):
        """Hash a raw token using SHA-256 (one-way, not reversible)."""
        import hashlib
        return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    @classmethod
    def validate_token(cls, raw_token):
        """Validate a raw token and return the associated user_id if valid.

        Returns None if the token is invalid, expired, or already used.
        """
        if not raw_token:
            return None
        token_hash = cls._hash_token(raw_token)
        token = cls.query.filter_by(token_hash=token_hash).first()
        if not token:
            return None
        if token.used_at is not None:
            return None
        if token.expires_at < datetime.utcnow():
            return None
        return token

    def mark_used(self):
        """Mark this token as used (prevents reuse)."""
        self.used_at = datetime.utcnow()
        db.session.commit()

    def __repr__(self):
        return f'<PasswordResetToken user={self.user_id} expires={self.expires_at}>'