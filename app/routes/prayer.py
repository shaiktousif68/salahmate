from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.prayer import Prayer
from app.models.attendance import Attendance
from app.models.dhikr import Dhikr
from app.date_utils import get_local_today, get_user_start_date
from app.services.prayer_times import PrayerTimesService

prayer_bp = Blueprint('prayer', __name__)

PRAYER_NAMES = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']
STATUS_VALUES = ['jamaat', 'alone', 'qaza', 'missed', 'not_recorded', 'excused']

# Daily Dhikr (Tasbeeh) configuration — informational/static metadata
DHIKR_NAMES = {
    'subhanallah': {
        'arabic': 'سُبْحَانَ اللَّهِ',
        'name': 'SubhanAllah'
    },
    'alhamdulillah': {
        'arabic': 'الْحَمْدُ لِلَّهِ',
        'name': 'Alhamdulillah'
    },
    'allahuakbar': {
        'arabic': 'اللَّهُ أَكْبَرُ',
        'name': 'Allahu Akbar'
    },
    'astaghfirullah': {
        'arabic': 'أَسْتَغْفِرُ اللَّهَ',
        'name': 'Astaghfirullah'
    },
    'lailahaillallah': {
        'arabic': 'لَا إِلَٰهَ إِلَّا اللَّهُ',
        'name': 'La ilaha illallah'
    },
}


def get_or_create_attendance(user_id, date_obj):
    """Get or create an attendance record for a user and date."""
    attendance = Attendance.query.filter_by(
        user_id=user_id,
        date=date_obj
    ).first()

    if not attendance:
        attendance = Attendance(user_id=user_id, date=date_obj)
        db.session.add(attendance)
        db.session.flush()

    return attendance


def update_attendance_from_prayers(user_id, date_obj, prayers=None):
    """Update daily attendance totals based on Prayer records."""

    attendance = get_or_create_attendance(user_id, date_obj)

    # If prayers aren't passed in, fetch them. This avoids a redundant query
    # when called from a route that has already fetched them.
    if prayers is None:
        prayers = Prayer.query.filter_by(
            user_id=user_id,
            date=date_obj
        ).all()

    total_completed = 0
    total_qaza = 0
    total_missed = 0
    total_excused = 0

    for prayer in prayers:
        if prayer.status in ['jamaat', 'alone']:
            total_completed += 1
        elif prayer.status == 'qaza':
            total_qaza += 1
        elif prayer.status == 'excused':
            total_excused += 1
        elif prayer.status == 'missed':
            total_missed += 1

    attendance.total_completed = total_completed
    attendance.total_qaza = total_qaza
    attendance.total_missed = total_missed
    attendance.total_excused = total_excused

    attendance.completion_percentage = round(
        (total_completed / 5) * 100,
        1
    )

    db.session.commit()

    return attendance


@prayer_bp.route('/prayers')
@login_required
def index():
    """Prayer Times informational page."""
    today = date.today()

    # Get prayer times
    prayer_times = PrayerTimesService.get_todays_prayer_times(current_user)

    # Format prayer times
    formatted_times = {}
    if prayer_times:
        for name in ['Fajr', 'Sunrise', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']:
            formatted_times[name] = PrayerTimesService.format_time(prayer_times.get(name))

    # Get today's Dhikr counts for this user
    dhikr_counts = {}
    dhikr_records = Dhikr.query.filter_by(
        user_id=current_user.id,
        date=today
    ).all()
    for record in dhikr_records:
        dhikr_counts[record.dhikr] = record.count

    return render_template(
        'prayers.html',
        prayer_times=formatted_times,
        today=today,
        dhikr_counts=dhikr_counts,
        dhikr_options=DHIKR_NAMES
    )


def _get_or_create_dhikr(user_id, date_obj, dhikr_key):
    """Get or create a Dhikr record for a user + date + dhikr."""
    record = Dhikr.query.filter_by(
        user_id=user_id,
        date=date_obj,
        dhikr=dhikr_key
    ).first()
    if not record:
        record = Dhikr(user_id=user_id, date=date_obj, dhikr=dhikr_key, count=0)
        db.session.add(record)
        db.session.flush()
    return record


@prayer_bp.route('/prayers/dhikr/increment', methods=['POST'])
@login_required
def dhikr_increment():
    """Increment today's count for a Dhikr by 1 (no upper limit).

    Also accepts an optional absolute ``count`` value. When provided, the
    stored count is set to ``max(current, count)`` — it can NEVER decrease.
    This makes the endpoint safe for debounced saves and page-unload
    flushes, so a newer database value is never overwritten by an older
    client value.
    """
    data = request.get_json() or {}
    dhikr_key = data.get('dhikr', '').strip()
    absolute_count = data.get('count')

    if dhikr_key not in DHIKR_NAMES:
        return jsonify({'success': False, 'error': 'Invalid Dhikr'}), 400

    today = date.today()
    record = _get_or_create_dhikr(current_user.id, today, dhikr_key)

    if absolute_count is not None:
        # Absolute-count save (debounced / page-unload flush).
        # Never decrease the stored count — only ever raise it.
        try:
            absolute_count = int(absolute_count)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid count'}), 400

        if absolute_count > record.count:
            record.count = absolute_count
    else:
        # Per-tap increment (no upper limit).
        record.count += 1

    try:
        db.session.commit()
        return jsonify({'success': True, 'count': record.count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@prayer_bp.route('/prayers/dhikr/reset', methods=['POST'])
@login_required
def dhikr_reset():
    """Reset today's count for a Dhikr back to 0."""
    data = request.get_json() or {}
    dhikr_key = data.get('dhikr', '').strip()

    if dhikr_key not in DHIKR_NAMES:
        return jsonify({'success': False, 'error': 'Invalid Dhikr'}), 400

    today = date.today()
    record = _get_or_create_dhikr(current_user.id, today, dhikr_key)
    record.count = 0

    try:
        db.session.commit()
        return jsonify({'success': True, 'count': 0})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@prayer_bp.route('/prayers/dhikr/state', methods=['GET'])
@login_required
def dhikr_state():
    """Get today's counts for all Dhikr (after page refresh)."""
    today = date.today()
    counts = {}
    records = Dhikr.query.filter_by(user_id=current_user.id, date=today).all()
    for record in records:
        counts[record.dhikr] = record.count
    return jsonify({'success': True, 'counts': counts})


@prayer_bp.route('/prayers/history')
@login_required
def history():
    """Prayer history page."""
    # Get date range filter
    days = request.args.get('days', 30, type=int)
    days = min(max(days, 7), 90)

    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    # Get attendance records for the period
    attendance_records = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).order_by(Attendance.date.desc()).all()

    # Get prayer records for the period
    prayer_records = Prayer.query.filter(
        Prayer.user_id == current_user.id,
        Prayer.date >= start_date,
        Prayer.date <= end_date
    ).order_by(Prayer.date.desc()).all()

    # Group prayers by date
    prayers_by_date = {}
    for prayer in prayer_records:
        date_key = prayer.date.isoformat()
        if date_key not in prayers_by_date:
            prayers_by_date[date_key] = {}
        prayers_by_date[date_key][prayer.prayer_name] = prayer.status

    # Calculate summary stats
    total_days = len(attendance_records)
    total_completed = sum(a.total_completed or 0 for a in attendance_records)
    total_qaza = sum(a.total_qaza or 0 for a in attendance_records)
    total_missed = sum(a.total_missed or 0 for a in attendance_records)
    total_possible = total_days * 5
    completion_rate = round((total_completed / total_possible) * 100, 1) if total_possible > 0 else 0

    # Calculate best streak
    best_streak = 0
    current_streak = 0
    for record in sorted(attendance_records, key=lambda x: x.date):
        if record.total_completed == 5:
            current_streak += 1
            best_streak = max(best_streak, current_streak)
        else:
            current_streak = 0

    return render_template(
        'history.html',
        attendance_records=attendance_records,
        prayers_by_date=prayers_by_date,
        prayer_names=PRAYER_NAMES,
        start_date=start_date,
        end_date=end_date,
        days=days,
        total_days=total_days,
        total_completed=total_completed,
        total_qaza=total_qaza,
        total_missed=total_missed,
        completion_rate=completion_rate,
        best_streak=best_streak
    )


@prayer_bp.route('/prayers/missed')
@login_required
def missed():
    """Qaza tracking page."""
    # Get all pending and completed Qaza prayers
    pending_qaza = Prayer.query.filter_by(
        user_id=current_user.id,
        status='missed'
    ).order_by(Prayer.date.desc()).all()

    # Group by date
    missed_by_date = {}
    for prayer in pending_qaza:
        date_key = prayer.date.isoformat()
        if date_key not in missed_by_date:
            missed_by_date[date_key] = {
                'date': prayer.date,
                'prayers': []
            }
        missed_by_date[date_key]['prayers'].append(prayer)

    completed_qaza_count = Prayer.query.filter_by(
        user_id=current_user.id,
        status='qaza'
    ).count()

    return render_template(
        'missed.html',
        missed_by_date=missed_by_date,
        prayer_names=PRAYER_NAMES,
        pending_qaza_count=len(pending_qaza),
        completed_qaza_count=completed_qaza_count,
        total_qaza=len(pending_qaza) + completed_qaza_count
    )


@prayer_bp.route('/prayers/missed/make-qaza', methods=['POST'])
@login_required
def make_qaza():
    """Convert a missed prayer to qaza."""
    data = request.get_json() or {}
    prayer_id = data.get('prayer_id')

    if not prayer_id:
        return jsonify({'success': False, 'error': 'Prayer ID is required'}), 400

    prayer = Prayer.query.filter_by(
        id=prayer_id,
        user_id=current_user.id
    ).first()

    if not prayer:
        return jsonify({'success': False, 'error': 'Prayer not found'}), 404

    if prayer.status != 'missed':
        return jsonify({'success': False, 'error': 'Prayer is not marked as missed'}), 400

    prayer.status = 'qaza'
    prayer.prayed_at = datetime.utcnow() # Set prayed_at to now for qaza

    try:
        db.session.commit()
        # Update attendance
        attendance = update_attendance_from_prayers(current_user.id, prayer.date)

        # Real counts from the database so the frontend can update summary
        # cards accurately (no guessing/incrementing).
        pending_count = Prayer.query.filter_by(
            user_id=current_user.id,
            status='missed'
        ).count()
        completed_count = Prayer.query.filter_by(
            user_id=current_user.id,
            status='qaza'
        ).count()

        return jsonify({
            'success': True,
            'counts': {
                'pending': pending_count,
                'completed': completed_count,
                'total': pending_count + completed_count
            },
            'attendance': {
                'total_completed': attendance.total_completed,
                'total_qaza': attendance.total_qaza,
                'total_missed': attendance.total_missed
            },
            'prayer_id': prayer_id
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@prayer_bp.route('/prayers/calendar')
@login_required
def calendar():
    """Calendar view showing daily prayer attendance."""

    today = get_local_today()
    user_start_date = get_user_start_date(current_user)

    # Get year and month from request, with robust validation.
    try:
        year = int(request.args.get('year', today.year))
    except (ValueError, TypeError):
        year = today.year

    try:
        month = int(request.args.get('month', today.month))
    except (ValueError, TypeError):
        month = today.month

    if not 1 <= month <= 12:  # Ensure month is valid
        month = today.month

    # First and last day of the displayed month
    first_day_of_month = date(year, month, 1)
    if month == 12:
        last_day_of_month = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day_of_month = date(year, month + 1, 1) - timedelta(days=1)

    # --------------------------------------------------
    # Get daily attendance summaries
    # --------------------------------------------------

    attendance_records = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        Attendance.date >= first_day_of_month,
        Attendance.date <= last_day_of_month
    ).all()

    attendance_by_date_obj = {record.date: record for record in attendance_records}

    # --------------------------------------------------
    # Get individual prayer records
    # --------------------------------------------------

    prayer_records = Prayer.query.filter(
        Prayer.user_id == current_user.id,
        Prayer.date >= first_day_of_month,
        Prayer.date <= last_day_of_month
    ).all()

    prayers_by_date_obj = {}
    for prayer in prayer_records:
        date_key = prayer.date
        if date_key not in prayers_by_date_obj:
            prayers_by_date_obj[date_key] = {}
        prayers_by_date_obj[date_key][prayer.prayer_name] = prayer.status

    # --------------------------------------------------
    # Prepare calendar days for template
    # --------------------------------------------------
    calendar_days = []
    # Fill in leading empty days
    first_weekday = first_day_of_month.weekday()  # Monday is 0, Sunday is 6
    for _ in range(first_weekday):
        calendar_days.append({'day_type': 'empty'})

    # Fill in days of the month
    current_day_iter = first_day_of_month
    while current_day_iter <= last_day_of_month:
        is_today = (current_day_iter == today)
        is_before_start = (current_day_iter < user_start_date)
        is_future = (current_day_iter > today)
        is_editable = not is_before_start and not is_future

        attendance_summary_obj = attendance_by_date_obj.get(current_day_iter)
        attendance_summary_dict = None
        if attendance_summary_obj:
            attendance_summary_dict = {
                'total_completed': attendance_summary_obj.total_completed or 0,
                'total_qaza': attendance_summary_obj.total_qaza or 0,
                'total_missed': attendance_summary_obj.total_missed or 0,
                'completion_percentage': attendance_summary_obj.completion_percentage or 0.0
            }

        calendar_days.append({
            'day_type': 'day',
            'date': current_day_iter,
            'day_number': current_day_iter.day,
            'attendance_summary': attendance_summary_dict,
            'prayers': prayers_by_date_obj.get(current_day_iter, {}),
            'is_today': is_today,
            'is_before_start': is_before_start,
            'is_future': is_future,
            'is_editable': is_editable
        })
        current_day_iter += timedelta(days=1)

    # --------------------------------------------------
    # Render calendar
    # --------------------------------------------------

    return render_template(
        'calendar.html',
        year=year,
        month=month,
        start_date=first_day_of_month,
        end_date=last_day_of_month,
        calendar_days=calendar_days,  # New structure
        prayer_names=PRAYER_NAMES,
        today=today,
        user_start_date=user_start_date
    )