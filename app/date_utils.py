from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

APP_TIMEZONE = ZoneInfo("Asia/Kolkata")

def get_local_today():
    """Gets the current date in the app's reference timezone."""
    return datetime.now(APP_TIMEZONE).date()

def get_user_start_date(user):
    """Calculates the user's local start date from the UTC created_at timestamp."""
    if not user or not user.created_at:
        return get_local_today()
    # Assume user.created_at is a naive datetime object stored in UTC
    utc_dt = user.created_at.replace(tzinfo=timezone.utc)
    local_dt = utc_dt.astimezone(APP_TIMEZONE)
    return local_dt.date()

def can_edit_date(user, selected_date):
    """Check if a user can edit attendance for a given date."""
    user_start_date = get_user_start_date(user)
    return user_start_date <= selected_date <= get_local_today()