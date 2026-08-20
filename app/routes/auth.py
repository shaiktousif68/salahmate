from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
import requests
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from app import db
from app.models.user import User
from app.models.password_reset import PasswordResetToken

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration route."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        full_name = request.form.get('full_name', '').strip()
        gender = request.form.get('gender', 'male').strip()

        errors = []

        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters long.')

        if not email or '@' not in email:
            errors.append('Please enter a valid email address.')

        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters long.')

        if password != confirm_password:
            errors.append('Passwords do not match.')

        if gender not in ['male', 'female']:
            errors.append('Invalid gender selected.')

        if User.query.filter_by(username=username).first():
            errors.append('Username already exists.')

        if User.query.filter_by(email=email).first():
            errors.append('Email already registered.')

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('auth/register.html', form_data=request.form)

        user = User(
            username=username,
            email=email,
            password=password,
            full_name=full_name or username,
            gender=gender,
            created_at=datetime.utcnow()
        )

        db.session.add(user)

        try:
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            flash(f'Registration failed: {str(e)}', 'danger')
            return render_template('auth/register.html', form_data=request.form)

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login route."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = 'remember' in request.form

        user = User.query.filter(
            (User.username == username) | (User.email == username.lower())
        ).first()

        if user and user.verify_password(password):
            login_user(user, remember=remember)
            flash(f'Welcome back, {user.username}!', 'success')

            next_page = request.args.get('next')

            if next_page and next_page.startswith('/'):
                return redirect(next_page)

            return redirect(url_for('dashboard.home'))

        else:
            flash('Invalid username/email or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request a password reset email using Brevo API."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        # Always show the same message whether or not the email exists.
        user = User.query.filter_by(email=email).first()

        if user:
            try:
                # Generate password reset token
                raw_token = PasswordResetToken.generate_for_user(user.id)

                # Generate reset URL
                reset_url = url_for(
                    'auth.reset_password',
                    token=raw_token,
                    _external=True
                )

                # Render email HTML
                email_html = render_template(
                    'auth/reset_email.html',
                    username=user.username,
                    reset_url=reset_url,
                    expires_minutes=PasswordResetToken.TOKEN_TTL_MINUTES
                )

                # Brevo configuration
                brevo_api_key = current_app.config.get('BREVO_API_KEY')
                sender_email = current_app.config.get('BREVO_SENDER_EMAIL')
                sender_name = current_app.config.get(
                    'BREVO_SENDER_NAME',
                    'SalahMate'
                )

                if not brevo_api_key:
                    raise ValueError('BREVO_API_KEY is not configured.')

                if not sender_email:
                    raise ValueError('BREVO_SENDER_EMAIL is not configured.')

                # Send email through Brevo API
                response = requests.post(
                    'https://api.brevo.com/v3/smtp/email',
                    headers={
                        'accept': 'application/json',
                        'api-key': brevo_api_key,
                        'content-type': 'application/json'
                    },
                    json={
                        'sender': {
                            'name': sender_name,
                            'email': sender_email
                        },
                        'to': [
                            {
                                'email': user.email,
                                'name': user.username
                            }
                        ],
                        'subject': 'SalahMate - Password Reset Request',
                        'htmlContent': email_html
                    },
                    timeout=15
                )

                # Raise an error if Brevo rejects the request
                response.raise_for_status()

                current_app.logger.info(
                    'Password reset email sent successfully to %s',
                    user.email
                )

            except Exception:
                # Do not reveal account existence.
                current_app.logger.error(
                    'Password reset email failed to send',
                    exc_info=True
                )

        flash(
            'If an account exists for that email, a password reset link has been sent. '
            'Please check your inbox.',
            'info'
        )

        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password using a one-time token."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))

    reset_token = PasswordResetToken.validate_token(token)

    if not reset_token:
        flash(
            'This password reset link is invalid or has expired. '
            'Please request a new one.',
            'danger'
        )
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        errors = []

        if len(password) < 6:
            errors.append('Password must be at least 6 characters long.')

        if password != confirm_password:
            errors.append('Passwords do not match.')

        if errors:
            for error in errors:
                flash(error, 'danger')

            return render_template(
                'auth/reset_password.html',
                token=token
            )

        user = User.query.get(reset_token.user_id)

        if not user:
            flash('User account not found.', 'danger')
            return redirect(url_for('auth.forgot_password'))

        # Set new password
        user.password = password

        # Mark token as used
        reset_token.mark_used()

        try:
            db.session.commit()

            flash(
                'Your password has been reset successfully. '
                'Please log in with your new password.',
                'success'
            )

            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()

            flash(
                f'Failed to reset password: {str(e)}',
                'danger'
            )

            return render_template(
                'auth/reset_password.html',
                token=token
            )

    return render_template(
        'auth/reset_password.html',
        token=token
    )


@auth_bp.route('/logout')
@login_required
def logout():
    """Logout user."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))