import requests, urllib3
urllib3.disable_warnings()
BASE = 'http://127.0.0.1:5000'
s = requests.Session()
s.post(BASE + '/login', data={'username':'testuser','password':'testpass'}, allow_redirects=True)

templates = {
    'Dashboard': '/',
    'Attendance': '/attendance',
    'Salah': '/prayers',
    'Calendar': '/prayers/calendar',
    'Missed Salah': '/prayers/missed',
    'Quran': '/quran?view=surah',
    'Reports': '/reports',
}

# Measure time-to-first-byte and page size (bytes proxy for render weight)
results = {}
for name, path in templates.items():
    url = BASE + path
    t0 = time.perf_counter_ns()
    r = s.get(url, timeout=15)
    dt = (time.perf_counter_ns() - t0) / 1e6
    results.setdefault(name, []).append(dt)
    print(f'{name:12s} {r.status_code} {dt:8.1f} ms  {len(r.content):8d} bytes')

print()
print('LATEST REQUEST (largest)')
for k, v in sorted(results.items(), key=lambda kv: -max(kv[1])):
    print(f'{k:12s} max={max(v):7.1f} ms  n={len(v)}')