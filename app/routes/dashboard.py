from datetime import date, timedelta, datetime
from flask import Blueprint, render_template, jsonify, send_from_directory, request
from flask_login import login_required, current_user
from app.models.prayer import Prayer
from app.models.attendance import Attendance
from app.models.quran import QuranReading
from app.services.prayer_times import PrayerTimesService
from app.date_utils import get_user_start_date, get_local_today
from flask import current_app

dashboard_bp = Blueprint('dashboard', __name__)

PRAYER_NAMES = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']


@dashboard_bp.route('/')
@login_required
def home():
    """Main dashboard route."""
    today = get_local_today()

    # Get today's prayer times
    prayer_times = PrayerTimesService.get_todays_prayer_times(current_user)
    next_prayer, next_prayer_time = PrayerTimesService.get_next_prayer(prayer_times)

    # Get today's attendance
    # This will be used for the summary card
    attendance = Attendance.query.filter_by(
        user_id=current_user.id,
        date=today
    ).first()

    # Get today's prayer statuses for dashboard display
    today_prayers = Prayer.query.filter_by(
        user_id=current_user.id,
        date=today
    ).all()

    prayer_status = {
        prayer.prayer_name: prayer.status
        for prayer in today_prayers
    }

    # Calculate weekly stats
    week_start = today - timedelta(days=today.weekday())

    # Fetch ALL attendance up to today ONCE, and derive both the weekly stats
    # and the streak from the same result set — eliminates a duplicate query.
    all_attendance = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        Attendance.date <= today
    ).order_by(Attendance.date.desc()).all()

    weekly_attendance = [a for a in all_attendance if a.date >= week_start]

    total_completed_week = sum((a.total_completed or 0) for a in weekly_attendance)
    total_qaza_week = sum((a.total_qaza or 0) for a in weekly_attendance)
    total_missed_week = sum((a.total_missed or 0) for a in weekly_attendance)
    total_possible_week = len(weekly_attendance) * 5
    weekly_percentage = round((total_completed_week / total_possible_week) * 100, 1) if total_possible_week > 0 else 0

    # Get streak (consecutive days with all 5 prayers completed)
    # Uses the same all_attendance result above — no extra query.
    streak = 0
    user_start = get_user_start_date(current_user)
    
    attendance_map = {att.date: (att.total_completed or 0) for att in all_attendance}
    check_date = today
    while check_date >= user_start:
        if attendance_map.get(check_date) == 5:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    # Get Quran progress
    recent_reading = QuranReading.query.filter_by(
        user_id=current_user.id
    ).order_by(QuranReading.read_at.desc()).first()

    # Count total readings
    total_readings = QuranReading.query.filter_by(user_id=current_user.id).count()

    # Get current para (from most recent reading)
    current_para = recent_reading.para_number if recent_reading else 1

    # Format prayer times for display
    formatted_times = {}
    if prayer_times:
        for name in ['Fajr', 'Sunrise', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']:
            formatted_times[name] = PrayerTimesService.format_time(prayer_times.get(name))

    # Current time for greeting
    now = datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        greeting = 'Assalamu Alaikum'
    elif 12 <= hour < 17:
        greeting = 'Assalamu Alaikum'
    elif 17 <= hour < 21:
        greeting = 'Assalamu Alaikum'
    else:
        greeting = 'Assalamu Alaikum'

    return render_template(
        'dashboard.html',
        greeting=greeting,
        prayer_times=formatted_times,
        attendance=attendance,
        next_prayer=next_prayer,
        next_prayer_time=PrayerTimesService.format_time(next_prayer_time) if next_prayer_time else None,
        weekly_percentage=weekly_percentage,
        total_completed_week=total_completed_week,
        total_qaza_week=total_qaza_week,
        total_missed_week=total_missed_week,
        streak=streak,
        recent_reading=recent_reading,
        total_readings=total_readings,
        current_para=current_para,
        hijri_date=prayer_times.get('hijri_date') if prayer_times else None,
        hijri_weekday=prayer_times.get('hijri_weekday') if prayer_times else None,
        current_time=now.strftime('%I:%M %p'),
        current_date=now.strftime('%A, %B %d, %Y'),
        prayer_names=PRAYER_NAMES,
        prayer_status=prayer_status,
        today=today
    )


@dashboard_bp.route('/api/countdown')
@login_required
def countdown():
    """API endpoint for next prayer countdown."""
    prayer_times = PrayerTimesService.get_todays_prayer_times(current_user)
    next_prayer, next_prayer_time = PrayerTimesService.get_next_prayer(prayer_times)

    return jsonify({
        'next_prayer': next_prayer,
        'next_prayer_time': next_prayer_time
    })
@dashboard_bp.route('/api/dashboard', methods=['GET'])
def api_dashboard():
    return jsonify({
        "greeting": "Assalamu Alaikum",
        "weekly_percentage": 0,
        "streak": 0,
        "total_completed_week": 0,
        "total_qaza_week": 0,
        "total_missed_week": 0,
        "current_para": 1,
        "total_readings": 0,
        "prayers": {
            "Fajr": "Pending",
            "Dhuhr": "Pending",
            "Asr": "Pending",
            "Maghrib": "Pending",
            "Isha": "Pending"
        }
    })