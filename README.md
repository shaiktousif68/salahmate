# SalahMate - Islamic Prayer & Quran Companion

SalahMate is a comprehensive Flask-based web application designed to help Muslims track their daily prayers, read the Quran, set prayer alarms, and monitor their spiritual progress.

## Features

- **User Authentication** - Secure registration and login with password hashing
- **Prayer Tracking** - Mark prayers as completed for Fajr, Dhuhr, Asr, Maghrib, and Isha
- **Prayer Times** - Automatic calculation of prayer times based on location
- **Quran Reader** - Browse and read the Quran by Para (Juz) with bookmarks
- **Prayer Alarms** - Set custom alarms for prayer times with notifications
- **Attendance History** - View your prayer attendance history
- **Reports & Analytics** - Visual charts showing your prayer consistency
- **Settings** - Customize your location and preferences

## Project Structure

```
salahmate/
│
├── app/
│   ├── __init__.py          # App factory
│   ├── config.py            # Configuration
│   ├── models/              # Database models
│   ├── routes/              # Route blueprints
│   ├── services/            # Business logic services
│   ├── templates/           # HTML templates
│   └── static/              # CSS, JS, images, audio
│
├── migrations/              # Database migrations
├── tests/                   # Unit tests
├── run.py                   # Application entry point
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables
└── README.md
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/salahmate.git
cd salahmate
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

### 3. Activate the virtual environment

**Windows:**
```bash
venv\Scripts\activate
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

Edit the `.env` file:

```
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///salahmate.db
FLASK_DEBUG=1
```

### 6. Initialize the database

```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

Or simply run the app which will auto-create the database:

```bash
python run.py
```

### 7. Run the application

```bash
python run.py
```

Visit `http://127.0.0.1:5000` in your browser.

## Usage

1. **Register** a new account
2. **Set your location** in Settings for accurate prayer times
3. **Track prayers** from the Dashboard or Prayers page
4. **Read the Quran** from the Quran section
5. **Set alarms** for prayer times
6. **View reports** to see your prayer consistency

## Testing

```bash
pytest
```

## Technologies Used

- **Flask** - Web framework
- **Flask-SQLAlchemy** - ORM for database operations
- **Flask-Login** - User session management
- **Flask-Bcrypt** - Password hashing
- **Flask-Migrate** - Database migrations
- **APScheduler** - Background task scheduling for notifications
- **Chart.js** - Interactive charts for reports

## License

This project is for educational and personal use.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.