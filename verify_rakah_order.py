"""Verify the Daily Salah & Rak'ahs section comes FIRST on the Salah page."""
import requests, time, urllib3
urllib3.disable_warnings()

BASE = 'http://127.0.0.1:5000'
s = requests.Session()

username = 'ordercheck' + str(int(time.time()))[-6:]
s.post(BASE + '/register', data={
    'username': username, 'email': username + '@test.com',
    'password': 'TestPass123', 'confirm_password': 'TestPass123',
    'full_name': 'Order Check', 'gender': 'male'
}, allow_redirects=True)
s.post(BASE + '/login', data={'username': username, 'password': 'TestPass123'}, allow_redirects=True)

html = s.get(BASE + '/prayers', timeout=15).text

# Check order: Daily Salah must come BEFORE Prayer Times heading
rakah_pos = html.find('Daily Salah')
prayer_pos = html.find('prayer-times-heading')
print('Rakah position:', rakah_pos)
print('Prayer Times heading position:', prayer_pos)
print('Rakah FIRST (correct order):', rakah_pos >= 0 and rakah_pos < prayer_pos)
print('Has rakah-card-primary class:', 'rakah-card-primary' in html)
print('Has prayer-times-heading class:', 'prayer-times-heading' in html)