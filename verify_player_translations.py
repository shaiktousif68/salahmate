"""Verify premium 3D player renders for all translations."""
import requests, time

BASE = 'http://127.0.0.1:5000'
s = requests.Session()

# Register a fresh user
u = 'verify' + str(int(time.time()))[-6:]
r = s.post(BASE + '/register', data={
    'username': u, 'email': u + '@test.com',
    'password': 'TestPass123', 'confirm_password': 'TestPass123',
    'full_name': 'Verify', 'gender': 'male'
}, allow_redirects=True)
print(f'Register: {r.status_code}')

r = s.post(BASE + '/login', data={
    'username': u, 'password': 'TestPass123'
}, allow_redirects=True)
print(f'Login: {r.status_code}')

translations = {'en.sahih': 'English', 'ur.jalandhry': 'Urdu', 'te.zekr': 'Telugu'}

# Test Surah reader for all translations
for trans, name in translations.items():
    r = s.get(f'{BASE}/quran/surah/1?translation={trans}')
    html = r.text
    premium = ('audio-player-3d-top' in html and
               'audio-player-icon-wrap' in html and
               'audio-waveform' in html)
    native_audio = '<audio' in html
    quran_js = 'js/quran.js' in html
    print(f'{name:8s} Surah ({trans}):')
    print(f'  Premium 3D player: {premium}')
    print(f'  Native <audio>: {native_audio}')
    print(f'  quran.js: {quran_js}')

# Check Para reader with English
r = s.get(f'{BASE}/quran/para/1?translation=en.sahih')
html = r.text
premium = ('audio-player-3d-top' in html and
           'audio-player-icon-wrap' in html and
           'audio-waveform' in html)
native_audio = '<audio' in html
print(f'\nPara 1 (en.sahih):')
print(f'  Premium 3D player: {premium}')
print(f'  Native <audio>: {native_audio}')