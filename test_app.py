"""Comprehensive test for SalahMate."""
from datetime import date, timedelta
from app import create_app, db
from app.models.user import User
from app.models.prayer import Prayer

app = create_app('testing')

with app.app_context():
    db.create_all()
    # Create test user
    user = User.query.filter_by(username='testuser').first()
    if not user:
        user = User(username='testuser', email='test@test.com', password='password123', full_name='Test User', gender='male')
        db.session.add(user)
        db.session.commit()

    client = app.test_client()

    # Login
    r = client.post('/login', data={'username': 'testuser', 'password': 'password123'}, follow_redirects=True)
    print(f'Login: {r.status_code}')

    # Test all pages
    pages = ['/', '/quran', '/reports', '/settings', '/attendance', '/prayers/calendar', '/prayers/history', '/prayers/missed', '/prayers']
    for p in pages:
        r = client.get(p)
        print(f'{p}: {r.status_code}')

    # Test attendance status transitions
    today = date.today().isoformat()
    transitions = [
        ('jamaat', 'alone'),
        ('jamaat', 'qaza'),
        ('jamaat', 'missed'),
        ('alone', 'jamaat'),
        ('alone', 'qaza'),
        ('alone', 'missed'),
        ('qaza', 'jamaat'),
        ('qaza', 'alone'),
        ('qaza', 'missed'),
        ('missed', 'jamaat'),
        ('missed', 'alone'),
        ('missed', 'qaza'),
    ]

    print('\n--- Attendance Transitions ---')
    for status1, status2 in transitions:
        # Set first status
        r = client.post('/attendance/update', json={
            'prayer_name': 'Fajr',
            'status': status1,
            'date': today
        })
        assert r.status_code == 200, f'Failed setting {status1}: {r.status_code}'
        data1 = r.json
        assert data1['success'], f'Failed setting {status1}: {data1}'

        # Verify only one record exists
        prayers = Prayer.query.filter_by(user_id=user.id, prayer_name='Fajr', date=date.today()).all()
        assert len(prayers) == 1, f'Expected 1 record, got {len(prayers)}'

        # Set second status
        r = client.post('/attendance/update', json={
            'prayer_name': 'Fajr',
            'status': status2,
            'date': today
        })
        assert r.status_code == 200, f'Failed setting {status2}: {r.status_code}'
        data2 = r.json
        assert data2['success'], f'Failed setting {status2}: {data2}'

        # Verify still only one record
        prayers = Prayer.query.filter_by(user_id=user.id, prayer_name='Fajr', date=date.today()).all()
        assert len(prayers) == 1, f'Expected 1 record after transition, got {len(prayers)}'
        assert prayers[0].status == status2, f'Expected status {status2}, got {prayers[0].status}'

        print(f'  {status1} -> {status2}: OK')

    # Test all 5 prayers independently
    print('\n--- All 5 Prayers ---')
    for prayer in ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']:
        r = client.post('/attendance/update', json={
            'prayer_name': prayer,
            'status': 'jamaat',
            'date': today
        })
        assert r.status_code == 200, f'Failed {prayer}: {r.status_code}'
        print(f'  {prayer}: OK')

    # Verify all 5 records exist
    prayers = Prayer.query.filter_by(user_id=user.id, date=date.today()).all()
    assert len(prayers) == 5, f'Expected 5 records, got {len(prayers)}'
    print(f'\nTotal records for today: {len(prayers)}')

    # Test different dates
    print('\n--- Different Dates ---')
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    r = client.post('/attendance/update', json={
        'prayer_name': 'Fajr',
        'status': 'alone',
        'date': yesterday
    })
    assert r.status_code == 200, f'Failed yesterday: {r.status_code}'
    print(f'  Yesterday: OK')

    # Test Quran pages
    print('\n--- Quran Pages ---')
    r = client.get('/quran?view=surah')
    print(f'  Surah list: {r.status_code}')
    r = client.get('/quran?view=para')
    print(f'  Para list: {r.status_code}')
    r = client.get('/quran/surah/1')
    print(f'  Surah 1: {r.status_code}')
    r = client.get('/quran/para/1')
    print(f'  Para 1: {r.status_code}')
    r = client.get('/quran/ayah/1/1')
    print(f'  Ayah 1:1: {r.status_code}')

    # Test reports data
    r = client.get('/reports/data')
    print(f'\nReports data: {r.status_code}')

    # Test countdown
    r = client.get('/api/countdown')
    print(f'Countdown: {r.status_code}')

    print('\n=== ALL TESTS PASSED ===')