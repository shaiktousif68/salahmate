"""Verify the new Daily Salah & Rak'ahs section renders on the Salah page."""
import requests, time, urllib3
urllib3.disable_warnings()

BASE = 'http://127.0.0.1:5000'
s = requests.Session()

username = 'rakahcheck' + str(int(time.time()))[-6:]
s.post(BASE + '/register', data={
    'username': username, 'email': username + '@test.com',
    'password': 'TestPass123', 'confirm_password': 'TestPass123',
    'full_name': 'Rakah Check', 'gender': 'male'
}, allow_redirects=True)
s.post(BASE + '/login', data={'username': username, 'password': 'TestPass123'}, allow_redirects=True)

r = s.get(BASE + '/prayers', timeout=15)
html = r.text

print('Status:', r.status_code)
print('Has Daily Salah & Rakahs section:', 'Daily Salah' in html and 'Rak\'ahs' in html)
print('Has Fajr:', 'Fajr' in html)
print('Has Dhuhr:', 'Dhuhr' in html)
print('Has Asr:', 'Asr' in html)
print('Has Maghrib:', 'Maghrib' in html)
print('Has Isha:', 'Isha' in html)
print('Has 2 Sunnah badge:', '2 Sunnah' in html)
print('Has 4 Fard badge:', '4 Fard' in html)
print('Has 3 Witr badge:', '3 Witr' in html)
print('Has rakah-table class:', 'rakah-table' in html)
print('Has rakah-card class:', 'rakah-card' in html)
print('Has Before Fard column:', 'Before Fard' in html)
print('Has After Fard column:', 'After Fard' in html)
print('Has Witr column:', 'Witr' in html)
print('Has existing prayer timings page title:', 'Prayer Times' in html)
print('Has temple icon:', 'fa-mosque' in html)