"""Verify Urdu is the default translation for Quran readers."""
import requests, time

BASE = 'http://127.0.0.1:5000'
s = requests.Session()

# Register a fresh user
u = 'urducheck' + str(int(time.time()))[-6:]
r = s.post(BASE + '/register', data={
    'username': u, 'email': u + '@test.com',
    'password': 'TestPass123', 'confirm_password': 'TestPass123',
    'full_name': 'Urdu Check', 'gender': 'male'
}, allow_redirects=True)
print(f'Register: {r.status_code}')

r = s.post(BASE + '/login', data={
    'username': u, 'password': 'TestPass123'
}, allow_redirects=True)
print(f'Login: {r.status_code}')

# Check Surah reader default (no translation param)
r = s.get(BASE + '/quran/surah/1')
html = r.text
print('\nSurah 1 (no translation param):')
print(f'  Has ur.jalandhry selected: {"ur.jalandhry" in html and "selected" in html}')
print(f'  Has en.sahih selected: {"en.sahih" in html and "selected" in html}')
print(f'  Has localStorage restore script: {"quranTranslation" in html}')

# Check Para reader default
r = s.get(BASE + '/quran/para/1')
html = r.text
print('\nPara 1 (no translation param):')
print(f'  Has ur.jalandhry selected: {"ur.jalandhry" in html and "selected" in html}')
print(f'  Has en.sahih selected: {"en.sahih" in html and "selected" in html}')
print(f'  Has localStorage restore script: {"quranTranslation" in html}')

# Check explicit English still works
r = s.get(BASE + '/quran/surah/1?translation=en.sahih')
html = r.text
print('\nSurah 1 (explicit en.sahih):')
print(f'  Has en.sahih selected: {"en.sahih" in html and "selected" in html}')

# Check explicit Telugu still works
r = s.get(BASE + '/quran/surah/1?translation=te.zekr')
html = r.text
print('\nSurah 1 (explicit te.zekr):')
print(f'  Has te.zekr selected: {"te.zekr" in html and "selected" in html}')

# Check ayah detail API default
r = s.get(BASE + '/quran/ayah/1/1')
data = r.json()
print('\nAyah detail API (no translation param):')
print(f'  translation_identifier: {data.get("translation_identifier")}')