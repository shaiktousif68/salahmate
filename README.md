# SalahMate - Islamic Prayer & Quran Companion

SalahMate is a Flask-based Islamic prayer and Quran companion application designed to help users track Salah, read the Quran, manage bookmarks, monitor spiritual progress, and view prayer statistics.

## Features

- **User Authentication** - Secure registration, login, logout, and password reset
- **Prayer Tracking** - Track Fajr, Dhuhr, Asr, Maghrib, and Isha
- **Jamaat / Alone / Missed / Qaza** - Record different prayer statuses
- **Prayer Times** - Calculate prayer times based on location
- **Quran Reader** - Read Quran by Surah and Para/Juz
- **Quran Audio** - Listen to Quran recitation
- **Quran Translations** - English, Urdu, Telugu, and other supported translations
- **Bookmarks** - Save Quran ayahs for later
- **Prayer Calendar** - View prayer attendance history
- **Reports & Analytics** - Track prayer consistency and completion
- **Dhikr Counter** - Record daily Dhikr
- **Password Reset** - Email-based password reset
- **Responsive UI** - Designed for desktop and mobile screens
- **Future Mobile App** - The web application is structured for future PWA/Android packaging

## Technology Stack

- Python 3.13
- Flask
- Flask-SQLAlchemy
- Flask-Login
- Flask-Migrate
- Flask-Bcrypt
- Flask-Mail
- PostgreSQL / Supabase
- HTML5
- CSS3
- JavaScript
- Chart.js

## Project Structure

```text
salahmate/
│
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── models/
│   ├── routes/
│   ├── services/
│   ├── static/
│   └── templates/
│
├── migrations/
├── tests/
├── run.py
├── requirements.txt
├── .gitignore
├── .python-version
└── README.md