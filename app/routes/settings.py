from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db, bcrypt

settings_bp = Blueprint('settings', __name__)

CALCULATION_METHODS = [
    (0, 'Shia Ithna-Ashari'),
    (1, 'University of Islamic Sciences, Karachi'),
    (2, 'Islamic Society of North America (ISNA)'),
    (3, 'Muslim World League (MWL)'),
    (4, 'Umm Al-Qura University, Makkah'),
    (5, 'Egyptian General Authority of Survey'),
    (7, 'Institute of Geophysics, University of Tehran'),
    (8, 'Gulf Region'),
    (9, 'Kuwait'),
    (10, 'Qatar'),
    (11, 'Majlis Ugama Islam Singapura, Singapore'),
    (12, 'Union Organization islamic de France'),
    (13, 'Diyanet İşleri Başkanlığı, Turkey'),
    (14, 'Spiritual Administration of Muslims of Russia')
]


@settings_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        city = request.form.get('city', '').strip()
        country = request.form.get('country', '').strip()
        latitude = request.form.get('latitude', '').strip()
        longitude = request.form.get('longitude', '').strip()
        calculation_method = request.form.get('calculation_method', type=int)

        # Validation
        errors = []
        if not full_name:
            errors.append('Full name is required.')

        try:
            lat = float(latitude) if latitude else None
            if lat is not None and not -90 <= lat <= 90:
                errors.append('Latitude must be between -90 and 90.')
        except ValueError:
            errors.append('Invalid latitude value.')

        try:
            lon = float(longitude) if longitude else None
            if lon is not None and not -180 <= lon <= 180:
                errors.append('Longitude must be between -180 and 180.')
        except ValueError:
            errors.append('Invalid longitude value.')

        if calculation_method not in [m[0] for m in CALCULATION_METHODS]:
            errors.append('Invalid calculation method.')

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('settings.html', methods=CALCULATION_METHODS)

        # Update user settings
        current_user.full_name = full_name
        current_user.city = city or current_user.city
        current_user.country = country or current_user.country
        current_user.latitude = lat if lat is not None else current_user.latitude
        current_user.longitude = lon if lon is not None else current_user.longitude
        current_user.calculation_method = calculation_method

        try:
            db.session.commit()
            flash('Settings updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating settings: {str(e)}', 'danger')

        return redirect(url_for('settings.index'))

    return render_template('settings.html', methods=CALCULATION_METHODS)


@settings_bp.route('/settings/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password."""
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    errors = []
    if not current_user.verify_password(current_password):
        errors.append('Current password is incorrect.')
    if len(new_password) < 6:
        errors.append('New password must be at least 6 characters long.')
    if new_password != confirm_password:
        errors.append('New passwords do not match.')

    if errors:
        for error in errors:
            flash(error, 'danger')
        return redirect(url_for('settings.index'))

    current_user.password = new_password
    try:
        db.session.commit()
        flash('Password changed successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error changing password: {str(e)}', 'danger')

    return redirect(url_for('settings.index'))