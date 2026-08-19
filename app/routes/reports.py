from datetime import date, timedelta
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models.attendance import Attendance
from app.models.prayer import Prayer
from app.models.quran import QuranReading

reports_bp = Blueprint('reports', __name__)

PRAYER_NAMES = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']


@reports_bp.route('/reports')
@login_required
def index():
    """Reports and analytics page."""
    # Get date range
    days = request.args.get('days', 30, type=int)
    days = min(max(days, 7), 90)

    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    # Get attendance records
    attendance_records = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).order_by(Attendance.date).all()

    # Calculate overall stats
    total_days = len(attendance_records)
    total_completed = sum((a.total_completed or 0) for a in attendance_records)
    total_qaza = sum((a.total_qaza or 0) for a in attendance_records)
    total_missed = sum((a.total_missed or 0) for a in attendance_records)
    total_possible = total_days * 5
    overall_percentage = round((total_completed / total_possible) * 100, 1) if total_possible > 0 else 0

    # Per-prayer stats
    prayer_records = Prayer.query.filter(
        Prayer.user_id == current_user.id,
        Prayer.date >= start_date,
        Prayer.date <= end_date
    ).all()

    prayer_stats = {}
    for name in PRAYER_NAMES:
        jamaat_count = sum(1 for p in prayer_records if p.prayer_name == name and p.status == 'jamaat')
        alone_count = sum(1 for p in prayer_records if p.prayer_name == name and p.status == 'alone')
        qaza_count = sum(1 for p in prayer_records if p.prayer_name == name and p.status == 'qaza')
        missed_count = sum(1 for p in prayer_records if p.prayer_name == name and p.status == 'missed')
        completed = jamaat_count + alone_count
        total_for_prayer = jamaat_count + alone_count + qaza_count + missed_count
        prayer_stats[name] = {
            'jamaat': jamaat_count,
            'alone': alone_count,
            'qaza': qaza_count,
            'missed': missed_count,
            'completed': completed,
            'percentage': round((completed / total_for_prayer) * 100, 1) if total_for_prayer > 0 else 0
        }

    # Weekly data for chart
    weekly_data = []
    for i in range(0, days, 7):
        week_start = start_date + timedelta(days=i)
        week_end = min(week_start + timedelta(days=6), end_date)
        week_records = [a for a in attendance_records if week_start <= a.date <= week_end]
        week_completed = sum((a.total_completed or 0) for a in week_records)
        week_qaza = sum((a.total_qaza or 0) for a in week_records)
        week_missed = sum((a.total_missed or 0) for a in week_records)
        week_possible = len(week_records) * 5
        weekly_data.append({
            'label': f'{week_start.strftime("%b %d")} - {week_end.strftime("%b %d")}',
            'completed': week_completed,
            'qaza': week_qaza,
            'missed': week_missed,
            'possible': week_possible,
            'percentage': round((week_completed / week_possible) * 100, 1) if week_possible > 0 else 0
        })

    # Daily data for chart
    daily_data = []
    for a in attendance_records:
        daily_data.append({
            'date': a.date.strftime('%Y-%m-%d'),
            'label': a.date.strftime('%b %d'),
            'completed': a.total_completed or 0,
            'qaza': a.total_qaza or 0,
            'missed': a.total_missed or 0,
            'percentage': a.completion_percentage
        })

    # Best streak
    best_streak = 0
    current_streak = 0
    for a in attendance_records:
        if (a.total_completed or 0) == 5:
            current_streak += 1
            best_streak = max(best_streak, current_streak)
        else:
            current_streak = 0

    # Quran reading stats
    quran_readings = QuranReading.query.filter(
        QuranReading.user_id == current_user.id,
        QuranReading.read_at >= start_date
    ).count()

    return render_template(
        'reports.html',
        days=days,
        start_date=start_date,
        end_date=end_date,
        total_days=total_days,
        total_completed=total_completed,
        total_qaza=total_qaza,
        total_missed=total_missed,
        overall_percentage=overall_percentage,
        prayer_stats=prayer_stats,
        weekly_data=weekly_data,
        daily_data=daily_data,
        best_streak=best_streak,
        quran_readings=quran_readings,
        prayer_names=PRAYER_NAMES
    )


@reports_bp.route('/reports/data')
@login_required
def data():
    """API endpoint for report data (for charts)."""
    days = request.args.get('days', 30, type=int)
    days = min(max(days, 7), 90)

    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    attendance_records = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).order_by(Attendance.date).all()

    # Daily data
    daily = [{
        'date': a.date.strftime('%Y-%m-%d'),
        'completed': a.total_completed or 0,
        'qaza': a.total_qaza or 0,
        'missed': a.total_missed or 0,
        'percentage': a.completion_percentage
    } for a in attendance_records]

    # Prayer breakdown
    prayer_records = Prayer.query.filter(
        Prayer.user_id == current_user.id,
        Prayer.date >= start_date,
        Prayer.date <= end_date
    ).all()

    prayer_breakdown = {}
    for name in PRAYER_NAMES:
        prayer_breakdown[name] = {
            'jamaat': sum(1 for p in prayer_records if p.prayer_name == name and p.status == 'jamaat'),
            'alone': sum(1 for p in prayer_records if p.prayer_name == name and p.status == 'alone'),
            'qaza': sum(1 for p in prayer_records if p.prayer_name == name and p.status == 'qaza'),
            'missed': sum(1 for p in prayer_records if p.prayer_name == name and p.status == 'missed')
        }

    return jsonify({
        'daily': daily,
        'prayer_breakdown': prayer_breakdown,
        'total_days': len(attendance_records),
        'total_completed': sum((a.total_completed or 0) for a in attendance_records),
        'total_qaza': sum((a.total_qaza or 0) for a in attendance_records),
        'total_missed': sum((a.total_missed or 0) for a in attendance_records)
    })