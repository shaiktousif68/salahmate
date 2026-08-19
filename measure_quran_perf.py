"""Measure Quran page load times (first uncached vs cached)."""
import requests, time, urllib3
urllib3.disable_warnings()

BASE = 'http://127.0.0.1:5000'
s = requests.Session()

# Login with a fresh user
username = 'perfuser' + str(int(time.time()))[-6:]
s.post(BASE + '/register', data={
    'username': username,
    'email': username + '@test.com',
    'password': 'TestPass123',
    'confirm_password': 'TestPass123',
    'full_name': 'Perf User',
    'gender': 'male'
}, allow_redirects=True)
s.post(BASE + '/login', data={'username': username, 'password': 'TestPass123'}, allow_redirects=True)

# Verify login
r = s.get(BASE + '/', timeout=15)
print(f'Login status: {r.status_code}, URL: {r.url}')

pages = {
    'Surah List': '/quran?view=surah',
    'Para List': '/quran?view=para',
    'Surah 1': '/quran/surah/1',
    'Surah 2': '/quran/surah/2',
    'Para 1': '/quran/para/1',
    'Para 2': '/quran/para/2',
}

print('\n=== FIRST LOAD (uncached) ===')
first_times = {}
for name, path in pages.items():
    t0 = time.perf_counter_ns()
    r = s.get(BASE + path, timeout=30)
    dt = (time.perf_counter_ns() - t0) / 1e6
    first_times[name] = dt
    print(f'{name:12s} {r.status_code} {dt:8.1f} ms  {len(r.content):8d} bytes')

print('\n=== SECOND LOAD (cached) ===')
second_times = {}
for name, path in pages.items():
    t0 = time.perf_counter_ns()
    r = s.get(BASE + path, timeout=30)
    dt = (time.perf_counter_ns() - t0) / 1e6
    second_times[name] = dt
    print(f'{name:12s} {r.status_code} {dt:8.1f} ms  {len(r.content):8d} bytes')

print('\n=== THIRD LOAD (cached again) ===')
third_times = {}
for name, path in pages.items():
    t0 = time.perf_counter_ns()
    r = s.get(BASE + path, timeout=30)
    dt = (time.perf_counter_ns() - t0) / 1e6
    third_times[name] = dt
    print(f'{name:12s} {r.status_code} {dt:8.1f} ms  {len(r.content):8d} bytes')

print('\n=== SUMMARY ===')
for name in pages:
    print(f'{name:12s} first={first_times[name]:7.1f} ms  cached={second_times[name]:7.1f} ms  cached2={third_times[name]:7.1f} ms')