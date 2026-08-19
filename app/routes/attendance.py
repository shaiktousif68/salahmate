from datetime import date, datetime

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app import db
from app.models.prayer import Prayer
from app.date_utils import get_local_today, get_user_start_date, can_edit_date
from app.routes.prayer import (
    PRAYER_NAMES,
    STATUS_VALUES,
    update_attendance_from_prayers
)

attendance_bp = Blueprint('attendance', __name__)

@attendance_bp.route('/attendance')
@login_required
def index():
    """Dedicated attendance page with date selection."""

    local_today = get_local_today()
    date_str = request.args.get(
        'date',
        local_today.isoformat()
    )

    try:
        selected_date = datetime.strptime(
            date_str,
            '%Y-%m-%d'
        ).date()
    except ValueError:
        selected_date = local_today

    prayers = Prayer.query.filter_by(
        user_id=current_user.id,
        date=selected_date
    ).all()

    prayer_status = {
        prayer.prayer_name: prayer.status
        for prayer in prayers
    }

    attendance = update_attendance_from_prayers(
        current_user.id,
        selected_date,
        prayers=prayers
    )

    # Determine if the selected date is editable
    is_editable = can_edit_date(current_user, selected_date)
    today = get_local_today()
    user_start_date = get_user_start_date(current_user)

    return render_template(
        'attendance.html',
        prayer_names=PRAYER_NAMES,
        prayer_status=prayer_status,
        attendance=attendance,
        selected_date=selected_date,
        is_editable=is_editable,
        min_date=user_start_date.isoformat(),
        max_date=today.isoformat(),
        is_future=selected_date > today
    )


@attendance_bp.route('/attendance/update', methods=['POST'])
@login_required
def update_attendance():
    """Update a Salah status for any selected date.

    Uses an upsert pattern to ensure only ONE record exists per
    (user_id, prayer_name, date) combination.
    """
    data = request.get_json() or {}

    prayer_name = data.get('prayer_name')
    status = data.get('status')
    date_str = data.get('date')

    if not all([prayer_name, status, date_str]):
        return jsonify({
            'success': False,
            'error': 'Missing data'
        }), 400

    if prayer_name not in PRAYER_NAMES:
        return jsonify({
            'success': False,
            'error': 'Invalid prayer name'
        }), 400

    if status not in STATUS_VALUES:
        return jsonify({
            'success': False,
            'error': 'Invalid status'
        }), 400

    try:
        selected_date = datetime.strptime(
            date_str,
            '%Y-%m-%d'
        ).date()
    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Invalid date format'
        }), 400

    # Backend Security: Enforce the date-access rule
    if not can_edit_date(current_user, selected_date):
        return jsonify({
            'success': False,
            'error': 'Attendance for this date is locked.'
        }), 403  # 403 Forbidden

    # Upsert logic that also cleans up potential duplicates
    all_prayers = Prayer.query.filter_by(
        user_id=current_user.id,
        prayer_name=prayer_name,
        date=selected_date
    ).all()

    if not all_prayers:
        # Create new if none exist
        prayer = Prayer(
            user_id=current_user.id,
            prayer_name=prayer_name,
            date=selected_date
        )
        db.session.add(prayer)
    else:
        # Use the first one found and remove any duplicates
        prayer = all_prayers[0]
        for duplicate in all_prayers[1:]:
            db.session.delete(duplicate)

    prayer.status = status

    if status in ['jamaat', 'alone', 'qaza']:
        prayer.prayed_at = datetime.utcnow()
    else:
        prayer.prayed_at = None

    try:
        db.session.commit()

        attendance = update_attendance_from_prayers(
            current_user.id,
            selected_date
        )

        return jsonify({
            'success': True,
            'attendance': {
                'total_completed': attendance.total_completed,
                'total_qaza': attendance.total_qaza,
                'total_missed': attendance.total_missed,
                'completion_percentage':
                    attendance.completion_percentage
            }
        })

    except Exception as e:
        db.session.rollback()

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500